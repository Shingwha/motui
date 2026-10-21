# W6 交接包（lead 收尾）

> 分支 `main` / 起点 `60615d6` 之后 / 2026-10-21

## A. 自动事实

- 提交：
  - `60615d6` `api: converge the 1.2 root and version`
  - `a6d69b1` `focus: route clicks through focus owners instead of patching Form`
  - `5597b3e` `docs: converge the 1.2.0 guide, contracts and component catalogue`（docs worker）
  - `7078997` `merge: W6 -- converge the 1.2 documentation`
- 最终门禁：
  - `uv run pytest -q -p no:cacheprovider` -> **891 passed**
  - `uv run python tools/golden.py --check` -> **57 topics match**
  - `uv run python tools/framebench.py` -> render hash `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`
  - `python -m motui < /dev/null` -> exit 0，sha `c793b32b...`（与 W4b 相同）
  - `python -m motui --pages` -> exit 0，sha `b6ba849d...`（仅 W5a 表格换行导致）
- 版本：`pyproject.toml` 和 `motui.__version__` fallback 都是 `1.2.0`。

## B. 最终 API（只写增量）

- root 37 names：`DEFAULT_THEME, App, Border, Button, Checkbox, Color, ColorPalette, CommandPalette,
  Component, Dialog, Editor, FocusEvent, Glyphs, Input, KeyEvent, Line, Link, List, Markdown, Modal,
  MouseEvent, MultiSelect, Option, PasteEvent, ResizeEvent, Segment, Select, Style, Styles, TUI,
  Table, Text, Theme, Tree, Widget, headless_tui, snapshot`。
- `core.__all__` 删掉 8 个 capability protocol；新增 `Color`、`descend_chain`。
- `widgets.__all__` 删掉 `Text` 重导出（Text 只在 core/root）。
- `prompt_dialog(style=)` -> `prompt_dialog(styles=)`。

## C. 焦点 owner（本次底层修正）

- `Widget.owns_focus = False`；`Form`/`ComboBox` = True。`App.add` 注册 owner 并跳过其子树。
- click 分两半：leaf `click` 动作 + 祖先 `focus_at` 内部游标；`FocusManager.click` 聚焦最近的
  已注册祖先；只有 leaf 且非 Container 在重复点击时 activate。
- `Form._field_at` 统一 child_at/focus_at/click 的行映射；`Dialog.focus_at` 更新按钮游标，
  `Dialog.click` 仍是 Modal 的直接一键门。
- 回归：`tests/app/test_app.py::test_a_form_owns_its_fields_and_a_click_moves_its_cursor`
  （点击 Email 行 -> index 1 -> 输入写 email，不写 name）。
- 不再需要给单个控件打补丁；新增复合焦点控件时只需 `owns_focus=True` + `focus_at`。

## D. 未决 / 后续

- `App.add` 的自动焦点注册仍是启发式（覆盖 `handle/activate/select/move/toggle`）；如果未来出现
  更多复合 owner，应优先加 `owns_focus` 而不是在 App 里写特例。
- `Scrollbar` 尚未泛化为任意 `Scrollable` 的 pane chrome；当前 ScrollView 自己的 bar 已可交互。
- `docs/releases/1.1.*` 保留历史原文；当前文档已不再引用旧命名空间。
