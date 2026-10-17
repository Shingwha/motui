# Spec render-cost · W4：Markdown 与容器（波次 W4）

> 分支 `rc-w4-markdown`（从 **W1 合并后**的 main 创建）；前置：W1；深读：
> `00-overview.md`（D4/D8/D9/D10/D12）、`ref/facts.md`、`ref/probe.py`。

## 目标

把流式回复这条主线上的三笔钱省掉：`Markdown` 尾部开放块的全量重解析（单段流式是二次的：
400 次追加 1.2 s、1200 次 13 s）、命中路径的每帧全量扫行（`_stamp_tasks` + `_span_index`，
2000 行 1.6 ms/帧）、以及容器包装把子组件**已缓存**的行整份重拼（`Panel(Markdown 2000 行)`
36 ms vs 裸 Markdown 0.9 ms）。

## 工单（按序执行，每项一个 commit，每个 commit 独立跑一遍 `uv run pytest -q`）

### T1 `widgets/markdown/component.py`：尾块增量（D8）

- 现状：`_resume` 只在存在"已封口边界"时生效；一段不断变长的段落/未闭合 fence 永远只有
  一个开放块 → 每次追加全量重解析。
- 目标：**唯一的尾部开放块**在追加时只重渲该块（前缀行按源行范围缓存/切片），每帧代价与
  已落的行数无关。前缀切片的正确性口径：以"已封口边界"为准，边界不可靠时退回全量重解析
  （宁可慢也不许错），并在报告里说明退回条件。
- 既有的"流式只渲染变化"承诺（frame-budget W3）不许退化：`stream-single`/`stream-split`
  两行的数字必须**只降不升**。

### T2 `Markdown` 命中路径与 `revision()`（D4/D8）

- `_stamp_tasks`/`_span_index` 随 `(text, width)` 的渲染缓存一起走：命中时不许再全量重建
  （目标：2000 行命中帧 ≤ 0.3 ms，改前 0.89 ms）；`fences()` 每次重解析的问题按同一原则处理。
- 加 `revision()`（`text` + hover span + 任务缓存版本等会影响行的状态），让 sealed 块的
  hover（链接标签/任务框）能落屏（探针 F4）。

### T3 `widgets/syntax.py`：按行记忆（D9）

- `RegexHighlighter` 加 `(行文本, 语言) → Line` 的记忆；`highlight` 逐行查表。
  跨行状态本来就没有（模块 docstring 已写明是逐行匹配），所以按行缓存是完备的——
  在 docstring 里把这条完备性写清楚。
- 目标：2000 行 Python 的重复高亮 ≤ 5 ms（改前 51.7 ms）；首次照旧。

### T4 容器只包装可见行（D10）

- `Panel`/`Row`/`Column`/`Padding`/`Collapsible`：包装结果按
  `(子行对象元组身份, 内宽/边框参数)` 缓存，未变即复用；`child_at` 的既有缓存语义
  （`tests/test_container_hit.py:135/145`）不动。
- 目标：`Panel(Markdown 2000 行)` render ≤ 2 ms（改前 36.7 ms）。
- **零字节变化**：包装出来的行必须与今天逐字节相同（这是纯缓存，不许顺手改边框/缩进）。

### T5 `tools/framebench.py`：新增 `stream-paragraph` 行（D12）

- 只加不改：单段不断变长的 `Markdown`（每帧追加一行）的 ms/frame；docstring 基线段落追加说明。
- 与 W1/W2 的新行相邻而不冲突（按上表顺序合并，冲突由 lead 处理）。

### T6 测试与产物

- 更新既有用例：`tests/test_widgets_markdown.py` 里与 `_resume`/缓存内部行为有关的少数几条
  （尤其是 `test_render_serves_and_invalidates_its_one_entry_cache` 一类）。
- 新增 ≤ 4 条：单段流式的近线性（追加 N 次的耗时上界或调用计数）、命中帧不再重建 span 索引
  （计数）、语法按行记忆命中（计数）、sealed `Markdown` 链接 hover 落屏（探针 F4 的断言版）、
  容器包装缓存命中（计数）——超过 4 条就挑最核心的。
- `docs/API.md` 如签名动了就 `--write`；golden **不重录**。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q`（W1 合并后的基线数）
2. `uv run python tools/golden.py --check`（不许 `--update`）× 与 `tools/apidoc.py --check`
3. `uv run python tools/framebench.py`：`stream-single`/`stream-split` 只降不升；
   `stream-paragraph` 必须动（1000 行处每帧 ≤ 1 ms）；`render-hash` 逐字不变
4. `%TEMP%\rc_probe.py`：E 行近线性（400 次追加总量比改前 1.2 s 至少低一个数量级）、
   I 行 ≤ 2 ms、Markdown 命中 ≤ 0.3 ms、**F4 必须 True**
5. `uv run python -m motui < /dev/null` exit 0 与 `--pages` 11 页
6. `git status --porcelain` 干净 + `git log --oneline main..HEAD`

## 禁触清单

- 只改：`src/motui/widgets/markdown/**`、`src/motui/widgets/{syntax,decor,layout,collapsible}.py`、
  `tools/framebench.py`（只加 `stream-paragraph` 段）、`docs/API.md`（仅 `--write`）、
  `tests/{test_widgets_markdown,test_widgets_containers,test_widgets_basics}.py`。
- 禁触：`src/motui/kernel/**`（需要动就停下报告）、`src/motui/app.py`、`src/motui/interaction/**`、
  `src/motui/widgets/{table,field,textbuf,choice,radio,autocomplete,list,tree}.py`（W2 的）、
  `chrome.py`、`docs/{DESIGN,COMPONENTS}.md`、`README.md`、`CHANGELOG.md`（W5 的）、`specs/**`。
- 不 merge / 不 push / 不打 tag / 不 checkout main；不碰主检出与其它 worktree（尤其 `rc-w2-table-editor`）。

## 报告格式（最终消息，中文）

工单状态表（T1–T6）/ commit 清单 / 自测真实结论 / 探针表（E/I/Markdown 命中/F4，改前 vs 改后）/
`stream-single`/`stream-split` 的迁移数字 / 退回条件（边界不可靠时全量重解析的判据）/
既有用例搬迁清单 / 偏差与取舍 / 未决问题 / 真机手测：未执行。
