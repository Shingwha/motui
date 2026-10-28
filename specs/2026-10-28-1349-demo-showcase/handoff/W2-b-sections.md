# handoff · W2-b sections：Components 游乐场 + Layout 实操

> 分支 `dm-w2b-sections`，worktree `C:\Users\shifu\.worktrees\mocode-tui\dm-w2b-sections`。
> **分支基点是 main `1468820`（W2-a 合入之前）**：本分支开工前已存在并带着前任未提交的
> 现场，红线禁 merge，故未并入 W2-a。波末全量 `uv run pytest -q` = **1649 passed**
> （= 本分支基线 1646 + 本波 3 条新测试；与工单口径 1650 的差 4 = W2-a 的 PixelCanvas
> 测试，回 main 合并时自然对齐，无文件冲突面）。`uv run ruff check` 零告警，
> `tools/semantic.py --check` = 10 场景 match，`tools/api.py --check` = 197 名（本分支基线，
> 未动登记册）。环境 `uv run python --version` = **3.13.16**。
> 两节 `render_scene` 两次调用逐字一致已验（100x30、phase 0 与 13，`diff` 空）。

## A · 文件地图与公开对象

### A.1 `src/motui/demo/sections/components.py`（485 行）——`ComponentsScene`

- 公开对象：`ComponentsScene`（`name = "components"`，实现 Scene 协议；escape → `"menu"`、
  q → `"quit"`，但 Input 持焦时 q 是输入）。
- 帧结构（自上而下）：标题行 → Tabs strip 行（整宽）→ `Row`（左 `Panel("widgets")`
  装 `Column`，右 `Panel("the whole story")` 装 `_CodeView`）→ toast 行 → 键位提示行；
  modal 时 `Dialog` 居中 overlay 盖在整帧上。
- 内部类 `_CodeView(Widget)`：render-only 代码块，`lines` 每帧由场景重建。
- 状态：`_tab`（页）、`_focus`（页内目标序号，0 恒为 strip）、`_sort_col`（-1 = 未排序）、
  `_modal`、`_toast: (text, issued_phase, level) | None`、`_dialog_rect`（点击命中用）。
- 键位：`tab`/`s-tab` 页内轮焦；strip 持焦时箭头切页；`enter`/`space` 激活 Button/Checkbox、
  激活表格行；`s` 表格排序循环（逐列 asc，末列后再按回未排序）；modal 内键进 Dialog，
  escape/enter/选项值即 resolve；按钮 → toast（save）或 modal（confirm），Dialog resolve → toast。
- 确定性：全场景唯一相位消费是 toast 倒计时（`_TOAST_TICKS - (phase - issued)`，纯整数），
  ●○ 五格衰减；无墙钟、无随机。
- 代码面板：`_snippet()` 每帧回读控件 live 值（Input 文本、RadioGroup index、Checkbox
  checked、Slider 值、表格排序态），`RegexHighlighter.highlight(text, "python")` 高亮，
  聚焦控件对应的行并 `Style(bold=True)`。

### A.2 `src/motui/demo/sections/layout.py`（420 行）——`LayoutScene`

- 公开对象：`LayoutScene`（`name = "layout"`；escape → `"menu"`、q → `"quit"`，无点击）。
- 四个 drill，数字键 `1`-`4` 切换：
  - **split**：双 Pane 分宽，sash 状态 `_split`（0-24 步），←→ 移动，两 Pane 报告实得列数；
  - **dock**：↑↓←→ 把 dock 条钉到 north/south/west/east，自由区报告剩余几何；
  - **scroll**：`Editor(_LONG_CODE, wrap=OVERFLOW)` 进 `ScrollPanel(axis="both")`——
    原 examples/code.py 的故事：一条超长行（harbour master 句尾）可滚到尾；
  - **wide table**：10 列 manifest（自然网格 ~120 列）进 `ScrollPanel(axis="x")`——
    原 examples/wide_table.py 的故事：←→ 走到最后一列（outcome "on schedule"）。
- readout 行回读 ScrollPanel live geometry（`offset/total`），数字即像素；无动画无钟，
  新场景逐字重放。

### A.3 `src/motui/demo/sections/__init__.py` 接线

- `_PLACEHOLDERS` 只剩 `terminal`、`themes`（W3-b 接手；全部迁完可删 `placeholder.py`
  连同 `_PLACEHOLDERS`，沿 W1-b B.3）。
- `_scenes()` 注册 `ComponentsScene(theme)` / `LayoutScene(theme)`；SCENES、瓷砖、
  golden 工具、`--pages` 全自动跟随（实际已验）。

### A.4 golden 清单（`tests/golden/semantic/`，仍 10 个）

| 文件 | 动作 | 原因 |
|---|---|---|
| `components.txt` | 重录 | 占位面板 → 游乐场真帧（tabs + 左控件右代码 + toast/hint 行） |
| `layout.txt` | 重录 | 占位面板 → split drill 首帧（双 Pane + readout/hint 行） |
| 其余 8 个 | **零变化** | 本波只重录两节；`--check` 全绿且 `git status` 仅这两个 golden modified |

### A.5 测试（`tests/test_demo_shell.py`，本波净增 3 条，≤4 红线内）

1. `test_the_components_playground_drives_and_replays_deterministically`——固定键脚本
   （切页×2 → tab×2 → enter 开 modal → esc 关）两次逐字一致 + modal resolve toast 落地。
2. `test_the_components_controls_answer_their_keys`——`s`×3 排序到第 3 列且行序真变
   （bergamot 0.31 在 cherries 0.95 前）；再切 overlays 页 enter 触发 save toast。
3. `test_the_layout_drills_reach_both_ends_and_replay_deterministically`——wide table
   滚到 `x_offset` 顶到右缘、长代码 60×4 列滚到右缘，两帧两次逐字一致，长行句尾
   与末列 "on schedule" 可见。
4. `tests/test_demo_scenes.py` 零修改，16 条仍绿。

## B · 机制与接手点

### B.1 控件盘点结论（工单要求"先盘点再设计"）

`motui.widgets` 实际导出 43 名：Autocomplete Button ButtonSpec Canvas Checkbox
CheckboxGroup Collapsible Column ComboBox ContextMenu Dialog Diff Divider Editor Field
Form Input Link List Markdown MenuBar MultiSelect NavList Notice Option Padding Panel
ProgressBar RadioGroup Row ScrollPanel Select ShortcutBar Slider Spacer Sparkline
Spinner StatusLine Table Tabs Text Tree TreeNode Widget。

- 没有 `Choice` 这个名字——单选组即 `RadioGroup`（choice.py），游乐场用它。
- 游乐场选用：Input / RadioGroup / Checkbox / Slider（inputs 页）、Table（data 页）、
  Button×2 + Dialog（overlays 页），Tabs 三页分组——全部是现存控件，零新控件。
- toast 未用现成 `Notice`：场景自绘一行（级别 glyph + 文案 + 相位倒计时段），
  与壳层 StatusLine 互不纠缠，且倒计时天然走整数 phase 纪律。

### B.2 接续现场（前任 vs 接续者的活，commit 划分依据）

- **前任（全部未提交，本波第一个 commit 承载）**：`components.py` / `layout.py` 全文、
  `sections/__init__.py` 接线、两个 golden 重录、`test_demo_shell.py` +3 条——完成度
  约 95%，设计与实现质量良好，**全部保留，未推倒**。
- **接续者**：修前任测试代码的 4 处 ruff（E741 `l`×2 → `row`；RUF059 `wide2`/`code2`
  未使用 → `_` 前缀）；全量验收（pytest/ruff/semantic/api/--pages/确定性 diff）；本
  handoff；两个 commit。

### B.3 踩坑

1. **分支基点旧于工单口径**：`dm-w2b-sections` 切自 `1468820`（W2-a 之前），pytest
   1649 而非 1650，api 197 而非 198。差值恰 = W2-a 的 4 条测试 + 1 个登记名。红线
   "不 merge" 按最严解读执行（未把 main 并进本分支）；两波改动文件面零交集，合并无冲突。
2. `Tabs.on_key` 箭头在两端**钳位不回绕**（实测 right×3 停在末页）：components 测试的
   "page → overlays" 连按两次 right 依赖这一点；W3-b 若做节内 Tabs 注意同语义。
3. modal overlay 的地面必须 `row.fill(width)` 造出真 Segment——从 bare blank `Line`
   cut 出来的行接 Dialog 会丢 pad（前任在 `_overlay` 注释里留了案底，实测成立）。
4. `kernel.cell.Line` 不可迭代、不加 tuple（W1-b 坑 2 沿用）；两文件全部先拼
   segments 再 `Line(...)`，`Line + Line` 拼行、`cut_line` 切列。
5. 每节行数超工单 150–350 带（components 485 / layout 420，含 docstring）：判断为
   前任"左控件右代码 + 三页共用一套控件实例 mount"设计的自然体量，验收门禁全绿，
   未为凑行数砍功能。
6. `--pages` 两节内容完整性、`render_scene` 两次逐字一致（phase 0/13，`diff` 空）均已
   实测，证据见最终报告。
