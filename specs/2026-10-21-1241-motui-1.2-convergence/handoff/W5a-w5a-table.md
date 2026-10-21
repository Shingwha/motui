# W5a 交接包
> 分支 `refactor/1.2-w5a-table` / 起点 `9b3ac88`（W4b merge `a346ed7` + 工单）/ 2026-10-21

## A. 自动事实（命令与代码实测）

- commits：`8184352`（T1）、`d6e02bf`（T2）、本文件所在 commit（T3 门禁 + 交接）。
- `git diff --stat 9b3ac88..d6e02bf`：10 files, +633/-335（不含本文件）。文件：
  `widgets/table.py`、`tests/widgets/{test_data,test_markdown}.py`、7 个表格 golden。
- `uv run pytest -q -p no:cacheprovider` -> **887 passed**（882 起点 + 5 个新用例）。
- `golden.py --check` -> **57 topics match**。
- `framebench.py`：`table-open 0.1 ms/frame`（基线 0.1，未退化），render hash
  `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（与基线同值）。
- 两个入口 exit 0：`python -m motui < /dev/null` sha256 `c793b32b...`（与基线同值）；`--pages` sha256 `b6ba849d...`（基线 `855f76fa...`；它逐 topic 渲染，7 个表格帧变化是其原因）。
- 实测签名：
  `Table(headers, rows, *, aligns, glyphs, grid, disabled, disabled_items, theme, styles,
  wrap=True, max_col_width=40, min_col_width=3)`。
- `widgets/markdown/tables.py` 未改：`TableRule` 直接使用默认 `wrap=True`。

## B. 宽度策略（`wrap=True`，`table.py::_wrap_budgets`）

1. natural 宽度仍是 `_measure_widths`：header/body 逐列取最大（mark 前缀已计入首列）。
2. `set_widths` 的 pin 先替换 natural（每列 `max(1, pin)`，短列表保留测量值）。
3. `preferred[i] = max(min_col_width, min(natural[i], max_col_width))`；`max_col_width=None` 不 cap。
4. 可用内容宽 `avail = width - (ncols + 1) - 2 * ncols`（边框 + 每格两侧 padding）。
5. `ncols * floor > avail` 时退化为 `[max(1, avail // ncols)] * ncols`（width=0 仍每列 1）。
6. 否则按 **cap 后** 宽度比例分配：`max(floor, w * avail // total)`；floor 造成的溢出从最宽列逐个减到 floor。
7. `wrap=False` 走原来的 `_shrink` / `Line.fit` 路径，未改一行；对 300 组随机表做过与新代码的
   差分（样式、link、mark、cursor、pin、aligns、宽 0..45）逐字节相同。

## C. 视觉行模型与命中映射

- `_Slot(kind, data_row, visual_line)`：`kind` 仍是数据行 idx 或 frame token；`data_row` 供命中；
  `visual_line` 是该记录内的 0-based 视觉行（frame 行恒为 0）。
- `_plan(width)` 一次产出 layout + 未 band 的 `Line`；`_grid` 只负责按 slot 加 band/`rest`。
  `render` 的 memo 同时存 `_memo_rows/_memo_layout`，命中/未命中都写 `_last_layout`。
- `click`/`hover_at` 走 `_hit_layout()`：读最近一次 render 的 layout；从未 render 时退化为
  `_unwrapped_layout()`（每记录 1 行），保持旧测试里“未 render 直接 click”的语义。
- 每个记录：`row_rule` 只在其**最后**一条视觉行之后；最后一条 rule 即 `bottom`。
- 每条视觉行都有左右边框，并各自套该记录的 band（`_row_band` 按数据行解析）。
- mark 前缀拼在首格 segments 头部，换行后天然只落在第一条视觉行；续行留空、band 照旧。
- `header_lines(width)` 新增（整块 header，已 `rest`）；`header_line(width)` 返回第一行。

## D. Golden 变化清单（7 帧，均为表格）

- `components--table`：`id` 列 natural=2，floor 到 3。
- `interactions--dispatch`：`#` 列 floor 到 3；`owns` 长句换行。
- `reference--api-layers`：`owns`/`import`/`depends on` 由省略号改为换行，表格变高。
- `reference--component-matrix`：`activated`/`handled` 表头与长组件名换行，不再省略。
- `reference--keymap`：action 列按新策略重新分配，`tab` 行换行。
- `reference--non-goals`：两列 ruling 文本换行，不再省略。
- `styling--glyphs`：`seat` 表头在 3 列 floor 上换行；表格变高触发 pane scrollbar，
  右侧 `used by` 随内容宽 -1 而换行（scrollbar 是表格变高的直接结果）。
- 逐行脚本核对：所有变化行都含表格框线或为末尾空白行；无任何非表格内容变化。
  `--update` 后其余 50 个被写成 LF 的未变文件已 `git checkout --` 还原（blob 相同）。

## E. 偏差与取舍

1. `patterns--streaming-markdown` 未变：该帧的流式前缀停在第 46 行表格之前，工单预期的
   “streaming 帧体现换行”在该帧不可达；Markdown 换行由 `test_markdown.py` 的新用例覆盖。
2. 未给 `TableRule` 显式传 `wrap=True`（默认即 true），减少无意义 diff。
3. 显式 `set_widths` 仍受 cap/floor 约束（pin 是偏好，不是溢出许可），与旧 docstring 的
   “render clamps”语义一致。
4. `_wrapped_row` 复用 `_cell_parts`，保留 `Line.fit` 的宽字符保护（单字超预算时仍省略）。
5. `Table` 构造器现有 13 个 keyword 参数，超过“≤10”目标；这是 interfaces §4 冻结签名，未拆。

## F. 未决

- demo `components_data.py` 的 `api_line` 仍写旧 Table 签名（工单禁触非表格文案，留给 W6）。
- `click` 在 render 后、rows 原地修改但未重绘时读旧 layout（契约明确“最近一次 render”）。
- W5b 并行区（`widgets/scroll.py`、`app/**`）本波未触碰；`git status` 干净，无未跟踪文件。

## G. 门禁命令（复现）

```bash
uv run pytest -q -p no:cacheprovider      # 887 passed
uv run python tools/golden.py --check     # 57 topics match
uv run python tools/framebench.py         # table-open 0.1 ms/frame
uv run python -m motui < /dev/null        # exit 0, sha256 c793b32b...
uv run python -m motui --pages            # exit 0, sha256 b6ba849d...
```
