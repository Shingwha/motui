# 01 · 目标架构

> 上级：`00-overview.md`　下级：`02-core-contracts.md` … `09-testing-tooling.md`
> 状态：ready

## 1. 一句话

把“值模型 / 渲染 / 终端 I/O / 运行时策略”四件事拆开：**kernel 纯值、terminal 边缘、widgets 树、app 策略**。

## 2. 分层图

```
                      ┌──────────────────────────────┐
                      │           motui (root)       │  ~28 names
                      └──────────────┬───────────────┘
        ┌────────────────┬───────────┴───────────┬──────────────────┐
        │                │                       │                  │
   motui.app        motui.widgets           motui.terminal     motui.testing
   Runtime          base/canvas/...          screen/decoder      headless/emulator
   Workspace        per-family modules       keys/ansi/win32     snapshot/harness
   Router                    │                     │
        └────────────────────┴──────────┬──────────┘
                                        │
                                  motui.kernel
                     geom / cell / text / events / document /
                     layout / frame / hit / overlay / paint
                     （不 import os sys io ctypes，不 import 上层）
```

依赖方向唯一：`kernel ← widgets ← app`，`kernel ← terminal`，`testing` 在最外。

## 3. 模块表

| 模块 | 职责 | 目标行数 |
|---|---|---|
| `kernel/geom.py` | `Size` `Rect` `Pos` `Axis` `Direction` + Rect 代数、split 计算 | ~200 |
| `kernel/text.py` | 宽度、换行、截断、`WrapMode`、cluster、tab 规则 | ~700 |
| `kernel/cell.py` | `Cell` `Line` `Surface` `Style` `Color` `Palette` `Glyphs` `Border` | ~550 |
| `kernel/theme.py` | `Theme`（10 组语义 token）+ 解析 | ~400 |
| `kernel/events.py` | `Key/Mouse/Paste/Resize/Focus` + `EventSource` | ~150 |
| `kernel/document.py` | `Section` `Document` `Fill` `PaneContent` | ~420 |
| `kernel/layout.py` | `Constraints` `Viewport` `Scroll` `Axis` | ~450 |
| `kernel/frame.py` | `Pane` `Split` `Dock` + compositor | ~420 |
| `kernel/hit.py` | `Hit` `HitPath` | ~160 |
| `kernel/overlay.py` | 8 层 + overlay 管线 | ~200 |
| `kernel/paint.py` | `Surface` 行差分 → 帧；光标锚点 | ~250 |
| `kernel/selection.py` | `Selection` + `highlight` / `extract` 方法 | ~300 |
| `terminal/ansi.py` | 唯一 escape 构造器（私有） | ~280 |
| `terminal/screen.py` | `Screen` ABC + `TerminalOptions` + `MouseMode` + 两个实现 | ~420 |
| `terminal/decoder.py` | `bytes → Event` 纯状态机 | ~650 |
| `terminal/keys.py` | `RawTerminalKeys`（POSIX/Windows） | ~380 |
| `terminal/win32.py` | console mode / record / ctypes | ~470 |
| `terminal/capability.py` | 颜色、尺寸、VT 探测 | ~120 |
| `terminal/clipboard.py` | `Clipboard` + `ScreenClipboard` | ~80 |
| `widgets/base.py` | `Widget` 树、hooks、失效、`Container`、`Cursor`、`MarkSet` | ~500 |
| `widgets/canvas.py` | `Canvas`、marker、`Sparkline` | ~350 |
| `widgets/text.py` | `Text` | ~250 |
| `widgets/input.py` | `TextBuffer` `Input` `Editor` | ~1,400 |
| `widgets/choice.py` | 选择族（keymap 化） | ~650 |
| `widgets/list.py` `tree.py` `table.py` `tabs.py` `menu.py` | 数据视图族 | ~1,900 |
| `widgets/layout.py` | `Column` `Row` `Padding` `Spacer` `Grid` | ~450 |
| `widgets/scroll.py` | `ScrollPanel(axis=)` | ~350 |
| `widgets/decor.py` | `Panel` `Divider` `Collapsible` `Notice` `StatusLine` | ~500 |
| `widgets/indicator.py` | `ProgressBar` `Slider` `Spinner` | ~500 |
| `widgets/markdown/` | component + rules + syntax | ~2,300 |
| `widgets/diff.py` | `Diff` | ~600 |
| `app/runtime.py` | clock / timers / invalidate / paint / run_session | ~300 |
| `app/workspace.py` | pane 树 / content / split / dock / focus / overlays | ~450 |
| `app/router.py` | 有序 handler + `DEFAULT_ROUTER` | ~150 |
| `app/commands.py` | `Command`（group）/ `CommandRegistry`（bind） | ~200 |
| `app/tiers/*.py` | focus/pointer/drag/selection/find/modal/toast/tooltip/palette/scrollbar | ~2,300 |
| `app/app.py` | 组合 + 默认 tiers | ~200 |
| `testing/` | headless / scripted / snapshot / emulator | ~600 |

预期总行数比 1.x 少约 12%，但能力多一层（画布/几何/模拟器/类型）。

## 4. 依赖规则（机器化）

```ini
[importlinter]
root_package = motui

[importlinter:contract:layers]
name = kernel layers
type = layers
layers =
    motui.app
    motui.widgets
    motui.terminal
    motui.kernel

[importlinter:contract:kernel-pure]
name = kernel has no I/O
type = forbidden
source_modules = motui.kernel
forbidden_modules = os, sys, io, ctypes, termios, tty, select, asyncio
```

额外规则：

- `kernel` 不得 import `motui.terminal/widgets/app`；
- 只有 `terminal/` 可以 import `ansi`；
- `widgets/canvas.py` 不得 import `paint`/`screen`（Canvas 只产 Surface）。

## 5. 所有权与构造（可增长性的根）

- 引擎值类型一律 `kw_only + 全默认 + 类方法入口`：
  ```python
  @dataclass(frozen=True, slots=True, kw_only=True)
  class Surface:
      width: int = 0
      rows: tuple[Line, ...] = ()
      @classmethod
      def blank(cls, size: Size) -> "Surface": ...
      @classmethod
      def of(cls, rows, width: int) -> "Surface": ...
  ```
- 用户**不直接构造** `Surface`/`Constraints`/`ScreenLayout`/`FrameDelta`；从 `render` 或类方法得到。
- 2.x 给这些类型加字段不改用户代码（`kw_only` 保证位置参数不移动）。
- 能力提供者用 ABC（`Screen`），能力消费者用 Protocol（`Component`/`Overlay`/`Controller`）。
- 可选能力用“带默认值的属性”或“构造注入的协作者”，不预置空字段（ADR-011）。

## 6. 对象模型

| 对象 | 拥有什么 | 谁构造 |
|---|---|---|
| `Cell` / `Line` / `Surface` | 内容与几何 | 组件/内核 |
| `Section` | id + widget + placement + sizing | `Document` |
| `Document` / `Fill` | 一个 pane 的内容 | 宿主 |
| `Pane` | rect + content + chrome | `Frame` |
| `Frame` | split 树 + docks + overlays + focus | `Workspace` |
| `Widget` | parent/children + 状态 + hooks | 宿主 |
| `Terminal` | screen + input + capability | `App` |
| `Runtime` | clock + timers + paint + session | `App` |
| `Workspace` | frame + content + focus 门面 | `App` |
| `Router` | 有序 handlers | `App` |
| `App` | 以上组合 + 默认策略 | 宿主 |

## 7. 生命周期

```
App.run()
  Terminal.enter()
  Runtime.start_pump()
  on_start()
  loop:
    event = Terminal.read()          # 纯读
    Router.dispatch(event)           # 有序 handler
    invalidate() 由 tier/widget 调用
  pump:
    tick(now) -> timers -> paint(diff) -> flush
  on_stop()
  Terminal.leave()
```

规则：

- `render()` 不读时钟；动画写状态再 `touch()`。
- 一次帧 = 一次 write + 一次 flush（DECSET 2026 包裹）。
- 非 live screen 零字节输出，最终 dump 文本。

## 8. 一个概念一个门

| 概念 | 唯一门 | 删除的重复门 |
|---|---|---|
| 终端输出 | `Screen` / `Terminal` | `ansi.*` 公开导出 |
| 定时器 | `Runtime.every/animation` | `EveryHandle`（在 `hit.py`） |
| pane/content | `Workspace` | `App.add` + `TUI.add` |
| 事件 | `Router` | 手写 `App.dispatch` if 链 |
| 主题 | `Widget.style(group)` | `Themed` |
| 结果 | `take()` | `take_result()` |
| 行操作 | `Line.*` | `fit`/`fill`/`fuse`/`overlay`/`rest` 自由函数 |

## 9. 扩展点（加东西时改哪里）

| 想加什么 | 改哪里 | 不要改 |
|---|---|---|
| 新组件 | `widgets/<family>.py` + 测试 | kernel / Screen |
| 新容器 | `widgets/layout.py`（实现 `children`） | 属性名遍历 |
| 新控制器 | `app/tiers/<name>.py`，构造 `(host, ...)` | App.dispatch |
| 新终端能力 | `terminal/` 的属性或注入协作者 | `Constraints` / `Widget` |
| 新媒体 | `terminal/graphics.py` + `Painter(..., graphics=)` | `Component` / `Surface` 公开字段（内部可加） |
| 新主题组 | `kernel/theme.py`（加字段） | 组件解析逻辑 |

## 10. 被拒绝的架构

| 方案 | 为什么拒绝 |
|---|---|
| retained tree + CSS | 丢掉值语义、行 diff、可测试性 |
| 消息总线 | 隐藏行为、重入、顺序不可控；2.2 非目标 |
| measure/render 两阶段 | 单趟 + FILL 已够；两阶段让每个组件写两份逻辑 |
| 第二条渲染路径（Canvas 直写字节） | 选择/hit/golden 全部失效 |
| `RenderEnv` 传进 render | 投机抽象；第三个消费者出现再说 |
| per-widget `on_result` | 重入/顺序/双门；ADR-023 |
| 图片字段预留在 `Cell`/`Surface` | 未验证语义会变成承诺；ADR-011 |

## 11. 文件级迁移总表（1.x → 2.0）

| 1.x | 2.0 |
|---|---|
| `core/ansi.py` `core/screen.py` | `terminal/ansi.py` `terminal/screen.py` |
| `core/decoder.py` `core/sources.py` `core/console.py` | `terminal/decoder.py` `keys.py` `win32.py` |
| `core/frame.py` | `kernel/geom.py` + `frame.py` + `hit.py` + `overlay.py` |
| `core/lines.py` | `kernel/cell.py` + `widgets/text.py` |
| `core/text.py` | `kernel/text.py` |
| `core/style.py` + `theme.py` + `glyphs.py` | `kernel/cell.py` + `theme.py` |
| `core/block.py` | `kernel/document.py` |
| `core/viewport.py` + `scroll.py` | `kernel/layout.py` |
| `core/painter.py` | `kernel/paint.py` |
| `core/selection.py` | `kernel/selection.py`（方法化） |
| `core/hit.py` | `kernel/hit.py` + `layout.RowSpan` + `runtime.Timer` |
| `core/mark.py` `cursor.py` `chrome.py` `clipboard.py` | 并入 `widgets/base.py` / `frame.py` / `terminal/clipboard.py` |
| `app/driver.py` | `app/runtime.py` + `workspace.py` + `terminal` |
| `app/application.py` | `app/app.py` + `router.py` |
| `app/*.py` tiers | `app/tiers/*.py` |
| `widgets/strip.py` | 合并进 `widgets/base.py` 的 `Cursor` |
| `app/find.py` + `command_palette.py` | `app/picker.py` + presets |

## 12. 检查点

- [ ] 依赖图无环，且 import-linter 通过；
- [ ] `kernel` 不 import `os/sys/io/ctypes/termios/tty/select/asyncio`；
- [ ] 每个公开类型只有一个构造入口（类方法/工厂）；
- [ ] 每个概念只有一个门（第 8 节）；
- [ ] 新增能力时不需要改 `Component`/`Screen`/`Constraints`（第 9 节）。
