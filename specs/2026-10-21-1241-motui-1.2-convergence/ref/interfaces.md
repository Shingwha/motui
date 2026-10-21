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

### W1 实际交付（2026-10-21，merge `5444cb2`）

- `ScrollState` 已落地：`src/motui/kernel/scroll.py`。字段 `offset/content_height/viewport_height/stick_to_bottom`；私有 `_extent` 记录上次布局的 extent（`compare=False`）。`thumb` 公式为 `round`，是唯一公式。
- `Scrollable` 已导出：`scroll_state` / `scroll_to` / `scroll_by`。`Viewport`、`ScrollView`、`Pane` 实现。
- `Viewport.scroll_to` 现在返回 `bool`（原 `None`）；新增 `Viewport.scroll_by`、`Viewport.scroll_state`；`Pane.scroll_state` 委托 viewport。
- `Viewport.scroll_to_bottom()` 现在会立即把 `offset` 写到 `max_offset()` 并置 `stick_to_bottom=True`；下一次 layout 仍贴底。
- `ScrollView` 用 `ScrollState`；`_thumb_span` 删除；`scrollbar` 属性名保留（W5b 再改 `bar`）；内容不超过窗口时 `thumb()` 返回 `None`，bar 只画 track（旧行为是满格 thumb，无 golden 覆盖）。
- `Cursor` 已取代 `CursorWindow`：`src/motui/kernel/cursor.py`。`count/index/disabled/wrap`；`clamp/select/move/home/end/window(size, anchor="top"|"center"|"bottom")`。构造不 clamp `index`（保留 stale-index 语义）；控件 setter 负责 clamp。
- `BlockState`/`seal`/`state`/`is_open` 删除；`Block.rows` 只在组件 `Revisioned` 且 `revision() is not None` 时缓存，否则每次 re-render。`testing.snapshot` 头改为 `[id]` / `[id | top]` / `[id | bottom]`。
- `Delegate`、`widgets/delegate.py`、`components--delegate` topic/golden、`DEFAULT_HEADER_STYLE`、`COLORBGBG` 删除。
- 当前真正结果：`pytest` 885 passed，golden 57 topics，render hash `a82f7968...` 不变，demo 两个入口 exit 0。
- 注意：`docs/**` 仍有 Delegate/COLORBGBG 段落，留给 W6；`app.py`/`kernel/host.py` 仍存在，W2 处理。

### W2 实际交付（2026-10-21，merge `0c25bc2`）

- 包结构已落地：`motui.core`（原 kernel + keys 扁平化）、`motui.widgets`、`motui.app`（原 app + interaction + commands）。
- `motui.core` 导出 79 names（含 `KeyDecoder`/`Keymap`/默认 keymaps/`RawTerminalKeys`）；`motui.app` 导出 14 names；root `__all__` 仍 37 names（import 来源已换）。
- `core/hit.py` 承接 `Hit`（仍 7 字段，W4 简化）、`RowRange`、`EveryHandle`；`Host`/`QueryInput`/`FilterList`/`OptionLike` 删除。
- `TUI.make_input`/`make_autocomplete` 删除；`Find`/`CommandPalette` 直接构造 `Input`/`Autocomplete`。
- `TUI.read_event` 的 `scroll_keys`/`focus_policy` 副作用原样保留，W4 再移入 App。
- 测试：879 passed（-6：facade 参数化 7→5，Host/工厂 4 例删除），golden 57 topics 未变，render hash 不变。
- 旧命名空间仅剩 demo 的 `overview--welcome`/`reference--api-layers` 渲染内容（层名表），W6 更新并重录这两帧。
- `tests/kernel|keys|interaction` 目录名暂未改；W6 可选改名。

### W3a 实际交付（2026-10-21，merge `4653802`）

- `Styles` 在 `core/theme.py`，10 个组字段；`Widget` 在 `core/widget.py`，`__slots__ = ("theme","styles","focused","hover")`，不继承 `Themed`。
- `Widget._theme` 是 property；`group(name)` 解析 `styles.<name>` 或 `theme.<name>`；默认 `handle/click/hover_at/activate -> False`、`take_result/revision -> None`、`render -> NotImplementedError`。
- `Button`/`Checkbox`/`Link` 已迁移：构造器只剩 `label/text, *, checked?, glyphs?, disabled, theme, styles`；`focused=` 与 4 个 `*_style` 删除；render 时读组；`revision()` 含 `theme/styles`。
- 活主题用例：`tests/widgets/test_action.py::test_a_theme_assignment_repaints_the_next_render`。
- 迁移 pattern（W3b/W3c 直接复用）：
  1. `class X(Widget)`；`super().__init__(theme, styles)`；不再用 `Themed.pick`。
  2. `__slots__` 删 `"theme"/"focused"/"hover"` 和所有 `_*_style` 缓存槽。
  3. 删除 `style/hover_style/focus_style/disabled_style/focused`；加 `styles: Styles | None = None`。
  4. render 每次 `self.group("<组>")`；状态优先级不变。
  5. `revision()` 末尾加 `self.theme, self.styles`。
- **focused 默认值**：移除 `focused=` 参数后，在 `__init__` 里保留旧默认值（Input/Select/Editor/Table/Tree/NavList/Tabs/MenuBar 默认 `True`；RadioGroup/CheckboxGroup/List 默认 `False`），以守住 golden。调用点传 `focused=` 的改成构造后赋值。
- `Dialog` 仍是 `Themed`；其 `_new_button` 已改为给 `Button` 传 `Styles`（W3c 再迁移 Dialog 本身）。
- 本波未改 golden；`docs` 与 demo 的 `api_line` 文案仍写旧签名，W6 统一更新。
- 结果：880 passed / 57 golden / render hash 不变。

### W3b 实际交付（2026-10-21，merge `5fc0736`）

- forms 家族全部迁移：`Select`/`MultiSelect`/`Autocomplete`/`RadioGroup`/`CheckboxGroup`/`Input`/`Editor`/`ComboBox`/`Form`。
- `Select` 删除 `multi/marked/focused` 与全部 style 参数；`MultiSelect(Select)` 承接 `marked`/`toggle()`；`CheckboxGroup` 为 `(_FormGroup, MultiSelect)`。
- `Select` 构造器：`options` + 10 个 keyword-only（title/max_rows/wrap/glyphs/commit/window/disabled/disabled_items/theme/styles）。
- `Input`/`Editor` 删除 `style/caret_style/prompt_style/focused`；`TextBuffer` 仍是纯编辑引擎，render 时接收解析后的样式。
- `ComboBox` 新增 `styles=` 转发；`focused` property 委托给 `.input`，构造顺序先建子控件再 `super().__init__`。
- 样式映射：Select 标签/标题 `text.base`、光标 `content.accent`、描述/计数 `text.muted`、disabled/dim `text.faint`、行 band `rows`；Radio/Check `content.accent`+`rows`；Input/Editor 正文 `text.base`、caret `text.caret`、prompt `content.accent`、placeholder `text.faint`、selection `text.selection`、hover `surfaces.hover`；Form 标签 `content.accent`、错误 `status.danger`。
- `focused` 旧默认保留：Input/Editor/Select True；RadioGroup/CheckboxGroup False。
- 结果：882 passed / 57 golden / render hash 不变。

### W3c 实际交付（2026-10-21，merge `06b54fa`）

- data/navigation 家族迁移：`List`/`Table`/`Tree`/`NavList`/`Tabs`/`MenuBar`/`ContextMenu`/`LabelStrip`/`ScrollView`。
- 构造器已删除全部 `*_style` 与 `focused=`；`styles` 为唯一覆盖入口。
- 旧默认焦点保留：List False；Table/Tree/NavList/Tabs/MenuBar/ScrollView True。
- 映射：List/Table/Tree 行 band `rows`、text 组；Tabs/MenuBar active `content.accent`/inactive+disabled `text.faint`/hover `surfaces.hover`/divider `text.muted`/indicator `controls.focus`；NavList bar 保持旧默认 `text.muted`/`content.accent`（字面映射会改 SGR，故按字节守 golden）；ScrollView track/thumb `chrome.*`。
- `LabelStrip` 基类为 `(ClampedCursor, Widget)`；Tabs/MenuBar 的 `theme/styles/focused/hover` 由 Widget 提供。
- `Table` 暂未加 `wrap`（W5a）；`ScrollView.scrollbar` 名称保留（W5b）。
- 结果：882 passed / 57 golden / render hash 不变。

### W3d 实际交付（2026-10-21，merge `f8390e1`）

- content/layout/markdown 全部迁移：Divider/Panel/Dialog/ButtonSpec/Diff/ProgressBar/Slider/Spinner/Padding/Collapsible/StatusLine/ShortcutBar/Notice/Markdown。
- `ButtonSpec` 的 style 字段换为 `styles`；`Dialog` 删 `border_style/title_style`；`Padding` 基类为 Widget，`fill_style` -> `styles`（`surfaces.base`）。
- `Markdown` 用 `_effective_theme()` 把 `Styles` 组 `replace` 进 theme，再传给 `RenderContext`；规则层未改；`_sync_theme` 换主题时清 `_StreamCache`。
- `Diff` 删除自有 `theme` property，缓存键含 `theme/styles`。
- 结果：882 passed / 57 golden / render hash 不变。

## 2. W3 冻结：Widget / Styles

### Component（不变）

```python
class Component(Protocol):
    def render(self, width: int) -> list[Line]: ...
```

### Widget（新增基类，不强制自定义组件继承）

```python
class Widget:
    __slots__ = ("theme", "styles", "focused", "hover")

    def __init__(self, theme: Theme | None = None, styles: Styles | None = None) -> None: ...

    theme: Theme | None       # None = 继承 App 主题
    styles: Styles | None     # 组级覆盖；None 字段继承 theme
    focused: bool             # 默认 False；FocusManager/App 写
    hover: bool               # 默认 False；Pointer/App 写

    @property
    def _theme(self) -> Theme: ...   # theme or DEFAULT_THEME

    def group(self, name: str) -> object: ...  # styles.<name> or _theme.<name>

    def render(self, width: int) -> list[Line]: ...   # 子类实现

    # 可选交互动词：默认 no-op，返回 False/None
    def handle(self, event: Event) -> bool: ...
    def click(self, row: int, col: int) -> bool: ...
    def hover_at(self, row: int, col: int) -> bool: ...
    def activate(self) -> bool: ...
    def take_result(self) -> object | None: ...
    def revision(self) -> object | None: ...
```

**增量策略（避免半迁移时 slot 冲突）**：

- `Widget` **不继承** `Themed`。`Themed` 保持现状（`__slots__ = ("_theme",)`，构造时解析），只服务尚未迁移的控件和控制器（`Find`、`RegexHighlighter`）。
- `Widget` 自己持有 `theme/styles/focused/hover`；迁移一个控件时把它的基类从 `Themed` 改为 `Widget`，并从该控件的 `__slots__` 删除 `"theme"`/`"focused"`/`"hover"`（基类已有）。
- 迁移后的控件在 render 时通过 `self._theme` / `self.group(...)` 读样式，不缓存解析结果；`revision()` 必须包含 `theme` 和 `styles`。
- 迁移完成的控件不再接受任何 `*_style` 参数；唯一覆盖入口是 `styles: Styles | None`。
- `Themed` 在 W3 全部完成后只应剩控制器使用；W6 可把 `Themed` 改成 `Widget` 的内部小基类或保留为控制器专用。
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

### W4a 实际交付（2026-10-21，merge `978a479`）

- **命名决策 A**：`motui.app` 包内的 main class 模块叫 `application.py`，即 `motui.app.application.App`；公开导入仍是 `from motui.app import App`。禁止 `app/app.py`（package/module/class 三重同名）。
- `TUI.read_event()` 已是纯读取：无 `scroll_keys`/`focus_policy`/副作用；事件原样返回。
- `TUI.add -> str`；`get/remove -> Component`；`dock(component) -> Pane`；`system -> str`。
- `Hit(pane, block, row, col, chain=())`，`leaf/leaf_row/leaf_col` 是从 chain 派生的 property；`descend_chain` 是新的祖先链原语；`Pane` 实现 `scroll_to/scroll_by`，完整满足 `Scrollable`。
- `App` 已实现：默认挂 focus/pointer/gesture/toasts/tooltip；dispatch 顺序 palette -> modal -> find -> toasts -> wheel -> mouse -> focus -> bind/tab -> hooks；`auto=False` 可退化为纯 TUI。
- App 额外能力：`focus_manager/pointer/gesture/toasts` 只读属性（高级宿主）；`set_focus_targets`；`dock` 主题化并纳入主题遍历；`run_session(body(app))`。
- 测试 880 passed（-4 旧行为用例，+2 App 用例）；golden 57 未变；render hash 不变；demo 两个入口正常。
- demo 仍保留手写循环 + W4a 临时 wheel/focus 路由（W4b 重写）。

### W4b 实际交付（2026-10-21，merge `a346ed7`）

- demo `Session` 现在是 `App` 子类，300 行；入口 `render_topic` / `_headless` / interactive / `Anchors` 全部 `Session(...)` + `run_async()`。
- 默认 focus/pointer/gesture/toasts/tooltip/find/palette 由 App 提供；Session 只保留导航、shell、picks、`Scrollbar`/`Stats` 两个自定义控制器。
- App 新增：`interactive/focus_events/sync/on_selection` 透传；`mount(controller, dispatch=True)`/`unmount`/`controllers`；`tooltip/palette/find_bar` 属性；`undock(edge)`；page 键路由（focused `Scrollable` -> focused pane）；theme 向 overlays/controllers 传播。
- `_MountedOverlay.set_theme`、`Toasts.set_theme`、`CommandPalette.set_theme`、`Modal.set_theme`、`Scrollbar.set_theme` 补齐。
- 两个 demo 输出 sha256 与 W4a 前完全一致：headless `c793b32b...`，`--pages` `855f76fa...`；golden 57 未变。
- 测试 882 passed（+2 App 用例）；render hash 不变。
- demo `shell.py` 现为 220 行，包含 shell 装配/状态/点击跟随；`Session.theme_name/focus_name` 不再是公开成员。

### W5a/W5b/W6 实际交付（2026-10-21）

- **W5a Table wrap（merge `6f47e1e`）**：`Table(wrap=True, max_col_width=40, min_col_width=3)`；
  `wrap=False` 逐字节保留旧省略行为。视觉行布局 `_Slot(kind,data_row,visual_line)`；
  header 可换行；rule/mark/band 落在正确视觉行；`click`/`hover_at` 读最近一次 render 的布局。
  Markdown `TableRule` 使用默认 `wrap=True`。
- **W5b ScrollView bar（merge `fc49907`）**：`ScrollView(bar=True)` 的 thumb 可拖、track 可翻页、
  wheel 可滚；`Widget.drag(row,col,kind)` + App 的 drag 路由（press/motion/release 在 gesture/pointer 之前）。
  pane `Scrollbar` 仍是 chrome controller。
- **W6 API/version（merge `60615d6` / `a6d69b1` / `7078997`）**：
  - root 仍 37 names：`DEFAULT_THEME, App, Border, Button, Checkbox, Color, ColorPalette,
    CommandPalette, Component, Dialog, Editor, FocusEvent, Glyphs, Input, KeyEvent, Line, Link,
    List, Markdown, Modal, MouseEvent, MultiSelect, Option, PasteEvent, ResizeEvent, Segment,
    Select, Style, Styles, TUI, Table, Text, Theme, Tree, Widget, headless_tui, snapshot`。
  - `motui.core.__all__` 不再导出 8 个 capability protocol；`Color`/`descend_chain` 加入。
  - `motui.widgets.__all__` 不再重导出 `Text`（Text 只在 core/root）。
  - `prompt_dialog(style=)` -> `prompt_dialog(styles=)`。
  - 版本 1.2.0；README/DESIGN/CONTRACT/COMPONENTS/CONTRIBUTING/CHANGELOG 全量同步。
- **最终焦点模型（W6 修正）**：
  - `Widget.owns_focus = False`；`Form`/`ComboBox` 设 `True`。`App.add` 注册 owner，
    跳过其子树，避免字段成为竞争焦点目标。
  - click 分两半：leaf 执行 `click(row,col)` 动作；每个祖先执行 `focus_at(row,col)` 更新内部游标
    （`Form.focus_at` -> field index，`Dialog.focus_at` -> button index）。
  - `FocusManager.click` 从 `Hit.chain` 找**最近的已注册祖先**作为焦点 owner；只有 leaf 且非
    Container 才在重复点击时 `activate`。
  - `Form` 的 name/email 点击切换、`Form` 只注册自身（不注册 Inputs）由
    `tests/app/test_app.py::test_a_form_owns_its_fields_and_a_click_moves_its_cursor` 覆盖。
- 最终门禁：891 tests / 57 golden / render hash `a82f7968...`；headless demo sha `c793b32b...`；
  `--pages` sha `b6ba849d...`（W5a 表格换行）。

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
