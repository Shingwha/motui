# Spec render-cost · W1：行缓存内核（波次 W1）

> 分支 `rc-w1-row-cache`（worktree `C:\Users\shifu\.worktrees\mocode-tui\rc-w1-row-cache`）；
> 前置：无；深读：`00-overview.md`（D1–D13 是权威契约）、`ref/facts.md`、`ref/probe.py`。
> **本波是整个组的地基**：后面三波都在用你落的 `Revisioned` 与 `Block.rows`。

## 目标

把"每帧重渲未变的块"这条根切断：行缓存从 `Viewport` 搬到 `Block`（键含修订令牌），
全仓所有"走块拿行"的路径共用它；`Text`（29 ms/帧）与三个动作原语先吃上；
顺带修好 **sealed 块的 hover 不落屏**。

## 工单（按序执行，每项一个 commit，每个 commit 独立跑一遍 `uv run pytest -q`）

### T1 `kernel/block.py`：`Revisioned` 协议 + `Block.rows(width)` 缓存（D1/D2/D3）

- 加 `Revisioned`（`runtime_checkable` Protocol，与 `Clickable`/`Hoverable` 同一层）：
  `def revision(self) -> object` —— 文档写明契约：**行的全部输入的值快照，相等 ⟹ 同宽下行相等**；
  必须是值语义（可变字段要拷贝）、必须 ≪ 它守的 render。
- `Block` 加 `rows(width) -> list[Line]`：命中返回行的拷贝（调用方拥有列表，行对象本身不可变可共享）；
  键 = `(width, revision)`；`revision` 来自组件（无协议 → `None`）。缓存槽进 `__slots__`。
  缓存规则（D2）：SEALED 一律缓存；OPEN 仅当组件 `Revisioned` 才缓存。
  `Block.render(width)` **保持原义**（直通组件）——它是"我要新鲜行"的门。
- `Block.seal()` 语义不变；缓存随 Block 生灭（不需要 prune）。

### T2 `kernel/viewport.py`：改用 `Block.rows`，删掉自己那套缓存（D1）

- 删 `_cache`/`_cache_width`/`_prune_cache`/`_block_rows`；布局逐块调 `block.rows(width)`。
- **`tests/test_viewport.py:175-196` 的调用计数断言必须一行不改继续绿**（sealed + 无 revision
  的组件 → 同宽度只渲一次；换宽度重渲一次）。`natural_height` 同样走 `block.rows`。

### T3 `kernel/lines.py`：`Text` 的记忆与修订（D4/D5）

- `Text._revision()`：默认返回 `(self.text, self.style, self._hover_span, self._hover_style)`
  ——可覆写的子类接缝（返回 `None` 即关闭缓存；子类加自己的状态）。docstring 写明。
- `render(width)`：`(revision, width)` 与缓存一致时返回缓存行的拷贝（无 hover span 时直接返回；
  hover span 仍在**拷贝**上合并，缓存里的行保持 hover-free——`_rows` 的"上次渲染命中表"语义不变）。
- 子类 `_rows_for` 的行为不变；默认行逐字节不变。

### T4 `widgets/{button,checkbox,link}.py`：动作原语的 `revision()`（D4）

- 三个各加 `revision()`，返回自己的可见状态快照（`hover` + 标签/label 文本 + 会影响行的样式字段）。
  这几条很便宜，别过度设计：目标是"hover 改了就能落屏"。

### T5 五处"裸 `block.render(width)`"改走 `Block.rows(width)`（D1）

`app.py`（`reveal`/`_body_address`，两处 + 让"已在窗口内"的判断提前）、
`interaction/search.py`（`_recompute` 的逐块循环）、`kernel/selection.py`（`extract` 的逐块循环）、
`interaction/gesture.py`（`_walk` 与双击的 `block.render`）。
每一处都要确认：取到的行与今天**逐字节相同**（sealed 块从缓存取，OPEN 且无 revision 的组件
仍走直通——行为不变）。

### T6 `tools/framebench.py`：新增 `text-open` 行（D12）

- 只加不改：新行 = 一个 3000 行 OPEN `Text` 块，一次 `paint()` 的 ms/frame；输出格式与既有行一致。
- 在工具 docstring 的基线段落追加一小段：本波新增该行的理由与改前/改后数字。
- **不许动** `render-hash` 与既有四行的负载。

### T7 测试与产物

- 更新被契约逼着改的既有用例（预计：`tests/test_viewport.py` 的缓存归属描述、
  `tests/test_selection.py:216` 附近、`tests/test_block.py` 若断言了 slots）。
- 新增 ≤ 4 条：`Block.rows` 的 sealed/OPEN×revision 四象限行为（一条覆盖）、
  `Text` 记忆命中与失效（改 text / 改 width）、sealed `Button` hover 落屏（探针 F1 的断言版）、
  `reveal`/`extract` 不再重渲（调用计数）。
- `uv run python tools/apidoc.py --write`（docstring 动了就重生成）；golden **不重录**（`--check` 绿）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q`（基线 1407 passed / 1 skipped → 贴改后总数）
2. `uv run python tools/golden.py --check`（**不许** `--update`）与 `uv run python tools/apidoc.py --check`
3. `uv run python tools/framebench.py`（六行 + `text-open`；`render-hash` 必须仍是 `de48e747…`，
   `replay` 如实）
4. `%TEMP%\rc_probe.py`（`ref/probe.py` 的拷贝）：A–I 全表 + F1/F2 两条 hover 回归
   （**F1/F2 必须 True**；F3/F4 仍 False 是正常的，那是 W2/W4 的活）；B 行 ≤ 1 ms、F 行 ≤ 0.1 ms@1000
5. `uv run python -m motui < /dev/null` exit 0
6. `git status --porcelain` 干净 + `git log --oneline main..HEAD`

## 禁触清单

- 只改：`src/motui/kernel/{block,viewport,lines,selection}.py`、`src/motui/app.py`、
  `src/motui/interaction/{search,gesture}.py`、`src/motui/widgets/{button,checkbox,link}.py`、
  `tools/framebench.py`（只加 `text-open` 段）、`docs/API.md`（仅 `--write` 生成）、
  `tests/{test_viewport,test_selection,test_block,test_core_text}.py`。
- 禁触：`src/motui/kernel/{frame,painter,screen}.py`、`chrome.py`（W3 的）、
  `src/motui/widgets/**` 的其它文件（`table.py`/`field.py`/`textbuf.py`/`markdown/**`/`decor.py`/
  `layout.py`/`collapsible.py`/`syntax.py` 是 W2/W4 的）、`docs/COMPONENTS.md`、`docs/DESIGN.md`、
  `README.md`、`CHANGELOG.md`（W5 的）、`specs/**`、`pyproject.toml`、其它测试文件。
- 不 merge / 不 push / 不打 tag / 不 checkout main；不碰主检出与其它 worktree（尤其 `rc-w3-compose`）。
- 渲染字节零变化：golden 不许重录，意外字节移动 = 停下报告。

## 报告格式（最终消息，中文）

工单状态表（T1–T7）/ commit 清单（hash + message）/ 自测真实结论 / 探针表（改前 vs 改后逐行，
含 F1/F2）/ framebench 六行 + `text-open` / 既有用例搬迁清单（哪条、为什么、新期望）/
偏差与取舍 / 未决问题 / 真机手测：未执行。
