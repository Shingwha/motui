# 06 · 组件族：合并、统一、迁移

> 上级：`01-architecture.md`　相关：`02` `03` `10-waves/W2` `W2.5` `W3`
> 状态：ready

## 1. 目标

在不改变行为的前提下：

1. 合并重复家族（两套游标、两套查询面板、三套编辑、两套主题解析）；
2. 统一族内参数（`height` + `window`，不再是 `window: int` vs `window: bool`）；
3. 把换行/截断交给 `WrapMode`；
4. 让每个组件的“状态 / 事件 / 扩展点”一眼可见。

## 2. 1.x 组件体检

| 文件 | 行数 | 问题 |
|---|---|---|
| `widgets/table.py` | 1,268 | 13 个构造参数；自有 wrap 预算；`wrap=False` 只能被裁 |
| `widgets/choice.py` | 1,028 | 12 个参数；`window` 是 bool（与 List 冲突） |
| `widgets/textbuf.py` | 994 | 与 `textfield.py` 一套编辑拆两文件 |
| `widgets/markdown/component.py` | 977 | 与 `blocks/inline` 三向循环 |
| `widgets/textfield.py` | 778 | Input/Editor 两套构造 |
| `widgets/diff.py` | 631 | 长行 `…` 截断 |
| `widgets/list.py` | 563 | `window: int`，自有游标 |
| `widgets/tree.py` | 531 | 自有游标 |
| `widgets/strip.py` | 227 | `ClampedCursor` 与 `core/cursor.py` 重复 |

## 3. 游标：一套 `Cursor`

**现状**

- `core/cursor.py` 179 行，7 个组件 import；
- `widgets/strip.py` 又实现了一个 `ClampedCursor`；
- 每个视图仍各自写 13–31 行 `move/select/home/end`。

**目标**

```python
class Cursor:
    count: int
    index: int
    disabled: frozenset[int]
    wrap: bool
    def select(self, index: int) -> bool: ...
    def move(self, delta: int) -> bool: ...
    def home(self) -> bool: ...
    def end(self) -> bool: ...
    def window(self, size: int, *, anchor: str = "center") -> tuple[int, int]: ...
```

- 只保留一个实现；删除 `ClampedCursor`；
- 所有数据视图持有 `self.cursor`，渲染读 `cursor.index`/`cursor.window()`；
- `List`/`Select` 的 `move/select` 变成 `on_action` 调用 `cursor`。

**测试**：空集、全 disabled、wrap/clamp、window 三 anchor、stale index。

## 4. 列表家族：`height` + `window`

| 1.x | 2.0 |
|---|---|
| `List(window: int)` | `List(height=8, window="center")` |
| `Select(max_rows=8, window: bool)` | `Select(height=8, window="top")` |
| `Tree`/`Table` 的窗口参数 | 统一 `height` + `window` |
| `commit: bool` | `commit_on_move: bool` |
| `prefix_jump: bool` | `type_to_jump: bool` |

`window` 的取值复用 `Cursor.window` 的 anchor：`"top" | "center" | "bottom"`。

**为什么**：同族里 `window` 有两个意思（渲染行数 vs 窗口策略），用户必须读源码才能区分。

## 5. 编辑：`TextField` 家族

- `widgets/input.py` 合并 `textbuf.py` + `textfield.py`；
- `TextBuffer` 仍是编辑引擎；`Input`/`Editor` 是薄预设；
- 公共参数：`text` / `placeholder` / `mask` / `read_only` / `keymap` / `wrap` / `theme` / `styles`；
- `Input` 默认 `WrapMode.OVERFLOW`（单行 + 水平跟随）；`Editor` 默认 `WORD`；
- 游标几何仍走 `text.spans`（editing 模式）。

**测试**：光标在 wrapped row 的上下移动、水平跟随、mask、只读。

## 6. 查询面板：`app/picker.py`

**现状**

- `Find` 与 `CommandPalette` 都自己组装“查询 Input + 过滤 List + Modal”；
- 两个文件合计 716 行，行为相似但不共享。

**目标**

```python
class QueryPanel(Widget):
    def __init__(self, *, placeholder="", items=(), filter=..., on_pick=...): ...
    # 查询行 + 过滤列表 + 键盘（up/down/enter/esc）
```

- `Find` / `CommandPalette` 变成薄 preset（标题、过滤器、结果处理）；
- `CommandPalette` 吃 `CommandRegistry`（见 `05`）；
- 共用一个 `Modal` 包装。

**测试**：查询过滤、上下、enter、esc、空结果、组标题。

## 7. 表格 / Diff / Markdown：接 `WrapMode`

| 组件 | 2.0 默认 | 说明 |
|---|---|---|
| `Table` | `cell_wrap=WORD`，可选 `CLIP`/`OVERFLOW` | 数据网格建议 `OVERFLOW` + ScrollPanel |
| `Diff` | `wrap=ELLIPSIS`，可选 `OVERFLOW` | 保持 `+/-` 对齐 |
| Markdown 代码块 | `code_wrap=WORD`，可选 `OVERFLOW` | 不再 `…` 丢内容 |
| 正文 | `WORD` | 不变 |

- `Table` 的 `wrap: bool` 删除，改 `cell_wrap: WrapMode`；列宽参数保留；
- `Diff` 的 `fit` 改成 `reflow`；长行默认截断，L1 可选 OVERFLOW；
- Markdown 代码块用 `reflow(WORD)` 而不是 `fit`。

## 8. 滚动条：`Scrollbar(axis=)`

```python
Scrollbar(host, pane=..., axis=Axis.Y, size=1, min_thumb=1, styles=..., glyphs=...)
```

- 删除 `style` / `thumb_style` / `track` / `thumb` 四个散参数；
- `styles=ScrollbarStyles(...)`（与其他 widget 一致）；
- `axis=Axis.X` 用于 L1 横向条；
- 与 `Scroll` 共用 `thumb()` 公式，不写第二套。

## 9. Canvas / Sparkline

```python
class Canvas(Widget):
    def put/text/hline/vline/box/blit/plot(...): ...
    def surface(self) -> Surface: ...
    def render(self, c: Constraints) -> Surface: ...
```

- `Marker`: `"cell"` / `"half"`（`▀▄█`）/ `"braille"`（2×4）；
- `Canvas` 可变化，`Surface` 不可变；Canvas 只产 Surface，禁止写 escape；
- `Sparkline` 是 Canvas 的薄封装；
- 内部维护 dirty rows，`Surface` 只重建变化的行。

## 10. 装饰 / 指示器 / 表单 / 对话

- `Panel`/`Divider`/`Collapsible`/`Notice`/`StatusLine`：统一 `theme/styles/glyphs`；
- `Panel` 边框与 frame 分隔条共用 `Border.paint(surface, rect)`；
- `ProgressBar`/`Slider`/`Spinner`：保持现状，只统一构造约定；
- `Form`：`focus_scope=True`，字段路由内部化；`on_submit` 保留（它是显式回调，不是结果门）；
- `Dialog`/`confirm_dialog`/`prompt_dialog`：保持；`Modal` 内部用 Router trap；
- 所有 `take_result` 改 `take`。

## 11. 重构顺序（与波次对齐）

1. W3：`Widget`/`Cursor`/`MarkSet` 基座 → 数据视图迁移（List/Tree/Table/Select/Nav/Tabs/Menu）。
2. W2.5：`WrapMode` → Table/Diff/Markdown/Editor。
3. W2.6：`ScrollPanel(axis="x")` → 宽表/宽代码。
4. W4：`Find`/`CommandPalette` → `Picker`；`Scrollbar` 收参；`Input`/`Editor` 合并。
5. W5：文档/示例。

## 12. 验收

- `Cursor` 只有一套实现；7 个视图都用它；
- `List`/`Select` 的 `window` 不再同名两义；
- `Table`/`Diff`/代码块长行不再 `…` 丢内容（默认或可选）；
- `Find`/`CommandPalette` 共用 `QueryPanel`；
- `Input`/`Editor` 共用一个模块；
- `Scrollbar` 只有 `styles/glyphs/axis`；
- 组件构造签名 ≤12 个参数（`Table`/`Dialog`/`Markdown` 例外需注释）。

## 13. 不做的

- ❌ `Table` 的 `Column` 规格（保持 kwargs；见 `05` 第 11 节）。
- ❌ 列表项换行（一项 = N 行；2.0 不做）。
- ❌ 通用 `Picker` 抽象泛型（`QueryPanel` 是具体实现）。
- ❌ 为每个组件加 `on_result`（ADR-023）。
