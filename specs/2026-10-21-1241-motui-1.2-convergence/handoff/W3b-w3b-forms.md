# W3b 交接包
> 分支 `refactor/1.2-w3b-forms` / 起点 `3e8fbde` / 2026-10-21
## A. 自动事实（从命令与代码生成，别凭记忆）

- commits：`0baa593`（T1）、`f270413`（T2）、本文件所在 commit（T3）。
- `git diff --stat 3e8fbde..HEAD`：11 files, +382/-379（不含本文件）。文件：
  `widgets/choice.py`、`autocomplete.py`、`textfield.py`、`combobox.py`、`form.py`、`widgets/__init__.py`、
  `widgets/dialog.py`（仅 prompt 构造）、`demo/topics/components_forms.py`、
  `tests/test_invariants.py`、`tests/widgets/test_choice.py`、`tests/widgets/test_editing.py`。
- 签名实测（`inspect.signature`，均无 `style/hover_style/focus_style/disabled_style/ground_style/label_style/
  cursor_text_style/description_style/title_style/active_style/caret_style/prompt_style/focused/multi`）：
  - `Select(options=(), *, title='', max_rows=8, wrap=True, glyphs=GLYPHS, commit=False, window=False, disabled=False, disabled_items=(), theme=None, styles=None)`
  - `MultiSelect(options=(), *, title='', max_rows=8, wrap=True, glyphs=GLYPHS, marked=(), disabled=False, disabled_items=(), theme=None, styles=None)`
  - `Autocomplete(options=(), *, max_rows=8, wrap=True, glyphs=GLYPHS, theme=None, styles=None)`
  - `RadioGroup(labels, *, index=0, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)`
  - `CheckboxGroup(labels, *, marked=(), index=0, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)`
  - `Input(text='', *, prompt=None, placeholder='', mask='', glyphs=GLYPHS, theme=None, styles=None, keymap=None, read_only=False)`
  - `Editor(text='', *, placeholder='', mask='', theme=None, styles=None, keymap=None, max_rows=None, read_only=False)`
  - `ComboBox(options=(), *, text='', max_rows=8, theme=None, styles=None, max_drop_rows=6, glyphs=GLYPHS)`
  - `Form(fields, *, gap=0, index=0, on_submit=None, theme=None, styles=None)`
  - `Select` 共 11 个参数但 keyword-only 恰 10 个（`options` 位置参数）；若按“含位置参数”计，需 W6 再收。
- `__slots__` 实测：`Select` 不再有 `theme/focused/hover/marked/multi` 与全部 `_*_style`；`MultiSelect` 只有 `marked`；
  `_TextField` 只有 `_buf/_mask/_memo_*`；`Input` 只有 `_prompt`；`Form` 无样式缓存。
- 全波真实结果（本 worktree，CPython 3.13）：`pytest -q -p no:cacheprovider` -> **882 passed**（880 基线 + 2 个活主题用例）；
  `golden.py --check` -> **57 topics match**，未重录任何帧；`framebench.py` -> render hash
  `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（与 W3a/W2 一致）；
  `python -m motui < /dev/null` -> exit 0；`--pages` -> exit 0，4059 行。
## B. 只存在于脑子里的东西（W3c 直接复用）

**迁移 pattern 的 forms 变体（均已验证）**

1. `class X(Widget)`；`super().__init__(theme, styles)`；`focused` 默认值在子类 `__init__` 里显式补：
   Input/Editor/Select 默认 `True`，RadioGroup/CheckboxGroup 默认 `False`。
2. render 每次 `self.group("<组>")`；`revision()` 另加 `self.theme, self.styles`（替换旧的解析后样式值）。
3. `TextBuffer` 仍是纯编辑引擎：`_rows_for` 在 render 时把 `text.base/caret/faint/selection`、`surfaces.hover` 传进 `row_body`。
4. `Form` 只读 `content.accent` / `status.danger`；`Field` 未动。
5. `Themed` 现在只剩未迁移控件/控制器（Tree/Table/List/NavList/Tabs/ScrollView/Dialog/Markdown/Find 等）；本波四个文件不再 import 它。

**样式映射（forms 全家）**

| 控件 | base | cursor/accent | muted/faint | 其他 |
|---|---|---|---|---|
| Select | 标签/标题 `text.base` | 光标行 `content.accent` | 描述/计数 `text.muted`；disabled+未聚焦 dim `text.faint` | 行 band `rows.band` |
| MultiSelect | 同上 | 同上 | 同上 | 额外 `check_on/check_off` 标记列 |
| RadioGroup | 标签 `text.base` | mark `content.accent` | disabled `text.faint` | form band: hover > focused active > base |
| CheckboxGroup | 同上 | 同上 | 同上 | 同上 |
| Input | 正文 `text.base` | prompt `content.accent`；caret `text.caret` | placeholder `text.faint` | selection `text.selection`；hover `surfaces.hover` |
| Editor | 正文 `text.base` | caret `text.caret` | placeholder `text.faint` | 同上 |
| Form | — | 标签 `content.accent` | 错误 `status.danger` | — |

**MultiSelect 取舍（拆分已做，无 W6 遗留）**

- `Select` 删除 `multi/marked/focused`，只留单选；`MultiSelect(Select)` 提供 `marked`、`toggle()`、`_sync_result()`，
  渲染/结果语义与旧 `Select(multi=True)` 逐字节一致。
- `CheckboxGroup` 改为 `(_FormGroup, MultiSelect)`；`_FormGroup` 从 `Select` 子类降为 mixin（`labels` + `_band`），
  这样 RadioGroup/CheckboxGroup 的 MRO 都能复用。
- 拆分只改了 2 个测试文件（`test_choice.py`、`test_invariants.py`）和 demo 1 处，golden 未变，未触发诚实出口。

**调用点清单（`rg` 扫描 + 实测）**

- 改了：`demo/topics/components_forms.py`（`Select(multi=True...)` -> `MultiSelect(...)`，导入同步）；
  `widgets/__init__.py`（导出 `MultiSelect`；root `__all__` 未动）；`widgets/dialog.py::prompt_dialog`
  （字段 `style=` -> `Styles(text=replace((theme or DEFAULT_THEME).text, base=style))`，默认渲染不变）。
- 无需改：`app/find.py`、`app/command_palette.py`（两者的 `Input`/`Autocomplete` 构造只用 `theme/glyphs/prompt`，签名兼容）；
  `demo/topics/patterns.py`、`components_overlays.py`（只用 `theme/mask/max_rows`）。
- 坑：`ComboBox.focused` 是委托给 `.input` 的 property，会遮蔽 `Widget.focused` 槽；因此其 `__init__` 必须先建
  `self.input/self.list` 再调 `super().__init__`，再补 `self.focused = True`。`ComboBox` 新增 `styles=` 转发，
  并在 `_skin()` 里把构造后对 `combo.theme/styles` 的赋值重新下发给两个子控件（`render`/`revision` 前调用）。
- 坑：`demo/topics/components_forms.py` 的 `api_line` 字符串仍是旧签名（进 golden），本波刻意未改；W6 更新文案时重录
  `components--select` / `radio-group` / `input` / `editor` 等帧。
- 坑：`tests/widgets/test_editing.py` 的 `caret_style=` 已改为 `Styles(text=replace(DEFAULT_THEME.text, caret=...))`；
  `focused=False` 改为构造后赋值。
## C. 指针

- `src/motui/widgets/choice.py`：`Select.__init__`、`MultiSelect`、`_FormGroup`、三份 `_row`/`_revision`。
- `src/motui/widgets/textfield.py`：`_TextField.__init__`、`_revision`、`_rows_for`、`Input._row_prefix`。
- `src/motui/widgets/combobox.py::_skin`；`src/motui/widgets/form.py::render`；`src/motui/widgets/dialog.py::prompt_dialog`。
- 活主题回归样板：`tests/widgets/test_choice.py::test_a_theme_assignment_repaints_the_next_render`、
  `tests/widgets/test_editing.py::test_a_theme_assignment_repaints_the_memoized_rows`。
- 稳定区（下一波不必重读）：`core/**`、全部 golden、`tools/**`、`docs/**`、`app/` 接线逻辑。
