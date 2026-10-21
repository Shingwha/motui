# interfaces — motui 1.2.0

> 本文件是当前契约。每波合并后由 lead 回写。W1 只冻结 3 节；W2-W4 的接口在对应波次前补全。
> 真相优先级：代码与测试 > handoff > 本文件。

## 0. 目标包结构（W2 冻结）

```
src/motui/
  __init__.py          curated root
  core/                值、事件、输入、文档、渲染
    __init__.py
    style.py           Style, Color, ColorMode, NONE
    theme.py           Theme + 10 role groups, ColorPalette, DEFAULT_THEME, Styles
    glyphs.py          Glyphs, Border, GLYPHS
    lines.py           Line, Segment, Text, wrap_line, action_at
    text.py            visible_width, wrap_text, ellipsize_tail, terminal_size
    events.py          Event + 5 event types
    block.py           Component, Widget?, Document, descend
    widget.py          Widget, Styles (if not in theme.py)
    cursor.py          Cursor
    scroll.py          ScrollState, Scrollable
    viewport.py        ScreenLayout, Viewport
    frame.py           Rect, Pane, Frame
    screen.py          Screen, TerminalScreen, HeadlessScreen
    painter.py         Painter
    selection.py       Selection, highlight, extract
    clipboard.py       Clipboard, ScreenClipboard, MemoryClipboard
    ansi.py            escapes
    decoder.py         KeyDecoder
    keymap.py          Keymap + default keymaps
    sources.py         RawTerminalKeys
    console.py         Windows console source
  widgets/             component library, markdown, syntax
    __init__.py
    ...
  app/                 App, TUI, controllers
    __init__.py
    app.py             App (default orchestration)
    driver.py          TUI (low-level runtime)
    focus.py, pointer.py, gesture.py, find.py, modal.py,
    command_palette.py, overlays.py, scrollbar.py, commands.py
  testing.py
```

依赖：`core <- widgets <- app`；`testing` 在最上。禁止 `motui.kernel` / `motui.keys` / `motui.interaction` / `motui.commands`。

## 1. W1 冻结：ScrollState / Scrollable / Cursor

### ScrollState

```python
@dataclass
class ScrollState:
    offset: int = 0
    content_height: int = 0
    viewport_height: int = 0
    stick_to_bottom: bool = False

    def max_offset(self) -> int: ...
    def clamp(self) -> bool: ...                 # 返回是否移动
    def scroll_to(self, offset: int) -> bool: ...# clamp 后移动
    def scroll_by(self, delta: int) -> bool: ...
    def reveal(self, row: int) -> bool: ...      # 最小移动，使 row 可见
    def thumb(self, track_height: int, min_length: int = 1) -> tuple[int, int] | None: ...
```

语义：

- `max_offset = max(0, content_height - viewport_height)`。
- `scroll_to` / `scroll_by` 总是 clamp；返回 offset 是否变化。
- `reveal(row)`：`row` 先 clamp 到 `[0, content_height-1]`；已可见返回 `False`；否则最小移动到可见。
- `stick_to_bottom=True` 时，`clamp()` 在 `offset` 已到达旧的 `max_offset`（或首次布局）时贴底；`scroll_to` 到 `max_offset` 重新贴底，`scroll_up` 脱离贴底。Viewport 用这个语义。
- `thumb(track_height, min_length)`：内容不超过窗口返回 `None`。公式只用这一份：

```
length = min(track, max(min_length, round(viewport * track / content)))
travel = max(1, track - length)
span   = max(1, content - viewport)
start  = min(travel, max(0, round(offset * travel / span)))
```

`ScrollView` 和 `Scrollbar` 都调用它，不再各自实现。该公式可能让 `ScrollView` 的 thumb 从 1 格变 2 格；golden 中仅因此变化的帧允许重录，commit message 要写明。

### Scrollable

```python
class Scrollable(Protocol):
    @property
    def scroll_state(self) -> ScrollState: ...
    def scroll_to(self, offset: int) -> bool: ...
    def scroll_by(self, delta: int) -> bool: ...
```

`Viewport`、`ScrollView`、`Pane`（委托 viewport）实现。`Scrollbar` 从 `Scrollable` 读状态和写偏移，不再只认 `Pane`。

### Cursor

```python
class Cursor:
    def __init__(
        self,
        count: int = 0,
        *,
        index: int = 0,
        disabled: Iterable[int] = (),
        wrap: bool = False,
    ) -> None: ...

    index: int
    count: int
    disabled: frozenset[int]
    wrap: bool

    def select(self, index: int) -> bool: ...
    def move(self, delta: int) -> bool: ...
    def home(self) -> bool: ...
    def end(self) -> bool: ...
    def window(self, size: int, *, anchor: str = "center") -> tuple[int, int]: ...
```

语义：

- `move` 跳过 disabled；`wrap=False` 时在两端 clamp，`wrap=True` 时循环。
- `select` clamp 到 `[0, count-1]`；disabled 目标拒绝并返回 `False`。
- `window(size, anchor)` 返回 `(start, stop)`（stop exclusive），`anchor` 为 `center` / `top` / `bottom`；空序列返回 `(0, 0)`。
- List/Select/Table/Tree/NavList/Tabs/MenuBar 共用；不再保留各自的“跳过 disabled、clamp、窗口”循环。

## 2. W3 冻结：Widget / Styles

### Component（不变）

```python
class Component(Protocol):
    def render(self, width: int) -> list[Line]: ...
```

### Widget（新增基类，不强制自定义组件继承）

```python
class Widget:
    theme: Theme | None       # None = 继承 App 主题
    styles: Styles | None     # 组级覆盖；None 字段继承 theme
    focused: bool             # 默认 False；FocusManager/App 写
    hover: bool               # 默认 False；Pointer/App 写

    def render(self, width: int) -> list[Line]: ...   # 子类实现

    # 可选交互动词：默认 no-op，返回 False/None
    def handle(self, event: Event) -> bool: ...
    def click(self, row: int, col: int) -> bool: ...
    def hover_at(self, row: int, col: int) -> bool: ...
    def activate(self) -> bool: ...
    def take_result(self) -> object | None: ...
    def revision(self) -> object | None: ...
```

- `Widget` 不再有 `focused=` 构造参数；初始焦点由 `App.focus(...)` 决定。
- 纯渲染组件可以只实现 `render`，不必继承 `Widget`。
- 9 个 capability protocol 从公共 `__all__` 删除；内部需要时用 `hasattr`/duck typing。`Component` 保留。
- `Widget.revision()` 默认 `None`（不缓存）；有状态的子类覆盖为值快照。

### Styles

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Styles:
    text: TextStyles | None = None
    surfaces: SurfaceStyles | None = None
    borders: BorderStyles | None = None
    controls: ControlStyles | None = None
    rows: RowStyles | None = None
    status: StatusStyles | None = None
    content: ContentStyles | None = None
    chrome: ChromeStyles | None = None
    overlays: OverlayStyles | None = None
    syntax: SyntaxStyles | None = None
```

- 每个字段为 `None` 时继承 `theme.<group>`；非 `None` 时整组覆盖。控件内部只读 `self._group("rows")` 这类方法，不把组名暴露给用户。
- 构造器删除 `style` / `hover_style` / `focus_style` / `disabled_style` / `ground_style` / `label_style` / `cursor_text_style` / `description_style` / `title_style` / `active_style` / `inactive_style` / `bar_style` / `bar_active_style` / `filled_style` / `empty_style` / `done_style` / `todo_style` / `guide_style` / `header_style` / `first_column_style` / `border_style` / `shade` 等样式参数，统一用 `styles: Styles | None = None`。
- `glyphs` 保留独立参数。
- 主题在 render 时解析；`revision()` 必须包含 `theme` 和 `styles`（或其等价值），否则缓存会吞掉主题切换。

### 控件构造器目标

- 除 `TUI`/`App` 外，任何公共构造器不超过 10 个参数。
- `Select` 去掉 `multi` / `marked` 布尔；多选拆成 `MultiSelect`。
- `Scrollbar` 降到 `target: Scrollable, *, size=1, min_thumb=1, styles=None, glyphs=GLYPHS, theme=None`；`scroll_tick` 移到 App/常量。
- `ScrollView`：`child, *, height=None, offset=0, bar=False, styles=None, glyphs=GLYPHS, theme=None`；`scrollbar` 改名 `bar`（1.2 破坏性变更）。
- `Table`：`headers, rows, *, aligns=None, grid=..., styles=None, glyphs=..., theme=None, wrap=True, max_col_width=40, min_col_width=3, disabled=False, disabled_items=()`。

## 3. W4 冻结：App / TUI / read_event

### TUI（低层）

- `read_event()` 只返回下一个事件或 `None`。**不**消费 wheel/page，**不**执行 `focus_policy`，**不**读 `scroll_keys`。
- 删除 `TUI.focus_policy`、`TUI.scroll_keys`、`TUI.make_input`、`TUI.make_autocomplete`。
- `TUI.add(component, *, id=None, pin=None, pane=None) -> str` 返回 id；`get/remove -> Component`。
- `TUI.dock(component, *, edge="bottom", size=None) -> Pane` 接受组件，不再要求 `Viewport`。
- `TUI.split(...) -> tuple[Pane, ...]` 保持。
- `TUI.hit(x, y) -> Hit | None`；`Hit` 简化并提供祖先链（精确形状在 W2 冻结）。
- `TUI` 仍保留 `screen/frame/document/rows/selection/painter` 供高级用法，但 root 不导出 `Frame`/`Viewport`/`ScreenLayout`/`Painter`。

### App（高层）

```python
class App:
    def __init__(
        self,
        *,
        theme: Theme | None = None,
        mouse: bool = True,
        hover: bool = True,
        color_mode: ColorMode | None = None,
        title: str = "",
        auto: bool = True,          # False = 不挂默认控制器
        screen: Screen | None = None,
        keys: EventSource | None = None,
        throttle: float = 0.030,
    ) -> None: ...

    def run(self) -> None: ...
    async def run_session(self, body) -> None: ...

    def add(self, component, *, id=None, pin=None, pane=None) -> str: ...
    def get(self, id: str) -> Component: ...
    def remove(self, id: str) -> Component: ...
    def bind(self, key: str, callback: Callable[[], object]) -> None: ...
    def focus(self, target: str | Component) -> bool: ...
    def focus_next(self) -> bool: ...
    def split(self, orientation: str, *, ratios=(1, 1), min_size=1, separator=True, pane=None) -> tuple[Pane, ...]: ...
    def dock(self, component, *, edge="bottom", size=None) -> Pane: ...
    def toast(self, text: str, *, style: Style | None = None) -> None: ...
    def open_modal(self, panel) -> Modal: ...
    def open_palette(self, commands, **kwargs) -> CommandPalette: ...
    def find(self) -> Find: ...
    def quit(self) -> None: ...

    # 可覆盖钩子
    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...
    def on_event(self, event: Event) -> bool: ...
    def on_key(self, event: KeyEvent) -> bool: ...
    def on_mouse(self, event: MouseEvent) -> bool: ...
    def on_tick(self) -> None: ...
```

默认分发顺序（`auto=True`）：

1. 打开的 `Modal` / `CommandPalette`；
2. `Toasts` / `Tooltip`；
3. 指针下的 pane chrome（`Scrollbar`）与 `ScrollView` 的 bar；
4. `SelectionGesture`（press/motion/release）；
5. `Pointer`（hover / stationary click）；
6. 焦点控件的 `handle(event)`；
7. 全局 `bind` 的键；
8. `on_key` / `on_mouse` / `on_event`；
9. wheel：`Hit.chain` 中最近的 `Scrollable`，否则 focused pane 的 viewport。

- `tab`：`focus_next()`；`shift-tab`：`focus_previous()`。
- 鼠标 press：聚焦命中的 pane；click 走 FocusManager 的 click 策略（descend → click → focus → activate）。
- `App.theme` 变更时遍历已挂载的组件，只更新 `theme is None` 的 `Widget`；显式 `theme=` 的控件保持本地覆盖。
- `auto=False` 时 App 不挂任何控制器，等价于 `TUI` + 用户自己的循环；`TUI` 仍可直接使用。

### read_event 契约

```python
event = await tui.read_event()   # 原样返回；None 表示 EOF / 非 live
```

- 不再有“读取时顺手滚动/聚焦”的副作用。
- 默认滚动/焦点策略只在 `App` 中执行。
- 高级宿主若直接用 `TUI`，自行处理 wheel/page。

## 4. W5 冻结：Table wrap / ScrollView bar

### Table

- `Table(..., wrap=True, max_col_width=40, min_col_width=3)`。
- `wrap=False`：保持 1.2 之前的自然宽度 + 比例收缩 + 省略号。
- `wrap=True`：列宽预算确定后，用 `wrap_line(Line(cell_segments), inner)` 换行；行高 = 最大单元格行数；每个视觉行都有左右边框；行间 rule 只在该记录最后一条视觉行后。
- `header` 也换行；`header_line(width)` 保留为单行兼容视图（内部取第一视觉行），新增 `header_lines(width)`。
- `_layout(width)` 记录 `(kind, data_row, visual_line)`；`click`/`hover_at` 用最近的布局映射回数据行。
- Markdown `TableRule` 默认 `wrap=True`；不新增 `Markdown` 构造参数，保持 `max_col_width=40` 默认。
- inline `Segment`、`link`、`action` 必须保留。

### ScrollView bar

- `ScrollView(child, *, height=None, offset=0, bar=False, ...)`；`bar=True` 时：
  - 最后一列绘制 track/thumb（内容渲染宽度 `width-1`）；
  - 鼠标 press 在 thumb 上进入拖动，在 track 上翻页；
  - motion 拖动映射到 `ScrollState.scroll_to`；
  - release 结束拖动；
  - wheel 在 bar 或内容上滚动 `ScrollState`；
  - `click(row, col)` 和 `handle(event)` 都可达；`child_at` 的 bar 列返回 `None`（view 自己消费）。
- pane 级 `Scrollbar` 与 `ScrollView` 共用 `ScrollState.thumb` 和同一套拖动映射；`Scrollbar` 接受 `Scrollable`，不再只接受 `Pane`。
- App 的 wheel 路由：`Hit.chain` 反向找最近的 `Scrollable`；找到就滚它，否则滚 focused pane。

## 5. 删除清单（W2/W3/W4 执行）

- `src/motui/kernel/host.py` 整个文件；`Host`、`QueryInput`、`FilterList`、`OptionLike`、`RowRange` 的公共导出（`EveryHandle` 可保留在 core）。
- `TUI.make_input` / `TUI.make_autocomplete`；`Find` / `CommandPalette` 直接构造 `Input` / `Autocomplete`。
- `widgets/delegate.py`；`Delegate` 从 `widgets.__all__` 删除。
- `BlockState`、`Block.seal`、`Block.state`；`testing.snapshot` 不再输出 state。
- `DEFAULT_HEADER_STYLE`（`widgets/table.py`）。
- `COLORBGBG` 兼容分支（`kernel/theme.py`）。
- 9 个 capability protocol 的公共导出：`Clickable`、`Activable`、`Focusable`、`Hoverable`、`Container`、`Controller`、`Resultful`、`Revisioned`（`Component` 保留）。
- `motui.kernel` / `motui.keys` / `motui.interaction` / `motui.commands` 命名空间。
- `Text` 从 `widgets.__all__` 删除（只在 core/root 导出）。
- `CommandPalette` 的 6 个纯转发；改为持有/继承 `Modal`，暴露 `modal` 属性。
