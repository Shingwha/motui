# W2 · widgets handoff

> 分支 `tests-w2-widgets`；基线 `main`；写入范围 `tests/widgets/**` + 删除旧 widgets 测试 + 本文件。
> 所有命令均用主检出解释器、`PYTHONPATH=<worktree>/src` 运行。

## A. 自动事实

### A.1 文件与用例数（`pytest --collect-only` 实测）

| 文件 | 用例 |
|---|---|
| `test_action.py` | 15 |
| `test_autocomplete.py` | 13 |
| `test_bands.py` | 8 |
| `test_choice.py` | 41 |
| `test_combobox.py` | 10 |
| `test_containers.py` | 22 |
| `test_data.py` | 45 |
| `test_delegate.py` | 6 |
| `test_dialog.py` | 11 |
| `test_diff.py` | 8 |
| `test_editing.py` | 47 |
| `test_form.py` | 9 |
| `test_indicators.py` | 11 |
| `test_markdown.py` | 15 |
| `test_menubar.py` | 10 |
| `test_navigation.py` | 21 |
| `test_rows.py` | 10 |
| `test_scroll.py` | 11 |
| `test_syntax.py` | 12 |
| **合计** | **325**（目标 240–330） |

### A.2 门禁结果

- `pytest -q -p no:cacheprovider tests/widgets` → **325 passed**。
- 全量 `pytest -q -p no:cacheprovider` → **1766 passed, 2 skipped**（基线 2190 passed / 2 skipped；旧 widgets 750 例删除，新目录 325 例）。
- `grep -RIn "\._[a-z]" tests/widgets` → **0**（无私有属性读取）。
- `grep -RIn "sleep(" tests/widgets` → **0**。
- `grep -RIn "_doubles|motui\.demo|from motui\._" tests/widgets` → **0**。
- `git diff --name-only main...HEAD` → 只有 `tests/test_widgets_*.py`、`tests/test_container_hit.py`、`tests/test_glyph_vocabulary.py` 的删除、`tests/widgets/**` 与 `specs/**`；`src/**`、`tools/**`、`tests/testing/**`、根级保留测试零 diff。

### A.3 删除的旧文件（24 个，均 `git rm`）

T2：`test_widgets_editing.py` `test_widgets_choice.py` `test_widgets_autocomplete.py`
`test_widgets_combobox.py` `test_widgets_action.py`
T3：`test_widgets_list.py` `test_widgets_table.py` `test_widgets_basics.py`
`test_widgets_navlist.py` `test_widgets_menubar.py` `test_glyph_vocabulary.py`
T4：`test_widgets_containers.py` `test_container_hit.py` `test_widgets_form.py`
`test_widgets_forms.py` `test_widgets_rows.py` `test_widgets_bands.py`
`test_widgets_delegate.py` `test_widgets_dialog.py` `test_widgets_indicators.py`
`test_widgets_diff.py`
T5：`test_widgets_scroll.py` `test_widgets_markdown.py` `test_widgets_syntax.py`

### A.4 Commit 清单

| hash | message |
|---|---|
| `889500c` | tests: add the widgets test skeleton -- one file per component family |
| `7a58251` | tests: rewrite the input, choice and action widgets -- behavior contracts, no cache mirrors -- delete the five flat files |
| `7fb175e` | tests: rewrite the data, navigation and menu widgets -- windows, cursors and group rows |
| `52156ad` | tests: rewrite the containers, forms, rows and dialogs -- child_at and results, no sealed caches |
| `c893335` | tests: rewrite scroll, markdown and syntax -- visible rows, links and tokens |
| 本 commit | tests: close the widgets wave -- trim duplicates and record the handoff |

## B. 取舍

### B.1 删除的测试类型

- 缓存/revision/sealed 到达屏幕：`revision()` 断言、`block.rows()` 命中、sealed 前缀复用、append-only 复用、`cache hits`、`rewrap exactly one line`、`monkeypatch wrap_spans` 等全部删除。
- 逐字节全帧/全组件表：完整 `Line.segments` 全集只在少数代表性行为各留 1 个精确样例；其余断言行文本、行数、宽度上界、包含关系、样式字段。
- 迁移考古与 meta：`test_glyph_vocabulary.py` 整文件删除；`__all__` 名单、旧常量清单不在本波（由 W4 收口）。
- 重复路径：每个组件的 hover/focus/disabled/glyph 宽度不再各写一套；跨组件 hover 收敛为 `test_action.py::test_hover_at_marks_and_clears_one_row_across_components`（Select/Tabs/Tree/Table 各 1 case）；disabled 保留每组件 1 条“拒绝 + 仍渲染”；glyph 宽度保留每族 1 条代表（choice marker、List marker、NavList bar、Tree fold）。
- 平台无关伪测试、自测 helper、文档镜像、demo IA/protocol、pytest 内 golden：本目录不再出现。
- 旧 `test_container_hit.py` 的 `descend` 用例（kernel 协议）未迁入；归 W1/W3 的 kernel/interaction 契约，`child_at` 行为已并入 `test_containers.py`。

### B.2 收敛与参数化

- 共享 helper 只用 `from tests.testing import ...`：`key/press/paste/wheel/texts/Rows/many/Clock` 等，未在测试文件里重定义；未新增共享 helper。
- 同组件多 case 的参数化均 ≤20 case/函数；实际最大为 `test_choice.py` 的 4-case 参数化与 `test_data.py` 的多 case 表。
- 组件族文件对应 §3.2 映射：`test_data.py` 合并 List/Table/Tree；`test_navigation.py` 合并 Tabs/NavList；`test_containers.py` 合并 Divider/Panel/Row/Column/Padding/Spacer/Collapsible/child_at；`test_form.py` 只保留 Form/Field。

### B.3 保留的核心契约

- 每个公开 widget 类至少 1 条行为测试（含 `ButtonSpec`、`Option`、`TreeNode`、`RowBands`、`confirm_dialog`、`prompt_dialog`）。
- Editing：keymap 路由、insert/backspace/delete/newline、undo/redo 合并步与 100 步上限、选择替换、只读、prompt/placeholder/mask、max_rows 窗口、click/cursor_position。
- Choice/Data：cursor clamp/wrap、window+counter、click 行映射、activate/take_result 一次性、sort_by 稳定性与记录跟随、marks、disabled items、group rows。
- Containers/Form：child_at（Row/Column/Padding/Panel/Collapsible/Form）、校验错误回写、submit 映射与 on_submit 一次、字段值提取。
- Dialog/Indicators/Diff：confirm/prompt、danger 默认焦点、click 按钮、无框模式；fraction/value clamp、slider click/track；hunk/context/elision/numbers/单边 diff。
- Scroll/Markdown/Syntax：clip/offset/reveal/scrollbar、link click/hover、task action、流式前缀安全、max_width、内置语言 token/alias/未知降级/自定义语言。

### B.4 精确数字与偏差

- 目标区间 240–330，实际 325：先写全行为后一次性裁掉重复/低价值用例（editing 58→47、choice 50→41、data 51→45、navigation 25→21 等），未删核心行为。
- `tests/widgets` 全绿 0 failed；全量 0 failed；无 skip/xfail/TODO。
- 未改 `src/**`、`tools/**`、`tests/testing/**`、根级保留测试；未 merge/push/建 venv。

## C. 指针

- 新测试目录：`tests/widgets/`（19 个文件 + `__init__.py`）。
- 需要共用能力时：`tests/testing/`（本波只读；未发现必须新增的 helper）。
- 旧映射与必须覆盖清单：`specs/2026-10-21-0310-test-refactor/ref/interfaces.md` §3.2 / §4。
- 视觉字节仍由 `tools/golden.py --check` 独立把关；本波没有逐字节全帧断言。
- 未决/交接给后续波次：
  - `descend` 的嵌套容器行为（kernel 契约）留给 W1/W3。
  - Dialog 的 Modal 居中/scrim/focus trap 归 W3 的 `tests/interaction/test_modal.py`；本目录只测 Dialog 自身。
  - Table 的 sticky header 作为真实 pinned row 的集成归 W3/W4；本目录只测 `header_line` 与 grid 的字节一致。
  - `tests/test_invariants.py`（W4）仍应覆盖全部公开组件 × 边界宽度；本目录只做各组件自己的宽度边界。
