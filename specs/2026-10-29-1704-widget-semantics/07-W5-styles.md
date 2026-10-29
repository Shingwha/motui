# W5 · 样式重构

> 分支 `w2.1.2-w5-styles`；起点 main @ `4a93d31`（W4 全部合并）。
> 写入范围：`src/motui/kernel/theme.py`、`widgets/{action,dialog,textfield,
> tabs,menubar,indicators,collapsible}.py`、
> `tests/kernel/{test_theme,test_theme_contract}.py`、
> `tests/widgets/{test_action,test_dialog,test_editing,test_navigation,
> test_menubar,test_indicators,test_text_widget}.py`、
> `tests/golden/semantic/*.txt`、`tests/demo/test_scenes.py`（如需）。
> 最高约束：**只改样式/SGR，不改渲染字符**；每个 scene 的行文本必须不变。

## 目标

把“主题角色 + 控件状态 overlay”落成：`SurfaceStyles` 增加
`control/accent/danger/inactive`；`ControlStyles` 瘦身为
`hover/focus/active/disabled` + `overlay()`（删除 `base`/`band()`）；
`ButtonKind` 四态与统一 `action_band`；Input/Editor 字段底板；Link/Tabs/
MenuBar 焦点修复；Dialog 内部 `surfaces.raised`；`Theme.flat()` 覆盖新 token。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §0、§2、§6 →
  `handoff/W4a-deepseek-v4.1-flash.md` → `handoff/W4b-deepseek-v4.1-flash.md`
  → `handoff/W4c-deepseek-v4.1-flash.md` → 本工单。
- 基线命令：

```bash
uv run pytest -q tests/kernel/test_theme.py tests/kernel/test_theme_contract.py tests/widgets/test_action.py tests/widgets/test_dialog.py tests/widgets/test_editing.py tests/widgets/test_navigation.py tests/widgets/test_menubar.py tests/widgets/test_indicators.py
uv run python tools/semantic.py --check
```

- 基线事实：1813 tests；semantic 9/9；`api.py --check` 243 names；render-hash
  `e7ca544b...`。
- 稳定区（勿重读）：`widgets/base.py`、`choice/list/table/tree/strip`、
  `layout.py`、`canvas/pixel_canvas/drawing`、`app/`。
- 已知约束：
  - `Style` 没有 `faint` 字段；faint 是 `theme.text.faint` 的一个
    foreground 样式。disabled = `text.faint` + `controls.disabled`（dim）。
  - `Style.merge(other)` 的 `other` 在顶层；布尔属性 OR。
  - `ControlStyles.band()` 当前**没有消费者**（只有 tests）；删除安全。
    `RowStyles.band()` 保留，不要动。
  - `ButtonSpec.danger` 被 Dialog/confirm_dialog/tests 使用；迁移到
    `kind=ButtonKind.DANGER`。
  - `Dialog.danger` 标志保留（边框/默认焦点）；只把按钮 danger 改成 kind。
  - `SurfaceStyles` 是 frozen keyword-only dataclass；新增字段必须带默认值。
  - semantic golden 包含 SGR；W5 允许 SGR 变化，但行文本（`\t` 前）必须
    逐场景不变。重录后必须贴出“文本未变”的证据。

## 工单（按序执行，每项一个 commit）

### T1 主题 token

- `SurfaceStyles` 增加：
  - `control: Style = DARK_PALETTE.surface_raised`
  - `accent: Style = Style(bg=Color("#53c8f0", ansi="bright_cyan"))`
  - `danger: Style = Style(bg=Color("#f2708a", ansi="bright_red"))`
  - `inactive: Style = DARK_PALETTE.surface_inactive`
  保留现有 `base/raised/hover/active/selected`。
- `ControlStyles` 改为：

```python
hover: Style = Style(bold=True, underline=True)
focus: Style = Style(bold=True, underline=True, reverse=True)
active: Style = Style(reverse=True, underline=True)
disabled: Style = Style(dim=True)

def overlay(self, *, hovered=False, focused=False, pressed=False,
            disabled=False) -> Style:
    # disabled > pressed > focused > hovered > NONE
```

- 删除 `ControlStyles.base` 和 `ControlStyles.band()`。
- `Theme.flat()`：`surfaces` 的 `base/raised/hover/active/selected/control/
  accent/danger/inactive` 全部 `NONE`；`controls` 设为
  `hover=Style(underline=True)`, `focus=Style(bold=True, underline=True)`,
  `active=Style(reverse=True, underline=True)`, `disabled=Style(dim=True)`。
- 更新 `tests/kernel/test_theme.py`、`test_theme_contract.py`：
  `controls.focus` 新默认；删除 `band()` 用例，增加 `overlay()` 的优先级/
  合并/空状态用例；新增四个 surface token 与 flat 用例。
- 验证：`uv run pytest -q tests/kernel/test_theme.py tests/kernel/test_theme_contract.py`。

### T2 ButtonKind + action_band

- `action.py` 增加：

```python
class ButtonKind(StrEnum):
    NEUTRAL = "neutral"
    PRIMARY = "primary"
    GHOST = "ghost"
    DANGER = "danger"

def action_band(kind, theme, *, hovered=False, focused=False,
                pressed=False, disabled=False) -> Style:
    base = {
        NEUTRAL: theme.surfaces.control.merge(theme.text.base),
        PRIMARY: theme.surfaces.accent.merge(theme.text.inverse),
        GHOST: theme.content.accent,
        DANGER: theme.surfaces.danger.merge(theme.text.inverse),
    }[kind]
    overlay = theme.controls.overlay(hovered=hovered, focused=focused,
                                     pressed=pressed, disabled=disabled)
    if disabled:
        base = base.merge(theme.text.faint)
    return base.merge(overlay)
```

- `Button(label, *, kind=ButtonKind.NEUTRAL, disabled=False, theme=None,
  styles=None)`；`self.kind = ButtonKind(kind)`（接受字符串）；render 用
  `action_band`；删除 `_band`（或保留为 `action_band` 的薄包装，若无其他
  消费者就删）。
- `Checkbox`：mark/label 基础样式不变（content.accent/text.base），叠加
  `controls.overlay(hovered=..., focused=..., disabled=...)`；disabled 额外
  `text.faint`。
- `Link`：基础 `content.link`；hover/focus/disabled 用同一个 overlay；
  focus 现在真正可见（bold+underline+reverse）。
- 从 `motui.widgets` 导出 `ButtonKind`（`__init__.py` 的 import/`__all__`）；
  lead 负责 API 快照。
- 更新 `tests/widgets/test_action.py`：四种 kind 的 base 样式、hover/focus/
  disabled overlay、Link focus、`Button(kind="primary")` 字符串转换。
- 验证：`uv run pytest -q tests/widgets/test_action.py`。

### T3 Dialog / ButtonSpec

- `ButtonSpec(label, value=None, styles=None, kind=ButtonKind.NEUTRAL)`；
  删除 `danger` 字段。
- `Dialog._new_button`：`Button(spec.label, kind=spec.kind,
  styles=spec.styles, theme=self.theme)`；删除 `controls.base` re-aim。
- `Dialog._default_index`：danger 按钮 = `spec.kind is ButtonKind.DANGER`；
  `Dialog.danger` 仍决定“打开时聚焦最后一个非 danger 按钮”。
- `confirm_dialog(danger=True)` 的 confirm 用 `ButtonKind.DANGER`。
- `Dialog` 内部面板背景：如果当前有 `surfaces.base`/`raised` 的选择，改为
  `surfaces.raised`（scrim 保留）。检查 `_interior_row`/render，只在 Dialog
  自己的内部行使用，不动 Panel。
- 更新 `tests/widgets/test_dialog.py` 与 `tests/widgets/test_contract_text_form.py`
  的 ButtonSpec/kind 用例。
- 验证：`uv run pytest -q tests/widgets/test_dialog.py tests/widgets/test_contract_text_form.py`。

### T4 Input / Editor 字段底板

- `textfield.py`：每个字段行先铺 `surfaces.control`，再按状态叠加：
  - hover → `controls.overlay(hovered=True)`；
  - read_only → `text.faint.merge(controls.overlay(disabled=True))`；
  - focus 不改变底板（caret 自带）。
- `_rows_for`（Input/Editor 两处）与 Editor OVERFLOW 分支都要覆盖；
  placeholder 也在地板上。
- 保留 `text.caret`/`text.selection` 的优先级（行 band 在最底层，caret 在
  cell 上层）。
- 更新 `tests/widgets/test_editing.py`：底板样式、hover overlay、read_only
  dim/faint。
- 验证：`uv run pytest -q tests/widgets/test_editing.py`。

### T5 Tabs / MenuBar / Slider / Collapsible

- `tabs.py`：active = `content.accent + underline` + `controls.overlay(
  focused=self.focused)`；inactive = `text.faint`；hover = `surfaces.hover`；
  disabled = `text.faint + controls.overlay(disabled=True)`。保留现有 indicator
  角色，但不要再单独 merge `controls.focus` 的旧默认（用 overlay）。
- `menubar.py`：`_style_of` 加 focus overlay；active 加 underline；hover
  `surfaces.hover`；disabled overlay。MenuBar 的 focused 渲染必须可见。
- `indicators.py` Slider：轨道 filled = `content.accent`；hover/focus/
  disabled 用 `controls.overlay`；不要再直接 merge `controls.focus`。
- `collapsible.py`：title 的 hover `surfaces.hover`、focus overlay、disabled
  faint+dim；保持 open/closed 字符不变。
- 更新对应测试：`test_navigation.py`、`test_menubar.py`、`test_indicators.py`、
  `test_containers.py`（Collapsible 样式）。
- 验证：`uv run pytest -q tests/widgets/test_navigation.py tests/widgets/test_menubar.py tests/widgets/test_indicators.py tests/widgets/test_containers.py`。

### T6 Goldens / demo

- `uv run python tools/semantic.py --update` 重录 9 个 golden。
- 逐场景验证行文本不变：写一个小脚本比较 `--check` 旧文件与更新后文件的
  `\t` 前文本；把结果贴进 handoff。若某场景行文本变了，先修渲染，不要
  接受。
- 如果 demo 有 style 断言（`tests/demo/test_scenes.py`），同步更新。
- 跑 `framebench`；render-hash 会变，记录新值与原因（预期）。
- 只改上述文件。

## 验收

1. 全量 `uv run pytest -q -p no:cacheprovider` 全绿。
2. `ruff check .`、改动文件 no-exclude ruff、`pyright`、`lint-imports` 全绿。
3. `semantic.py --check` 全绿；handoff 附“9 场景行文本未变”的证据。
4. `framebench.py` 的 render-hash 新值已记录（样式变化是预期的）。
5. `api.py --check` 会因 `ButtonKind`/ButtonSpec/Button 构造变化失败；贴差异，
   不改快照。

## 禁触清单

`widgets/base.py`、`choice.py`、`autocomplete.py`、`combobox.py`、`list.py`、
`table.py`、`tree.py`、`navlist.py`、`strip.py`、`layout.py`、`canvas.py`、
`pixel_canvas.py`、`drawing.py`、`form.py`、`text.py`、`markdown/`、`app/`、
`tools/`、`docs/`、`pyproject.toml`。
`handoff/W5-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W5-<agent>.md`：新 token 默认、`overlay` 优先级、ButtonKind
映射、字段底板实现、哪些 scene 的 SGR 变了但文本不变、api 差异、W6 可用的
样式钩子。

## 最终报告

同 W1 模板。
