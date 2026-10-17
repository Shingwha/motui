# Spec render-cost · W5：文档（波次 W5）

> 分支 `rc-w5-docs`（从 **W1–W4 全部合并后**的 main 创建）；前置：W1–W4。
> 深读：`00-overview.md`（决策表是权威契约）、`01`–`04` 四份工单（实际交付了什么）、`ref/facts.md`。

## 目标

把这一组改掉的**架构事实**写进语言文档（本仓「一个事实一个家」：`DESIGN.md` 放架构与理由，
`COMPONENTS.md` 放组件契约，`CHANGELOG.md` 面向使用者）。只写四波真实交付的东西，
不许发明 API、不许写没被实现的优化。

## 工单（按序执行，每项一个 commit）

### T1 `docs/DESIGN.md`

- **缓存归属变了**：今天的设计写着"the sealed-row cache lives on the viewport，按宽度失效"
  （`:302`、`:330`、`:345` 的 Pane 行、`:653`）——现在缓存搬到 `Block.rows(width)`（键含修订令牌），
  且**OPEN 块在有修订协议时也缓存**。这几处逐条改成新事实，保持一行一条的密度。
- **修订协议**：在合适的位置（模块表/协议表一带）补一行 `Revisioned` 的语义：
  "行的全部输入的值快照；相等 ⟹ 同宽下行相等；sealed 块的陈旧由它解"。
- **合成路径**：`:454` 一带描述 painter 是纯差分器的那段，补上"compose 逐行复用未变的行、
  splice 在平凡窗口早退"这一层事实（如果 W3 确实落了这个形状——以合并后的代码为准）。
- `:84` 的 `motui.widgets` 与 `:86` 的 `motui.kernel.lines` 门面行按需核对。

### T2 `docs/COMPONENTS.md`

- 受影响的组件表行/小节按新事实更新：`Text`（记忆与修订）、`Table`（记忆与修订）、
  `Editor`/`Input`（按行 wrap 记忆）、`Markdown`（尾块增量、命中缓存、hover 落屏）、
  容器（包装缓存）、语法高亮（按行记忆）。
- **框架级的一段**：`Block`/viewport 的缓存故事（`Block.rows` 是缓存入口、`Block.render` 是新鲜行
  的门、修订协议怎么让 sealed 块的 hover 落屏）。放在合适的位置（离 `Block`/`Viewport` 的叙述处），
  不要新开一节讲三遍。

### T3 `CHANGELOG.md` 的 `[Unreleased]`

- `### Changed`（面向使用者、英文、一条一行）：未变的块不再每帧重渲（大文本/表格/编辑器/流式
  Markdown 的快照数字可以挑最亮的两三个写）、带滚动条的帧不再整屏重建、sealed 块的 hover 修复。
- `### Fixed`：sealed 块的 hover/状态变化不落屏。
- 不动版本号、不打 tag。

### T4 `README.md` 核对

- 核对后无改动就**不要改**，报告里写明"核对后无改动"。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q`（合并后基线）与 `uv run python tools/apidoc.py --check`、
   `uv run python tools/golden.py --check`（都应绿：本波不动代码/产物）
2. 逐条自检：写进文档的每个事实都能指到决策号或某波的交付（报告里列"事实 → 出处"）
3. 残留句自查：`rg -n "sealed-row cache|sealed cache|once per width" docs/`——不许留下与
   `Block.rows` 新事实矛盾的句子
4. `git status --porcelain` 干净 + `git log --oneline main..HEAD`

## 禁触清单

- 只改：`docs/DESIGN.md`、`docs/COMPONENTS.md`、`CHANGELOG.md`、`README.md`（按需）。
- 禁触：`src/**`、`tests/**`、`docs/API.md`（生成物）、`tools/**`、`specs/**`、`pyproject.toml`。
- 不 merge / 不 push / 不打 tag / 不 checkout main；不碰主检出与其它 worktree。

## 报告格式（最终消息，中文）

工单状态表（T1–T4）/ commit 清单 / 自测真实结论 / 事实→出处对照表 / README 核对结论 /
残留句自查输出 / 偏差与取舍 / 未决问题 / 真机手测：未执行。
