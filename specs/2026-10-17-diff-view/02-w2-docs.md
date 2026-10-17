# Spec diff-view · W2：语言文档（波次 W2）
> ✅ 已完成并合并 2026-10-17 @ `diff-w2-docs`（tip `0611c97`）→ main `0ddaf19`；文档事实逐条对合并后代码验真。

> 分支 `diff-w2-docs`（worktree `C:\Users\shifu\.worktrees\mocode-tui\diff-w2-docs`，
> 从 lead 合并时刻的 main 创建）；前置：W1 已合并（lead 会验真后再合你这份）。
> 必读：`00-overview.md`（决策表 D1–D13 是权威契约）、`01-w1-diff-core.md`（W1 的实际交付）。

## 目标

把 W1 的新行为写进**语言文档**，遵守本仓「一个事实一个家」的分工：
`docs/COMPONENTS.md` 是组件目录与契约细节，`docs/DESIGN.md` 是架构与理由（一行一条），
`CHANGELOG.md` 是面向使用者的变更记录。**只写 spec 决策表里有的东西**，不许发明 API、
不写没被 W1 实现的选项、不引用未实测的仓外工具默认值作为理由（理由用本仓自有的两条：
`kernel/style.py` 的 markdown 调色注释「bold 归 `**…**`」与 `kernel/theme.py` 的 heading 注释）。

## 工单（按序执行，每项一个 commit）

### T1 `docs/COMPONENTS.md` 的 Diff 表行

- 第 ~150 行的表行（现为 `Diff(before, after, *, context=3, theme=None)`）改成新签名
  `Diff(before, after, *, context=3, numbers=False, theme=None)`，并把这一段话改写成新的契约：
  构造时算一次；先裁公共头尾、再对区间跑 LCS（预算 `LCS_LIMIT` 是**一次 DP 比较的区间**
  的上限）、超预算先按「段内唯一共同行」锚点切分、无锚点才整段替换成**一个** hunk；
  省略行带跳过行数（`… N lines`）；内容行不带 weight；`numbers=True` 加行号栏；
  `before`/`after`/`context`/`numbers`/`theme` 赋值即重建；`render(width)` 按宽度缓存。
  保持表行的既有口吻（一行之内说清，别写成小作文）。
- commit 建议：`docs(components): the Diff row carries its new contract`

### T2 `docs/COMPONENTS.md` 的 `### Diff` 小节

- 第 ~193 行起的小节重写，顺序建议：两个文本进 → 行词汇（`@@` / ` `/ `-` / `+` / `… N lines`
  与行号栏）→ 算法阶梯（裁剪 → 预算内 DP → 唯一共同行锚点 → 诚实的单 hunk 替换）→
  样式规则（`error` 色相无 weight、`success`、`muted`；为什么：bold 归 `**…**`）→
  赋值与缓存语义 → display-only 与宿主如何挂载滚动（这一段与今天一致，别丢）。
- 代码示例更新为体现新选项（`context=`、`numbers=True`），示例必须是真能跑的
  （与 `tests/test_readme_examples.py` 无关，但别杜撰参数）。
- 旧小节里与今天不符的句子（如「the LCS runs once, in the constructor」若还在、
  以及「past `LCS_LIMIT` the whole text is replaced in two hunks」）必须改掉。
- commit 建议：`docs(components): the Diff section follows the new walk`

### T3 `docs/DESIGN.md` 的 D17 行

- 第 ~139 行的 D17 行里 Diff 的那一句（「the LCS runs once, in the constructor … past
  `LCS_LIMIT` … two hunks」）更新为：构造时一次；裁剪 + 锚点；超预算退化为**一个** hunk；
  `numbers=` 与 weight 规则各点到为止。**保持一行一条的密度**，不要展开成段落。
- 第 ~84 行的 `motui.widgets` 门面行只列名字——核对无需改动（如实报告"无改动"）。
- commit 建议：`docs(design): the diff view's one line follows the walk`

### T4 `CHANGELOG.md` 的 `[Unreleased]`

- 在 `## [Unreleased]` 下补 `### Added`（`numbers=False` 行号栏）与 `### Changed`
  （大文件不再退化为整文替换；省略行带跳过行数；删除行不再加粗；赋值即重建；render 按宽度缓存）。
- 英文，Keep a Changelog 口吻，一条一行；**不动版本号、不加 tag**。
- commit 建议：`docs(changelog): the diff view's changes`

### T5 `README.md` 核对

- 核对 README 是否有需要跟随的 Diff 契约（现在只在组件清单里出现名字）。
  若无需改动就**不要改**，在报告里明说「README：核对后无改动」。
- 若确有需要改的句子，只改那一句，并说明位置。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q`（全绿；基线 1395 passed / 1 skipped —— 本分支不动代码，数字应一致）
2. `uv run python tools/apidoc.py --check` 与 `uv run python tools/golden.py --check`（都应绿：
   本分支不碰产物）
3. 自检清单：文档里每条事实都能在 `00-overview.md` 的决策表或 `01-w1-diff-core.md` 里
   找到出处（报告里逐条列出处，例如「省略行文本 → D10」）
4. `git status --porcelain` 干净
5. `rg -n "two hunks|in two hunks" docs/ README.md` 之类的自查：不许留下与新行为矛盾的残留句

## 禁触清单

- 只改这四份（README 允许「零改动」）：`docs/COMPONENTS.md`、`docs/DESIGN.md`、
  `README.md`、`CHANGELOG.md`。
- 明确禁触：`src/**`、`tests/**`、`docs/API.md`（生成物）、`tools/**`、`specs/**`、
  `pyproject.toml`。
- 不 merge / 不 push / 不打 tag / 不 checkout main；不碰主检出与其它 worktree；不改任何 spec。
- 阻塞即停：报告阻塞点，不越界自救。

## 报告格式（最终消息，中文）

工单状态表（T1–T5）/ commit 清单（hash + message）/ 自测真实结论 / 每条事实的出处（决策号）/
README 核对结论 / 偏差与取舍 / 未决问题 / 真机手测：未执行。
