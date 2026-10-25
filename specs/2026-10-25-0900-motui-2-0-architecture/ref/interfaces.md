# 接口契约（interfaces）

> 本文件是波次之间唯一的稳定契约。每波合并后由 lead 回写“现实”，下一波只读这里。
> 权威推导见 `ref/source/02-core-contracts.md`、`03-interaction.md`、`04-runtime.md`、`05-api-surface.md`。
> 状态：W0a 已落地（2026-10-25）。标 ⏳ 的波次落地后改为 ✅ 并写实际签名。

## 1. kernel 值（W0a ✅）

**实际面**（`src/motui/kernel/__init__.py` 恰好 12 名）：`Axis` `Cell` `Constraints` `Line` `Pos` `Rect` `Scroll` `ScrollAxis` `Segment` `Size` `Surface` `WrapMode`。

已定决策：

- 几何方向枚举是 `geom.Axis`；滚动轴值叫 `layout.ScrollAxis`（**最终名**，不再改）。
- `Line.clip(width: int)` 本波是整数硬裁；W2.5 换成 `clip/reflow(mode, width)`。
- `Line.styled()` **不在 kernel**：kernel 不构造 terminal 字节；W1 把 SGR/OSC8 渲染放到 `terminal/` 与 `kernel/paint.py` 的边界（`Painter` 注入 renderer）。
- `kernel/cell.Style` 是 8 字段过渡占位；W1 用真实 `core.style.Style` 替换后删除占位。
- `Surface.blank(size)` 返回 `height` 行空 `Line()`（宽 0）；`Surface.of` 才保证每行恰 `width`。
- `Segment.action` 不参与 equality；`Cell.action` 过内容门。W1 合并时统一为 `Cell`/`Segment` 同一门。

```python
# kernel/geom.py
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
    @property
    def right(self) -> int: ...
    @property
    def bottom(self) -> int: ...
    @property
    def area(self) -> int: ...
    def contains(self, pos: Pos) -> bool: ...
    def intersect(self, other: Rect) -> Rect: ...
    def split(self, axis: Axis, weights: Sequence[int], min_size: int = 0) -> tuple[Rect, ...]: ...

class Axis(Enum):
    X = "x"   # 切宽度（左右）
    Y = "y"   # 切高度（上下）
```

```python
# kernel/cell.py
@dataclass(frozen=True, slots=True)
class Cell:
    char: str = " "
    style: Style = Style()
    link: str | None = None
    action: str | None = None

class Line:
    # 对外仍是 tuple[Segment, ...] 的 RLE 视图
    text: str
    width: int
    def clip(self, mode: WrapMode, width: int) -> Line: ...     # 单行
    def reflow(self, mode: WrapMode, width: int) -> list[Line]: ...
    def pad(self, width: int, style: Style = NONE) -> Line: ...
    def band(self, width: int, style: Style = NONE) -> Line: ...
    def under(self, style: Style) -> Line: ...
    def over(self, start: int, end: int, style: Style) -> Line: ...
    def cut(self, start: int, end: int) -> Line: ...
    def slice(self, start: int, end: int) -> Line: ...
    def styled(self) -> str: ...                                # 原 Line.styled 保留
    def action_at(self, col: int) -> tuple[str, int, int] | None: ...

@dataclass(frozen=True, slots=True, kw_only=True)
class Surface:
    width: int = 0
    rows: tuple[Line, ...] = ()
    @classmethod
    def blank(cls, size: Size) -> "Surface": ...
    @classmethod
    def of(cls, rows: Sequence[Line], width: int) -> "Surface": ...
    @property
    def height(self) -> int: ...
```

```python
# kernel/layout.py
@dataclass(frozen=True, slots=True, kw_only=True)
class Constraints:
    width: int = 0
    max_height: int | None = None     # None = 自然高度

@dataclass(frozen=True, slots=True, kw_only=True)
class ScrollAxis:   # 最终名（避免与方向枚举 geom.Axis 冲突）
    offset: int = 0
    content: int = 0
    viewport: int = 0
    sticky: bool = False
    def clamp(self) -> "ScrollAxis": ...
    @property
    def max_offset(self) -> int: ...
    def reveal(self, row: int) -> "ScrollAxis": ...
    def thumb(self, track: int, min_length: int = 1) -> tuple[int, int] | None: ...

@dataclass(frozen=True, slots=True, kw_only=True)
class Scroll:
    x: ScrollAxis = ScrollAxis()
    y: ScrollAxis = field(default_factory=lambda: ScrollAxis(sticky=True))
```

> 命名已定：`geom.Axis` 是方向枚举（X/Y），滚动轴状态是 `layout.ScrollAxis`，两者都在
> `motui.kernel` 根导出。W2.6 不再改名。

```python
# kernel/text.py
class WrapMode(Enum):
    WORD = "word"; CHAR = "char"; ELLIPSIS = "ellipsis"
    CLIP = "clip"; OVERFLOW = "overflow"
```

## 2. 组件协议（W2 ⏳）

```python
class Component(Protocol):
    def render(self, c: Constraints) -> Surface: ...

class PaneContent(Protocol):
    def layout(self, rect: Rect) -> Surface: ...
    def scroll(self) -> Scroll | None: ...
```

- `Surface.width` 是内容宽度；每行 `≤ width`；`OVERFLOW` 时 `Surface.width > Constraints.width` 合法。
- `len(rows) <= c.max_height` 由组件/容器保证。
- 行内容不含控制字符（`Segment`/`Cell` 门）。

## 3. 文档（W2/W4 ⏳）

```python
class Placement(Enum):
    FLOW = "flow"; TOP = "top"; BOTTOM = "bottom"

class Sizing(Enum):
    NATURAL = "natural"; FILL = "fill"

@dataclass
class Section:
    id: str
    widget: Component
    placement: Placement = Placement.FLOW
    sizing: Sizing = Sizing.NATURAL

class Document:
    def add(self, widget, *, id=None, placement=Placement.FLOW, sizing=Sizing.NATURAL) -> Section: ...
    def remove(self, id: str) -> Section: ...
    def get(self, id: str) -> Section: ...

class Fill:
    widget: Component
```

规则：`Document` 至多一个 `FILL`，且在所有 `FLOW` 之后；`TOP/BOTTOM` 只能 `NATURAL`；`Fill` 独占 pane、不参与滚动索引。

## 4. Widget（W3 ⏳）

```python
class Widget:
    parent: Widget | None
    children: list[Widget]
    def walk(self) -> Iterator[Widget]: ...       # 前序、含 self、对象去重

    focusable: bool = False
    clickable: bool = False
    hoverable: bool = False
    activatable: bool = False

    keymap: Mapping[str, str] = {}

    def on_key(self, e: KeyEvent) -> bool: ...
    def on_mouse(self, e: MouseEvent) -> bool: ...
    def on_paste(self, e: PasteEvent) -> bool: ...
    def on_resize(self, e: ResizeEvent) -> None: ...
    def on_focus(self, gained: bool) -> None: ...
    def on_click(self, pos: Pos) -> bool: ...
    def on_hover(self, pos: Pos | None) -> bool: ...
    def on_drag(self, pos: Pos, phase: DragPhase) -> bool: ...
    def on_action(self, name: str) -> bool: ...

    def touch(self) -> None: ...
```

- 返回 `True` = 消费；改变由 `touch()` 表达。
- 实例 keymap 合并：`{**Type.keymap, **instance.keymap}`。
- `focus_scope = True` 的容器内部路由（`Form`）。
- `focusable=True` 节点按前序组成焦点环。
- `take()` / `HasResult`：

```python
class HasResult(Protocol):
    def take(self) -> object | None: ...
```

## 5. 运行时（W4 ⏳）

```python
class MouseMode(Enum):
    OFF = "off"; BUTTON = "button"; DRAG = "drag"; MOVE = "move"

@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalOptions:
    stream: TextIO | None = None
    input: EventSource | None = None
    mouse: MouseMode = MouseMode.MOVE
    paste: bool = True
    focus_events: bool = False
    color_mode: ColorMode | Literal["auto"] = "auto"
    sync: bool = True

class App:
    def __init__(self, *, theme=None, terminal=TerminalOptions(), throttle=..., auto=..., title=..., on_selection=..., handlers=DEFAULT_HANDLERS): ...
    runtime: Runtime
    workspace: Workspace
    terminal: Terminal

class Runtime:
    def every(self, period: float, fn, *, catch_up: str = "skip") -> Timer: ...
    def animation(self, hz: float, draw) -> Timer: ...
    def invalidate(self) -> None: ...
    def paint_now(self) -> None: ...
    def advance(self, dt: float) -> None: ...
    def clock(self) -> float: ...

class Workspace:
    def add(self, component, *, id=None, placement=Placement.FLOW, sizing=Sizing.NATURAL, pane=None) -> Section: ...
    def get(self, id: str) -> Section: ...
    def remove(self, id: str) -> Section: ...
    def split(self, axis: Axis, weights=(1, 1), *, pane=None) -> tuple[Pane, ...]: ...
    def dock(self, component, *, placement=Placement.BOTTOM, size=None) -> Pane: ...
    def undock(self, placement: Placement) -> Pane | None: ...
    def focus(self, widget) -> bool: ...
    def focus_next(self) -> bool: ...
    def focus_previous(self) -> bool: ...

Handler = Callable[[Event], bool]
DEFAULT_HANDLERS: tuple[Handler, ...]
```

## 6. 命令（W4 ⏳）

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Command:
    name: str
    description: str = ""
    group: str = ""
    keys: tuple[str, ...] = ()
    handler: Callable[..., object] | None = None
    enabled: bool = True

class CommandRegistry:
    def bind(self, app: App) -> None: ...
```

## 7. 删除名单（全 2.0 生效）

`take_result`、`Resultful`、`TUI`、`App.tui`、`Revisioned`、`Themed`、`set_focus_targets`、
`EveryHandle`、`RowRange`、`ClampedCursor`、`mark_prefix`、`fit/fill/fuse/overlay/rest`
自由函数、`ansi.*` 公开导出、`core/` 包、`Block`、`pin` 字符串、`ScrollView`、
`ScrollState`、`split("vertical")`、`dock(edge=...)`、`Table(wrap=bool)`。

## 8. 待 lead 决策（波内遇到再定，写进 handoff）

| 项 | 默认决定 |
|---|---|
| 滚动轴值命名 | `layout.ScrollAxis`（避免与方向枚举 `geom.Axis` 冲突）；公开面以 `Scroll` 为主 |
| `Line.styled` 与新 `styled(mode)` | 保留 `Line.styled()` 作为 SGR 渲染；`mode` 通过 `Painter`/`sgr_prefix` 传，避免签名破坏 |
| `text.*` 命名 | 先保留 1.x 名字并加 `text.width/wrap/spans/...` 别名；W2.5 删除旧名 |
| `Fill` 在 pane 的入口 | `Workspace.fill(component, pane=None)` + `App.fill` 代理 |
| 旧字节 golden | W2a 同时保留 `.txt` 与新增语义快照，W5 删 `.txt` |
