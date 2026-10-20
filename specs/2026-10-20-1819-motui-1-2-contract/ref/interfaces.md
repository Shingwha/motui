# interfaces · motui 1.2 contract（草案 v1）

> W0 冻结 §1（W1 直接实现）；§2–§5 是目标契约，随对应波次合并后由 lead 更新。
> 代码/测试是最终权威；本文件是跨波导航，不得被 worker 修改。

## 1. 事件模型（W1 已落地 @ `a84bcf7`）

> W1 实现与本节一致。合并后的补充事实：
> - `ScriptedEvents` 位于 `motui.testing`（`motui.testing.__all__` 含它）。
> - `\n` → `c-j`、`\r` → `enter`；`EDITOR_SUBMIT_KEYMAP` 的 `c-j` 现在可达。
> - kitty 的 `super` 修饰键名前缀为 `super-`（契约未规定，W1 采用；W4 若改名需回写）。
> - `CSI R` 按本节映射为 `f4`（带修饰符）；xterm cursor-position report 不使用。
> - SGR 低 2 位 = 3 的 press/release 产出 `button="none"`。
> - X10 在文本层解析；ASCII 坐标精确，两个高位字节恰好构成合法 UTF-8 的极端组合可能失真。
> - `wRepeatCount=N` 解释为 1 个 `press` + (N−1) 个 `repeat`。
> - `TUI.read_event()` 已替代 `read_key`；`TUI.stop/run/split/hit_test` 仍待 W2。

### 1.1 类

```python
class Event:
    """Base class for every input event."""

@dataclass(frozen=True, slots=True)
class KeyEvent(Event):
    key: str                      # canonical routing name (see 1.2)
    char: str = ""                # printable text, "" for special keys
    modifiers: frozenset[str] = frozenset()   # "ctrl" | "alt" | "shift" | "super"
    kind: str = "press"           # "press" | "repeat" | "release"

@dataclass(frozen=True, slots=True)
class MouseEvent(Event):
    button: str = "none"          # "left"|"middle"|"right"|"none"|
                                  # "wheel_up"|"wheel_down"|"wheel_left"|"wheel_right"
    x: int = 0                    # 0-based column
    y: int = 0                    # 0-based row
    kind: str = "press"           # "press" | "release" | "motion" | "wheel"
    modifiers: frozenset[str] = frozenset()

@dataclass(frozen=True, slots=True)
class PasteEvent(Event):
    text: str

@dataclass(frozen=True, slots=True)
class ResizeEvent(Event):
    width: int                    # columns
    height: int                   # rows

@dataclass(frozen=True, slots=True)
class FocusEvent(Event):
    focused: bool
```

硬约束：

- `MouseEvent`、`PasteEvent`、`ResizeEvent`、`FocusEvent` **不是** `KeyEvent` 的子类。任何 `isinstance(event, KeyEvent)` 只匹配键盘。
- 所有事件值相等、可 hash；字段只读。
- `Event` 不带时间戳；时间由 driver 的 clock seam 提供。
- `PasteEvent` 的文本永不重新解释为按键。
- `ResizeEvent`/`FocusEvent` 由 decoder 或 source 产生；driver 原样交给 host。

### 1.2 键名语法

| 类别 | `key` | `char` | 例 |
|---|---|---|---|
| 可打印 | 字符本身 | 字符本身 | `a` / `中` / `!` |
| 空格 | `space` | `" "` | `KeyEvent("space", " ")` |
| 控制 | `c-a` … `c-z` | `""` | `c-c` |
| 回车 | `enter`（`\r`）；`c-j`（`\n`） | `""` | `enter` / `c-j` |
| 编辑键 | `tab` `backspace` `insert` `delete` `home` `end` `page_up` `page_down` | `""` | |
| 方向 | `up` `down` `left` `right` | `""` | |
| 功能键 | `f1` … `f24` | `""` | |
| 转义 | `escape` | `""` | |
| Shift 和弦 | `s-up` `s-down` `s-left` `s-right` `s-home` `s-end` `s-tab` | `""` | |
| Alt/Ctrl 和弦 | 前缀 `a-` / `c-`，顺序 `c-` → `a-` → `s-` | `""` | `c-s-left`、`a-s-up`、`c-a-s-tab` |

说明：

- `modifiers` 与 `key` 前缀表达同一事实；escape sequence 带显式 modifier 时两者都填。普通 UTF-8 字符不推断 shift（`A` 就是 `A`，`modifiers` 为空）。
- `kind` 默认 `press`；kitty 协议的 repeat/release 映射为 `repeat`/`release`。
- 键名是路由身份；组件/keymap 读 `event.key`，不再读 `event.name`。

### 1.3 鼠标

- SGR 1006 是主路径；X10（`ESC [ M`）与 urxvt 1015 也解析。
- 位映射：低 2 位 0=left、1=middle、2=right、3=none；64/65=wheel up/down；66/67=wheel left/right；32=motion；4=shift、8=alt、16=ctrl。
- 坐标转换为 0-based（终端字段 - 1）。
- `kind`：wheel 报告为 `wheel`；带 motion bit 为 `motion`；否则按 M/m 为 `press`/`release`。
- 水平 wheel 在 1.2.0 解析为 `wheel_left`/`wheel_right`，是否消费由 host 决定（跨 pane 滚动仍 out of scope）。

### 1.4 来源

```python
@runtime_checkable
class EventSource(Protocol):
    async def read(self) -> Event | None: ...
```

- `None` 只表示 EOF；EOF 后重复 `read()` 仍返回 `None`，不得挂起。
- `RawTerminalKeys.start()` 可在 `close()` 后再次调用；每次 start 重置 EOF/decoder 状态。
- `close()` 必须尽力解除阻塞中的 `read()`（POSIX self-pipe；Windows 轮询标志）。
- EOF 时 reader 调用 `KeyDecoder.finish()`，把未完成的 UTF-8/paste 吐出。
- Windows console 保留 `wRepeatCount`：重复次数产生多个 `KeyEvent(kind="repeat")`。

### 1.5 解码覆盖（W1 验收矩阵）

必须解析：

- UTF-8 增量（含被 chunk 切断的多字节字符）。
- C0：`\r`→`enter`、`\n`→`c-j`、`\t`→`tab`、`\x7f`→`backspace`；其余控制键按 `c-x`。
- CSI 字母：`A/B/C/D/H/F`、`Z`→`s-tab`、`P/Q/R/S`→`f1`..`f4`。
- CSI `~`：`1/7`→home、`2`→insert、`3`→delete、`4/8`→end、`5`→page_up、`6`→page_down、`11/12`→f1/f2、`15`..`24`→f5..f12。
- SS3：`ESC O A/B/C/D/H/F/P/Q/R/S`。
- 修饰符参数：`CSI 1;m X` 与 `CSI n;m ~`；m=2..8 按 1.3 的位映射。
- kitty：`CSI codepoint;mods u`、`CSI codepoint;mods:event u`、`CSI 27;mod;code~`（modifyOtherKeys）。
- bracketed paste：`CSI 200~` … `CSI 201~` → `PasteEvent`。
- focus：`CSI I` → `FocusEvent(True)`、`CSI O` → `FocusEvent(False)`。
- resize：`CSI 8;rows;cols t` → `ResizeEvent(cols, rows)`。
- 鼠标：SGR、X10、urxvt 1015；button/modifiers/kind 按 1.3。
- `finish()`：未闭合 paste、未完成 UTF-8、悬而未决的 ESC 序列不丢字节（能判定的吐出，不能判定的按字面字符）。

`feed(data: bytes)` 的编程错误（非 bytes）可以抛 `TypeError`；其余输入不得崩。

## 2. Driver / 坐标 / pane / dock（W2 已落地 @ `041e270`）

> W2 实现与本节一致。合并后的补充事实：
> - `ScreenLayout.viewport_rows` 改名 `body_rows`，并新增 `viewport_start`（body 在 pane rows 内的起点）。
> - `RowRange(first, last)` 在 `motui.app.__all__`；`visible_range` 返回屏幕行（含 top pin 偏移）。
> - `Hit` 字段为 `pane, block, row, col, leaf, leaf_row, leaf_col`，`pane_id` 是只读便捷属性；
>   命中 chrome 列返回 `None`；`leaf` 在命中时总是 descend 后的组件。
> - `run_async()` 只由 `exit()` 结束；带 body 的脚本用 `run_session(body)`；`run()` 是同步包装。
> - dock 只支持 `top`/`bottom`；空 dock 放到 0×0 并从 compose/ownership 跳过；dock id 用 `pane-N`。
> - `add` 默认目标是 focused pane；`frame.pane()` 含 dock，`frame.panes` 不含。
> - `Screen.copy` → `copy_to_clipboard`，写后 flush；`TUI.screen`/`document`/`viewport` 只读。
> - `Pane` 仍是 frozen dataclass（D7 归 W3）；`TUI.paint()` 保留为低层入口。
> - 删除的旧名：`stop`、`invalidate`、`run(body)`、`hit_test`、`hit_component`、`focus_at`、
>   `add_band`、`remove_band`、`TUI.band`、`TUI.viewport_rows`、`Frame.band/set_band`、`Screen.copy`。

```python
await tui.read_event() -> Event | None
tui.exit() -> None
tui.refresh() -> None
tui.run_session(body) / tui.run() / await tui.run_async()
tui.hit(x, y) -> Hit | None
tui.hit_leaf(x, y) -> tuple[Component, int, int] | None
tui.pane_at(x, y) -> Pane | None
tui.visible_range(pane: Pane | str | None = None) -> RowRange | None
tui.dock(viewport, *, edge: str = "bottom", size: int | None = None) -> Pane
tui.undock(edge: str = "bottom") -> Pane | None
```

- `Hit(pane, block, row, col)`：`row`/`col` 是 block 自己的 0-based 坐标；另有 `leaf`/`leaf_row`/`leaf_col`（`hit()` 可一次返回；`hit_leaf` 是便捷入口）。
- 越界 `x<0`、`y<0`、`x>=width`、`y>=height` 一律 `None`；不再 clamp。
- `Hit.col` 相对 pane 的 **inner rect**（chrome 扣除后），不是外框。
- 所有 document 操作有显式 pane 作用域：`tui.pane(id).add/get/remove`，或 `tui.add(..., pane=...)`；默认 = focused pane（无 split 时即 primary）。
- block id 在 frame 内全局唯一；跨 pane 不允许重复。
- pane id 单调递增、永不复用；`Pane` 是普通可变类。
- `dock` 一次可挂多个 edge；`size=None` 表示内容自适应；band 内容为空时清空该 dock，不留幽灵行。
- `Frame` 的结构变更（split/close/chrome/dock/overlay）必须让 driver 变脏；host 不需要额外 `refresh()`。
- `TUI.stop` 的语义由 `exit()` 取代：取消/唤醒 pending `read_event`，取消 pump，按 run 生命周期清理。
- 同一 TUI 可以多次 `run_session`；每次运行重置 timers/selection/keys。
- `Screen` 增加 `size`、`encoding`、`color_mode`、`close`、`copy_to_clipboard`；`Screen.copy_to_clipboard` 负责 flush。
- overlay 有显式 layer：`background` < `content` < `chrome` < `overlay` < `modal` < `tooltip` < `toast`；同层按注册顺序。

## 2b. 值语义（W3 已落地）

> - `Pane`：`@dataclass(eq=False)` 普通可变类；身份相等/身份 hash；所有字段普通赋值。
> - `ScreenLayout.rows` / `body_rows` / `row_blocks` / `block_order`：tuple；`__post_init__` 归一。
> - `Theme.notice_levels` / `FG_CODES`：`MappingProxyType`，写入抛 `TypeError`。
> - `Style` / `Segment`：`dataclass(frozen=True, slots=True)`；隐藏缓存仍通过 `object.__setattr__`。
> - `Text`：删除组件 memo；`render` 每次重算；`Block.rows` 是唯一缓存所有者；`_rows` 仅是 last-render 几何。
> - `Painter.rows`：paint 前归一，恒为 `screen.height` 行。
> - `selection.highlight(..., *, style=SELECTION)`；TUI selection overlay 传 `theme.selection`。

## 3. 组件契约（W4a 已落地；W4b 续）

> W4a 事实：
> - `Controller` / `Resultful` 在 `motui.kernel`；`handle` = consumed，`take_result()` 读一次并清空。
> - action/choice/textfield/dialog/collapsible/indicators 家族已删 `chosen`，改用 `take_result()`。
> - `Radio` → `RadioGroup`，`CheckGroup` → `CheckboxGroup`；`CheckboxGroup.click` 现在移动 cursor 并 toggle。
> - `Select` 新增 `select/home/end`、`disabled`/`disabled_items`；`cursor_text_style`（原 `selected_style`）；
>   组控件 `active_style`。
> - `Input(text=...)`、`text` setter、`read_only`、`caret_style`；`TextBuffer.read_only/set_text`。
> - `ComboBox`：`take_result`、`child_at`、`focused/click` 委托、`Revisioned`；打开时 Paste 不再崩。
> - `Dialog`：`take_result`、`child_at`、`focused_button`（不再被 `Focusable` 误判）；按钮走 `Button.activate().take_result()`。
> - `Collapsible`：`take_result`、`child_at`、`disabled`。
> - `Spinner.render(width)` + `Revisioned`；`Slider` 的 min/max/step setter 会重新 clamp/snap。
> - `Markdown.revision()` 覆盖 `max_width`/`task_marks`/gap/divider cap/hover span。
> - `prompt_dialog` 已从 `motui.widgets` 导出。
> - `Modal`/`Palette` 仍公开 `chosen`（面板 socket 用 `_take_decision()` 适配）；W6 决定是否迁到 `take_result()`。
> - W4b 仍待：List/Table/Tree/Tabs/NavList 的 `take_result`/disabled/RowBands/CursorWindow，
>   以及 Divider/Panel/Notice/StatusLine/ShortcutBar 的 `Revisioned`。

```python
class Controller(Protocol):
    def handle(self, event: Event) -> bool: ...   # True = consumed

class Resultful(Protocol):
    def take_result(self) -> object | None: ...   # read-once + clear
```

- `handle` 统一为“是否消费”；需要重绘的 tier 自己调 `tui.refresh()`，不再用 `handle` 返回值表达“changed”。
- 所有可选/多选/数据视图：`index: int`、`select(index) -> bool`、`move(delta) -> bool`、`home()/end()`、`activate() -> bool`；多选加 `toggle() -> bool`。
- `selected` 只读当前值；`take_result()` 取一次性结果并清空；`on_activate` 可选回调。
- 所有交互组件：
  - `Clickable.click(row, col) -> bool`
  - `Activable.activate() -> bool`（适用者）
  - `Focusable.focused: bool`
  - `Hoverable.hover: bool` + 可选 `hover_at(row, col) -> bool`
  - `Container.child_at(row, col) -> (Component, int, int) | None`（`Dialog`/`Collapsible`/`ComboBox` 必须实现）
  - `Revisioned.revision() -> object`（覆盖 render 读取的全部可变输入）
- 行带统一：`RowBands(ground, active, hover, focus, text, disabled)`；`Select`/`List`/`Table`/`Tree`/`NavList` 共用同一实现。
- disabled/read-only：`Disableable.disabled: bool` + 每项 disabled；`Input/Editor.read_only: bool`。
- 文本输入：`Input(text=...)`、`Editor(text=...)`；`text` 可读写；`caret_style` 取代 `cursor_style`。
- `Spinner.render(width)` 必须存在；否则从组件 facade 删除。
- `CheckGroup` 改名 `CheckboxGroup`；`Radio` 改名 `RadioGroup`（若 W4 决定保留旧名，必须在 interfaces 回写理由）。
- 一次性 `chosen` 全部删除；有结果的组件实现 `take_result()`。

## 4. 分层 / Host（W6 冻结）

```python
class Host(Protocol):
    screen: Screen
    frame: Frame
    def refresh(self) -> None: ...
    async def read_event(self) -> Event | None: ...
    def clock(self) -> float: ...
    def every(self, seconds: float, fn: Callable[[], object]) -> EveryHandle: ...
    def hit(self, x: int, y: int) -> Hit | None: ...
    def set_selection(self, selection: Selection | None, *, pane=None) -> None: ...
    def visible_range(self, pane=None) -> RowRange | None: ...
```

- `interaction/**` 只 import `kernel` + `Host`，不 import `app` / `widgets`。
- `app.TUI` 实现 `Host`；interaction tier 构造接收 `Host`。
- `Find`/`Palette` 需要的 `Input`/`Autocomplete` 通过构造注入（组合根在 app 或 host 层）。
- `kernel` 不 import `keys`/`widgets`/`interaction`/`app`。
- `keys` 只 import `kernel`。
- `widgets` 只 import `kernel` + `keys.keymap`。
- `app` 可以 import 全部；`testing` 只 import `app`/`kernel`。

## 5. 命名对照（target）

| 现名 | 1.2 目标 | 波次 |
|---|---|---|
| `Key` | `KeyEvent` | W1 |
| `Paste` | `PasteEvent` | W1 |
| `KeySource` | `EventSource` | W1 |
| `ScriptedKeys` | `ScriptedEvents`（移到 `motui.testing`） | W1 |
| `event.name` | `event.key`（KeyEvent） | W1 |
| `MouseEvent.button: int` | `button: str` + `kind: "wheel"` | W1 |
| `TUI.read_key` | `TUI.read_event` | W1 |
| `TUI.stop` | `TUI.exit` | W2 |
| `TUI.invalidate` | `TUI.refresh` | W2 |
| `TUI.run(body)` | `run()` / `run_async()` / `run_session(body)` | W2 |
| `TUI.hit_test` | `TUI.hit` | W2 |
| `TUI.hit_component` | `TUI.hit_leaf` | W2 |
| `TUI.focus_at` | `TUI.pane_at` | W2 |
| `TUI.add_band/remove_band/band` | `TUI.dock/undock/dock_region` | W2 |
| `TUI.viewport_rows` | `TUI.visible_range` | W2 |
| `Hit(block,row,col,pane_id)` | `Hit(pane, block, row, col, leaf...)` | W2 |
| `Screen.copy` | `Screen.copy_to_clipboard` | W2 |
| `chosen` | `take_result()` | W4 |
| `active`（Tabs/NavList） | `index` | W4 |
| `max_rows`/`window`/`max_drop_rows` | `max_rows` | W4 |
| `cursor_style`（text field） | `caret_style` | W4 |
| `selected_style`（Select） | `cursor_text_style` + `active_style` | W4 |
| `CheckGroup` | `CheckboxGroup` | W4 |
| `Radio` | `RadioGroup` | W4 |
| `Spinner` | 实现 `render(width)` | W4 |
| `ScreenLayout` | `Composition`（若 W3 决定） | W3 |
| `Frame.layout` | `Frame.composition` | W3 |
| `band`（四处） | `dock` / `dock_region` | W2 |

不要求为“像 Textual”改：`TUI`、`kernel`、`widgets`、`interaction`、`add/remove/get`、`split`、`render(width)`。
