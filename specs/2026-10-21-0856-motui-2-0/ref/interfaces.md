# Interfaces — motui 2.0

## 0. 公开面变化

新增根导出：`Palette`, `Glyphs`, `Border`（`Theme`, `DEFAULT_THEME` 保留）。
删除（W4）：`kernel.style` 的 `ACCENT/BORDER/CODE/DIM/ERROR/FOCUS/HEADING/INLINE_CODE/LINK/LIST_MARKER/MUTED/SUCCESS/WARNING` 语义常量；`kernel.glyphs` 的 `CURSOR/.../TASK_DONE` 旧常量；各组件逐字形参数（W3 迁移）。

`Style`、`Line`、`Segment`、`Component` 等核心类型不变。

## 1. Style / Color

```python
@dataclass(frozen=True, slots=True)
class Color:
    value: str | tuple[int, int, int]   # "#rrggbb" or (r,g,b)
    ansi: str | None = None             # FG_CODES name, e.g. "bright_cyan"

@dataclass(frozen=True, slots=True)
class Style:
    fg: Color | str | tuple[int, int, int] | None = None
    bg: Color | str | tuple[int, int, int] | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False
    strike: bool = False
```

- `Color.ansi` 必须是 `FG_CODES` 的键或 `None`（`__post_init__` 校验）。
- `sgr_prefix`/`_mode_codes`：
  - `truecolor`/`256`：用 `Color.value`（256 量化）。
  - `16`：优先 `Color.ansi`，否则量化。
  - `none`：丢弃颜色，属性保留。
- 现有 `Style(fg="#...")`/tuple 写法继续有效。

## 2. Palette（创作层）

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Palette:
    ink: Style = NONE
    muted: Style = ...
    faint: Style = ...
    line: Style = ...
    surface: Style = NONE
    surface_raised: Style = ...
    surface_hover: Style = ...
    surface_active: Style = ...
    surface_inactive: Style = ...
    accent: Style = ...
    success: Style = ...
    warning: Style = ...
    danger: Style = ...
    code: Style = NONE
    heading: Style = ...
    link: Style = ...
    inline_code: Style = ...
    marker: Style = ...
```

### DARK_PALETTE

| 字段 | 值 |
|---|---|
| ink | `NONE` |
| muted | `Style(fg=Color("#8b95a7", ansi="bright_black"))` |
| faint | `Style(fg=Color("#5d6677", ansi="bright_black"))` |
| line | `Style(fg=Color("#4a5568", ansi="bright_black"))` |
| surface | `NONE` |
| surface_raised | `Style(bg=Color("#161d27", ansi="black"))` |
| surface_hover | `Style(bg=Color("#1b2430", ansi="black"))` |
| surface_active | `Style(bg=Color("#1f2937", ansi="black"))` |
| surface_inactive | `Style(bg=Color("#151b24", ansi="black"))` |
| accent | `Style(fg=Color("#53c8f0", ansi="bright_cyan"))` |
| success | `Style(fg=Color("#5bd18b", ansi="bright_green"))` |
| warning | `Style(fg=Color("#f2c14e", ansi="bright_yellow"))` |
| danger | `Style(fg=Color("#f2708a", ansi="bright_red"))` |
| code | `NONE` |
| heading | `Style(fg=Color("#53c8f0", ansi="bright_cyan"))` |
| link | `Style(fg=Color("#53c8f0", ansi="bright_cyan"), underline=True)` |
| inline_code | `Style(fg=Color("#c4b5fd", ansi="magenta"))` |
| marker | `Style(fg=Color("#8b95a7", ansi="bright_black"))` |

### LIGHT_PALETTE

| 字段 | 值 |
|---|---|
| ink | `NONE` |
| muted | `Style(fg=Color("#5b6472", ansi="bright_black"))` |
| faint | `Style(fg=Color("#8b95a7", ansi="bright_black"))` |
| line | `Style(fg=Color("#b6c0cc", ansi="bright_black"))` |
| surface | `NONE` |
| surface_raised | `Style(bg=Color("#f1f5f9", ansi="bright_white"))` |
| surface_hover | `Style(bg=Color("#eef3f9", ansi="bright_white"))` |
| surface_active | `Style(bg=Color("#e2e8f0", ansi="bright_white"))` |
| surface_inactive | `Style(bg=Color("#f5f8fb", ansi="bright_white"))` |
| accent | `Style(fg=Color("#0369a1", ansi="cyan"))` |
| success | `Style(fg=Color("#15803d", ansi="green"))` |
| warning | `Style(fg=Color("#b45309", ansi="yellow"))` |
| danger | `Style(fg=Color("#be123c", ansi="red"))` |
| code | `NONE` |
| heading | `Style(fg=Color("#0369a1", ansi="cyan"))` |
| link | `Style(fg=Color("#0369a1", ansi="cyan"), underline=True)` |
| inline_code | `Style(fg=Color("#7e22ce", ansi="magenta"))` |
| marker | `Style(fg=Color("#5b6472", ansi="bright_black"))` |

## 3. Theme role groups

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class TextStyles:
    base: Style = NONE
    muted: Style = ...
    faint: Style = ...
    inverse: Style = ...
    disabled: Style = ...
    caret: Style = ...
    selection: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class SurfaceStyles:
    base: Style = NONE
    raised: Style = ...
    hover: Style = ...
    active: Style = ...
    selected: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class BorderStyles:
    base: Style = ...
    grid: Style = ...
    focus: Style = ...
    danger: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class ControlStyles:
    base: Style = ...
    hover: Style = ...
    focus: Style = ...
    active: Style = ...
    disabled: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class RowStyles:
    base: Style = NONE
    hover: Style = ...
    active: Style = ...
    inactive: Style = ...
    selected: Style = ...
    marked: Style = ...
    disabled: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class StatusStyles:
    success: Style = ...
    warning: Style = ...
    danger: Style = ...
    info: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class ContentStyles:
    accent: Style = ...
    link: Style = ...
    code: Style = NONE
    inline_code: Style = ...
    headings: tuple[Style, ...] = ...
    marker: Style = ...
    quote: Style = ...
    strong: Style = Style(bold=True)
    emphasis: Style = Style(italic=True)
    strike: Style = Style(strike=True)

@dataclass(frozen=True, slots=True, kw_only=True)
class ChromeStyles:
    divider: Style = ...
    scrollbar: Style = ...
    scrollbar_thumb: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class OverlayStyles:
    scrim: Style = ...
    toast: Style = ...
    tooltip: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class SyntaxStyles:
    comment: Style = ...
    keyword: Style = ...
    string: Style = ...
    number: Style = ...
    builtin: Style = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    text: TextStyles = field(default_factory=TextStyles)
    surfaces: SurfaceStyles = ...
    borders: BorderStyles = ...
    controls: ControlStyles = ...
    rows: RowStyles = ...
    status: StatusStyles = ...
    content: ContentStyles = ...
    chrome: ChromeStyles = ...
    overlays: OverlayStyles = ...
    syntax: SyntaxStyles = ...

    @classmethod
    def dark(cls) -> "Theme": ...
    @classmethod
    def light(cls) -> "Theme": ...
    @classmethod
    def flat(cls) -> "Theme": ...
    @classmethod
    def auto(cls, env=None) -> "Theme": ...
    @classmethod
    def from_palette(cls, palette: Palette) -> "Theme": ...
```

### 3.1 W1/W2 的 legacy 默认值（必须与 1.x 逐字节一致）

W1 把各 group 的**字段默认值**设为下表；`DEFAULT_THEME = Theme()`。W3 再改成暗色值。

| group.field | legacy 值 |
|---|---|
| text.base | `NONE` |
| text.muted | `MUTED` (`#8b949e`) |
| text.faint | `DIM` (`Style(dim=True)`) |
| text.inverse | `NONE` |
| text.disabled | `DIM` |
| text.caret | `Style(reverse=True)` |
| text.selection | `Style(reverse=True)` |
| surfaces.base | `NONE` |
| surfaces.raised | `NONE` |
| surfaces.hover | `NONE` |
| surfaces.active | `NONE` |
| surfaces.selected | `NONE` |
| borders.base | `NONE` |
| borders.grid | `NONE` |
| borders.focus | `Style(reverse=True)` |
| borders.danger | `Style(fg="#e5534b", bold=True)` |
| controls.base | `Style(fg="#58a6ff", bold=True)` |
| controls.hover | `NONE` |
| controls.focus | `Style(reverse=True)` |
| controls.active | `NONE` |
| controls.disabled | `DIM` |
| rows.base | `NONE` |
| rows.hover | `NONE` |
| rows.active | `NONE` |
| rows.inactive | `DIM` |
| rows.selected | `NONE` |
| rows.marked | `NONE` |
| rows.disabled | `DIM` |
| status.success | `Style(fg="#4bb563")` |
| status.warning | `Style(fg="#d29922")` |
| status.danger | `Style(fg="#e5534b", bold=True)` |
| status.info | `Style(fg="#58a6ff", bold=True)` |
| content.accent | `Style(fg="#58a6ff", bold=True)` |
| content.link | `Style(fg="#58a6ff", underline=True)` |
| content.code | `Style(fg="#a5d6ff")` |
| content.inline_code | `Style(fg="#f778ba")` |
| content.headings | `(HEADING+underline, HEADING, HEADING, HEADING, HEADING, HEADING)` |
| content.marker | `Style(fg="#bc8cff")` |
| content.quote | `MUTED` |
| content.strong | `Style(bold=True)` |
| content.emphasis | `Style(italic=True)` |
| content.strike | `Style(strike=True)` |
| chrome.divider | `NONE` |
| chrome.scrollbar | `DIM` |
| chrome.scrollbar_thumb | `NONE` |
| overlays.scrim | `DIM` |
| overlays.toast | `Style(reverse=True, dim=True)` |
| overlays.tooltip | `Style(reverse=True, dim=True)` |
| syntax.comment | `MUTED.merge(Style(italic=True))` |
| syntax.keyword | `Style(fg="#58a6ff")` |
| syntax.string | `SUCCESS` |
| syntax.number | `WARNING` |
| syntax.builtin | `CODE` |

`HEADING = Style(fg="#e3b341")`；`MUTED=#8b949e`，`DIM=Style(dim=True)`，`SUCCESS=#4bb563`，`WARNING=#d29922`，`ERROR=#e5534b bold`，`ACCENT=#58a6ff bold`，`CODE=#a5d6ff`。

### 3.2 暗色主题（W3 起的默认）

由 `Theme.from_palette(DARK_PALETTE)` 派生：

| group.field | 值 |
|---|---|
| text.base | palette.ink (`NONE`) |
| text.muted | palette.muted |
| text.faint | palette.faint |
| text.inverse | `Style(fg="#0d1117")` |
| text.disabled | palette.faint |
| text.caret | `Style(reverse=True)` |
| text.selection | `Style(reverse=True)` |
| surfaces.base | palette.surface (`NONE`) |
| surfaces.raised | palette.surface_raised |
| surfaces.hover | palette.surface_hover |
| surfaces.active | palette.surface_active |
| surfaces.selected | palette.surface_active |
| borders.base | palette.line |
| borders.grid | palette.line |
| borders.focus | palette.accent |
| borders.danger | palette.danger |
| controls.base | palette.accent |
| controls.hover | palette.surface_hover |
| controls.focus | `Style(underline=True)` |
| controls.active | palette.surface_active |
| controls.disabled | palette.faint |
| rows.base | `NONE` |
| rows.hover | palette.surface_hover |
| rows.active | palette.surface_active |
| rows.inactive | palette.surface_inactive |
| rows.selected | palette.surface_active |
| rows.marked | palette.surface_hover |
| rows.disabled | `NONE` |
| status.success | palette.success |
| status.warning | palette.warning |
| status.danger | palette.danger |
| status.info | palette.accent |
| content.accent | palette.accent |
| content.link | palette.link |
| content.code | palette.code (`NONE`) |
| content.inline_code | palette.inline_code |
| content.headings | `(palette.heading.merge(Style(underline=True)), palette.heading, palette.heading, palette.heading, palette.heading, palette.heading)` |
| content.marker | palette.marker |
| content.quote | palette.line |
| content.strong | `Style(bold=True)` |
| content.emphasis | `Style(italic=True)` |
| content.strike | `Style(strike=True)` |
| chrome.divider | palette.line |
| chrome.scrollbar | palette.faint |
| chrome.scrollbar_thumb | palette.muted |
| overlays.scrim | `Style(dim=True)` |
| overlays.toast | palette.surface_raised |
| overlays.tooltip | palette.surface_raised |
| syntax.comment | palette.muted + italic |
| syntax.keyword | palette.accent |
| syntax.string | palette.success |
| syntax.number | palette.warning |
| syntax.builtin | palette.inline_code |

亮色主题用 `LIGHT_PALETTE` 同样派生；`text.inverse=Style(fg="#ffffff")`。
`Theme.flat()` = 暗色主题，但 `surfaces.*=NONE`，`rows.active=Style(reverse=True)`、`rows.inactive=Style(dim=True)`、`rows.hover=Style(underline=True)`、`rows.selected=Style(reverse=True)`、`overlays.toast/tooltip=Style(reverse=True)`。

### 3.3 状态解析

```python
class RowStyles:
    def band(self, *, active: bool = False, hovered: bool = False,
             focused: bool = True, selected: bool = False,
             marked: bool = False, disabled: bool = False) -> Style:
        # disabled > hovered > (active ? (focused ? active : inactive)) > selected > marked > base

class ControlStyles:
    def band(self, *, hovered: bool = False, focused: bool = False,
             active: bool = False, disabled: bool = False) -> Style:
        # disabled > active > focused > hovered > base
```

组件可继续自己合并 `hover_style`/`focus_style` 等显式参数；`band()` 是默认解析。

### 3.4 临时兼容属性（W1–W3，W4 删除）

| 旧属性 | 映射 |
|---|---|
| `dim` | `text.faint` |
| `muted` | `text.muted` |
| `accent` | `content.accent` |
| `success` | `status.success` |
| `error` | `status.danger` |
| `warning` | `status.warning` |
| `border` | `borders.base` |
| `code` | `content.code` |
| `focus` | `controls.focus` |
| `selection` | `text.selection` |
| `heading` | `content.headings[1]` |
| `link` | `content.link` |
| `inline_code` | `content.inline_code` |
| `list_marker` | `content.marker` |
| `hover` | `surfaces.hover` |
| `caret` | `text.caret` |
| `ground` | `surfaces.base` |
| `ground_active` | `rows.active` |
| `table_border` | `borders.grid` |
| `first_column` | `text.base` |
| `scrollbar` | `chrome.scrollbar` |
| `scrollbar_thumb` | `chrome.scrollbar_thumb` |
| `toast` | `overlays.toast` |
| `headings` | `content.headings` |
| `notice_levels` | `{"warn": ("WARNING: ", status.warning), "error": ("ERROR: ", status.danger)}` |

## 4. Glyphs / Border

```python
@dataclass(frozen=True, slots=True)
class Border:
    top_left: str = "┌"; top: str = "─"; top_tee: str = "┬"; top_right: str = "┐"
    left: str = "│"; middle: str = "─"; cross: str = "┼"; right: str = "│"
    middle_left: str = "├"; middle_right: str = "┤"
    bottom_left: str = "└"; bottom: str = "─"; bottom_tee: str = "┴"; bottom_right: str = "┘"

    @classmethod
    def square(cls) -> "Border": ...
    @classmethod
    def rounded(cls) -> "Border": ...
    @classmethod
    def heavy(cls) -> "Border": ...
    @classmethod
    def double(cls) -> "Border": ...
    @classmethod
    def ascii(cls) -> "Border": ...
    @classmethod
    def none(cls) -> "Border": ...

@dataclass(frozen=True, slots=True, kw_only=True)
class Glyphs:
    prompt: str = "❯"
    cursor: str = "→"
    rail: str = "▌"
    fold_open: str = "▾"
    fold_closed: str = "▸"
    radio_off: str = "( )"
    radio_on: str = "(•)"
    check_off: str = "[ ]"
    check_on: str = "[x]"
    check_indeterminate: str = "[-]"
    more_up: str = "↑"
    more_down: str = "↓"
    bar_full: str = "█"
    bar_empty: str = "░"
    slider_track: str = "━"
    slider_thumb: str = "●"
    horizontal_rule: str = "─"
    vertical_rule: str = "│"
    quote: str = "│"
    separator: str = " · "
    bullets: tuple[str, ...] = ("•", "◦", "▪")
    notice_info: str = "i"
    notice_success: str = "✓"
    notice_warn: str = "!"
    notice_error: str = "×"
    diff_add: str = "+"
    diff_remove: str = "-"
    diff_context: str = " "
    spinner: tuple[str, ...] = ("⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏")
    box: Border = Border.square()
    grid: Border = Border.square()

GLYPHS = Glyphs()
```

W1 定义 `GLYPHS`，但组件在 W3 才使用。

## 5. 组件映射（W2 只迁 theme groups；W3 迁 glyphs）

| 组件 | theme 读取 | glyph |
|---|---|---|
| Button | `controls.base/hover/focus/disabled` | 无 |
| Checkbox | mark `content.accent`; label `text.base`; band `controls.*` | `check_on/off` |
| RadioGroup | mark `content.accent`; label `text.base`; band `rows.*` | `radio_on/off` |
| CheckboxGroup | mark `content.accent`; label `text.base`; band `rows.*` | `check_on/off` |
| Input | prompt `content.accent`; text `text.base`; placeholder `text.faint`; caret `text.caret`; selection `text.selection` | `prompt` |
| Editor | text `text.base`; caret `text.caret`; selection `text.selection` | 无 |
| List | cursor `content.accent`; band `rows.*`; counter `text.muted` | `cursor`, `more_*`, `check_*` |
| Select | cursor `content.accent`; band `rows.*`; description `text.muted` | `cursor` |
| Autocomplete | 同 Select | `cursor` |
| ContextMenu | 同 Select | `cursor` |
| NavList | active `content.accent`; inactive/group `text.muted`; band `rows.*` | `rail` |
| Tabs | active `content.accent`; inactive `text.muted`; divider `chrome.divider`; hover `rows.hover` | `vertical_rule` |
| MenuBar | active `content.accent`; inactive `text.muted`; divider `chrome.divider`; hover `rows.hover` | `vertical_rule` |
| Tree | label `text.base`; guide `text.faint`; fold `text.muted`; band `rows.*` | `fold_*` |
| Collapsible | title `text.base`; marker `text.muted`; hover `rows.hover` | `fold_*` |
| Table | grid `borders.grid`; header `text.muted`; first col `text.base`; band `rows.*` | `grid`, `check_*` |
| Panel | border `borders.base`; title `text.muted` | `box` |
| Dialog | border `borders.base`/`borders.danger`; title `content.accent` | `box` |
| Notice | info `text.base`; success `status.success`; warn `status.warning`; error `status.danger` | `notice_*` |
| ProgressBar | filled `content.accent`; empty `text.faint` | `bar_full/empty` |
| Slider | filled/thumb `content.accent`; empty `text.faint`; value `text.muted` | `slider_track/thumb` |
| Spinner | `content.accent`; label `text.muted` | `spinner` |
| Scrollbar | track `chrome.scrollbar`; thumb `chrome.scrollbar_thumb` | `bar_empty/full` |
| Diff | add `status.success`; del `status.danger`; hunk `text.muted` | `diff_*` |
| Markdown | headings `content.headings`; link `content.link`; code `content.code`; inline `content.inline_code`; marker `content.marker`; quote `content.quote` | `check_*`, `bullets`, `quote` |
| Syntax | `syntax.*` | 无 |
| Find | `overlays.toast`; `text.*`; `content.*` | `prompt` |
| Modal | `overlays.scrim` | 无 |
| Toasts | `overlays.toast` | 无 |
| Tooltip | `overlays.tooltip` | 无 |
| Stats | `overlays.tooltip` | 无 |
| ShortcutBar | key `content.accent`; label `text.muted` | `separator` |
| StatusLine | `text.muted` | 无 |
| Form/Field | label `text.muted`; error `status.danger`; hint `text.faint` | 无 |
| ComboBox | Input + Select roles | `prompt`, `cursor` |

## 6. 测试中的旧 Theme 构造映射（W1 机械更新）

| 旧写法 | 新写法 |
|---|---|
| `replace(T, accent=x)` | `replace(T, content=replace(T.content, accent=x))` |
| `replace(T, heading=x)` | `replace(T, content=replace(T.content, headings=(x,...)))` |
| `replace(T, link=x)` | `replace(T, content=replace(T.content, link=x))` |
| `replace(T, inline_code=x)` | `replace(T, content=replace(T.content, inline_code=x))` |
| `replace(T, list_marker=x)` | `replace(T, content=replace(T.content, marker=x))` |
| `replace(T, muted=x)` | `replace(T, text=replace(T.text, muted=x))` |
| `replace(T, dim=x)` | `replace(T, text=replace(T.text, faint=x))` |
| `replace(T, caret=x)` | `replace(T, text=replace(T.text, caret=x))` |
| `replace(T, selection=x)` | `replace(T, text=replace(T.text, selection=x))` |
| `replace(T, hover=x)` | `replace(T, surfaces=replace(T.surfaces, hover=x))` |
| `replace(T, ground=x)` | `replace(T, surfaces=replace(T.surfaces, base=x))` |
| `replace(T, ground_active=x)` | `replace(T, rows=replace(T.rows, active=x))` |
| `replace(T, border=x)` | `replace(T, borders=replace(T.borders, base=x))` |
| `replace(T, table_border=x)` | `replace(T, borders=replace(T.borders, grid=x))` |
| `replace(T, focus=x)` | `replace(T, controls=replace(T.controls, focus=x))` |
| `replace(T, success=x)` | `replace(T, status=replace(T.status, success=x))` |
| `replace(T, warning=x)` | `replace(T, status=replace(T.status, warning=x))` |
| `replace(T, error=x)` | `replace(T, status=replace(T.status, danger=x))` |
| `replace(T, scrollbar=x)` | `replace(T, chrome=replace(T.chrome, scrollbar=x))` |
| `replace(T, scrollbar_thumb=x)` | `replace(T, chrome=replace(T.chrome, scrollbar_thumb=x))` |
| `replace(T, toast=x)` | `replace(T, overlays=replace(T.overlays, toast=x))` |
| `Theme(heading=..., warning=...)` | `Theme(content=replace(Theme().content, headings=...), status=replace(Theme().status, warning=...))` |

## 7. W3 视觉切换清单

- `kernel/theme.py` 字段默认值改为暗色（3.2）。
- `DEFAULT_THEME = Theme()`（暗色）。
- 所有组件逐字形参数 -> `glyphs=`；Notice 文本前缀 -> `notice_*`；Markdown task -> `check_*`；Input/Find prompt -> `prompt`；List/Select -> `cursor`；Slider -> `slider_*`；Scrollbar/Progress -> `bar_*`。
- 重录 `tests/golden/topics/*`，记录新 render-hash。
- 更新所有断言旧样式的测试。
- 更新 demo 的 `THEMES`/styling topic 到新 groups。

## 8. 错误语义

- `Color.ansi` 未知名称 -> `ValueError`。
- `Theme.auto()` 只读 env，不改全局。
- `Theme.from_palette` 是纯函数。
- `RowStyles.band`/`ControlStyles.band` 无副作用。
- 其余错误语义（Document/Frame/Pane/TUI）不变。
