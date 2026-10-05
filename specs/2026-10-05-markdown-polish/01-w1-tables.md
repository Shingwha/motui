# Spec markdown-polish · 表格与测量正确性（波次 W1）

> ✅ 已合并 main(2026-10-05) @ 分支 md-w1-tables

> 分支 `md-w1-tables`（从最新 main 创建）；前置：无；深读：`specs/2026-10-05-markdown-polish/00-overview.md`
>（决策 3/4/5/6/7 与不变量）、`src/mocode_tui/widgets/table.py`、`src/mocode_tui/core/text.py`、`src/mocode_tui/core/lines.py`。

## 目标

修掉表格与文本测量的三类实锤缺陷：双路径测量导致的边框参差、单元格不渲染内联 markup、`\|` 转义竖线切错列；
并给表格补数据行之间的内部横线（完整网格，对齐 pi）。**最高约束：公共 API 向后兼容
（`Table` 的 str/tuple 单元格行为不变、`render(width) -> list[Line]` 协议与流式安全不动）。**

## 工单（按序执行，每项一个 commit，每个 commit 独立过门禁）

### T1 测量统一：`core/text.py` + `core/lines.py`

- 新增 `fit_text(text: str, budget: int) -> str`：返回 `visible_width` ≤ budget 的最长前缀。
  **后置条件 `visible_width(result) <= budget` 对任意输入成立**（含 VS16 `️`、ZWJ 家庭 emoji
  `👨‍👩‍👧‍👦`、组合符号、CJK、tab）。实现建议：前缀宽度随 k 单调不减，可二分；或收缩循环。
  加入 `__all__`，英文 docstring。
- `ellipsize_tail` 重写在其上：不适配时 `fit_text(text, width - 1) + ELLIPSIS`；
  保持 `width <= 0 -> ""`、`width == 1 -> "…"`（文本本就适配时原样返回）语义。
- `Line.fit`（`core/lines.py:94-132`）内层逐字符walk改用 `fit_text(seg.text, budget - used)`，
  消除同一测量病根。流式安全回归必须仍然成立。
- 测试（新建 `tests/test_text_fit.py` 或并入现有测量测试文件）：对上述 nasty 输入 × 预算
  0..len+2 断言三件事：`visible_width(fit_text(s,w)) <= w`；`visible_width(ellipsize_tail(s,w)) <= w`；
  `Line([...多段 nasty...]).fit(w)` 的行 `visible_width(row.text) <= w`。
  回归断言：`ellipsize_tail("⚠️ Blocked", 4)` 宽度 ≤ 4（现状是 5，先写成红的再修绿）。

### T2 `widgets/table.py`：多段单元格 + 网格横线 + 列对齐

- 单元格类型扩展：`str | tuple[str, Style] | Sequence[Segment]`。str/tuple 归一化为单段，
  行为与现状逐字节一致；`Sequence[Segment]` 按段保留样式。
- base 风格合并：表头行每格 base = `header_style`，数据行 col 0 base = `first_column_style`、
  其余列 base = `NONE`；对 Segment 单元格，属性型段（fg、bg 均为 None）`base.merge(seg)`，
  带色段保持绝对（与 `inline_segments` 同一规则）。
- 新参数 `aligns: Sequence[str] | None = None`（每列 `left/center/right`，缺省 left，越界列按 left）。
  对齐在 `_row` 内用 pad Segment 实现（pad 用该格 base 风格），截断用 `Line(segments).fit(budget)`，
  pad 数 = `budget - line.width`（负数按 0）。现状按列预 padding 的职责从 markdown 侧移入此处。
- 网格横线：输出序列变为 top、header、header-rule、row1、rule、row2、…、rowN、bottom——
  即**每两行之间一条** `├─┼─┤`（复用 `_HEADER_RULE` 字符）。空表体（无数据行）输出不变。
- 每行（含 rules）最终 `fit(width)` 保障保留；**帧一致性**成为硬约定：同一张表所有行等宽。
- docstring 同步（多段单元格、aligns、网格横线）。

### T3 `widgets/markdown.py`：TableRule 内联 + 转义竖线

- `TableRule` 改继承 `_InlineMixin`：`__init__(self, theme=None, inline_rules=None)`；
  **必须覆写** `with_theme(theme) -> TableRule(self._theme... )` 与
  `with_inline_rules(rules) -> TableRule(...)`——注意 `_InlineMixin.with_inline_rules` 默认实现是
  `type(self)(rules, self._theme)`（参数序 inline_rules 在前），与 TableRule 签名相反，不覆写必炸。
- `render`：每格 `self._segments(cell_text)`（base=NONE，base 风格由 Table 注入）；
  对齐从 delim 行算出（`_cell_align`/`_align_of` 保留），以 `aligns=` 传给 `Table`。
- `_split_row`（`markdown.py:641-650`）：以 `(?<!\\)\|` 切分，格内 `\|` 还原为 `|`；
  docstring 注明"反斜杠紧邻竖线的双重转义不区分"的简化。
- **拆除 `_pad`**（对齐移入 Table 后失去消费者，不留 shim）；docstring 436-437
  "Cells are plain text" 改为"cells render inline markup"。
- `match` 逻辑不动（流式安全的两行前瞻保持）。

### 测试更新（随 T2/T3 分布在对应 commit）

- `tests/test_widgets_table.py`：新增——两行数据表行间有横线；带 `⚠️ Blocked` 格的表在宽度 20..80
  全部行宽相等；Segment 单元格样式；aligns=center/right；str/tuple 兼容旧断言全部保持绿。
- `tests/test_widgets_markdown.py`：新增——`| **Bold** 加粗 | \`code\` | [t](u) |` 单元格渲染出
  bold/code/link 段；`` `a \| b` `` 渲染为含 `a | b` 的行内代码单格。现有网格形状断言
  （`test_tables_need_header...` 单数据行）与对齐断言（`test_table_alignment_markers`）应保持不变——
  若有出入，先查实现再改断言，并在报告里说明。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 全绿，基线 389 passed / 1 skipped 只增不减。
2. `uv run python examples/pi_demo.py < /dev/null` 与 `uv run python examples/markdown_demo.py < /dev/null` 均 exit 0
   （dump 内容变化仅允许来自表格网格/内联渲染，不得出现空行类变化——那是 W2 的活）。
3. `specs/2026-10-05-markdown-polish/ref/before-tables-w100.txt` 对比：同一输入渲染后
   边框等宽、行间横线出现、内联样式生效（报告里贴 3 行前后对照）。

## 禁触清单

`core/theme.py`、`widgets/chrome.py`、`widgets/syntax.py`、`chat/**`、`examples/**`、`docs/**`、
`README.md`、`specs/**`、`pyproject.toml`、`src/mocode_tui/__init__.py` 及各 facade `__all__`。
越界即停、上报 lead。

## 最终报告格式

工单状态表（T1/T2/T3 + 测试项）/ commit 清单（hash + message）/ `uv run pytest -q` 真实输出结论
（用例数与失败项）/ demo exit code / 偏差与取舍 / 未决问题。阻塞即停，不越界自救。
