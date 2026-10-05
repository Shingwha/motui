# Components

A component is anything with `render(width) -> list[Line]`. That single protocol
— frozen since the first wave — is the whole contract.

## The protocol

- **`render(width)` returns rows.** One `Line` per visual row, each already
  wrapped and sized. A component never paints, scrolls, or touches a screen.
- **`width` is the full painting width** — on a real screen that is
  `screen.width`; a `Row`/`Column` child gets the width its parent gives it. The
  painter only counts rows; components own their own wrapping and truncation.
- **`Line`** is an immutable run of styled **`Segment`**s (`text` + `Style`), with
  `width` (display columns via wcwidth), `fit(width)` (truncate-with-ellipsis),
  and `pad_to(width)`. `Line`, `Segment` and `Style` live in the kernel
  (`mocode_tui.core.lines` / `mocode_tui.core.style`) and are exported at the
  package root.
- **Sealing is a cache hint, not a render mode.** `BlockState` is `OPEN`/`SEALED`
  only — a sealed block renders once per width and is cached; an open block
  re-renders every frame. There is no "inline" or "committed" render mode; the
  same `render(width)` runs in both states.

Every component below is importable straight from `mocode_tui`; the generic ones
also from `mocode_tui.widgets`, the pi-style ones from `mocode_tui.chat`.

## Styling: Style and Theme

`Style(fg=..., bg=..., ...)` is frozen and hashable (so `prefix()` is memoized
per instance) and takes a color in one of three forms:

- a **named 16-color** from `core.style.FG_CODES` (`"red"`, `"bright_black"`, …);
  unknown names raise `KeyError` from `prefix()`;
- a **`"#rrggbb"` string** or an **`(r, g, b)` tuple** — both emit 24-bit
  truecolor SGR (`38;2;r;g;b` / `48;2;r;g;b`). Truecolor is a superset of
  the named set, so old named styles keep working unchanged.

**`Theme`** (a frozen dataclass, `DEFAULT_THEME` as the shipped instance) is the
one place every semantic default lives. A component takes an explicit
`style=...` (which always wins) plus `theme=Theme | None`, and resolves each
style at render time as **explicit > theme field > `DEFAULT_THEME` field** — so
the defaults below render unchanged, and `replace(DEFAULT_THEME, accent=...)`
restyles a whole family of components at once. Equality is field-wise, so a
custom theme never compares equal to `DEFAULT_THEME` unless every field matches.

| Theme field | Default | Used for |
|---|---|---|
| `dim` | dim gray | secondary rows, placeholders, status lines |
| `muted` | `#8b949e` gray | secondary text (thinking, list markers, quotes) |
| `accent` | `#58a6ff` soft blue | prompts / emphasis / headings / the working label |
| `success` | `#4bb563` soft green | success, `+` rows, ✓ |
| `error` | `#e5534b` soft red | errors, `-` rows |
| `warning` | `#d29922` amber | warnings, notice titles |
| `border` | `#3d444d` blue-gray | rules, panel borders |
| `code` | `#a5d6ff` ice blue | inline code, plain code text |
| `cursor` | reverse video | the block cursor |
| `selection` | the selected row | `Select` / `Autocomplete` / `SlashPalette` cursors |
| `user_bg` | `#1c2b3a` slate blue | the `user` band |
| `tool_bg` | `#16281c` deep green | the `"tool"` tone band |
| `code_bg` | `#12181f` near-black blue | the `"code"` tone / `EditBlock` band |
| `table_border` | no color | `Table` grid lines (`Table(border_style=...)` tints them) |
| `first_column` | `#bc8cff`, bold | `Table` data rows' first column |
| `headings` | derived from `accent`/`muted` | the Markdown heading ladder |
| `tones` / `title_tones` | derived from `tool_bg`/`code_bg`/`success` | the `ToolBlock` bands |
| `notice_levels` | derived from `warning`/`error` | the `Notice` level labels |

The semantic colors mirror the exported `core.style` constants (`DIM`, `MUTED`,
`ACCENT`, `SUCCESS`, `ERROR`, `WARNING`, `BORDER`, `CODE`, `CURSOR`,
`SELECTION`); the band colors and the table defaults used to live in the
component modules themselves and now live only in `Theme`.

## widgets — text & structure

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None)` | Rule-registry engine: paragraphs, `#`–`######` headings, fenced code, lists, block quotes, GFM tables, thematic breaks, inline `` `code` ``/`**bold**`/`*italic*`/`[t](u)`; unknown constructs degrade to paragraph. See below. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None)` | Full-width rule from one repeated character; a `label` embeds `char*2 + " " + label + " " + char*fill` (e.g. `── ⠋ Working ───`) across the full width, an over-wide label is ellipsize'd to `width - 4`, and `label`/`label_style` are mutable attributes. |
| `Notice` | `Notice(text, *, level="info")` | One message row; `warn`/`error` prepend a styled label. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None)` | Child inside a single-line box; titled top border when it fits. |
| `Row` | `Row(children, *, widths=None, gap=1)` | Side-by-side columns (fixed/flex widths), tallest child sets the height. |
| `Column` | `Column(children, *, gap=0)` | Vertical stack with `gap` blank rows between children. |
| `Spacer` | `Spacer(rows=1)` | Blank rows — the transcript rhythm's building block. |
| `Padding` | `Padding(child, *, left=0, right=0, top=0, bottom=0)` | A child inset on all four sides, fill themed. |

## widgets — input & choice

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=None, …, keymap=None)` | Single-line cursor-editable field (`insert`/`backspace`/`delete`/`move_*`/`home`/`end`/`clear`); up/down follow wrapped rows; empty+focused shows a dim placeholder. Keys route through `handle_key(key, width)` and the component's **keymap** — the driver feeds keys, it reads none. |
| `Editor` | `Editor(*, text="", placeholder="", …, keymap=None, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; `newline`/`insert` (multi-line paste) / merged `backspace`; `max_rows` caps the rendered rows with a sliding window on the cursor. `enter` is unbound in the composer's keymap so it stays the host's submit gesture. |
| `Select` | `Select(options, *, title="", label_style=None, selected_style=None, hint_style=None, title_style=None)` | Vertical `Option(label, value, hint)` list; `move(delta)` clamped cursor, `selected` getter; selected row marked `❮`. |
| `Confirm` | `Confirm(message, *, danger=False)` | Yes/No `Select`; `danger` styles the message in `ERROR`. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |

## widgets — data, progress & status

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None)` | Full box frame (`┌─┬─┐` top / `├─┼─┤` header rule / `└─┴─┘` bottom) with uncolored rules by default; cells are `str` or `(str, Style)`; natural column widths, proportional shrink + ellipsis when over width, never stretched below natural size. |
| `Tabs` | `Tabs(tabs, *, active=0, active_style=None, inactive_style=None, divider="│")` | One row of tab labels, the active one emphasized and `│`-separated. |
| `Tree` | `Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None)` with `TreeNode(label, children=(), *, expanded=False)` | Indented tree; `expanded` toggles a node's children in place; a cursor style marks the selected row. |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None)` | Determinate bar: filled `█` run over shaded `░` run inside `[ ]`, clamped to `[0, 1]`. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, label_style=None, hint_style=None, selected_style=None)` | The filter kernel: prefix matching (`query`, `set_query`, `move`), a scrolling window that keeps the cursor visible, `selected` getter, `render` — the engine `SlashPalette` is built on. |
| `StatusBar` | `StatusBar(*, segments=())` with `StatusSegment(text, priority=0)` | Priority-ordered footer cells via `segment(text, priority)`; keeps the highest priority and drops the lowest first to fit. |

## chat — the pi-style pieces

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Message` | `Message(role, text="", *, style=None)` | Role-banded chat row: `user` (full-width color band, 1 pad cell per side, plus one **pure band padding row** above and below — the in-band vertical padding), `assistant` (plain), `thinking` (dim italic); unknown role degrades to `assistant`. `style` overrides the role default. |
| `ToolBlock` | `ToolBlock(title, body=(), *, tone="tool", footer="")` | Tool call: bold title row, blank row, `body` rows, italic footer ("Took 0.1s"), the whole block wrapped in **pure band padding rows** (top and bottom, following `tone`). `tone` picks the band: `tool` (deep-green truecolor, green bold title), `code` (near-black), `plain` (none). Empty sections leave no stray gap; the padding rows always stay. |
| `EditBlock` | `EditBlock(path, context=(), removed=(), added=())` | A diff wrapped in pure band padding rows (top and bottom): accent path row; numbered context / `-` (red) / `+` (green) rows; last added row ends in a green `(edited)` badge. |
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, gap_style=None)` | Exactly one dim two-sided row: left part at column 0, right part one column short of the width, computed gutter between (at least one column); `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place. Over-wide rows keep the left part and ellipsize the right tail. |
| `SlashPalette` | `SlashPalette(commands, *, theme=None, max_rows=8)` | The command palette a leading slash opens: `open()`/`close()`/`sync_query(editor_text)` (the leading slash owns it — lose the slash, close), and `handle_key(key) -> str \| None \| False` consuming only up/down/enter/escape. Renders zero rows while closed. |
| `Composer` | `Composer(theme=None, *, prompt="", placeholder="…", commands=[])` | **Controller.** `attach(tui)` pins the five-piece footer (top rule / `Editor` / bottom rule / palette slot / `StatusLine`); `.editor`, `.palette`, `.statusline` are its pieces; `set_working(on)` ref-counts the working spinner's label; `anchor_cursor(tui)` pins the IME cursor. Enter is the host's; `c-j` breaks lines (`COMPOSER_KEYMAP`). |
| `Transcript` | `Transcript(tui, *, theme=None, spacer=True)` | **Controller.** The body message stream: `append(component)` (plus one blank row after each block when `spacer`), `stream(role) -> StreamHandle` (`.append(chunk)` to grow, `.seal()` to freeze), `clear()` empties the body while the pinned regions stay. |

The two controllers are not `render(width)` components: they touch the TUI's
document and driver (pinned blocks, `TUI.every`, the painter's IME anchor) —
that assembly is what the `chat` layer exists for. Everything else in it is an
ordinary component.

### Markdown

`Markdown` (in `mocode_tui.widgets.markdown`) is a **rule-registry
engine**, not a regex pile. Two ordered registries do all the work: a
`BlockRule` classifies the line at the cursor — `match(lines, i)` returns how
many lines it consumes, `None` to decline — and renders exactly those lines;
an `InlineRule` recognizes one inline construct at a position and returns
`(end, segments)`. The engine walks the buffer, first match wins, and
`ParagraphRule` is the mandatory catch-all at the end of `BLOCK_RULES`.

| element | input | rendering |
|---|---|---|
| heading | `#`..`######` + space | h1 ACCENT bold, h2 ACCENT+underline, h3 MUTED, h4–h5 MUTED dim, h6 MUTED dim italic |
| unordered list | `- ` / `* ` (2-space indent per level) | marker kept **verbatim** (no bullet), nesting by indent, hanging indent on wrap |
| ordered list | `N. ` | number kept verbatim, nesting as above |
| block quote | `> ` | every line gets a muted `│ ` prefix |
| fenced code | ```` ``` ````-delimited | code rows highlighted through the `Highlighter` seam (`highlighter=`, the theme's `code` style by default), language tag dropped, unclosed fence runs to the end |
| table | `\| a \| b \|` + `\|---\|---\|` | box grid via the `Table` component (uncolored `Theme.table_border`, bold header, `:--`/`--:`/`:-:` alignment) |
| thematic break | `---` / `***` on its own line | full-width `Divider` rule |
| paragraph | anything else | soft line breaks join, word-wrapped |
| inline | `` `code` `` `**b**` `*i*` `[t](u)` | `CODE` ice blue / bold / italic / ACCENT+underline label + MUTED ` (url)` |

**Streaming is safe by construction.** `text` is mutable — assign it one
chunk at a time — and every prefix renders: a half-open fence keeps its body,
a table is only a table once header *and* delimiter row are both present
(otherwise it is a paragraph), and an unclosed `**`/`` ` ``/`[t](` stays
literal. No row ever exceeds `width`.

**Extending is construction, not patching:**

```python
from mocode_tui import Markdown
from mocode_tui.widgets.markdown import BLOCK_RULES, INLINE_RULES

md = Markdown(
    text,
    block_rules=[MyBlockRule(), *BLOCK_RULES],   # first match wins
    inline_rules=[MyInlineRule(), *INLINE_RULES],
)
```

A block rule is `name` + `match(lines, i)` + `render(lines, width)`; an inline
rule is `name` + `match(text, pos) -> (end, [Segment, ...])`. Block rules that
parse inline markup expose `with_inline_rules(rules)`, and `Markdown` re-binds
the built-ins, so a custom inline rule reaches every built-in block and a
custom block rule interrupts paragraphs like a built-in one. A `theme=`
reaches the built-in rules the same way (`with_theme(theme)`), restyling
headings, code, quotes, list markers, links and the embedded
`Table`/`Divider`; custom rules keep their own styles.

**Math is the documented extension point, not a feature.** `$...$` slots in
as one more `InlineRule` (and `$$...$$` display equations as one more
`BlockRule`); the registries are the only integration surface, so nothing in
the engine needs to change when it lands.

### Highlighting

`Markdown(..., highlighter=...)` — and any component that takes the seam —
accepts a **`Highlighter`**: any object with `highlight(code, lang) ->
list[Line]`. The built-in `RegexHighlighter` colors ~25 languages with five
token classes resolved against the theme (`comment` muted-italic, `string`
success, `number` warning, `keyword` accent, `builtin` code-bold), per-line and
first-match-wins; `default_highlighter()` shares the stock instance (building
one compiles every rule, so components share rather than rebuild), and
`RegexHighlighter(theme=…, languages=…)` restyles or extends the table.
`highlight(code, lang)` is the convenience entry point. Injecting your own
object replaces the engine entirely — the protocol is the integration surface.

## Building your own component

A component is one class with `render(width)`. The protocol is `mocode_tui.Component`:

```python
from mocode_tui import DIM, Line, NONE, Segment, Style, SUCCESS
from mocode_tui import Component

class ProgressBar:
    """A determinate progress bar -- a custom component, not a library one."""
    __slots__ = ("fraction", "label")

    def __init__(self, fraction: float, label: str = ""):
        self.fraction = min(1.0, max(0.0, fraction))  # clamp to [0, 1]
        self.label = label

    def render(self, width: int) -> list[Line]:
        lead = f"{self.label} " if self.label else ""
        lead_w = Line.from_text(lead).width
        track = max(0, width - lead_w - 2)  # room for the [ ] frame
        done = min(track, int(round(track * self.fraction))) if track else 0
        row = Line((
            Segment(lead),
            Segment("["),
            Segment("\u2588" * done, SUCCESS),         # filled: green
            Segment("\u2591" * (track - done), DIM),    # empty: shaded
            Segment("]"),
        ))
        return [row.fit(width)]  # always fit back to the painting width
```

Rules of thumb:

- **Measure, don't guess.** Use `Line(...).width` (or `Segment` counts) for
  display width — never `len()`, which miscounts wide characters. The toolkit's
  own truth is `visible_width` (wcwidth), exported at the package root
  together with `wrap_text` and `ellipsize_tail`; `Line.width` is its
  per-row face.
- **Always `fit(width)`** the rows you return so a tight screen truncates with a
  `…` instead of wrapping or overflowing.
- **Keep it pure.** `render` must not paint, sleep, read keys, or mutate global
  state — the same component renders in any width and caches like any other.
- **Drive it through the driver.** Put it in a block (`tui.add(ProgressBar(0.4))`),
  mutate it over time, and call `tui.invalidate()`; the pump and diff handle the
  rest.

`ProgressBar` and any other class shaped like this drop straight into
`Document.add`, `Row`, `Column`, and `Panel` — which is exactly how the built-ins
are assembled.
