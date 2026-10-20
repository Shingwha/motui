# W4a handoff · 结果契约、action/choice/input/modal 与 P0

## A · 交付

分支 `w4a-components`；本 handoff 之前的实现 commit（按提交顺序）：

| commit | 内容 |
|---|---|
| `kernel: add the controller and resultful protocols -- handle consumes, take_result clears` | `Controller` / `Resultful`，kernel facade 导出 |
| `widgets: one-shot results for the action and choice families -- take_result, disabled and the group renames` | action/choice/autocomplete/combobox |
| `widgets: the text fields take text=, read_only and caret_style -- TextBuffer history reset` | textbuf/textfield/kernel Text |
| `widgets: container dialogs and collapsibles, a renderable spinner and markdown revision -- P0 fixes` | dialog/collapsible/indicators/markdown + Modal/Palette socket |
| `facade: export the renamed groups and prompt_dialog -- demo, docs and tests follow` | facade/demo/docs/tests + handoff |

`git diff --stat main...HEAD`（handoff 前）：47 files changed, 2079 insertions(+), 842 deletions(-)；
无 golden 文件、`docs/CONTRACT.md`、`pyproject.toml`、`uv.lock`、W4b 文件改动。

新增/变更公开签名（本波范围）：

```python
kernel: Controller.handle(event) -> bool; Resultful.take_result() -> object | None
Button/Checkbox/Link: take_result(); disabled; disabled_style
Checkbox: style/hover_style/focus_style/disabled_style; mark_pair=(MARKED, UNMARKED)
Link: Focusable + Activable
Select: cursor_text_style (was selected_style); select/home/end; disabled/disabled_items
RadioGroup (was Radio): active_style; take_result()
CheckboxGroup (was CheckGroup): click() toggles; take_result(); active_style
Autocomplete(options, ...): positional options; case-insensitive; set_query clears hover/result
ComboBox: take_result(); child_at(); focused/click delegate; revision()
Input(text="", *, ..., caret_style=None, read_only=False); Input.text setter
Editor(..., caret_style=None, read_only=False); TextBuffer.read_only/set_text
Text/Markdown/Dialog/Collapsible/Slider/ComboBox: take_result()
Dialog: focused_button; child_at(); Button.activate().take_result()
Spinner: Themed; render(width); revision()
Slider: minimum/maximum/step property setters; disabled
Markdown.revision(): text, max_width, task_marks, divider cap, gap, hover span/style
widgets facade: CheckboxGroup, RadioGroup, prompt_dialog
```

基线真实结果（Windows，HEAD 待提交 handoff）：

- `uv run pytest -q -p no:cacheprovider`：**1777 passed, 2 skipped**（基线 1742 + 35 新增）。
- `uv run python tools/golden.py --check`：`golden: 11 pages match`。
- `uv run python tools/framebench.py`：exit 0；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（未变）。
- demo：`python -m motui < /dev/null` exit 0 / 70 行；`--pages` exit 0 / 792 行。
- P0 grep（工单第 7 条）：零命中。

## B · 偏差、踩坑与约束

- **Modal/Palette 的 panel socket 必须一起改**：组件删除 `chosen` 后，`Modal._arm/_collect` 不再能
  向 panel 写 sentinel。改为 `take_result()`；需要区分“决策值就是 None”和“没有决策”的 panel 实现私有
  `_take_decision() -> (made, value)`（`Dialog` 和 `_PalettePanel` 都已实现）。`Modal.chosen` /
  `Palette.chosen` 仍是交互层的公开结果，W6 可决定是否迁到 `take_result()`。
- **golden 优先**：demo 的 `registry.py` / `notes.py` / `views.py` / forms caption 中出现的旧名
  （`Radio` / `CheckGroup` / `chosen`）是**渲染内容**，改动会移动 golden，故保持原文；代码侧
  （imports/构造/调用）已迁移。W7 重写 demo 文案时再统一。
- demo 的 kit/session 读取 pick 时先 `take_result()`，对仍只有 `chosen` 的 W4b 行视图保留
  `getattr(..., "chosen")` 回退；W4b 完成后删除该回退。
- `Input(text=...)` 构造后 cursor 停在 0（同 `Editor`）；测试 helper 再 `_park` 到末尾以保持旧语义。
- `read_only` 只拒绝 routed `handle`，程序化编辑仍允许（`TextBuffer.handle` docstring 写明）。
- `Select.disabled_items` 是 `frozenset[int]`（整体替换）；`move` 逐行跳过 disabled，`wrap=False` 时停在边界。
- W4b 必须遵守：`List/Table/Tree/Tabs/NavList` 仍用 `chosen`，**不要**把它们接进本波的
  `take_result` facade；`RowBands` 未动；`Controller/Resultful` 由 kernel 提供，别再定义第二份。
- 未决（无阻塞）：Palette/Modal 的 `chosen` 归属 W6；demo 文案旧名归 W7。
## C · 关键位置与稳定区

- `src/motui/kernel/block.py:145`（Controller）、`:163`（Resultful）；`kernel/__init__.py:73`。
- `src/motui/widgets/action.py:80`（Button）、`:197`（Checkbox）、`:320`（Link）。
- `src/motui/widgets/choice.py:151`（Select）、`:737`（RadioGroup）、`:852`（CheckboxGroup）。
- `src/motui/widgets/autocomplete.py:52`（set_query）；`combobox.py:150`（handle/child_at/revision）。
- `src/motui/widgets/textfield.py:143`（_TextField text/read_only）、`:655`（Input）、`:760`（Editor）。
- `src/motui/widgets/textbuf.py:355`（handle read_only）、`:525`（set_text）。
- `src/motui/widgets/dialog.py:240`（focused_button/_take_button/take_result）、`:345`（child_at）。
- `src/motui/widgets/collapsible.py:155`（take_result/child_at）。
- `src/motui/widgets/indicators.py:200`（Slider）、`:430`（Spinner）。
- `src/motui/widgets/markdown/component.py:840`（revision）；`kernel/lines.py:585`（Text take_result）。
- `src/motui/interaction/modal.py:298`（arm/collect）；`interaction/palette.py:120`（panel decision）。
- 稳定区（未触碰）：`widgets/{list,table,tree,tabs,navlist,layout,decor,rows,delegate}.py`、
  `kernel/{frame,viewport,painter,selection,theme,style}.py`、`app.py`、`keys/**`、
  `kernel/events.py`、`tests/golden/**`、`docs/CONTRACT.md`、`pyproject.toml`、`uv.lock`。
