# Spec base-components · W1 交互内核（波次 W1）
> ✅ 已合并 2026-10-16 @ `bc1-kernel`（tip `f7833e0`）→ main `78fef97`；966 passed。
> 分支 `bc1-kernel`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md`（交互宪法、D3/D4/D6）。
> **最高约束：本波只加「无策略的协议与纯函数」——不碰 pointer/focus/gesture，不改任何组件的可见渲染。**
> 目标是把「hover 状态怎么声明」「坐标怎么下钻」两件事在 kernel 层立住，后面两波才好接线。

## 目标

1. `core/block.py` 长出 `Hoverable` 协议与 `Container` 下钻协议 + 纯函数 `descend`。
2. `Theme` 长出 `hover` 样式字段（本波只声明，不消费——消费在 W2）。
3. `Row` / `Column` / `Padding` / `Panel` 实现 `child_at`（缓存上一次 render 的几何），
   **不改它们的渲染输出一个字节**。
4. 单测：容器几何下钻、`descend` 递归、`Hoverable` 运行时协议。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 现有交互协议（`Clickable` / `Activable` / `Focusable`） | `src/mocode_tui/core/block.py` |
| `Themed` 基类与 `_pick`；`Theme` 字段与派生表 | `src/mocode_tui/core/theme.py` |
| `Row` / `Column` / `Spacer` / `Padding` | `src/mocode_tui/widgets/layout.py` |
| `Panel` | `src/mocode_tui/widgets/decor.py` |
| 「读上一次 render 的几何」先例 | `widgets/textbuf.py` 的 `visual_rows` / `move_up`（`render` 种几何） |
| kernel facade 导出 | `src/mocode_tui/core/__init__.py` |

## 工单（按序执行，每项一个 commit）

### T1 `core/block.py`：`Hoverable` + `Container` + `descend`

- 新增运行时协议：

  ```python
  @runtime_checkable
  class Hoverable(Protocol):
      """A component that can be highlighted while the pointer is over it.

      ``hover`` is the one read-write flag the pointer tier flips, the exact
      peer of ``Focusable.focused``.  A component decides what being hovered
      *looks like* and never learns that a pointer manager exists.  A
      component with finer granularity may also implement ``hover_at(row,
      col) -> bool`` (an optional method, not part of this protocol): it
      records which of its own cells the pointer is on and answers whether
      what it renders changed.  ``row < 0`` means the pointer left.
      """
      hover: bool

  @runtime_checkable
  class Container(Protocol):
      """A component made of children, translating its own cells to a child's.

      ``child_at(row, col)`` takes a 0-based cell of this component's own
      ``render`` output (exactly ``Hit.row`` / ``Hit.col``) and answers
      ``(component, row, col)`` for the child that owns it, or ``None`` for a
      cell the container itself owns (its border, padding or gap).  The
      geometry comes from this component's **last render** -- the same
      precedent ``TextBuffer.move_up`` follows -- so a container that has not
      rendered yet answers ``None``.  A container never proxies ``handle`` /
      ``move`` / ``activate`` / ``focused``; it only routes coordinates.
      """
      def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
          ...
  ```

- 新增纯函数：

  ```python
  def descend(component, row: int, col: int) -> tuple[Component, int, int]:
      """The deepest component owning a cell, with that component's own coords.

      Walks ``Container.child_at`` until a component is not a container or
      declines the cell; then returns it unchanged.  Pure, allocation-light
      and depth-guarded (a malformed container that returns itself cannot
      loop forever).  The kernel's one coordinate-descend primitive, shared by
      the pointer tier and the focus ring's click policy.
      """
  ```

- 深度上限用一个模块常量（如 `_DESCEND_LIMIT = 64`），超过即停下并返回当前层（防御，不抛）。
- 把三个名字加进 `core/block.py` 的 `__all__`；`Component` 已在前，`descend` 的返回类型用字符串注解避免环。
- 验证：`tests/test_container_hit.py` 直接构造组件并断言：
  - `descend(Text("x"), 0, 0)` 返回原组件原坐标；
  - 一个自造的「返回自己」容器在 `descend` 下不挂（深度上限生效）。

### T2 `core/theme.py`：`Theme.hover`

- 在语义色区末尾加字段：`hover: Style = Style(reverse=True)`。
- docstring 写明：hover 是**指针悬停**的语义样式（与 `selection` 的文档选区是两套机制，视觉可能相同）；
  组件可显式传 `hover_style=` 覆盖。派生表不动。
- 验证：`tests/test_theme.py` 加一条断言 `DEFAULT_THEME.hover == Style(reverse=True)` 且字段参与字段级相等。

### T3 `widgets/layout.py`：容器几何缓存 + `child_at`

**共同规则：每个容器在 `render(width)` 里把本次布局的几何存到实例私有字段；`child_at` 只读缓存。
不改渲染输出。** 用 `__slots__`，几何字段加进 slots。

- **`Row`**：render 时子列布局已知（`col_widths` 与 `gap`）。缓存 `_cells: list[tuple[int,int]]`
  （每个子组件的 `(x_start, width)`）与 `_cell_rows: list[int]`（每个子组件的渲染行数）。
  `child_at(row, col)`：
  - `row` 落在 `0..max(rows)-1`；逐个 cell 判断 `col` 落在 `[x_start, x_start+width)`；
  - 命中则返回 `(child, row, col - x_start)`；`row` 越过该子组件的行数时返回该子组件 `(row, col)` 亦可，
    但更精确：若 `row >= cell_rows[i]` 返回 `None`（空白填充格容器自持）；
  - gap 列（子之间）与越界 → `None`。
- **`Column`**：render 时每个子组件的 `(y_start, rows)` 已知（含 `gap` 行）。缓存 `_offsets`。
  `child_at(row, col)`：找 `row` 落在哪个子区间 → `(child, row - y_start, col)`；gap 行/越界 → `None`。
- **`Padding`**：render 时 `inner = width - left - right`、`top` 行、`left` 列已知。
  `child_at(row, col)`：`row < top` 或 `row >= top + child_rows` → `None`；
  `col < left` 或 `col >= left + inner` → `None`；否则 `(child, row - top, col - left)`。
  （右侧 fill 列也在 inner 之外，返回 `None`。）
- **`Spacer`**：不实现 `child_at`（没有子组件；`isinstance(Spacer, Container)` 为 False）。
- `Spacer` / `Row` / `Column` 的 docstring 补一句「本容器实现 `Container.child_at`」。
- 验证（`tests/test_container_hit.py`）：
  - `Column([Text("a"), Text("b")], gap=0)` render(10) 后 `child_at(1,0)` 命中第二个 `Text` 且 `row==0`；
  - `Row([Text("aa"), Text("bb")], widths=[2, None], gap=1)` render(10) 后 `child_at(0,0)` 命中第一个、
    `child_at(0,3)` 命中第二个，`child_at(0,2)`（gap 列）返回 `None`；
  - `Padding(Text("x"), left=2, top=1)` render(10) 后 `child_at(1,2)` 命中 `Text` 且坐标 `(0,0)`，
    `child_at(0,0)`（inset 内）返回 `None`；
  - **未 render 就 `child_at` 返回 `None`**。

### T4 `widgets/decor.py`：`Panel.child_at`

- `Panel` 在 render 时缓存 `width`、`inner = width - 4`、子行数；`child_at(row, col)`：
  - 顶/底边框行 → `None`；
  - 内容行 `row` 对应子行 `row - 1`；`col` 必须落在 `[2, 2 + inner)`（边框 2 列 + 左内边 1 列 + 右 1 列）；
  - `width < 4`（降级为裸 child）时按「整块偏移 0」返回 `(child, row, col)`；
  - 否则返回 `(child, row - 1, col - 2)`。
- 验证：`Panel(Text("x"), title="t")` render(10) 后 `child_at(1,2)` 命中 child；`child_at(0,0)`（顶框）`None`。

### T5 `core/__init__.py`：导出

- 从 `.block` 导出 `Hoverable`、`Container`、`descend`；加进 `__all__`（常量/类/函数分组顺序不变）。
- kernel 包 docstring 的「document model」段补一句这三个名字。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **只增不减**：贴 `baseline_before` 与 `after`（新增 `test_container_hit.py` 的数量）。
2. 行为零变化证据：`uv run python tools/framebench.py` → render-hash **与基线逐字符一致**
   （本波不消费 `Theme.hover`、不改渲染）。
3. `uv run python -c "import mocode_tui; from mocode_tui.core import Hoverable, Container, descend; print('ok')"` → `ok`。
4. 探针（贴输出）：贴 T1/T3/T4 断言里的关键几何例子各一条（尤其 `Row` 的 gap 列 → `None`、
   `Padding` 未 render → `None`）。
5. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0，dump 与改前**逐字节一致**
   （本波不该动 demo 输出）。

## 禁触清单

- `src/mocode_tui/pointer.py`、`focus.py`、`gesture.py`、`chrome.py`（W2 的活）
- 任何组件的 `render` 输出、`click` / `activate` / `handle` 行为
- `chat/`（W3 的活）
- `examples/`（W5 的活；本波只跑验收，不改）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单（hash + message）/ 自测真实结论（逐条命令 + 关键输出行 + pytest 数）/
几何探针输出（T3/T4 逐条）/ 行为零变化证据（framebench hash、demo dump diff 为空）/
偏差与取舍 / 未决问题 / 真机手测：无（本波纯 kernel，无真机项）。

遇到阻塞（`child_at` 几何需要改渲染、协议触发 `isinstance` 误判、framebench hash 变化）：
**停下上报，不越界自救**。
