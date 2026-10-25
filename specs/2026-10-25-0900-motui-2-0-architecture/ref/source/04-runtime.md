# 04 · 运行时：Terminal / Runtime / Workspace / Router

> 上级：`01-architecture.md`　相关：`10-waves/W4-runtime-api.md`
> 状态：ready

## 1. 目标

把一个 1,333 行的 `TUI` 拆成四个单一职责对象，并把终端开关收成一份配置：

| 对象 | 职责 | 目标行数 |
|---|---|---|
| `Terminal` | screen、原始模式、输入源、resize、能力探测 | ~350 |
| `Runtime` | clock、定时器、invalidate、paint、run_session | ~300 |
| `Workspace` | pane 树、content、split/dock、focus、overlays | ~450 |
| `Router` | 有序 handler | ~150 |
| `App` | 组合 + 默认 tiers | ~200 |

## 2. 为什么

- 1.x 的 `App` 14 参数、`TUI` 11、`Screen` 6；`mouse/hover/color_mode/focus_events/sync/keys` 在三层重复，新增一个终端开关要改三处。
- `hover` 不是独立开关：它只在鼠标开启时才有意义；用 `mouse=True, hover=True` 表达不了 1000/1002/1003 的区别。
- `driver.py` 同时做屏幕、frame、pane、文档、split/dock、选择、pump、定时器、paint、dump。
- 定时器 `next_run = now + period` 会累积漂移：实测 50ms → 58–65ms，1 秒 17 次。
- 1.x 的 `EveryHandle` 放在 `core/hit.py`，与“命中”无关。

## 3. 配置：`TerminalOptions` + `MouseMode`

```python
class MouseMode(Enum):
    OFF = "off"        # 0
    BUTTON = "button"  # 1000：按下/抬起
    DRAG = "drag"      # 1002：按下 + 拖动
    MOVE = "move"      # 1003：任意移动（hover）

@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalOptions:
    stream: TextIO | None = None
    input: EventSource | None = None       # 原 keys=
    mouse: MouseMode = MouseMode.MOVE
    paste: bool = True
    focus_events: bool = False
    color_mode: ColorMode | Literal["auto"] = "auto"
    sync: bool = True

app = App(terminal=TerminalOptions(...), theme=..., throttle=..., auto=...)
```

规则：

- `App` 只收策略参数：`theme` / `throttle` / `auto` / `title` / `on_selection` / `terminal` / `handlers`；
- `interactive` 由 `terminal.live` + `input` 推导；测试用 `headless()`，不再暴露开关；
- `throttle` / `fps` 属于 `Runtime`，不属于终端；
- `input` 取代 `keys`（它同时包含鼠标/粘贴/焦点事件，叫 keys 不准确）。

## 4. Terminal

**职责**

- 构造并持有 `Screen`（`TerminalScreen` / `HeadlessScreen`）；
- `enter()` / `leave()` 的字节顺序；
- attach/close 输入源；
- `read_event() -> Event | None`（纯读，不做 scroll/focus 策略）；
- `refresh_size()` / `size` / `live` / `capability`；
- 剪贴板：`Clipboard`（`ScreenClipboard` 默认）。

**不职责**

- 不派发、不聚焦、不滚动、不决定 paint 时机。

## 5. Runtime

**职责**

- `clock()`：唯一时间入口，可注入；
- `every(period, fn, *, catch_up="skip"|"coalesce")`、`animation(hz, draw)`；
- `invalidate()` / `paint_now()`；
- `run_session(body)` 的会话生命周期；
- `advance(dt)`：测试/回放的虚拟时钟；
- 帧预算（`fps` / `frame_budget`），超时丢帧不补帧；
- `pause_when_hidden`（隐藏/失焦暂停动画）。

**定时器语义**

```python
next_run += period              # 不是 next_run = now + period
if now - next_run > period * 4: # 落后太多
    next_run = now + period     # 丢弃并重排（可配）
```

- `catch_up="skip"`：只跑一次，跳到下一个未来时刻；
- `catch_up="coalesce"`：合并错过的 tick；
- 永不 sleep 在库里；pump 用 `asyncio.wait_for` 等下一次唤醒。

## 6. Workspace

**职责**

- `add(component, *, id=None, placement=FLOW, sizing=NATURAL, pane=None) -> Section`；
- `get(id) -> Section` / `remove(id) -> Section`；
- `split(axis=Axis.X, weights=(...), pane=None) -> tuple[Pane, ...]`；
- `dock(component, *, placement=Placement.BOTTOM, size=None) -> Pane` / `undock(placement) -> Pane | None`；
- `focus(widget)` / `focus_next()` / `focus_previous()` / `focus_pane(pane)`；
- `frame` / `pane(id)` / `selection` / `reveal(section, row)`；
- 挂载/卸载控制器（`mount` / `unmount`）。

**规则**

- `add/get/remove` 统一返回 `Section`（ADR-019）；
- `split` 用 `Axis` 而不是 `"vertical"`；`weights` 取代 `ratios`；
- 文档 pane 只跑 y；横向在 `ScrollPanel`（`02` 第 6 节）。

## 7. Router

```python
Handler = Callable[[Event], bool]

DEFAULT_HANDLERS = (
    PaletteHandler(), ModalHandler(), FindHandler(), ToastHandler(),
    ControllersHandler(), WheelHandler(), DragHandler(), GestureHandler(),
    PointerHandler(), PaneFocusHandler(), FocusHandler(),
    PageKeyHandler(), BindingHandler(), HostHandler(),
)
```

- 顺序即文档；`auto=False` = `handlers=()`；
- 新 tier 只需实现 `__call__(event) -> bool`；
- 每个 handler 只回答“消费与否”，repaint 由它自己 `invalidate()`。

## 8. 生命周期

```
App.run()
  Terminal.enter()
  Runtime.start_pump()
  on_start()
  loop:
    event = Terminal.read()
    Router.dispatch(event)
  pump:
    tick(now) -> timers -> paint(diff)
  on_stop()
  Terminal.leave()
```

- 异常路径也走 `on_stop` + `Terminal.leave`；
- `KeyboardInterrupt` 视为 `quit()`；
- 非 live screen：不写字节，最终 dump 文本；
- 一次 run 可重复（reset timers/painter/selection）。

## 9. 错误模型

- 构造期：参数错误抛 `ValueError`（placement/sizing/axis/mouse/keys）；
- 运行期：`read_event` 返回 `None` 表示 EOF/session 结束，不抛；
- 回调异常：由 `Router` 冒泡到 `on_event` 的兜底；`on_stop` 必须执行；
- 终端能力未知：返回 `None`，不猜。

## 10. 重构方式（W4）

1. 从 `driver.py` 抽 `Terminal`（screen/keys/resize）、`Runtime`（pump/timers/paint/run）、`Workspace`（frame/document/split/dock/focus/selection）。
2. `Screen` 由 Protocol 改 ABC + 默认实现（W1 先做）。
3. 新增 `TerminalOptions`/`MouseMode`；删除 App/TUI/Screen 的重复开关。
4. `App.dispatch` 10 层 if → `DEFAULT_HANDLERS`。
5. `EveryHandle` → `Timer`（`runtime`）；`RowRange` → `RowSpan`（`layout`）。
6. `add/get/remove` 返回 `Section`；`split/dock` 用枚举。
7. `CommandRegistry.bind(app)` / `open_palette(registry)`（见 `05`）。

## 11. 测试与门禁

- 定时器：`every(0.05)` 跑 1s，19–20 次（误差 ≤5%）；
- `advance(dt)` 确定性：同一脚本两次运行输出一致；
- 非 live：0 字节 + 最终 dump；
- 生命周期：异常/quit/EOF 都执行 `on_stop` + `leave`；
- 一次 run 可重复；
- `App` ≤250 行，`Runtime/Workspace/Terminal` ≤450 行。

## 12. 不做的

- ❌ 异步 widget API；事件+定时器已够。
- ❌ 运行时颜色协商查询（能力来自环境/显式配置）。
- ❌ 多窗口/多会话。
- ❌ 把 `throttle`/`fps` 放进 Terminal。
