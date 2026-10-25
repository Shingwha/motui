# W2b2 交接 · 编辑/内容族迁移到 Surface

> 分支 `2.0/w2b2-content`；起点 `01a5148`（W2a 合并 `fddbf93` 之后的 spec 排序）。前置：`ref/interfaces.md`、`handoff/W2a-surface.md`。
> 结论：T1–T7 全部完成；**1066 collected / 1058 passed / 8 failed**，8 个失败全部来自 `app/command_palette.py:110` 的一处 `+`（禁触的 `app/**`，lead 决定本波不改）；57 golden 与 render-hash 逐字节不变。

## A. 交付面与门禁

### 迁移清单（全部 `render(self, c: Constraints | int) -> Surface`）
- `widgets/action.py`：`Button`(161) / `Checkbox`(291) / `Link`(415)
- `widgets/collapsible.py`：`Collapsible`(234)
- `widgets/form.py`：`Form`(255)；`widgets/dialog.py`：`Dialog`(426)
- `widgets/textfield.py`：`_TextField`(511)（`Input`/`Editor` 共用；`textbuf.py` 零 diff）
- `widgets/combobox.py`：`ComboBox`(307)
- `widgets/autocomplete.py`：`Autocomplete`(103)，委托 `Select.render(int)` 的薄包装
- `widgets/indicators.py`：`ProgressBar`(110) / `Slider`(398) / `Spinner`(507)
- `widgets/diff.py`：`Diff`(583)
- `widgets/markdown/component.py`：`Markdown`(822)
- `widgets/syntax.py` 无 render（见 B.3）

统一模式：`as_constraints` 归一；内部/子组件仍收 `int`；`c.max_height is not None` 时截断组装后的 rows；返回 `Surface.clipped(rows, c.width)`（只裁不补）。memo/revision/child_at/编辑几何/高亮/markdown 缓存键均按 width，不乘 max_height。

### 契约细节
- 每个迁移类都有 `render(n) == render(Constraints(width=n))` 的测试（逐族，n 为该族代表宽度）。
- `max_height=0` 一律返回空 `Surface`；单行组件在 `max_height=1` 时保留原行。
- 截断只作用于返回值；hover/click/child_at 读的表来自未截断的缓存（见 B.5）。
- `Input`/`Editor` 的 `_buf.last_width` 在零预算渲染时也种子化，点击映射不因预算失效。
- 视觉零变化：57 golden 逐字节不变，`render-hash` 相同；新增 `Surface.clipped` 不补空格。

### 门禁实测（2026-10-25，本 worktree）
- `pytest -q -p no:cacheprovider`：**1066 collected, 1058 passed, 8 failed**（+21 新用例：T1 2 / T2 5 / T3 3 / T4 2 / T5 3 / T6 3 / T7 3）。8 个失败 = `tests/app/test_command_palette.py` 7 个 + `tests/test_smoke.py::test_the_piped_entry_replays_and_dumps`，同一行异常。
- `tools/golden.py --check`：`57 topics match`；`framebench`：`render-hash a82f7968…` 不变。
- `python -m motui --pages`：exit 0 / **4059 行**；`python -m motui < /dev/null`：**exit 1 / 48 行**（同一个 seam）。
- grep `def render(self, width` 于 11 个工单文件 + `markdown/`：空（exit 1）。
- `ruff check .` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept / 0 broken；`tools/api.py --check` 179 names match；`growth.py --quick` pass/pass/OK。
- W2a 适配器：把 6 个迁移类 `doc.add()` 后 `section.rows(40)` 得 9 行，全部新式 `Surface`；`inspect.signature(Input.render)` 为 `(self, c: 'Constraints | int') -> 'Surface'`。

## B. 偏差、取舍与坑

1. **唯一红门禁：`app/command_palette.py:110`** `return self.input.render(width) + self.list.render(width)`。`Input` 与本波 `Autocomplete` 都返回 `Surface`，`+` 不再成立；W2c 的一行修法：`return [*self.input.render(width), *self.list.render(width)]`。lead 已决定本波不破例改 `app/**`，所以 8 个失败与 piped demo 是**已知、单一、非本波文件**的问题；修掉后预计 1066 passed / 70 行（未验证，未改禁触文件）。
2. **Autocomplete 的 render**：`autocomplete.py` 本身没有 render（继承 `Select`，属 W2b1）。为满足 T4 与验收 grep，加了薄覆盖：`list(super().render(c.width))` + 截断 + `Surface.clipped`；W2b1 把 `Select.render` 改为 Surface 后仍兼容（`list()`/迭代均可）。
3. **syntax.py 无 render**：`Highlighter.highlight() -> list[Line]` 是规则层的行源，不是 Component；未改签名。`test_syntax.py` 固定“高亮器不是组件”的事实，Markdown 侧另测 Constraints 消费。
4. **markdown 规则层签名不动**：`blocks/nested/tables` 的 `render(lines, width, ctx) -> list[Line]` 是内部装配函数（`_BlockScan` 逐块 extend），不是组件入口；`Divider`/`Table` 子调用仍传 int。仅 `Markdown.render` 迁 Constraints。
5. **几何表均保持未截断**（W2a 容器先例）：Collapsible `_body_count`、Form `_spans`、Dialog `_body_rows/_hit`、ComboBox `_last_count`、TextField `_buf.last_width`。`max_height` 只裁返回值。
6. **memo/cache 键不含 max_height**：`_TextField`（width+revision）、`Diff`（width+theme+styles）、`Markdown`（text+clamped width）、Collapsible body memo（行 id+width+indent）、Slider `_last_width`。
7. **Surface 不是 list**：两个旧断言改成 `list(...)`（`test_form.py` 的空表单、`test_diff.py` 的 identical texts）；其余测试用迭代/索引，int 调用无需改（W2c codemod）。
8. **`Markdown._rows`** 仍记未截断的基础行（本波无读者；`_acts` 保持全量命中表）。
9. **Demo 行为**：`--pages` 正常；默认入口在退出前的 modal paint 命中同一 seam（traceback 停在 `command_palette.py:110`），不是迁移逻辑错误。
10. **W2a 适配器**：`Section._render_takes_constraints` 按类识别参数名 `c`，本波 10 个类全部走新式分支；旧式测试双打仍走 `render(width)` 旧式分支，两式在 `section.rows()` 下都返回 Lines。
11. **测试写法**：旧用例继续传 int（W2c 再统一 codemod）；只有新增用例显式构造 `Constraints`，带 `max_height` 的断言集中在各族末尾。

## C. 位置与 commit

- 源码：`src/motui/widgets/{action,collapsible,form,dialog,textfield,combobox,autocomplete,indicators,diff}.py`、`src/motui/widgets/markdown/component.py`（行号见 A）。
- 测试：`tests/widgets/{test_action,test_containers,test_dialog,test_form,test_editing,test_combobox,test_autocomplete,test_indicators,test_diff,test_syntax,test_markdown}.py`。
- commit：
  - `c297a18` widgets: render buttons, checkboxes and links into surfaces
  - `e847689` widgets: render collapsibles, forms and dialogs into surfaces
  - `1a62453` widgets: render input and editor rows into surfaces
  - `f53a7f1` widgets: render comboboxes and autocomplete rows into surfaces
  - `5b370b7` widgets: render progress, slider and spinner rows into surfaces
  - `e063939` widgets: render diff rows into surfaces
  - `0ae1a8b` markdown: render documents into clipped surfaces under constraints
  - 本文件（最后一个 commit）
