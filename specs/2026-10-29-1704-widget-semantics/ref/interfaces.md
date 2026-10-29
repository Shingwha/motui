# 目标接口契约（2.1.2）

> 状态：W1–W3 已落地（main `314c973`，1700 tests / semantic 9/9 / render-hash
> 不变）。W4a 起按本文件继续；每波合并后 lead 更新“已落地”标记与偏差。
> 真相优先级：代码与测试 > handoff > 本文件。本文件是意图，不是现状。

## 0. 已落地（W1–W3）

- `Line.overlay(base)` / `Surface.overlay(base)` 已在 `kernel/cell.py`。
  实现偏差：顶层非透明 cell 压到双宽 glyph 的任一半时，**整个底层 glyph**
  被擦除，未覆盖列变成该 glyph 样式的单列空白；透明顶层保留整字。
  `Surface.overlay` 用 `Surface.of` 归一化（行宽恰好为 max）。
- `Stack(children, *, theme, styles)` / `Align(child, *, horizontal,
  vertical, theme, styles)` 已从 `motui.widgets` 导出。实现偏差：`Align`
  的“实际尺寸”取行数 × 最宽行（不是 `Surface.width`），因为 `Text`/`Rows`
  合法返回短行；`Stack.child_at` 交互优先，全部非交互时回退最顶层。
- `Drawing` 已在 `widgets/drawing.py`，但**尚未从 `motui.widgets` 导出**；
  W4a 决定是否公开。`Canvas`/`PixelCanvas` 已继承它；`Canvas.marker` →
  `plot_marker`；两者不再接受 `styles`；`PixelCanvas.palette=None` 时
  `PixelPalette.from_theme(theme)`。
- 本组 wave 的 `handoff/W1-zcode.md`、`W2-zcode.md`、
  `W3-deepseek-v4.1-flash.md` 已随分支提交。


## 1. 类层次

```python
Widget
├── ResultWidget          # _pending + take()
│   ├── ActionWidget      # disabled / hint / activate / toggle / on_action
│   ├── CursorWidget      # index / selected / select / move / home / end
│   ├── Form
│   ├── Dialog
│   ├── Text / Markdown   # inline action 结果
│   └── Collapsible
├── Drawing               # width/height/resize/surface/render
│   ├── Canvas
│   └── PixelCanvas
└── Container             # children / child_at
    ├── Row / Column / Stack
    ├── Padding / Panel / Align / ScrollPanel
    └── Collapsible（同时是 ResultWidget；按家族归 ActionWidget 更准确）
```

`CursorWidget` 的子类不再各自持有 `_index`/`_cursor()`/`select`/`move`；它们
提供四个钩子：

```python
class CursorWidget(ResultWidget):
    def _entry_count(self) -> int: ...
    def _entry_at(self, index: int) -> object | None: ...      # visible row -> item
    def _cursor_disabled(self) -> Iterable[int]: ...            # visible-row indices
    def _cursor_wraps(self) -> bool: return False
    def _page_size(self, size: int) -> int: return size         # page_prev/page_next
```

公开面：

```python
index: int                       # 可读写；赋值委托 select()；空集合为 0
selected: object | None          # 只读；_entry_at(index)
def select(self, index: int) -> bool
def move(self, delta: int) -> bool
def home(self) -> bool
def end(self) -> bool
def activate(self) -> bool       # 子类实现；基类 False
def toggle(self) -> bool         # 子类实现；基类 False
def on_key(self, event) -> bool  # 通用 keymap → on_action 路由
```

迁移期补充（W4a 合并后）：`CursorWidget` 增加 `_cursor_enabled()` 钩子
（整控件 disabled 策略），`index` setter 委托 `select()`，通用 `on_key`
按 `keymap` 路由。这样 W4b/W4c 不再改基类，宿主既有的 `index =` 赋值也
继续工作。

`Cursor`（`widgets/cursor.py`）仍是内部算术；`CursorWidget` 持有一个
`Cursor` 实例并在 `select`/`move`/`home`/`end` 后写回组件状态。

## 2. 构造契约

规则：主内容唯一位置参数；其余全部 keyword-only；尾部顺序
`glyphs, theme, styles, keymap`。缺省的尾部参数省略。

| 组件 | 目标签名（只列公开参数） |
|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)` |
| `Button` | `Button(label, *, kind=ButtonKind.NEUTRAL, disabled=False, theme=None, styles=None)` |
| `Checkbox` | `Checkbox(label, *, checked=False, glyphs=GLYPHS, disabled=False, theme=None, styles=None)` |
| `Link` | `Link(text, *, disabled=False, theme=None, styles=None)` |
| `Tabs` | `Tabs(items, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False, theme=None, styles=None)` |
| `MenuBar` | `MenuBar(items, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False, theme=None, styles=None)` |
| `NavList` | `NavList(items, *, groups=(), index=0, disabled_items=(), disabled=False, glyphs=GLYPHS, bar_space=None, theme=None, styles=None)` |
| `List` | `List(items=(), *, window=8, prefix_jump=True, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)` |
| `Table` | `Table(rows, *, headers=(), aligns=None, glyphs=GLYPHS, grid=None, disabled=False, disabled_items=(), theme=None, styles=None, cell_wrap=WrapMode.WORD, max_col_width=40, min_col_width=3)` |
| `Tree` | `Tree(nodes=(), *, indent=2, glyphs=GLYPHS, disabled=False, theme=None, styles=None)` |
| `TreeNode` | `TreeNode(label, children=(), *, open=False, disabled=False)` |
| `Select` | `Select(options=(), *, title="", max_rows=8, wrap=True, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)` |
| `MultiSelect` | 同 `Select`，加 `marked=()` |
| `RadioGroup` | `RadioGroup(options, *, index=0, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)` |
| `CheckboxGroup` | `CheckboxGroup(options, *, marked=(), index=0, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)` |
| `Autocomplete` | `Autocomplete(options=(), *, max_rows=8, wrap=True, glyphs=GLYPHS, theme=None, styles=None)` |
| `ComboBox` | `ComboBox(options=(), *, text="", max_rows=8, max_drop_rows=6, glyphs=GLYPHS, theme=None, styles=None)` |
| `ContextMenu` | `ContextMenu(options=(), *, title="", max_rows=8, glyphs=GLYPHS, theme=None, styles=None)` |
| `Form` | `Form(fields, *, gap=0, index=0, on_submit=None, theme=None, styles=None)` |
| `Dialog` | `Dialog(body, *, title="", buttons=(), danger=False, width=None, align="center", border=None, shade=True, frame=True, glyphs=GLYPHS, theme=None, styles=None)` |
| `Collapsible` | `Collapsible(body, *, title="", open=True, glyphs=GLYPHS, disabled=False, theme=None, styles=None)` |
| `Panel` | `Panel(child, *, title="", frame=True, border=None, glyphs=GLYPHS, theme=None, styles=None)` |
| `Padding` | `Padding(child, *, left=0, right=0, top=0, bottom=0, theme=None, styles=None)` |
| `Row` | `Row(children, *, widths=None, gap=1)` |
| `Column` | `Column(children, *, gap=0)` |
| `Stack` | `Stack(children, *, theme=None, styles=None)` |
| `Align` | `Align(child, *, horizontal="center", vertical="middle", theme=None, styles=None)` |
| `ScrollPanel` | `ScrollPanel(child, *, height=None, offset=0, bar=False, axis="y", glyphs=GLYPHS, theme=None, styles=None)` |
| `Divider` | `Divider(*, char=None, label="", glyphs=GLYPHS, theme=None, styles=None, max_width=None)` |
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, styles=None)` |
| `ShortcutBar` | `ShortcutBar(items, *, glyphs=GLYPHS, theme=None, styles=None)` |
| `Notice` | `Notice(text, *, level="info", glyphs=GLYPHS, theme=None, styles=None)` |
| `ProgressBar` | `ProgressBar(value=0.0, *, maximum=1.0, label="", width_chars=None, glyphs=GLYPHS, theme=None, styles=None)` |
| `Slider` | `Slider(value=0, *, minimum=0, maximum=10, step=1, glyphs=GLYPHS, disabled=False, theme=None, styles=None)` |
| `Spinner` | `Spinner(text="", *, frames=None, glyphs=GLYPHS, theme=None, styles=None)` |
| `Canvas` | `Canvas(*, width=0, height=0, plot_marker="cell", glyphs=GLYPHS, theme=None)` |
| `PixelCanvas` | `PixelCanvas(*, width=0, height=0, marker=Marker.BRAILLE, palette=None, theme=None)` |
| `Sparkline` | `Sparkline(values=(), *, marker="half", style=Style(), glyphs=GLYPHS)` |
| `Markdown` | 保持现有构造，尾部 `glyphs, theme, styles` |
| `Diff` | `Diff(before, after, *, context=3, numbers=False, glyphs=GLYPHS, theme=None, styles=None, wrap=WrapMode.ELLIPSIS)` |
| `Input` | `Input(text="", *, prompt=None, placeholder="", mask="", glyphs=GLYPHS, theme=None, styles=None, keymap=None, read_only=False, wrap=WrapMode.OVERFLOW)` |
| `Editor` | `Editor(text="", *, placeholder="", mask="", theme=None, styles=None, keymap=None, max_rows=None, read_only=False, wrap=WrapMode.WORD)` |
| `ButtonSpec` | `ButtonSpec(label, value=None, styles=None, kind=ButtonKind.NEUTRAL)` |
| `Field` | `Field(name, component, label="", validate=None, value=None, error=None)` |
| `Option` | `Option(label, value=None, description="")` |

明确例外（多内容/无单一主内容/原始内容）：

- `Diff(before, after)`、`Field(name, component)`、`ButtonSpec(label, value)`、
  `Option(label, value)` 保留两个位置参数。
- `StatusLine(*, left, right)`、`Divider(*, ...)` 无主内容。
- `Sparkline(values, *)` 的原始序列保留位置参数。
- `Row/Column/Stack/Padding/Align/ScrollPanel` 的 `children`/`child` 是唯一的
  结构位置参数。

`Canvas`/`PixelCanvas` 不再接受 `styles`：原始绘制不走角色组。`PixelCanvas`
的 `palette=None` 表示从 `theme` 派生（`PixelPalette.from_theme`），显式
`palette` 永远优先。

## 3. 状态

| 概念 | 名字 | 类型 | 组件 |
|---|---|---|---|
| 光标位置 | `index` | `int`（空为 0） | Tabs/MenuBar/NavList/List/Table/Tree/Select/MultiSelect/RadioGroup/CheckboxGroup/Autocomplete/ComboBox/ContextMenu/Form/Dialog |
| 光标项 | `selected` | 项对象或 `None`（只读） | 同上（Table 为行对象，Tree 为 TreeNode，Form 为 Field） |
| 多选 | `marked` | `MarkSet`（源数据索引） | List/Table/MultiSelect/CheckboxGroup |
| 标量值 | `value` | int/float | Slider/ProgressBar |
| 布尔 | `checked` | bool | Checkbox |
| 展开/下拉 | `open` | bool | TreeNode/Collapsible/ComboBox/ContextMenu |
| 文本 | `text` | str | Text/Input/Editor/Markdown/ComboBox |

删除：`root_nodes`、`expanded`、`is_open`、`labels` 公开属性、
`Table.index: int | None`、`ProgressBar.fraction` 的可写性、`Canvas.marker`。

- `Table.index` 是 int（空表为 0），`Table.selected` 是行对象；`take()` 返回
  激活的行对象，不再返回索引。
- `Tree.index` 是可见行的平面索引，`Tree.selected` 是节点对象。
- `ComboBox.open` 是可读写 bool；删除 `open()`/`close()` 方法；用
  `toggle()` 或赋值。
- `ProgressBar.fraction` 是只读派生属性 `value / maximum`；构造用
  `ProgressBar(value, maximum=...)`。
- `RadioGroup.selected` / `CheckboxGroup.selected` 返回 `Option`，不再返回
  label；公开 `labels` 属性删除（内部可用 `_labels`）。
- `open` 只有属性，不允许方法同名。

## 4. 动词

| 动词 | 语义 | 返回 |
|---|---|---|
| `activate()` | 主操作：按下/选取/提交/切换 | bool（是否发生） |
| `toggle()` | 翻转布尔/标记/展开态 | bool（是否发生） |
| `select(index)` | 精确放置光标（clamp；disabled 拒绝） | bool（是否移动） |
| `move(delta)` | 步进光标或值（跳 disabled；不 wrap 的组件在端点停） | bool（是否移动） |
| `advance()` | 下一帧（Spinner） | None |
| `take()` | 读取一次性结果 | object / None |

`on_action(name)` 只路由九个名字：
`prev / next / first / last / page_prev / page_next / activate / toggle /
open / close`。规则：

- `on_action("activate")` 委托 `self.activate()`；`on_action("toggle")`
  委托 `self.toggle()`。
- 未知名字、disabled 控件、disabled 行返回 `False`。
- `on_action("prev")` 返回 `move(-1)` 的结果（不再是“按键被消费就 True”）。
- 状态变化动词（`select`/`move`/`home`/`end`/`open`/`close` 及光标点击）
  清 pending；只有 `activate`/`toggle` 写 pending。
- `Select` 删除 `commit` 参数：移动/点击不再写 pending（Form 的值提取读
  `selected`，不依赖 `take`）。`window` 保留（top-stick vs center）。
- `page_prev`/`page_next` 的步长由 `_page_size` 决定；不支持的组件返回
  `False`。

`CursorWidget` 提供默认实现；子类只覆盖 `activate`/`toggle` 和钩子。

## 5. 结果

| 组件族 | `take()` 返回 |
|---|---|
| Button / Link | bool（按下） |
| Checkbox / Collapsible | bool（新的 checked/open） |
| Select / RadioGroup / Autocomplete / ComboBox / ContextMenu | 选项的 `value`（`value is None` 时用 label） |
| MultiSelect / CheckboxGroup | 已标记项的 value 列表（按行序） |
| List | 激活的 item（str） |
| Table | 激活的 row（原始行对象） |
| Tree | 激活的 TreeNode |
| Tabs / MenuBar / NavList | 激活的标签/item（str） |
| Form | 提交的 `dict[str, object]` |
| Dialog | 按钮的 value |
| Text / Markdown | inline action payload |
| Slider | 无 take（删除） |
| Input / Editor | 无 take |

`ResultWidget` 内部：

```python
_MISSING = object()
if self._result is not _MISSING:   # pending，包括合法 None
    value, self._result = self._result, _MISSING
else:
    value = None
```

`take()` 读取即清空；合法 `None` 与“无结果”在内部用 sentinel 区分。公开
`take()` 返回 `object | None`，调用方用“是否调用过 take”表达取消（Dialog）。

## 6. 样式

主题仍是通用角色组，不做 per-component recipe。

`SurfaceStyles` 新增：

```python
control: Style = DARK_PALETTE.surface_raised   # 字段/neutral 按钮底板
accent:  Style = solid(accent)                 # primary 按钮底板
danger:  Style = solid(danger)                 # danger 按钮底板
```

`ControlStyles` 瘦身为状态 overlay，删除 `base` 和 `band()`：

```python
hover:    Style = Style(bold=True, underline=True)
focus:    Style = Style(bold=True, underline=True, reverse=True)
active:   Style = Style(reverse=True, underline=True)
disabled: Style = Style(dim=True)

def overlay(self, *, hovered=False, focused=False, pressed=False,
            disabled=False) -> Style:  # disabled > pressed > focused > hovered
```

Button kind 映射（`action_band(kind, theme, ...)`，`action.py` 内唯一实现）：

| kind | 底板 + 前景 |
|---|---|
| `NEUTRAL` | `surfaces.control` + `text.base` |
| `PRIMARY` | `surfaces.accent` + `text.inverse` |
| `GHOST` | 无底板 + `content.accent` |
| `DANGER` | `surfaces.danger` + `text.inverse` |

之后叠加 `controls.overlay(hovered=..., focused=..., pressed=..., disabled=...)`。
`Button` 标签仍是 `" label "`，不加括号。

其他默认：

- Input/Editor：`surfaces.control` 字段底板；hover 下划线；focus 靠 caret；
  disabled dim。
- Checkbox/Radio：mark `content.accent`、label `text.base`；hover/focus 用
  overlay；无底板。
- Link：`content.link` 基础；focus bold+underline（修复当前无效焦点）。
- Tabs/MenuBar：active `content.accent` + underline；hover `surfaces.hover`；
  focus bold+underline；MenuBar 补焦点渲染。
- Slider：accent 轨道；focus 作用于 thumb/轨道；无 take。
- List/Table/Tree：保留 `RowStyles.band`。
- Dialog：内部 `surfaces.raised`；按钮按 kind；scrim 保留。
- Panel：保持 border-only。
- PixelCanvas：palette 默认从 theme 派生；`surface()` 缓存；`render` 纯。

`Theme.flat()`：`surfaces.base/raised/hover/active/selected/control/accent/
danger` 全部 `NONE`；`controls.hover=underline`、`focus=bold+underline`、
`active=reverse+underline`、`disabled=dim`；rows/overlays 同现有规则。

## 7. 键位与激活

`Widget.keymap` 是 `Keymap` 描述符：

```python
class Keymap:
    def __get__(self, instance, owner=None) -> dict[str, str]:
        # class -> class table; instance -> that instance's copy
    def __set__(self, instance, value: Mapping[str, str]) -> None:
        # replace one instance's copy
```

`Widget.__slots__` 增加 `_keymap`，`Widget.__init__` 写入
`dict(type(self).keymap)`；子类删除自己的 `_keymap` slot 和
`self._keymap = dict(type(self).keymap)` 行。

统一默认表：

```python
CURSOR_KEYMAP = {
    "up": "prev", "left": "prev",
    "down": "next", "right": "next",
    "home": "first", "end": "last",
    "page_up": "page_prev", "page_down": "page_next",
}
```

- 组件只在自己文件里写 `keymap = Keymap({**CURSOR_KEYMAP, ...})`。
- `TREE_KEYMAP` 删除 `left`/`right` 的 prev/next，改为 `left: close`、
  `right: open`。
- 可勾选行（MultiSelect/CheckboxGroup/List/Table）显式 `space: toggle`。
- 焦点层 `FocusManager.handle` 在 `on_key` 之后、对 `activatable` 目标接受
  `enter` 和 `space` 两个激活回退；文本字段自己消费 space/enter，不受影响。
- 删除 Tabs/NavList 里“绑 enter:activate 但 on_action 拒绝 activate”的死
  键位；统一实现 `activate()`。
- TextField 仍由 `TextBuffer` 持有编辑键表，是明确例外；`Input`/`Editor`
  的 `keymap` 构造参数保留。

## 8. 组合与绘制

### 8.1 overlay

`Line.overlay(base: Line) -> Line`、`Surface.overlay(base: Surface) -> Surface`。

- 透明 cell：`char == " "` 且 `style == Style()` 且 `link is None` 且
  `action is None`。透明 cell 保留底层 cell。
- 非透明 cell 覆盖底层；样式 `base_style.merge(top_style)`（top 在栈顶）。
- `Line` 结果宽度 `max(base.width, top.width)`；`Surface` 结果
  `width = max`、`height = max`；短行按空白补齐到结果宽度再覆盖。
- 底行不足时，顶层 cell 从空白开始；顶层透明 cell 留在空白。
- 宽字符：一个双宽 glyph 占 lead + continuation 两列；顶层覆盖 lead 时整
  个底层 glyph 被替换，顶层透明时保留整个底层 glyph；实现不得产生半个宽
  字符。
- 空顶层（`Line()` 或全透明行）必须返回 base 行本身（identity 或等值）。

### 8.2 Stack / Align

```python
class Stack(Container):
    children: list[Component]        # bottom -> top
    def render(self, c) -> Surface   # 逐层 render 后 overlay；遵守 max_height
    def child_at(self, row, col) -> tuple[Component, int, int] | None
```

命中：从顶层到底层，返回第一个“该点上有可交互节点”的层；若都没有，返回
最顶层包含该点的层（保留文本选择/命中几何）。可交互 = `clickable`/
`focusable`/`hoverable` 为 True，或容器在该点有可交互后代。非交互背景
Canvas 因此不是点击目标。

```python
class Align(Widget):
    def render(self, c) -> Surface
```

`horizontal ∈ {"left","center","right"}`，`vertical ∈ {"top","middle","bottom"}`；
非法值 `ValueError`。子组件按完整 constraints render，取实际 `Surface`
尺寸，在空白 frame 里按锚点嵌入；超出 constraints 的部分裁剪。没有
measure/render 两阶段；会撑满宽度的子组件看不到对齐效果，这是子组件的
选择。

### 8.3 Drawing

```python
class Drawing(Widget):
    width: int; height: int        # setter 调 resize
    def resize(self, width: int, height: int) -> None
    def surface(self) -> Surface   # 全尺寸缓存
    def fit(self, c: Constraints) -> None
    def render(self, c: Constraints) -> Surface   # 只裁剪，不改尺寸
```

- `render` 不调用 `resize`；`PixelCanvas` 删除 render 时 resize。
- `fit(c)` 把尺寸设为 `(c.width, c.max_height or height)`；宿主在 paint 前
  调 `resize` 或 `fit`。
- `Canvas(*, width=..., plot_marker=...)`：`marker` → `plot_marker`，只影响
  `plot`；`styles` 删除。
- `PixelCanvas(*, ..., palette=None)`：`palette=None` 时
  `PixelPalette.from_theme(theme)`；显式 palette 优先；`styles` 删除。
- `PixelPalette.from_theme(theme)`：用 theme 的 accent/inline_code/success/
  warning/danger/text.muted/text.faint/content.heading 生成 8 个 slot，
  cool 为 main 的 38% 亮度；无 `Color` 的 token 用固定 fallback。

## 9. 迁移矩阵

| 旧 API | 新 API |
|---|---|
| `Tabs(tabs)` / `RadioGroup(labels)` / `CheckboxGroup(labels)` | `Tabs(items)` / `RadioGroup(options)` / `CheckboxGroup(options)` |
| `Tree(root_nodes)` / `TreeNode.expanded` | `Tree(nodes)` / `TreeNode.open` |
| `ComboBox.is_open` + `open()`/`close()` | `ComboBox.open` 状态 + `toggle()` |
| `Table(headers, rows)` | `Table(rows, headers=...)` |
| `Table.take() -> int` | `Table.take() -> row`；`Table.index` 仍是 int |
| `Tree.selected`（光标节点） | `Tree.index`（可见行）+ `Tree.selected`（节点） |
| `Tabs`/`NavList` 无 activate/take | 增加 `activate()` / `take()`；`activatable=True` |
| `Slider.take()` | 删除；`value` 是唯一状态 |
| `ProgressBar(fraction)` | `ProgressBar(value, maximum=1.0)`；`fraction` 只读派生 |
| `Dialog(title, body, buttons)` | `Dialog(body, title=..., buttons=...)` |
| `Collapsible(title, body)` | `Collapsible(body, title=...)` |
| `Canvas(width, height)` / `PixelCanvas(width, height, palette=...)` | 全部 keyword-only；`PixelCanvas(palette=None)` |
| `Canvas.marker` | `Canvas.plot_marker` |
| `ButtonSpec.danger=True` | `ButtonSpec(kind=ButtonKind.DANGER)` |
| `ControlStyles.base/active/band()` | 删除；`ControlStyles.overlay()` + `surfaces` |
| 各 widget 的 `_band` 手写合并 | 统一 `action_band(...)`（action 族）/ `ControlStyles.overlay`（其他） |
| `RadioGroup.selected -> str` / `.labels` | `selected -> Option`；`labels` 删除 |
| `List.on_action("prev")` 在端点返回 True | 返回 `move(-1)` 的真实结果 |

## 10. 测试矩阵

`tests/widgets/test_contracts.py`（W4a 独占）覆盖基类层：

- 构造：主内容位置参数、keyword-only、尾部顺序（用 `inspect.signature`）。
- 能力/hook：`focusable/clickable/hoverable/activatable` 为 True 时对应方法
  存在且可调用。
- 状态：`index/selected/marked/value/checked/open/text` 的语义。
- 动词：`activate/toggle/select/move/take`；移动清 pending、激活写 pending。
- 键位：cursor 组件默认表覆盖统一动作名；实例 rebind 不污染类表。
- 结果：`take()` 读一次清空；合法 None 的 sentinel 行为。

`test_contract_choice_nav.py`（W4b）与 `test_contract_text_form.py`（W4c）
按 family 覆盖同样的条目，避免并行写同一文件。

行为测试保留：编辑、表格网格、树展开、滚动几何、Markdown、Diff、mask、
wrap、宽字符、overlay/Stack/Align/Drawing。删除重复：能力断言、keymap
rebind、height-budget、纯改名断言。
