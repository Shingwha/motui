# W5a · Table 换行

> 分支 `refactor/1.2-w5a-table`；worktree `C:\Users\shifu\.worktrees\motui\1.2-w5a-table`
> 前置：W4b 已合并（`a346ed7`）；写入范围见下；波末必须全量绿。

## 目标

让 `Table`（以及委托它的 Markdown 表格）支持单元格自动换行，长内容不再被省略号截断；`wrap=False` 保留旧行为。**这是 1.2.0 明确允许改变 golden 的波次，但只允许表格相关内容变化。**

## 前置上下文

- 必读顺序：
  1. `ref/repo-map.md`
  2. `ref/interfaces.md`（§4 W5 Table + W4b 实际交付）
  3. `handoff/W4b-w4b-demo.md`
  4. 本工单
- 基线命令：

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python -m motui < /dev/null | sha256sum
```

起点 **882 passed / 57 topics match**；记录 headless sha256。
- 稳定区（勿重读/勿改）：`widgets/scroll.py`（W5b 并行）、`app/**`、`core/**`、`demo/**` 的非表格文案、`docs/**`。
- 已知约束/坑：
  - `Table` 现在在 `wrap` 之外还有 `styles`/`glyphs`/`grid`/`disabled`/`disabled_items`；不要改这些语义。
  - Markdown `TableRule` 只是解析管道并构造 `Table`（`widgets/markdown/tables.py`），换行逻辑必须落在 `Table`。
  - `Table._layout()` 目前不带宽度，`click`/`hover_at` 也直接调用；换行后布局必须记录“视觉行 -> 数据行”的映射，命中读最近一次 render 的布局。
  - `Line` 是一个视觉行；用 `wrap_line(Line(cell_segments), budget)` 保 Segment/link/action，不要走纯文本路径。
  - `header_line(width)` 是单行 API；保留它（取第一视觉行），新增 `header_lines(width)`。
  - `mark()` 前缀只加在记录的第一视觉行；续行留空。
  - `table-open` framebench 不应明显退化（目标 ≤2x）。

## 工单（按序执行，每项一个 commit）

### T1 · Table 宽度策略 + 换行行模型

- `widgets/table.py::Table.__init__` 增加：
  ```python
  wrap: bool = True,
  max_col_width: int | None = 40,
  min_col_width: int = 3,
  ```
- 宽度策略：
  - `wrap=False`：完全保留当前 `_natural_widths` + `_shrink` + `Line.fit` 省略行为。
  - `wrap=True`：
    1. 自然宽度按列取最大（header/body 都算，含 mark 前缀）；
    2. 每列 cap 到 `max_col_width`（None 表示不 cap），floor 到 `min_col_width`（若列数 × min 超过可用宽度，则退化为 `max(1, inner // ncols)`）；
    3. 若 cap 后总宽 <= 可用 inner，使用 cap 后的自然宽度；否则按比例分配剩余宽度，保证每列至少 floor；
    4. 用 `wrap_line(Line(cell_segments), budget)` 换行；记录高度 = 各单元格视觉行数的最大值。
- 布局：
  - `_layout(width)` 返回每个视觉行的 `(kind, data_row, visual_line)`；`kind` 仍是 `"top"/"header"/"header_rule"/"row_rule"/"bottom"/"empty"` 或数据行 index。
  - `render(width)` 缓存最近一次布局（例如 `self._last_layout` / `self._last_width`）；`click`/`hover_at` 读它，映射回数据行。
  - 每条数据记录的 `row_rule` 只在其最后一条视觉行后绘制；续行只画垂直边框。
  - header 也换行；`header_lines(width)` 新增，`header_line(width)` 返回第一行。
  - 每条视觉行都应用 band；mark 前缀只在第一视觉行。
- 允许改：`widgets/table.py`、`widgets/markdown/tables.py`（仅传 `wrap=True` 或不传，使用默认）、`tests/widgets/test_data.py`、`tests/widgets/test_markdown.py`。
- 验证：pytest；`wrap=False` 的现有测试必须保持旧输出。

### T2 · 最小行为测试 + demo/golden

- 只加必要测试（优先扩展现有文件）：
  - 长单元格在 `wrap=True` 下产生多行且不出现省略号；
  - 第二视觉行的 `click`/`hover_at` 映射回同一数据行；
  - inline Segment/style 在换行后保留；
  - `wrap=False` 仍省略（现有断言改/保留）。
- Markdown：`TableRule` 使用默认 `wrap=True`；`fixture.md` 里的长表格应在 streaming 帧里体现换行。
- 运行 `golden.py --check`：
  - 只允许包含表格的帧变化（预计 `patterns--streaming-markdown`，以及任何 table topic）；逐个 hunk 核对，`--update` 后逐帧在 commit message 解释。
  - 不允许非表格帧变化；若出现，停下来报告。
- 允许改：`tests/widgets/test_data.py`、`tests/widgets/test_markdown.py`、`tests/golden/topics/*`（仅表格相关）。
- 验证：pytest + golden + framebench + `python -m motui < /dev/null` + `--pages`。

### T3 · 波末门禁

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

## 验收

1. 五条门禁全绿；报告贴真实用例数/失败项。
2. 长表格单元格换行而非省略；`wrap=False` 逐字节保留旧行为。
3. 第二视觉行点击命中同一数据行；mark/band/边框正确。
4. 只有表格相关 golden 变化，并逐帧解释；`table-open` 不出现数量级退化。
5. 不新增独立测试文件；只扩展现有 test 文件。

## 禁触清单

- `widgets/scroll.py`、`app/**`（W5b 并行）、`core/**`、`widgets/markdown/*` 除 `tables.py` 的构造参数。
- 非表格 demo 文案、`docs/**`、README/CHANGELOG/pyproject、root `__all__`。
- `.zcodeignore`、`dist/`、`.venv/`。

## 交接包

完成后写 `handoff/W5a-w5a-table.md`（60-80 行），重点写宽度策略、布局映射、视觉行/规则/mark、golden 变化清单、framebench。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题
