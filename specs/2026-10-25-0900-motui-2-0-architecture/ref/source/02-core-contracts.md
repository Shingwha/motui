# 02 · 核心契约（kernel）

> 上级：`01-architecture.md`　相关：`10-waves/W0` `W1` `W2` `W2.5` `W2.6`
> 状态：ready

本 spec 定义 kernel 的**唯一数据模型**。所有改动以这里的契约为准；组件、控制器、终端都只是它的消费者。

## 1. 几何：`Size` / `Rect` / `Pos` / `Axis`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Size:
    width: int = 0
    height: int = 0

@dataclass(frozen=True, slots=True, kw_only=True)
class Pos:
    x: int = 0
    y: int = 0

@dataclass(frozen=True, slots=True, kw_only=True)
class Rect:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    # right / bottom / area / contains / intersect / split ...

class Axis(Enum):
    X = "x"   # 切宽度（左右）
    Y = "y"   # 切高度（上下）
```

**为什么**

- 当前 `Rect` 藏在 `core/frame.py`（1,677 行），`split("vertical")` 的字符串语义反直觉；几何值必须在 `kernel/geom.py` 且被 `frame`/`layout` 共用。
- `Axis.X` 明确“切宽度”，消灭 `"vertical" = 左右切` 的歧义（ADR-019）。

**重构方式**

- 从 `core/frame.py` 抽出 `Rect` 与 split 代数；
- 所有 `x/y/width/height` 参数改用 `Pos`/`Size`/`Rect` 或 `Axis`；
- 测试：Rect 代数随机化（intersect/contains/split 的不变量）。

## 2. 渲染：`Constraints` → `Surface`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Constraints:
    width: int = 0
    max_height: int | None = None    # None = 自然高度

@dataclass(frozen=True, slots=True, kw_only=True)
class Surface:
    width: int = 0                   # 内容宽度
    rows: tuple[Line, ...] = ()

    @classmethod
    def blank(cls, size: Size) -> "Surface": ...
    @classmethod
    def of(cls, rows: Sequence[Line], width: int) -> "Surface": ...

class Component(Protocol):
    def render(self, c: Constraints) -> Surface: ...
```

**不变量（谁强制）**

1. 每行 `line.width <= surface.width` —— `Surface` 构造时保证（裁剪 + 补齐）。
2. `len(rows) <= c.max_height` —— 容器 / `Viewport` 放置时保证。
3. 行内不得含控制字符 —— `Cell`/`Segment` 内容门保证（见第 7 节）。
4. `Surface.width` 是**内容宽度**；`OVERFLOW` 时可以 > `Constraints.width`，可见宽度由容器裁剪。

**为什么**

- 当前 `render(width)` 只有宽度，组件无法“填满窗格”；`ScrollView(height=)` 由宿主硬塞。
- 当前单 pane 全宽透传不裁剪，20 列屏写 40 列会破坏整屏（实测）。
- 返回一个值而不是 `list[Line]`，未来媒体/度量可以在 `Surface` 内部增长，`Component` 协议不变（ADR-001/011）。

**取舍**

- 不做 measure/render 两阶段：单趟 + `Sizing.FILL` 覆盖目标场景（ADR-002）。
- 构造入口是类方法，用户只读；字段不是构造契约（`kw_only` + 默认值），2.x 可加字段（ADR-011）。

**重构方式**

- `render(width)` → `render(Constraints)`（38 处）；
- `Viewport.layout` / 容器 / 1.x `Block.rows` 改为传 `Constraints`；
- `Surface.of` 统一裁剪：超宽 `fit`、短行 `fill`；
- 测试：宽度 0/1/2/emoji/CJK、`max_height=None/0/1`、超宽裁剪。

## 3. 行与单元：`Cell` / `Line`

```python
@dataclass(frozen=True, slots=True)
class Cell:
    char: str = " "
    style: Style = Style()
    link: str | None = None
    action: str | None = None

class Line:
    # 对外仍是 tuple[Segment, ...]；Line 是同质 Cell 的 RLE
    text: str
    width: int
    def reflow(self, mode: WrapMode, width: int) -> list[Line]: ...
    def clip / pad / band / under / over / cut / slice / styled / action_at ...
```

**为什么**

- `Segment` 的 `link`/`action` 已是“行内 payload”的特例（`action` 还 `compare=False`）；`Cell` 把它们统一成原子。
- `Line` 保持 RLE，行 diff 仍是值比较；不需要逐 cell 对象。
- 内容安全门在 `Cell` 构造时执行：删除 C0/DEL/C1，tab→空格（沿用 1.x 的 `_cells_only`）。

**重构方式**

- `Segment` 保留为 `Line` 的内部 RLE 视图；`Cell` 是写入面（Canvas/行构造）；
- `Line` 的所有操作从 `core/lines.py` 的自由函数收成方法（ADR-016）：
  `fit→clip`、`fill→pad`、`filled→blank`、`merge_span→over`、`fuse→fused`、`overlay→under`、`rest→band`、`cut_line→cut`、`slice_line→slice`、`styled_with→styled`、`wrap_line→reflow`、`action_at→action_at`。
- 测试：内容门（控制字符/链接/动作）、RLE 合并、equal/hash、styled 缓存、宽度测量。

## 4. 换行：`WrapMode`

```python
class WrapMode(Enum):
    WORD = "word"          # 词级换行（1..N 行）
    CHAR = "char"          # 字符级（1..N）
    ELLIPSIS = "ellipsis"  # 单行 + "…"
    CLIP = "clip"          # 单行硬裁
    OVERFLOW = "overflow"  # 单行，允许超宽
```

**为什么**

- 1.x 的换行/截断散落在 59 处 `.fit()`，代码块/`Diff`/`Table(wrap=False)` 被 `…` 静默截断。
- 行业没有全局默认：正文换行，代码/数据行裁切，输入单行水平滚动（ADR-012）。

**默认值（2.0）**

| 组件 | 默认 | L1 可选 |
|---|---|---|
| Text / Markdown 正文 | `WORD` | — |
| Markdown 代码块 | `WORD`（不丢内容） | `OVERFLOW` |
| Diff | `ELLIPSIS`（对齐优先） | `OVERFLOW` |
| Table | `WORD`（保持现状） | `OVERFLOW` |
| 行式组件（List/Tree/Select/Nav/Tabs/Menu/Status） | `ELLIPSIS` | — |
| Input | `OVERFLOW`（单行水平跟随） | — |
| Editor | `WORD` | `OVERFLOW` |

**不变量**

1. `WORD`/`CHAR` 返回 1..N 行；其余恰好 1 行。
2. 单行模式保持逻辑行 ↔ 视觉行 1:1。
3. `OVERFLOW` 可超宽；`Surface.width` 变内容宽度，容器裁剪。
4. `WrapMode` 是组件配置，不进 `Constraints`；改变它必须 `touch()`。

**重构方式**

- `Line.reflow` 为唯一入口；内部复用 `text.wrap/spans/fit/ellipsize` 与 `cut_line`；
- 59 处 `.fit()` 迁移；`fit` 降为私有；
- 见 `10-waves/W2.5-wrapmode.md`。

## 5. 文档：`Section` / `Document` / `Fill`

```python
class Placement(Enum): FLOW = "flow"; TOP = "top"; BOTTOM = "bottom"
class Sizing(Enum):    NATURAL = "natural"; FILL = "fill"

@dataclass
class Section:
    id: str
    widget: Component
    placement: Placement = Placement.FLOW
    sizing: Sizing = Sizing.NATURAL

class Document:
    def add(...) -> Section: ...
    def remove(self, id: str) -> Section: ...
    def get(self, id: str) -> Section: ...

class PaneContent(Protocol):
    def layout(self, rect: Rect) -> Surface: ...
    def scroll(self) -> Scroll | None: ...

class Fill:
    widget: Component
```

**规则**

- `Document` 至多一个 `FILL` section，且在所有 `FLOW` 之后；
- `TOP`/`BOTTOM` 只能 `NATURAL`；
- `Fill` 独占一个 pane，不参与滚动索引。

**为什么**

- 保留 1.x 的差异化：地址化 block 支撑流式 Markdown、聊天、`reveal`、文档选择、`extract`。
- 给游戏/仪表盘一个一等入口 `Fill`，同时不把画布塞进滚动文档（会破坏行归属表/hit/extract）。
- `pin="top"` 字符串 → `Placement` 枚举；`add/get/remove` 返回 `Section`（ADR-019）。

**重构方式**

- `Block` → `Section`；`Block.rows` 缓存 → `Section` 的 `(width, height, generation)` 缓存；
- `Document` 的 `pin` 参数迁移到 `placement`；
- `TUI.add/get/remove` 统一走 `Workspace`，返回 `Section`。

## 6. 滚动：`Axis` + `Scroll`（2D）

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Axis:
    offset: int = 0
    content: int = 0
    viewport: int = 0
    sticky: bool = False

@dataclass(frozen=True, slots=True, kw_only=True)
class Scroll:
    x: Axis = Axis()
    y: Axis = field(default_factory=lambda: Axis(sticky=True))
```

- `clamp` / `max_offset` / `reveal` / `thumb` 只写一遍，两轴共用；
- `sticky` 只对 y；
- 2.0 的 `Pane`/`Document` 只跑 y；横向在 `ScrollPanel(axis="x")` 与 `Input` 内部；
- 不换行内容用 `OVERFLOW` + `ScrollPanel`，自动换行的文档流横向留 2.x（ADR-013）。

**为什么**

- `ScrollState` 的 `offset: int` 以后改 2D 会牵动 `Viewport`/`Pane`/`Scrollbar`/`Find`/`Selection` 的所有公式；
- 形状现在对，行为按需启用，成本几乎为零。

**迁移**

- `ScrollState` → `Scroll`；`Pane.viewport.scroll_state` → `view.scroll`；
- `ScrollView` → `ScrollPanel(axis=)`；
- `visible_range()` → `Viewport.visible() -> RowSpan`。

## 7. 帧：`Pane` / `Split` / `Dock` / `Overlay`

- `Pane` = `Rect` + `PaneContent` + chrome；
- `Frame` = split 树 + docks + overlay 管线 + focus；
- `splice_row` 降为 `Surface`/合成器私有；
- `Overlay.paint(frame) -> Surface`，8 层顺序：`background/content/selection/chrome/overlay/modal/tooltip/toast`。

**不变量**

- 合成后的每一行宽度 = frame 宽度；pane 的写入被裁剪到自己的矩形；
- overlay 不改变行数，只重写内容；
- 行归属表（`row_blocks`）与布局同源，供 selection/hit 使用。

## 8. 绘制：`Painter` / `Screen`

- `Painter.paint(surface)`：按行 diff；一次 write + 一次 flush；空帧 0 字节；
- `Screen` 是 **ABC**（不是 Protocol）：稳定成员 + 默认实现；
- 可选能力用“带默认值的属性”或注入协作者（`Painter(screen, graphics=...)`）；
- `Screen` 不拥有剪贴板；剪贴板是 `Clipboard` 能力。

**为什么**

- 1.x 的 `Screen` 是可被外部实现的窄 Protocol，加方法即破坏实现者；ABC 可加法（ADR-014）。
- `ansi.*` 与 `Screen.*` 是双门；收敛到 `Screen`（ADR-017）。

## 9. 选择 / 提取

```python
class Selection:
    @classmethod
    def between(cls, anchor: DocPosLike, head: DocPosLike) -> "Selection": ...
    def highlight(self, layout: Surface, *, style: Style = ...) -> Surface: ...
    def extract(self, document: Document, *, width: int) -> str: ...
```

- 当前 `highlight`/`extract` 是自由函数 → 变成值方法（ADR-016）；
- 可选 `DocPos(block,row,col)` 仍待讨论（`13-risks-migration.md` 的“未决项”）；
- 选择仍是文档空间按行；x 只影响屏幕高亮裁剪。

## 10. 内容安全

- `Cell`/`Segment` 构造是唯一内容门：删除 C0/DEL/C1，tab→空格；
- 内容永远不能携带 escape；`link`/`action` 也走同一门；
- 只有 `terminal/ansi.py` 构造字节；
- 画布（Canvas）同样走 `Cell`，不能例外。

## 11. 测试与门禁

| 契约 | 测试 |
|---|---|
| Rect/Size/Pos | 随机代数不变量 |
| Surface | 裁剪/补齐/高度上限/内容门 |
| Line | RLE/equal/hash/styled 缓存/emoji |
| WrapMode | 5 模式 × 宽度 1/2/3 × emoji/CJK |
| Document | FILL 约束/placement/返回 Section |
| Scroll | 两轴 clamp/reveal/thumb/内容宽度 |
| Frame | pane 裁剪/overlay 顺序/行归属 |
| Painter | 行 diff/空帧 0 字节/一次 write+flush |
| Selection | highlight/extract 与 1.x 行为一致 |

**门禁**：W0/W1 字节级不变；W2 起 golden 语义重录 + 差异分类。

## 12. 不做的

- ❌ 第二条渲染路径（Canvas 直写字节）。
- ❌ 逐 cell 线上 diff。
- ❌ `Surface` 预置媒体/图片字段（ADR-011）。
- ❌ measure/render 两阶段。
- ❌ 自动换行文档流的横向滚动（2.0）。
