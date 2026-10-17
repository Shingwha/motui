# Spec diff-view · W1：`Diff` 的核心（波次 W1）

> 分支 `diff-w1-core`（worktree `C:\Users\shifu\.worktrees\mocode-tui\diff-w1-core`，
> 从 lead 合并时刻的 main 创建）；前置：无；深读：`00-overview.md`（决策表 D1–D13 是权威）。
> 必读文件：`00-overview.md`、`ref/facts.md`、`ref/probe.py`、`src/motui/widgets/diff.py`、
> `src/motui/widgets/markdown/component.py`（宽度缓存的既有惯例，86–106 行）、
> `tests/test_widgets_diff.py`、`tests/test_render_invariants.py`（模块 docstring 的三条不变量）。

## 目标

把 `Diff` 从「每边 ~141 行的 LCS 天花板 + 无缓存 + 赋值静默过期 + 删除行加粗」改成
「真文件给出真 hunk、按宽度缓存、赋值即重建、内容行 weight-neutral、可选行号栏」，
且**除 D9/D10/D11/D12 写明的渲染变化外，对外行为零变化**。

## 工单（按序执行，每项一个 commit，每个 commit 独立跑一遍 `uv run pytest -q`）

### T1 公共前后缀裁剪 + 退化形状（D2/D3/D6）

- `_build` 的计算部分拆成模块级私有函数（名字可自定，语义固定）：
  - `_lcs_ops(before, after)` —— **保留原名与原签名，一行不改**（它是 DP 引擎，探针也用它）；
  - 裁剪：按行严格相等剥离公共头 / 公共尾，得到中段；
  - 中段：任一侧为空 → 该侧无 op、另一侧全 `del`/`ins`；`len(b)*len(a) <= LCS_LIMIT` →
    `_lcs_ops`；否则（T1 阶段）整段 `del+ins`；
  - 完整 op 流 = 头部 `same` ops + 中段 ops + 尾部 `same` ops，**hunk/窗口/行号逻辑
    （`_regions`/`_line_counts`/`_range`/窗口合并）一行不改**。
- 退化形状改为**一个 hunk**（D6）：整段 `del+ins` 是连续的 non-`same` run，天然落到一个窗口里
  ——不要为它写特例代码，改完自然就是这个形状。
- 更新既有用例（唯一允许的期望值改动）：
  `test_the_bounded_walk_replaces_the_whole_text_in_two_hunks` → 改名
  `test_a_region_with_no_shared_line_replaces_itself_in_one_hunk`，fixture 换成**毫无共同行**的
  2000 vs 2000 行，断言：`headers == ["@@ -1,2000 +1,2000 @@"]`、2000 条 `-`、2000 条 `+`、
  无省略行。（旧 fixture 的"改 1 行"现在走真 hunk，所以旧断言必须换。）
- 新增 1 条：2000 行改中间 1 行 → 9 行、头 `@@ -998,7 +998,7 @@`（胜在"真 hunk"）。
- docstring（模块 + 类 + `LCS_LIMIT`）改写为裁剪语义：预算是**一次 DP 比较的区间**的上限
  （D1）；两侧相同 → 零行。
- 产物：`uv run python tools/apidoc.py --write`（docstring 动了，`--check` 必须绿）。
- commit 建议：`perf(diff): the walk trims the common head and tail before the table`

### T2 唯一共同行锚点（D4/D5）

- 中段超预算时（替代 T1 的整段替换）：
  - 在**本段的**两侧各统计行出现次数，取"两侧各恰好一次"的行配对；
  - 配对的 (i, j) 按 i 递增走一遍，保留 j 严格递增者（跨越的丢弃），得到锚点序列；
  - 依次：段前区间递归 + 锚点行本身一个 `same` op + 段后区间递归；
  - 本段无锚点 → 整段 `del+ins`（诚实退化）。
- 终止性与代价上界（写进 docstring 与报告）：每段严格更短 → 必然终止；段内退化保证
  **总编辑代价 ≤ n+m**，即永不比今天的整文替换更差。
- 新增 1 条：500 行、第 10/250/490 行各改一处 → **29 行、3 个 hunk、两条省略行计数 233 / 233**。
- commit 建议：`perf(diff): unique-line anchors split a big region before degrading`

### T3 `render(width)` 按宽度缓存（D7）

- 新增 `_rendered_width: int | None`、`_rendered_rows: list[Line] | None`；
  `render(width)` 同宽度命中 → `list(self._rendered_rows)`（调用方拥有这份拷贝）；
  否则重建、存缓存、返回 `list(...)`。
- 对齐 `markdown/component.py:86-106` 的既有写法与注释口吻。
- **不新增测试**：`tests/test_render_invariants.py` 的三条不变量（幂等 / 有界 / 换宽度无漂移）
  就是它的门禁——逐条跑过即可。
- commit 建议：`perf(diff): render caches its fitted rows per width`

### T4 赋值即重建（D8）

- `before` / `after` / `context` / `numbers` 改为 property + setter；`theme` 也从 slot 改成
  基于 `Themed._theme` 的 property + setter（setter 重新解析三个色带）。
  `__slots__` 相应改为 `_before` / `_after` / `_context` / `_numbers` / `_rendered_width` /
  `_rendered_rows`（`_del_style` / `_ins_style` / `_hunk_style` / `_rows` 保留）。
- 任一个 setter：校验（`context` 先校验 `< 0` → `ValueError` 且**状态不变**）→ 改内部值 →
  重建 `_rows` → 清空渲染缓存。五个 setter 共用一个私有重建方法。
- `__repr__` 保持今天的形状（`Diff(N rows, context=3)`），不动。
- 新增 1 条：赋 `before` / `context` 之后 `render()` 跟着变；`context=-1` 抛 `ValueError` 且
  `context` 与行都不变。
- commit 建议：`fix(diff): assigning the inputs rebuilds the rows`

### T5 样式：删除行去 weight + 省略行带计数（D9/D10）

- 删除行 band = 解析出的 `error` 去掉 bold：`dataclasses.replace(resolved, bold=False)`
  （只剥 bold；宿主注入的 italic/underline 等保留）。类 docstring 写明规则：内容行
  （上下文 / `-` / `+`）不带 weight —— 仓规是 bold 归 `**…**`（`kernel/style.py` 的
  markdown 调色注释与 `kernel/theme.py` 的 heading 注释）。
- 省略行文本 = `"… N lines"` / `"… 1 line"`（D10）；`ELISION` 常量仍是 `"\u2026"`。
- 更新既有用例 2 条：
  - `test_context_zero_tightens_the_hunk_and_keeps_the_numbers_exact`：省略行断言改
    `"… 7 lines"`（1–10 行改第 2、10 行，context=0，中间 7 行被跳过）；
  - `test_the_elision_row_sits_between_hunks_in_the_muted_band`：segments ==
    `(Segment("… 7 lines", HUNK_BAND),)`（12 行改第 2、12 行、context=1，中间 7 行）。
- 新增 1 条：删除行的字节 = `\x1b[38;2;229;83;75m-b\x1b[0m`（`1;` 前缀必须不在），
  插入行 `\x1b[38;2;75;181;99m+c\x1b[0m`、`@@` 行 `\x1b[38;2;139;148;158m…\x1b[0m` 与今天一致。
- commit 建议：`style(diff): the deletion row keeps the hue and loses the weight`

### T6 `numbers=True` 行号栏 + demo 展台（D11/D12）

- content 行 = 两个 segment：`f"{n:>{w}} "`（`muted`）+ 既有文本（各自 band）；
  `same`/`del` 取 before 侧行号，`ins` 取 after 侧行号；`w` 在构造时按整份文本定
  （D11 的公式）；`@@` 与 `…` 行不加栏；`numbers=False`（默认）逐字节同 T5 之后的样子。
- 新增 1 条：行号栏（同一行对上 `-` 与 `+` 各取自己那侧的行号；`@@`/`…` 无栏；
  gutter segment 的 style == theme 的 muted）。
- `tests/test_render_invariants.py` 的组件矩阵 **+1 行**：
  `("Diff numbers", lambda: Diff("a\nb\nc\nd", "a\nB\nc\nd\ne", numbers=True)),`
  ——除这一行外该文件零改动。
- demo 展台：`Diff(BEFORE, AFTER, numbers=True)`；`BEFORE`/`AFTER` 扩成能出现一条省略行的
  fixture（两处改动相隔 > 2×context 行）；`api_note` 文案同步（提到 `numbers` 与省略行计数）。
- `uv run python tools/golden.py --update` **整组**重录，报告里列出真正移动的文件（预期
  `content.txt` 动；其它页若动要说明原因）。
- commit 建议：`feat(diff): an optional line-number gutter, shown in the demo exhibit`

### T7 探针（不提交任何文件）

- 把 `ref/probe.py` 拷到 `%TEMP%\probe.py`，`sys.path` 指向本 worktree 的 `src`，跑出
  探针表（六例）与两个差分段，贴真实输出，与 `00-overview.md` 的预期值逐行对比。
- 差分段若出现"比 DP 更贵"的样本：如实报告分布（个数、最大 delta），并对照 D5 的
  `≤ n+m` 上界说明。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q`（每个 commit 后都跑；最终报告贴总数）
2. `uv run python tools/golden.py --check`（T6 之后）
3. `uv run python tools/apidoc.py --check`
4. `uv run python tools/framebench.py`（六行；`render-hash` 预期不变——Diff 不在负载路径）
5. `uv run python -m motui --pages`（页数与 content 页内容）与
   `uv run python -m motui < /dev/null`（exit 0）
6. `%TEMP%\probe.py` 的探针表
7. `git status --porcelain` 干净（探针在 `%TEMP%`，不在 worktree）

## 禁触清单

- 除这些文件外一行不改：`src/motui/widgets/diff.py`、`tests/test_widgets_diff.py`、
  `tests/test_render_invariants.py`（仅矩阵 +1 行）、`src/motui/demo/pages/content.py`
  （仅 Diff 展台与其 `api_note`）、`tests/golden/pages/*.txt`（仅 `--update` 重录）、
  `docs/API.md`（仅 `--write` 生成）。
- 明确禁触：`src/motui/kernel/**`（含 `style.py` / `theme.py` / `lines.py`）、
  `src/motui/widgets/**` 的其它文件（`syntax.py`、`list.py`、`markdown/**` …）、
  `docs/COMPONENTS.md`、`docs/DESIGN.md`、`README.md`、`CHANGELOG.md`（W2 的活）、
  `tools/**`、`specs/**`、`pyproject.toml`、`tests/**` 的其它文件。
- 不 merge / 不 push / 不打 tag / 不 checkout main；不碰主检出
  `C:\Users\shifu\Desktop\mocode-tui` 与其它 worktree；不改任何 spec。
- 阻塞即停：报告阻塞点，不越界自救（见 `00-overview.md` 的诚实出口）。

## 报告格式（最终消息，中文）

工单状态表（T1–T7）/ commit 清单（hash + message）/ 自测真实结论（用例数与失败项）/
探针表（改前 vs 改后，逐行）/ 差分段（含无更贵样本的分布）/ golden 与 apidoc 说明 /
framebench 六行 / 偏差与取舍 / 未决问题 / 真机手测：未执行。
