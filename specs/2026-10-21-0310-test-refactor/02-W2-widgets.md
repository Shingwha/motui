# W2 · widgets 测试重写

> 分支 `tests-w2-widgets`；前置 W0；写入范围 `tests/widgets/**`。

## 目标

把 widgets 的测试重写成**组件行为契约**：每个公开类的构造、render 形状、核心动词、结果语义、disabled/空输入边界。
最高约束：**不测缓存/revision 到达屏幕、不逐组件重复 hover/focus/disabled/glyph 宽度、不锁完整帧字符串**；`src/**` 零改动。

## 前置上下文

- 必读顺序：`00-overview.md` → `ref/repo-map.md` → `ref/interfaces.md` §1–§4。
- 基线命令：

```bash
cd C:/Users/shifu/.worktrees/motui/tests-w2-widgets
PYTHONPATH=$PWD/src C:/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python.exe \
  -m pytest -q -p no:cacheprovider tests/widgets
```

（开工时目录未建，先跑全量确认基线。）
- 稳定区：`tests/testing/**`、`src/**`、`tools/**`。
- 已知约束：见 `repo-map.md` §6。

## 工单（按序执行，每项一个 commit）

### T1 建目录与骨架

- `tests/widgets/__init__.py`；建目标空壳：
  `test_action.py test_autocomplete.py test_bands.py test_choice.py test_combobox.py
   test_containers.py test_data.py test_delegate.py test_dialog.py test_diff.py
   test_editing.py test_form.py test_indicators.py test_markdown.py test_menubar.py
   test_navigation.py test_rows.py test_scroll.py test_syntax.py`。
- 验证：`pytest --collect-only tests/widgets` 不报错。

### T2 输入与选择

- `test_editing.py`（Input/Editor/TextBuffer）：keymap 路由、插入/退格/删除/换行、undo/redo 与合并步、
  选择（shift 扩展/全选/替换）、render/cursor/placeholder/mask、click 放置、只读、max_rows 窗口。
  **删除**：逐行 rewrap 计数、`revision` 快照、逐 keymap 全表枚举、“one line rewraps exactly one line”这类实现断言。
- `test_choice.py`（Select/RadioGroup/CheckboxGroup）：cursor 移动/clamp/wrap、window+counter、
  click 映射、activate/take_result、disabled、group 行为；删逐 glyph 宽度与 `revision` 测试。
- `test_autocomplete.py`：过滤排序、move/window、click、set_query、结果。
- `test_combobox.py`：open/close、enter 取值、escape、paste、child_at、focus/click 委托。
- `test_action.py`（Button/Checkbox/Link）：render、hover/focus 合并、click/activate、disabled、结果；
  跨组件的 hover 标记测试收敛为 1 个参数化（Select/Tabs/Tree/Table 各 1 case，不再每个组件一套）。
- 删除旧文件：`test_widgets_editing.py`、`test_widgets_choice.py`、`test_widgets_autocomplete.py`、
  `test_widgets_combobox.py`、`test_widgets_action.py`。

### T3 数据视图与导航

- `test_data.py`（List/Table/Tree）：
  List：window/counter、move/activate、click 映射、prefix jump、marks、disabled/bands。
  Table：grid 宽度/缩列、cursor band、move/click/activate、sort、set_widths、marks、disabled。
  Tree：展开/折叠、visible rows、move/clamp、click 行映射、filter、disabled/bands。
  **删除**：sealed cache、revision 输入清单、`sort` 的逐内部实现断言（保留行为：按渲染文本稳定排序）。
- `test_navigation.py`（Tabs/NavList）：render active label、move/clamp/disabled、click 列→项、
  group row、unfocused 去指示器；代表性 glyph 参数化（2–3 case）。
- `test_menubar.py`：bar render/move/click/activate/disabled；ContextMenu 预设、点击挂载、结果。
- 删除旧文件：`test_widgets_list.py`、`test_widgets_table.py`、`test_widgets_basics.py`、
  `test_widgets_navlist.py`、`test_widgets_menubar.py`、`test_glyph_vocabulary.py`。

### T4 布局/容器/表单/装饰

- `test_containers.py`：Divider、Panel（borderless 降级）、Row/Column、Padding、Spacer、Collapsible
  （从 `test_widgets_forms.py` 并入）；**并入** `test_container_hit.py` 的 `child_at` 行为测试，
  删其中 `child_at reads the cache` / `re-render replaces cached geometry`。
- `test_form.py`：字段栈、label/error、gap、focus/navigation、values、validation、submit、child_at；
  删 `snapshot moves...` / sealed revision。
- `test_rows.py`：StatusLine/ShortcutBar/Notice 的核心布局与截断；删 mutable input + sealed 组合。
- `test_bands.py`：优先级矩阵、rest、frozen；保留 4–6 个。
- `test_delegate.py`：render/click/hover/child_at 转发、child swap；删 sealed cache/revision 测试。
- `test_dialog.py`：confirm/prompt、按钮导航、click、borderless、body+button 布局；删 sealed 输入到达屏幕。
- `test_indicators.py`：ProgressBar/Slider/Spinner 的核心渲染、clamp、click/activate、disabled；删 sealed 系列。
- `test_diff.py`：hunk/context/numbers/one-sided；删 sealed 赋值到达屏幕。
- 删除旧文件：`test_widgets_containers.py`、`test_container_hit.py`、`test_widgets_form.py`、
  `test_widgets_forms.py`、`test_widgets_rows.py`、`test_widgets_bands.py`、`test_widgets_delegate.py`、
  `test_widgets_dialog.py`、`test_widgets_indicators.py`、`test_widgets_diff.py`。

### T5 滚动 / Markdown / 语法

- `test_scroll.py`：固定高度裁剪、offset/clamp、scroll/reveal、keys、child_at、scrollbar 列；
  删 revision/snapshot/identity 测试。
- `test_markdown.py`：标题/段落/列表/引用/代码块/表格/分隔线/行内（粗斜删链）/任务列表/流式安全/
  链接点击/自定义规则/max_width；删 `render serves and invalidates its one entry cache`、
  `append-only growth reuses sealed prefix`、`streaming render matches whole render`（保留 1 个流式安全 smoke）。
- `test_syntax.py`：每语言 token 行、fence 高亮、alias/未知语言降级、主题色、自定义语言。
- 删除旧文件：`test_widgets_scroll.py`、`test_widgets_markdown.py`、`test_widgets_syntax.py`。

### T6 收口

- 全目录：`pytest -q -p no:cacheprovider tests/widgets`。
- `grep -R "\._[a-z]" tests/widgets` 0；`grep -R "sleep("` 0。
- 用例数落在 **240–330**。
- 写 `handoff/W2-widgets.md`。

## 验收

1. `tests/widgets` 全绿，贴数字。
2. 全量 pytest 0 failed。
3. diff 只含 `tests/widgets/**`、删除的旧文件、handoff。
4. 每个公开 widget 类至少一个行为测试；`ref/interfaces.md` §4 清单逐项覆盖。
5. 私有属性/sleep grep 为 0。

## 禁触清单

`src/**`、`tools/**`、`tests/golden/**`、`tests/testing/**`、`tests/__init__.py`、`tests/conftest.py`、
`tests/kernel/**`、`tests/keys/**`、`tests/app/**`、`tests/interaction/**`、根级 `tests/test_*.py`（除删除项）。

## 交接包

分支最后 commit 写 `handoff/W2-widgets.md`（A 自动事实 / B 取舍 / C 指针）。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 探索审计 / 未决问题。
