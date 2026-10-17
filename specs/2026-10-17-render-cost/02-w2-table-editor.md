# Spec render-cost · W2：Table 与编辑器（波次 W2）

> 分支 `rc-w2-table-editor`（从 **W1 合并后**的 main 创建）；前置：W1（要用它的 `Revisioned`
> 协议与 `Block.rows`）；深读：`00-overview.md`（D3/D6/D7/D12）、`ref/facts.md`、`ref/probe.py`。

## 目标

两个"全量物化"大户吃上记忆：`Table`（60×6 = 5.9 ms/帧、240×6 = 24 ms/帧）与
`Editor`/`Input`（3000 行 9 ms/帧、9 ms/键——只显示 20 行却 wrap 全文）；
顺带给 6 个带光标/hover 状态的组件补 `revision()`，让它们在 sealed 块里也活得对（D4）。

## 工单（按序执行，每项一个 commit，每个 commit 独立跑一遍 `uv run pytest -q`）

### T1 `widgets/table.py`：记忆 + 修订（D7）

- `revision()`：值快照 = `(rows 的副本, headers 副本, 显式 widths, index, hover_row, focused,
  相关样式字段, theme)`。**必须是副本**：`self.rows` 是宿主可原地改的裸列表，
  `rows == cached` 会因同一对象而恒真，探测不到原地修改。
- `render(width)`：`(revision, width)` 命中即返回缓存行的拷贝；`_natural_widths` 的测量结果
  随缓存一起走（别每帧重测）。
- 代价约束：算快照 + 比较必须 ≤ 该 render 的 5%（240×6 目标 ≤ 2 ms/帧，60×6 ≤ 1 ms）。
  达不到就报告真实数字，不要放宽目标。

### T2 `widgets/textbuf.py` + `widgets/field.py`：按行 wrap 缓存（D6）

- `TextBuffer` 加单调 `version`（每次变更 +1）与按逻辑行的 wrap 缓存：
  `行索引 → (行文本, 内宽, spans)`；同行编辑只失效该行，结构性变更（换行/跨行粘贴/`set_text`/
  整体替换）清空整表。`move_*`/`locate`/`place`/`cursor_position`/`click` 全部受益于同一个缓存。
- `Editor`/`Field`/`Input` 的 `revision()` 以 `(self._buf.version, 光标/选区/窗口/focused/
  placeholder/indent 等会进行的状态)` 为主；`render` 命中即返回缓存行。
- 目标：3000 行暖渲染 ≤ 1 ms、每键（`move_down` / 一次插入）≤ 1 ms；冷渲染可比今天略慢
  （多一层比较），报告里如实写。

### T3 六个组件的 `revision()`（D4）

`Select`/`Radio`/`Autocomplete`/`List`/`Tree` 的可见状态（`index`/`hover`/`focused`/`chosen` 相关）
各加一个便宜的 `revision()`；`Tree` 的 `expanded`/`filter` 状态也要进快照。
这一条只为"sealed 块里的光标/hover 落屏"，不要顺手做窗口化（那是遗留项）。

### T4 `tools/framebench.py`：新增 `table-open` 行（D12）

- 只加不改：240×6 的 `Table` 块，一次 `paint()` 的 ms/frame；docstring 基线段落追加说明与数字。
- 与 W1 的 `text-open` 相邻而不冲突（按上表顺序合并，冲突由 lead 处理）。

### T5 测试与产物

- 更新既有用例：`tests/test_widgets_*` 里若断言了"每次 render 都新建行/调用次数"的少数几条。
- 新增 ≤ 4 条：`Table` 记忆命中与原地改 cell 后失效、`TextBuffer` 同行编辑只失效一行（计数）、
  `Editor` 每键不再全量 wrap（计数或时间上限）、sealed `Table` hover 落屏（探针 F3 的断言版）。
- `docs/API.md` 如签名动了就 `--write` 重生成；golden **不重录**。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q`（W1 合并后的基线数，报告里写明）
2. `uv run python tools/golden.py --check`（不许 `--update`）与 `tools/apidoc.py --check`
3. `uv run python tools/framebench.py`：`table-open` 必须动（≤ 1 ms，改前 24 ms 量级），
   `text-open` 保持 W1 的水平；`render-hash` 逐字不变
4. `%TEMP%\rc_probe.py`：C 行 ≤ 1 ms@60×6 与 ≤ 2 ms@240×6、D 行暖 ≤ 1 ms / 每键 ≤ 1 ms、
   **F3 必须 True**；其余行不因本波变化
5. `uv run python -m motui < /dev/null` exit 0
6. `git status --porcelain` 干净 + `git log --oneline main..HEAD`

## 禁触清单

- 只改：`src/motui/widgets/{table,field,textbuf,choice,radio,autocomplete,list,tree}.py`、
  `tools/framebench.py`（只加 `table-open` 段）、`docs/API.md`（仅 `--write`）、
  `tests/test_widgets_{basics,forms,editing,list,choice,containers}.py`（按需）。
- 禁触：`src/motui/kernel/**`（W1 的地基；若发现需要动它，**停下报告**）、`src/motui/app.py`、
  `src/motui/interaction/**`、`src/motui/widgets/{markdown/**,syntax,decor,layout,collapsible}.py`
  （W4 的）、`chrome.py`、`docs/{DESIGN,COMPONENTS}.md`、`README.md`、`CHANGELOG.md`（W5 的）、
  `specs/**`、`pyproject.toml`。
- 不 merge / 不 push / 不打 tag / 不 checkout main；不碰主检出与其它 worktree（尤其 `rc-w4-markdown`）。

## 报告格式（最终消息，中文）

工单状态表（T1–T5）/ commit 清单 / 自测真实结论 / 探针表（C/D/F3 逐行，改前 vs 改后）/
快照代价的实测占比（对比 render 本身）/ framebench 全行 + `table-open` / 既有用例搬迁清单 /
偏差与取舍 / 未决问题 / 真机手测：未执行。
