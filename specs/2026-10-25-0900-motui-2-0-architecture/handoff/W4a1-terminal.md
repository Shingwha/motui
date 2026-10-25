# W4a1 交接 · TerminalOptions / Terminal / 截止时间定时器

> 分支 `2.0/w4a1-terminal`；起点 `d779b89`（W3b3b 合并后）。结论：T1–T4 完成；**1568 passed**（1531 基线 + 37 新增）；57 byte / 57 semantic / hash `e7ca544b…` 全不变；demo 70 / 4059 行，exit 0；禁触清单零 diff。

## A. 交付面与门禁

### MouseMode / TerminalOptions（`terminal/screen.py`）

```python
class MouseMode(Enum): OFF="off"; BUTTON="button"; DRAG="drag"; MOVE="move"
def mouse_switches(mode: MouseMode) -> tuple[bool, bool]   # (mouse, hover)

@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalOptions:
    stream: TextIO | None = None
    input: EventSource | None = None
    mouse: MouseMode = MouseMode.MOVE
    paste: bool = True
    focus_events: bool = False
    color_mode: ColorMode | Literal["auto"] = "auto"
    sync: bool = True
    screen: Screen | None = None      # testing/headless 入口，优先于其余 screen 开关
```

映射：OFF→(False,False)、BUTTON→(True,False)、DRAG→(True,False)、MOVE→(True,True)。App 旧默认 `hover=True` 折叠为 MOVE（1003），`hover=False` 为 DRAG（1002），`mouse=False` 为 OFF；demo 字节不变。`TerminalOptions.screen` 给定后 stream/mouse/paste/focus/color 全部不参与建屏。

### Terminal（`terminal/terminal.py`，terminal/__init__ 导出）

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Capability: color_mode: ColorMode; size: tuple[int,int]; live: bool; encoding: str|None=None

class Terminal:
    def __init__(self, options: TerminalOptions = _DEFAULT_OPTIONS, *, screen: Screen|None = None)
    screen; input; live; size; capability; clipboard      # clipboard: ScreenClipboard
    def attach(source: EventSource|None); def enter(); def leave()
    async def read_event() -> Event|None                  # input is None = EOF
    def refresh_size(); def close()
```

screen 选择顺序：显式 `screen=` > `options.screen` > 按 `mouse_switches` 构造 `TerminalScreen`。`enter/leave` 原样转发（字节顺序与非 live 静默仍由 Screen 决定）；`read_event` 是纯读；`close()` 尽力关闭 input 的 `close`（若有）再关 screen。`terminal/__init__` 新增 `Capability`、`MouseMode`、`Terminal`、`TerminalOptions`，`ansi` 仍不导出。

### Timer（`app/driver.py`）

```python
class Timer(EveryHandle):   # 继承 1.x EveryHandle，cancelled/cancel 保留
    period; fn; next_run; catch_up; # catch_up: "skip"|"coalesce"
    def __init__(period, fn, next_run=0.0, *, catch_up="skip")

TUI.every(period, fn, *, catch_up="skip") -> Timer
TUI.animation(hz, draw) -> Timer
TUI.invalidate() -> None     # = refresh()
TUI.paint_now() -> None      # = paint()
TUI.advance(dt) -> None      # 虚拟时钟
```

截止时间语义：到期后 `next_run += period`（不是 `now + period`）。`skip`：若新 deadline 仍 ≤ now，则重排到 `now + period`；`coalesce`：按整周期前推直到 > now。一次 tick 最多调用一次。`Timer` 拒绝 `period ≤ 0`、未知 catch_up；`animation` 拒绝 `hz ≤ 0`。`clock()` = 可注入 `_clock`（默认 `time.monotonic`）+ `_clock_offset`；旧测试替换 `tui.clock` 的 seam 仍工作。

### 门禁（本 worktree，Python 3.12.14 / uv 0.12.21）

- `pytest -q -p no:cacheprovider`：**1568 passed**；57 byte / 57 semantic；hash `e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`
- `python -m motui < /dev/null`：exit 0，**70** 行；`--pages`：exit 0，**4059** 行
- 定时器：`every(0.05)` + `advance(1.0)` → **19** 次（19–20，误差 0%；浮点累加使第 20 个 deadline 为 `1.0000000000000002`）；同脚本两次 calls/字节完全一致
- ruff All checks passed；pyright 0；lint-imports 4 kept；`api --update/--check` **185 names**（旧名签名仅 App/TUI 增加 `terminal=`，4 个 terminal 新名）；`growth --quick` OK

## B. 实现细节 / 坑

1. **App 旧参数折叠**：`App(terminal=None)` 时把 `mouse/hover` 折成 MouseMode，连同 `keys/focus_events/color_mode/sync/screen` 组成 `TerminalOptions`，先建 `Terminal` 再 `TUI(terminal=...)`；因此 App 永远走 terminal 路径，`App.terminal` 永远是真实对象。`terminal=` 给定时旧参数全部忽略（显式优先）。
2. **TUI 双路径**：直接 `TUI(screen=..., keys=...)` 仍走旧路径；`TUI(terminal=...)` 时 `self._screen=terminal.screen`、`self.keys=terminal.input`、`_hover` 由 `options.mouse is MOVE` 推导、`sync` 取 `options.sync`。`terminal=` 覆盖旧参数。
3. **委托**：enter/leave 在 `_enter_run`/`_teardown` 内走 `Terminal.enter/leave`（仍受 `screen.live` 门控与 `screen.flush()` 顺序约束）；`read_event` 的 exit/cancel 竞速留在 TUI，只把内层 `source.read()` 换成 `terminal.read_event()`；非 live 仍直接 `None`。clipboard 走 `terminal.clipboard`（同一 ScreenClipboard，字节相同）。
4. **自有输入源**：交互式 attach 的 `RawTerminalKeys` 在 `_enter_run` 里 `terminal.attach(source)`，teardown `attach(None)` 并照旧只 close 自有源。若宿主直接改 `tui.keys`，terminal 路径不跟随（改 `tui.terminal` 的 Terminal.input）；旧路径不受影响。
5. **EveryHandle**：Timer 选择“子类”而非 `EveryHandle = Timer`，因为 `overlays/gesture/scrollbar`（禁触）仍按 kernel 的 `EveryHandle` 标注并接收 `every()` 返回值；`isinstance(timer, EveryHandle)` 为 True，W4b 删名时再改这些模块。
6. **advance 的语义**：除推进 offset 外，会按 deadline 步进调用 `tick`（每个 deadline 一次，最后落到 target 再 tick），否则单次 `advance(1.0)` 无法满足 19–20 次门禁；不 sleep、不采真实时间，故可复现。若要“只动时钟不跑 tick”，W4b 需重新定义门禁。
7. **coalesce 无落后上限**：工单伪代码是整周期 while 前推，未实现 `04-runtime.md` 的“落后 > 4×period 重排”上限；当前测试值域安全，长暂停场景留给 Runtime 拆分时补。
8. **Capability**：源规格只给了名字，这里定为 frozen 值（color_mode/size/live/encoding），`Terminal.capability` 每次按需采样；`size`/`live` 也可直接读 Terminal。
9. **W4a2 边界**：本波未拆 Workspace、未删 TUI、未改 focus/pointer/gesture/overlays/demo/widgets/kernel。W4a2 应从 TUI 抽出 `Runtime`（clock/timers/invalidate/paint/run_session/teardown）与 `Workspace`（frame/document/split/dock/focus/selection），Terminal 已是现成协作者；Timer 的公开面随 Runtime 一起上移，`EveryHandle` 与 `TUI` 在 W4b 删除。
10. **禁触**：`git diff d779b89..HEAD` 只含 screen/terminal/__init__/driver/application/tests/terminal/tests/app/api-2.0.txt；kernel/widgets/demo/golden/工具/README/docs/pyproject/uv.lock 零 diff。

## C. 位置与 commit

- 源码：`terminal/{screen,terminal}.py`、`terminal/__init__.py`、`app/{driver,application}.py`
- 测试：`tests/terminal/{test_screen,test_terminal}.py`、`tests/app/{test_driver,test_app}.py`
- 快照：`tools/api-2.0.txt`（+4 terminal 名；App/TUI 签名加 `terminal=`）
- commit：
  - `acda4c6` terminal: mouse mode and terminal options name one configuration（T1）
  - `3bbb9a6` terminal: a terminal adapter owns the screen, input and capability（T2）
  - `e39c3a8` driver: timers keep deadlines and a virtual clock advances them（T3）
  - `0defdd4` app: the driver and app enter, leave and read through a terminal（T4）
  - 本文件（收口）
