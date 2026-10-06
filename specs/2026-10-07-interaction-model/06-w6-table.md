# Spec interaction-model · Table 行光标（波次 W6，**可裁剪**）
> 分支 `im6-table`；前置：**W3 已合并**（要 `Activable`/`chosen` 的家族契约）；深读：
> `00-overview.md`（决策 D10）、`ref/audit-interaction.md`。
> **裁决：本波可整波跳过。** 它不与 W1–W5 有任何依赖，lead 若判定本轮不必交付，直接不派工。
> 裁剪不影响总纲其余部分的完整性。

## 目标

`Table` 从纯展示件升级为**可选中的**数据表：行光标 + `move` / `click` / `activate`，
样式走主题的 `selection`。它同时是"选择族契约"对第二种数据形状（行 × 列）的检验：
`chosen` 装的不再是 `Option` 而是数据行。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| Table 目前零状态 | `widgets/table.py` 的 `__slots__` 只有样式与数据（`headers`/`rows`/`aligns`） |
| 渲染结构 | 顶框 `┌─┬─┐`、表头行、**每两行之间一条 `├─┼─┤`**、底框 `└─┴─┘`（`docs/COMPONENTS.md` 的 Table 行有描述） |
| 家族契约 | `Select.chosen`（W3）+ `Activable`（W3）+ `Clickable.click(row, col)`（W2） |
| 对照 | ratatui 用 `TableState`（A 家族）；Textual 的 DataTable 有 cursor 与 `RowSelected`（B 家族） |

## 工单（按序执行，每项一个 commit）

### T1 状态与渲染

- `Table.__slots__` 加 `_index` 与 `_selected_style`；构造参数 `selected_style: Style | None = None`
  （解析章程照旧：explicit > theme 的 `selection` > 默认），`focused: bool = True`
  （与 W4 的 `Focusable` 对齐；失焦时 `selected_style.merge(theme.dim)`）。
- `index: int | None`（**数据行**下标，不含表头；空表 `None`；赋值夹取到 `[0, len(rows)-1]`）、
  `selected -> Sequence[cell] | None`（光标行的原始数据）。
- 渲染：光标行的**每个数据单元格**样式 `.merge(selected_style)`（表头与网格线不动）；
  **行数与列宽一字不变**（`tests/test_widgets_table.py` 现有宽度/收缩用例必须全绿）。

### T2 交互

- `move(delta) -> bool`：**夹取**（不循环）。docstring 必须写明与菜单族相反的理由：
  菜单是"选项列表"（首尾相接），表格是"数据视图"（到边即止）；这是 D10 的拍板。
- `click(row, col) -> bool`：把**块内行号**映射成数据行下标——按渲染结构判定（顶框 / 表头 /
  行分隔线都不是数据行），**不许硬编码行号偏移**（列宽与收缩会改变分隔线的存在与否，
  以自己 `render()` 出来的行为准）；`col` 忽略（写明）。越界/非数据行 → False。
- `activate() -> bool`：`self.chosen = self.index`（新增 `chosen: int | None`，读一次清一次，
  与 `Select` 同款；`move`/`click` 清空它）；空表 → False。
- 因此 `Table` 满足 `Clickable`（W2 签名）、`Activable`、`Focusable`。

### T3 测试与文档

- `tests/test_widgets_table.py` 新增：渲染（光标行样式、**行数与列宽不变**、`focused=False` 时的样式）、
  `index` 夹取、`move` 到边即止、`click` 映射（点顶框 / 表头 / 分隔线 → False，点每个数据行 → 正确下标；
  含"表头换行/单元格换行导致行数变化"的用例）、`activate`/`chosen` 读一次清一次、空表。
- 文档：`docs/COMPONENTS.md` 的 Table 行 + 交互表（`click`/`move`/`activate` 的组件列加上 `Table`）；
  `README.md` 组件表 Table 行；`docs/DESIGN.md` 命名表的 `move(delta)` 行注明"表格夹取、菜单循环"。
- `examples/showcase/components.py` 的 data 页：把表格示例接上环（`FocusRing([table])`）或至少更新文案。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → 全绿（含新用例与**既有的宽度/收缩用例零改动**）。
2. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；`--pages` 的 data 页正常。
3. `uv run python tools/framebench.py` → render-hash 不变（`selected` 默认 `None`，渲染零变化）。
4. 真机：点第 3 行 → 整行反白；`↑↓` 移动光标；`enter` 后宿主能读到 `chosen`。

## 禁触清单

- `widgets/{choice,tree,tabs,textbuf,field,input,editor}.py`（家族已就位，本波只加消费者）。
- `core/`、`keys/`、`app.py`、`chat/`。
- `specs/`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 结构与宽度不变的证据（既有用例零改动 diff）/
偏差与取舍 / 未决问题。
