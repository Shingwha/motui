# W7a handoff · demo 整体重构（master–detail 组件浏览器）

## A · 交付

分支 `w7a-demo`；实现 commit `707f067`（本文件所在 commit 为 handoff）。

**新 IA（6 sections / 58 topics）**

| section | topics | 数量 |
|---|---|---|
| overview | `welcome` | 1 |
| components | Text: text, markdown, diff, notice · Forms: input, editor, checkbox, radio-group, checkbox-group, select, combobox, autocomplete, slider, form · Data: list, table, tree, tabs, navlist, progress, spinner · Layout: row-column, padding-panel, divider, collapsible, spacer, scroll-view, delegate · Actions: button, link, menu-bar, context-menu · Overlays: dialog, modal, palette, toasts, tooltip, stats | 38 |
| interactions | focus, pointer, selection, find, scrollbar, modal-stack, dispatch | 7 |
| styling | theme-tokens, custom-theme, glyphs, row-bands | 4 |
| patterns | streaming-markdown, form-validation, command-palette, own-shell | 4 |
| reference | api-layers, keymap, component-matrix, non-goals | 4 |

每个 topic 由 `TopicBuilder` 固定模板：title → summary → Divider → `Panel("preview")` →
可选 `Panel("variants")` → 可选附加块 → `Try:` 一行 → `API:` 一行 → 可选 Echo；上限 8 块。

**组件覆盖（topic → 公共类）**：text=Text；markdown=Markdown；diff=Diff；notice=Notice；
input=Input；editor=Editor；checkbox=Checkbox；radio-group=RadioGroup/Option；
checkbox-group=CheckboxGroup/Option；select=Select/Option；combobox=ComboBox/Modal/Button；
autocomplete=Autocomplete/Option；slider=Slider；form=Form/Field/Input/Checkbox；
list=List；table=Table；tree=Tree/TreeNode；tabs=Tabs；navlist=NavList；progress=ProgressBar；
spinner=Spinner；row-column=Row/Column；padding-panel=Padding/Panel；divider=Divider；
collapsible=Collapsible；spacer=Spacer；scroll-view=ScrollView；delegate=Delegate/Button/Link；
button=Button；link=Link；menu-bar=MenuBar；context-menu=ContextMenu/Modal/Button/Option；
dialog=Dialog/ButtonSpec/Button/Text/Input；modal=Modal/Dialog；palette=Palette；
toasts=Toasts；tooltip=Tooltip/Button/Link/Checkbox；stats=Stats/Button/Notice。
interactions 覆盖 FocusManager/Pointer/SelectionGesture/Find/Scrollbar/Modal；styling 覆盖 RowBands；
patterns 覆盖 Palette/CommandRegistry/ShortcutBar/StatusLine；`motui.widgets.__all__` 全部类由测试断言。

**golden 新旧统计**：旧 `tests/golden/pages/*.txt` 11 个（actions, forms, layout, modals, notes,
overview, shell, streaming, text, themes, views，已全删）→ 新 `tests/golden/topics/<section>--<topic>.txt`
58 个；每帧 71 行（70 行屏幕 + 1 行 trailing newline），LF 写入。

**真实自测（worktree 根）**

- `uv run pytest -q -p no:cacheprovider`：**2178 passed, 2 skipped**（基线 1942；新增 demo 测试 237 项）。
- `uv run python tools/golden.py --check`：`golden: 58 topics match`。
- `uv run python tools/framebench.py`：exit 0；render-hash 旧 `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`，新值**相同**；`replay` 315–343 ms。
- `uv run python -m motui < /dev/null`：exit 0，70 行，首屏 header + `Welcome`，终帧为 welcome（theme violet）。
- `uv run python -m motui --pages`：exit 0，4130 行；58 条 topic header + 6 条 section header。
- `grep -rn "Page(\|PageBody\|Exhibit\|CheckGroup\|\bRadio\b" src/motui/demo`：0 命中（exit 1）。
- `git diff --stat main...HEAD`（实现 commit）：108 files changed, 7954 insertions(+), 4597 deletions(-)；
  路径全部在 `src/motui/demo/**`、`tools/golden.py`、demo/golden 测试、`tests/golden/**`、`README.md`。

## B · 偏差、取舍与约束

- **topic 数 58 而非工单的 35–45**：工单的组件 topic 表逐项列出 38 个组件 topic，ASCII catalog 也把
  Input/Editor/Checkbox/RadioGroup 画成独立行；若压到 45 必须删掉这些具名 topic。以显式 IA 表为准，
  测试 `test_demo_model.py::test_the_topic_table_is_the_work_orders_ia` 锁定每 section 的 key 顺序。
- **render-hash 未变化**：验收 3 假设 demo 在 hash 路径上，但 `framebench.hash_workload` 只组合
  HeadlessScreen + Scrollbar + 两个 Markdown + split/scroll；demo 不在其路径，且红线禁止改 framebench。
  因此如实报告旧值 = 新值，而不是为了“变化”改基准。
- **dispatch 顺序调整**：pointer 在 gesture 之前（stationary click 后补一次 gesture release 清理）。
  否则 selection gesture 会吞掉 header dock 的点击，MenuBar 无法点击切换 section。
- **host wrapper 是文档配方**：ComboBox 需要 `_ComboHost`（combo.handle 先于 Modal 并同步开合），
  ContextMenu 需要 `_MenuHost`（Select 没有 handle，host 路由 up/down/enter）。未改库。
- **初始多选不是 pick**：CheckboxGroup(marked=...)、Select(multi=True) 构造期有 pending，
  build 时调用 `take_result()` 清掉，避免首帧 inspector 出现伪 pick。
- **catalog 键盘滚动**：catalog 在 70 行回放几何下 44 行全部可见；更矮终端只能靠点击/滚轮
  （wheel 属于 focused pane）。`esc` 把焦点还给 catalog widget，不切 pane。此为已知限制。
- **header 无 “motui studio” 品牌字**：按工单正文“MenuBar + right theme”实现，ASCII 的品牌字未做。
- 未修改 `kernel/keys/widgets/interaction/app.py/pyproject/uv.lock/docs/**/specs/**`（handoff 除外）；
  无 merge / push / tag / checkout main，未碰主检出或其他 worktree。

## C · 关键位置与稳定区

- 模型与模板：`src/motui/demo/model.py`（Section/Topic/TopicBody/Report）、`stage.py`（TopicBuilder/Echo/walk_objects）。
- 注册表：`registry.py`（SECTIONS/TOPICS/TOPICS 顺序、BY_KEY、GROUPS、topics_for）。
- 会话与 shell：`session.py`（导航、palette、find、theme、stats、drag copy、模态结果）、`shell.py`（Header/MenuBar、catalog、footer）。
- topic：`topics/overview.py`、`components_{text,forms,data,layout,actions,overlays}.py`、`interactions.py`、`styling.py`、`patterns.py`、`reference.py`。
- 入口/回放：`__init__.py`（render_topic / --pages / piped）、`script.py`（Anchors + 全链路 replay）。
- 工具/测试：`tools/golden.py`、`tests/test_demo_model.py`、`test_demo_topics.py`、`test_demo_protocol.py`、`test_golden_frames.py`、`tests/golden/README.md`。
- 稳定区（未触碰）：`kernel/**`、`keys/**`、`widgets/**`、`interaction/**`、`app.py`、`docs/**`（README 除外）、
  `pyproject.toml`、`uv.lock`；无兼容 alias、无旧 page 名。
