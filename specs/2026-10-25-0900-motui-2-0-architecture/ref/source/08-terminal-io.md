# 08 · 终端 I/O：Screen / 输入 / 能力 / 剪贴板

> 上级：`01-architecture.md`　相关：`10-waves/W1` `W4`
> 状态：ready

## 1. 目标

把所有“字节”收进 `motui.terminal`，让 kernel 变成纯值库：

```
terminal/
  ansi.py        # 唯一 escape 构造器（私有）
  screen.py      # Screen ABC + TerminalOptions + MouseMode + 两个实现
  decoder.py     # bytes -> Event 纯状态机
  keys.py        # RawTerminalKeys（POSIX/Windows）
  win32.py       # console mode / record / ctypes
  capability.py  # 颜色、尺寸、VT 探测
  clipboard.py   # Clipboard + ScreenClipboard
```

## 2. 为什么

- 1.x 的 `core/` 里放了 2,150 行终端 I/O：`ansi.py`（278）、`screen.py`（372）、`decoder.py`（666）、`sources.py`（378）、`console.py`（474）。
- `core.__all__` 导出 `clear_screen` / `cursor_position` / `enter_alt_screen` 等字节构造器。
- 结果：内核无法脱离终端使用；测试必须理解 escape；无法替换渲染后端。
- 输入侧已就绪：`decoder.py` 已解码 `wheel_left/right`，只是没人消费。

## 3. Screen（ABC）

```python
class Screen(ABC):
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def size(self) -> tuple[int, int]: ...
    @property
    def live(self) -> bool: ...
    @property
    def color_mode(self) -> ColorMode: ...
    @property
    def encoding(self) -> str | None: ...

    def enter(self) -> None: ...
    def leave(self) -> None: ...
    def write(self, s: str) -> None: ...
    def flush(self) -> None: ...
    def refresh_size(self) -> None: ...
    def close(self) -> None: ...
```

- **ABC 不是 Protocol**：宿主/测试要实现它；ABC 可以加带默认实现的方法而不破坏子类（ADR-014）。
- 可选能力用“带默认值的属性”（未来 `cell_metrics -> CellMetrics | None = None`）或注入协作者（`Painter(screen, graphics=...)`）。
- 禁止 `supports_*` 布尔堆叠；未知 = `None`。
- `leave()` 顺序：可选清理 → 关 focus/paste/tracking → show cursor → 离开 alt screen。

## 4. TerminalOptions / MouseMode

见 `04-runtime.md` 第 3 节。要点：

- `stream` / `input` / `mouse` / `paste` / `focus_events` / `color_mode` / `sync` 一份声明；
- `MouseMode.OFF/BUTTON/DRAG/MOVE` 映射 0/1000/1002/1003；
- `App` / `TUI` / `Screen` 不再各写一遍。

## 5. 输入解码

- `decoder.py`：纯 `bytes -> Event`；覆盖 UTF-8 增量、CSI/SS3、kitty、modifyOtherKeys、bracketed paste、SGR/X10/urxvt 鼠标、focus、resize；
- ESC 单独键：`_SETTLE_SECONDS` 静默后交付；
- `keys.py`：raw mode（POSIX termios / Windows console mode）、reader 线程、executor drain、cooked fallback；
- `win32.py`：console mode / record 映射 / ctypes 结构；
- **不 sleep**：settle 用时间戳，不用 sleep。

## 6. 能力

- 颜色：`NO_COLOR` / `TERM=dumb` / `COLORTERM` / `256color` 环境探测；显式 `color_mode` 优先；
- 尺寸：`terminal_size()` 只在 `terminal/` 使用；
- 图形/像素尺寸：2.x 作为可选能力；2.0 不预置字段；
- 不做运行时查询协商（启动阻塞 + 终端差异大）；查询作为显式 opt-in（2.x）。

## 7. 帧发送

- `Painter` 一次帧：一次 `write` + 一次 `flush`；
- DECSET 2026 包裹（`sync=True`）；
- 空帧 0 字节；
- 非 live screen：不写字节，最终 dump 文本；
- 光标锚点（IME）作为帧尾声。

## 8. 剪贴板

```python
class Clipboard(Protocol):
    def copy(self, text: str) -> bool: ...

class ScreenClipboard:
    # OSC 52 through screen.copy_to_clipboard? 2.0 改为 Screen 不再拥有剪贴板
```

- 2.0 的 `Screen` **不拥有**剪贴板；`ScreenClipboard` 是 `terminal/clipboard.py` 的适配器；
- `MemoryClipboard` 进 `testing`；
- `App` 接受 `clipboard=`（默认 `ScreenClipboard`），删除 `on_selection` 的隐式复制耦合。

## 9. 安全

- 内容永远不能携带 escape：`Cell`/`Segment` 门删除 C0/DEL/C1；
- 只有 `terminal/ansi.py` 构造字节；
- 剪贴板文本走 OSC 52，不解释；
- `link` 走 OSC 8，同样过内容门；
- fuzz：随机字节流 → decoder 不崩、不泄漏状态。

## 10. 重构方式（W1）

1. 建 `terminal/` 包；移动 `ansi/screen/decoder/sources/console`。
2. `Screen` Protocol → ABC；`TerminalScreen`/`HeadlessScreen` 继承。
3. `TerminalOptions`/`MouseMode` 新增（W4 接入 App）。
4. `core/clipboard.py` → `terminal/clipboard.py`；内存替身进 `testing`。
5. `core.__all__` 移除所有字节函数；`terminal` 只导出 `Screen`/`Terminal`/`Clipboard`/`Capability`/`Decoder`。
6. import-linter 规则：kernel 不 import terminal；只有 terminal 可以 import ansi。
7. 门禁：demo 输出逐字节不变（W1）。

## 11. 测试

- decoder：各协议、分片、ESC settle、边界；
- screen：enter/leave 字节顺序、非 live 0 字节、clipboard；
- keys：POSIX/Windows（CI 双平台）；
- capability：env 矩阵；
- fuzz：随机字节 10k 轮不崩；
- 回归：1.x 的 escape 字节快照。

## 12. 不做的

- ❌ 运行时颜色/图形查询协商（默认）。
- ❌ 图片协议（2.x，见 archive）。
- ❌ 多路复用器（tmux）特殊适配。
- ❌ 把 escape 暴露给 widgets/内容。
