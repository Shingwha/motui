# Spec audit-fixes · W2：Revisioned 正确性（D2；F2/F4/F5）
> ⏳ 待执行；前置：无；深读：`00-overview.md`（D2）+ `specs/2026-10-17-render-cost/00-overview.md`
> （其 D4 是同一决策的原始波次——本波是它的剩余 rollout）。
> 铁律：**先落复现测试（sealed 块上突变，此时应为红），再修**；docstring 承诺与快照必须一致。

## 目标

1. **F2**：`Dialog.revision()` 补全 render 实际读取的全部可变行输入，并稳定 body 快照。
2. **F4**：`Diff` 实现 `revision()`，"never a stale frame" 承诺由测试背书。
3. **F5**：`Tabs` / `NavList` / `Slider` / `ProgressBar` / `Collapsible` 补齐 `revision()`，
   sealed 块的 hover/focus/值突变全部落屏。

## 工单（按序；每项完成跑 `uv run pytest -q -p no:cacheprovider`；本波不 commit）

### T1 复现测试先行（此时应全红）

测试形状统一为：`headless_tui()` 建组件 → `tui.add(comp, id=...)` → `block.seal()` →
`block.rows(W)` 预热 → **突变** → `block.rows(W)` 与 `comp.render(W)` 逐行比对，不等即失败。
参照 `ref/probe_dialog_matrix.py` 的矩阵形状。

- Dialog：title / width / frame / shade / align 五个赋值，各一条（当前全红——这就是 F2）。
- Diff：sealed 块上 `diff.after = "..."` 后断言行进（当前红——F4）。
- Tabs：`hover_at` 移到另一标签、`focused` 翻转、`select()` 换活动项。
- NavList：同上三样。
- Slider：`hover_at` 进入/离开、`focused` 翻转、`value` 赋值。
- ProgressBar：`fraction` 赋值、`focused` 翻转。
- Collapsible：`hover_at` 标题行、`focused` 翻转、`open` 翻转、`title` 赋值。

### T2 `widgets/dialog.py`：修 `revision()`（F2）

- 通读 `render` **及其全部 helper**（`_top_row` / `_interior_row` / `_button_row`），列出真实行输入；
  已知五项：`title`、`width`、`frame`、`shade`、`align`（公开可变属性）。构造时解析的样式
  （`_border_style` / `_title_style` 等）若是公开可变属性也纳入；逐个核实后再定，别照抄本 spec。
- body 快照稳定性：当前 `tuple(map(id, self._body_rows))` 在首帧渲染前是空元组、每帧渲染后又变
  （新 Line 对象）——缓存键一次性漂移 + 每次渲染后必 miss。评估后二选一，并在 docstring 写明：
  (a) 改用 body 组件的 `revision()`（body 是 `Revisioned` 时）或其内容值；(b) 保留 id 元组但
  在 docstring 说明"每帧一次 miss 是设计代价"。优先 (a)。
- docstring：快照字段逐一说明"为什么是行输入"。

### T3 `widgets/diff.py`：实现 `revision()`（F4）

- 通读全部 setter：`before` / `after` / `context` / `numbers` / `theme`。
  **特别注意 `theme` 是 resolved-Theme setter（`:464`）**：检查它是否真正重新解析
  `_del_style` / `_ins_style` / `_hunk_style`（`:477-479` 只在 `__init__` 解析过一次）——
  若 setter 静默 no-op（赋值了 `_theme` 但不重解析样式），这是真 bug，一并修（setter 内重新解析），
  并在报告单列一节。
- 快照覆盖 render 读取的一切：两个文本、context、numbers、三个样式、以及任何 hover/focus 状态
  （通读 `render` 与 `_build` 自己列全）。
- docstring：把"never a stale frame"的承诺与快照字段对应起来。

### T4 `widgets/tabs.py` + `widgets/navlist.py`：`revision()`

字段：hover 标记（`_hover_index`）、`focused`、`active`、`disabled`、labels/tabs、
divider / bar 配置、全部构造时解析的样式字段。两个文件的 `move`/`select` 逐字重复**
不在本波范围**（D5）——只加 revision，不重构。

### T5 `widgets/indicators.py`：Slider + ProgressBar

Slider：`value`、`_marked`、`focused`、`minimum`/`maximum`/`step`、样式字段。
ProgressBar：`fraction`、`focused`、样式字段。（两个组件同一文件，各自的快照各自算全。）

### T6 `widgets/collapsible.py`：`revision()`

字段：`open`、`_marked`、`focused`、`title`、body 的 revision（body 是 `Revisioned` 时取其
`revision()`；否则沿用现有 body 行记忆键——docstring 写明策略与理由）。

### T7 全量回归

`uv run pytest -q -p no:cacheprovider` 贴总数（基线 1539/1，加本波新增）。

## 验收

1. pytest：总数、失败数、本波新增条数，全部贴真实输出
2. F2 五突变矩阵全绿：贴 `ref/probe_dialog_matrix.py` 改后输出（五行全 fresh）
3. 六个组件 sealed 块突变（T1 的每条）全绿
4. 每个改动组件的 docstring 与快照字段一一对应（自述清单）
5. `uv run python -m motui < /dev/null` exit 0
6. Diff.theme setter 的发现与处置（若动了，附测试）

## 禁触清单

- 只改：`src/motui/widgets/{dialog,diff,tabs,navlist,indicators,collapsible}.py` 与对应测试
  （先 `ls tests/` 确认组件测试的真实文件名与归属，只碰测这几个组件的文件）。
- 禁触：`kernel/`、`interaction/`、`app.py`、其它任何 widget、`docs/`、golden、
  `CHANGELOG.md`、`specs/`、`pyproject.toml`。
- 不 commit / 不建分支 / 不 push。

## 报告格式（最终消息，中文）

工单状态表（T1–T7）/ 每组件的快照字段清单（字段 + 为什么是行输入）/ 新测试清单（名字 + 断言什么）/
Diff.theme setter 专项发现 / 自测真实输出 / 偏差与未决。
