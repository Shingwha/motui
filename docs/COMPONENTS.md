# Components

A component is anything with `render(width) -> list[Line]`. That single
protocol — frozen since the first wave — is the whole contract.

## The protocol

- **`render(width)` returns rows.** One `Line` per visual row, each already
  wrapped and sized. A component never paints, scrolls, or touches a screen.
- **`width` is the full painting width** — on a real screen that is
  `screen.width`; a `Row`/`Column` child gets the width its parent gives it.
  The painter only counts rows; components own their own wrapping and
  truncation.
- **`Line`** is an immutable run of styled **`Segment`**s (`text` + `Style`),
  with `width` (display columns via wcwidth), `fit(width)`
  (truncate-with-ellipsis) and `pad_to(width)`. `Line`, `Segment` and
  `Style` live in the kernel (`mocode_tui.core.lines` /
  `mocode_tui.core.style`) and are exported at the package root.
- **Sealing is a cache hint, not a render mode.** `BlockState` is
  `OPEN`/`SEALED` only — a sealed block renders once per width and is cached;
  an open block re-renders every frame. There is no "inline" or "committed"
  render mode; the same `render(width)` runs in both states.
- **Editing keys arrive as events, not coordinates.**
  `Input` / `Editor` / `Autocomplete` / `SlashPalette` consume an event
  through `handle_key(event)` and answer `True` when they consumed it. The
  wrap geometry that `move_up`/`move_down` follow comes from the component's
  last render (80 columns before the first render), not from the event — a
  host that renders a field at 40 columns and then feeds it a `down` moves
  inside the geometry the user actually saw, and a component never asks the
  host to pass a width back in.

Every component below is importable straight from `mocode_tui`; the generic
ones also from `mocode_tui.widgets`, the pi-style ones from
`mocode_tui.chat`.

## Styling: Style and Theme

`Style(fg=..., bg=..., ...)` is frozen and hashable (so `prefix()` is
memoized per instance) and takes a color in one of three forms:

- a **named 16-color** from `core.style.FG_CODES` (`"red"`,
  `"bright_black"`, …); unknown names raise `KeyError` from `prefix()`;
- a **`"#rrggbb"` string** or an **`(r, g, b)` tuple** — both emit 24-bit
  truecolor SGR (`38;2;r;g;b` / `48;2;r;g;b`). Truecolor is a superset of
  the named set, so old named styles keep working unchanged.

Attributes are `bold`, `dim`, `italic`, `underline`, `reverse`, `strike`
(SGR `9`, crossed-out) and `reverse`; `merge(other)` OR-sets the booleans
and lets `other`'s colors win — the operation a component uses to layer an
emphasis onto a base band. An attribute-only style (no `fg`/`bg`) merges
*under* whatever run it lands in, which is how `**bold**` inside an accent
heading stays accent.

**`Theme`** (a frozen dataclass, `DEFAULT_THEME` as the shipped instance) is
the one place every semantic default lives. A component takes an explicit
`style=...` (which always wins) plus `theme=Theme | None`, and resolves each
style **once, at construction**, as **explicit > theme field >
`DEFAULT_THEME`** — storing the resolved `Style` (or the resolved `Theme`,
when the choice depends on a mutable attribute such as `Message.role`). A
`render(width)` call looks its styles up rather than resolving them.
`replace(DEFAULT_THEME, accent=...)` still restyles a whole family of
components at once, and nothing global is mutated. Equality is field-wise,
so a custom theme never compares equal to `DEFAULT_THEME` unless every field
matches.

| Theme field | Default | Used for |
|---|---|---|
| `dim` | dim | secondary rows, placeholders, the `Editor`'s dim states |
| `muted` | `#8b949e` gray | secondary text (thinking, quote bars, fence lines) |
| `accent` | `#58a6ff` soft blue | prompts, the working label, syntax keywords |
| `success` | `#4bb563` soft green | success, `+` rows, ✓, the `ProgressBar` fill |
| `error` | `#e5534b` soft red | errors, `-` rows, a dangerous `Confirm` |
| `warning` | `#d29922` amber | warnings, notice titles |
| `border` | no color (terminal default fg) | rules, panel borders |
| `code` | `#a5d6ff` ice blue | untagged/unknown fence code, syntax `builtin` |
| `cursor` | reverse video | the block cursor (`Input` / `Editor`) |
| `selection` | `reverse` + `dim` | `Select` / `Autocomplete` / `SlashPalette` cursors |
| `heading` | `#e3b341` gold | the Markdown heading ladder's base |
| `link` | `#58a6ff`, underlined | Markdown link labels (never bold) |
| `inline_code` | `#f778ba` pink | inline `` `code` `` runs |
| `list_marker` | `#bc8cff` purple | list bullets / numbers |
| `user_bg` | `#1c2b3a` slate blue | the `user` band |
| `tool_bg` | `#16281c` deep green | the `"tool"` tone band |
| `code_bg` | `#12181f` near-black blue | the `"code"` tone / `EditBlock` band |
| `table_border` | no color | `Table` grid lines (`Table(border_style=...)` tints them) |
| `first_column` | no color (plain) | `Table` data rows' first column |
| `scrollbar` | dim | the `Scrollbar` track (`░` cells) |
| `scrollbar_thumb` | no color (plain fg) | the `Scrollbar` thumb (`█` cells) |
| `toast` | reverse + dim | the `Toasts` band |
| `headings` | derived from `heading` | the Markdown heading ladder (read-only property) |
| `tones` / `title_tones` | derived from `tool_bg`/`code_bg`/`success` | the `ToolBlock` bands |
| `notice_levels` | derived from `warning`/`error` | the `Notice` level labels |

The semantic colors mirror the exported `core.style` constants (`DIM`,
`MUTED`, `ACCENT`, `SUCCESS`, `ERROR`, `WARNING`, `BORDER`, `CODE`,
`CURSOR`, `SELECTION`, plus the markdown palette `HEADING`, `LINK`,
`INLINE_CODE`, `LIST_MARKER`); the band colors and the table defaults live
only in `Theme`. **Bold is reserved for the `**…**` syntax itself and
strike for `~~…~~`**: none of the markdown-facing defaults (the heading
ladder, the link, inline code, list markers, the table header, the table
first column) is bold or struck — structure reads by color instead of weight
(syntax highlighting's keyword=accent aside).

## widgets — text & structure

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. `theme` is carried for the uniform signature; plain text has no theme-able style of its own. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None, gap=1, divider_max_width=80)` | Rule-registry engine: paragraphs, `#`–`######` headings, fenced code, lists, block quotes, GFM tables, thematic breaks, inline `` `code` ``/`**bold**`/`~~strike~~`/`*italic*`/`[t](u)`; unknown constructs degrade to paragraph. See below. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None, theme=None, max_width=None)` | Full-width rule from one repeated character; a `label` embeds `char*2 + " " + label + " " + char*fill` (e.g. `── ⠋ Working ───`) across the full width, an over-wide label is ellipsize'd to `width - 4`, and `label`/`label_style`/`max_width` are mutable attributes. |
| `Notice` | `Notice(text, *, level="info", theme=None)` | One message row; `warn`/`error` prepend a styled label from the theme's `notice_levels`. Any other level degrades to plain `info`. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None, theme=None)` | Child inside a single-line box; titled top border when it fits. |
| `Row` | `Row(children, *, widths=None, gap=1)` | Side-by-side columns (fixed/flex widths), tallest child sets the height. |
| `Column` | `Column(children, *, gap=0)` | Vertical stack with `gap` blank rows between children. |
| `Spacer` | `Spacer(rows=1)` | Blank rows — the transcript rhythm's building block. |
| `Padding` | `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None)` | A child inset on all four sides; with `fill_style` set the blank areas are painted and merge *under* the child's colors (the `Message` user band's pattern). The fill is never themed. |

## widgets — input & choice

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=None, prompt_style=None, cursor_style=None, focused=True, theme=None, keymap=None)` | Single-line cursor-editable field (`insert`/`backspace`/`delete`/`move_*`/`home`/`end`/`clear`); up/down follow wrapped rows; empty+focused shows a dim placeholder. Keys route through the component's **keymap** at `handle_key`, answering `True` when consumed — the driver feeds keys, it reads none. `cursor_position(width)` reports the block-cursor cell for an IME anchor. |
| `Editor` | `Editor(*, text="", placeholder="", style=None, cursor_style=None, theme=None, keymap=None, focused=True, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; `newline`/`insert` (multi-line paste) / merged `backspace`; `max_rows` caps the rendered rows with a sliding window on the cursor. `enter` is unbound in the composer's keymap so it stays the host's submit gesture. |
| `Select` | `Select(options, *, title="", label_style=None, selected_style=None, hint_style=None, title_style=None, theme=None)` | Vertical `Option(label, value, hint)` list; `move(delta)` clamped cursor, `selected` getter, `click(row)` for a mouse hit; selected row marked `❮`. |
| `Confirm` | `Confirm(message, *, danger=False, theme=None)` | Yes/No `Select`; `danger` styles the message in `ERROR`. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |

## widgets — data, progress & status

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None, aligns=None, theme=None)` | Full box grid (`┌─┬─┐` top, a `├─┼─┤` rule between every pair of rows, `└─┴─┘` bottom) with uncolored rules by default; cells are `str`, `(str, Style)`, or styled `Segment` runs (inline markup); per-column `aligns` (`left`/`center`/`right`); natural column widths, proportional shrink + ellipsis when over width, never stretched below natural size. |
| `Tabs` | `Tabs(tabs, *, active=0, active_style=None, inactive_style=None, divider="│", theme=None)` | One row of tab labels, the active one emphasized and `│`-separated. |
| `Tree` | `Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None, theme=None)` with `TreeNode(label, children=(), *, expanded=False)` | Indented tree; `expanded` toggles a node's children in place; a cursor style marks the selected row. |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, theme=None)` | Determinate bar: filled `█` run over shaded `░` run inside `[ ]`, clamped to `[0, 1]`; `fraction` is a mutable attribute that re-clamps on assignment. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, label_style=None, hint_style=None, selected_style=None, theme=None)` | The filter kernel: `query`, `set_query`, `move`, a scrolling window that keeps the cursor visible, `selected` getter, `handle_key(event)` — the engine `SlashPalette` is built on. |
| `StatusBar` | `StatusBar(*, segments=())` with `StatusSegment(text, priority=0)` | Priority-ordered footer cells via `segment(text, priority)`; keeps the highest priority and drops the lowest first to fit. Draws no color of its own. |

## chat — the pi-style pieces

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Message` | `Message(role, text="", *, style=None, theme=None)` | Role-banded chat row: `user` (full-width color band, 1 pad cell per side, plus one **pure band padding row** above and below — the in-band vertical padding), `assistant` (plain), `thinking` (muted italic); unknown role degrades to `assistant`. `style` overrides the role default. |
| `ToolBlock` | `ToolBlock(title, body=(), *, tone="tool", footer="", theme=None)` | Tool call: title row, blank row, `body` rows, italic footer, the whole block wrapped in **pure band padding rows** (top and bottom, following `tone`). `tone` picks the band: `tool` (deep green, green bold title), `code` (near-black), `plain` (none). |
| `EditBlock` | `EditBlock(path, context=(), removed=(), added=(), *, theme=None)` | A diff wrapped in pure band padding rows (top and bottom): accent path row; numbered context / `-` (red) / `+` (green) rows; last added row ends in a green `(edited)` badge. |
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, gap_style=None)` | Exactly one dim two-sided row: left part at column 0, right part one column short of the width, computed gutter between (at least one column); `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place. Over-wide rows keep the left part and ellipsize the right tail. |
| `SlashPalette` | `SlashPalette(commands, *, theme=None, max_rows=8)` | The command palette a leading slash opens: `open()` / `close()` / `set_query(text)` (the leading slash owns it — lose the slash, close), and `handle_key(key) -> str \| None \| False` consuming only up/down/enter/escape. Renders zero rows while closed. |
| `Composer` | `Composer(theme=None, *, prompt="", placeholder="", commands=[])` | **Controller.** `attach(tui)` pins the five-piece footer (top rule / `Editor` / bottom rule / palette slot / `StatusLine`); `.editor`, `.palette`, `.statusline` are its pieces; `set_working(on)` ref-counts the working spinner's label; `anchor_cursor(tui)` pins the IME cursor. Enter is the host's; `c-j` breaks lines (`COMPOSER_KEYMAP`). |
| `Transcript` | `Transcript(tui, *, theme=None, spacer=True)` | **Controller.** The body message stream: `append(component)` (plus one blank row after each block when `spacer`), `stream(role) -> StreamHandle` (`.append(chunk)` to grow, `.seal()` to freeze), `clear()` empties the body while the pinned regions stay. |

The two controllers are not `render(width)` components: they touch the TUI's
document and driver (pinned blocks, `TUI.every`, the painter's IME anchor) —
that assembly is what the `chat` layer exists for. Everything else in it is
an ordinary component.

## The frame tier — Pane, split, chrome, overlays

The frame model's public face, all of it host policy over the driver's
`tui.frame` seam (the tiling, its focus, its overlay registry, each pane's
last layout). `mocode_tui.chrome` is the assembly tier — the peer of
`mocode_tui.selection` — and the three space claims it implements (pane /
chrome / overlay) are the design constitution in
[`docs/DESIGN.md`](DESIGN.md).

### `Pane` and `split` — the rectangles

```python
tui.split("vertical" | "horizontal", *, ratios=(1, 1), min_size=1, separator=True) -> tuple[Pane, ...]
left, right = tui.split("vertical", ratios=(2, 1))   # transcript | preview
left.document; left.viewport; left.focus(); left.split(...)   # the Pane handle
```

`tui.split` divides the **focused** pane and returns the children in paint
order — one code path with `Pane.split`. The first child keeps the split
pane's id, document, viewport and chrome, so a host's blocks and any chrome
registered before the split ride the division; every child after it opens
over a fresh, empty document (`right.document.add(...)` is the preview side
of the split). A split leaves focus where it was, and re-divides the tiling
immediately, so the returned panes already hold their rectangles. The 1-cell
separator is inter-pane chrome (budgeted, never a gap) themed by focus — the
tmux convention: the theme's `accent` beside the focused pane, its `border`
otherwise — and `separator=False` leaves the panes abutting. There is no
`Theme.separator` field: a host wanting a different look splits with
`separator=False` and registers its own chrome on the pane (the recipe
below). A resize re-divides the same tree in place: every pane keeps its
viewport, its chrome and its scroll state.

### `Scrollbar` — the reference chrome

```python
Scrollbar(tui, *, pane=None, size=1, min_thumb=1, style=None, thumb_style=None, theme=None, scroll_tick=0.05)
scrollbar = Scrollbar(tui)            # pane=None: the frame's first pane
scrollbar.handle(event) -> bool       # the consume-a-key contract
scrollbar.detach()                    # unregister + cancel the ticker
```

Constructing the bar registers a right-edge `Chrome` on its pane (an id the
frame does not hold raises `ValueError`); the budget is negotiated at the
next composition and the pane's viewport re-wraps at the reduced width.
`detach()` is the symmetric unregister (`Pane.remove_chrome`), and the
registration rides a retile: a split keeps the pane's id on its first child,
so a bar on the transcript survives the division. The strip paints from the
pane's last layout alone — `offset` / `total_rows` are the only view state a
painter reads — and the thumb geometry is pure arithmetic over them (a small
window over a long document is a short thumb; a document that fits paints a
plain track). `handle(event)` is the bar's own gesture: a left press in the
strip is consumed (grab-and-drag on the thumb, anchored so it never jumps; a
held track click pages and repeats), every other event — every key, every
paste, every wheel report, every press outside the strip — passes through.

### `Toasts` — the reference overlay

```python
Toasts(tui, *, ttl=4.0, max_shown=3, corner="top-right", style=None, theme=None)
toasts = Toasts(tui)                  # registers the overlay on the frame
toasts.show("Copied 2 lines")         # a str, or any Component
toasts.handle(event) -> bool          # dismiss the toast under the pointer
toasts.detach()                       # unregister + cancel the ticker
```

`show` takes a plain string (wrapped in a `Text`) or any `Component` — a
toast can be a `Notice`, a `Spinner`, a host's own renderable — plus an
optional per-toast `style` (it wins over the controller's) and `ttl`. A show
past `max_shown` evicts the oldest; the stack grows away from `corner`, one
blank row between neighbours, and never covers more than half the frame. The
paint is the pure half (`frame -> layout`, the frame's rows and the live list
its only inputs) and the controller owns everything time- and input-shaped:
one `tui.every` ticker checks expiry against `tui._clock()`, and `handle`
consumes a press inside a toast's own rectangle to dismiss it. `detach()`
unregisters the overlay (`Frame.remove_overlay`) and cancels the ticker.

### The dispatch order

One rule everywhere, and it is geometric: a host routes every event through
the chrome before any content gesture and before its own dispatch, with the
overlays between the chrome and the gestures.

```python
scrollbar = Scrollbar(tui)            # chrome, first
toasts = Toasts(tui)                  # overlays, next
gesture = SelectionGesture(tui)       # content gestures
event = await tui.read_key()
if not scrollbar.handle(event):       # 1. chrome
    if not toasts.handle(event):      # 2. overlays
        if not gesture.handle(event): # 3. gestures
            ...                       # 4. the host's own dispatch
```

Three rules make the order exact. **Chrome first, and geometrically:** the
bar's strip is derived from its pane's rectangle, so it routes before any hit
test runs — a press that reached a hit test first would anchor a selection on
the text under the strip. **Overlays after chrome, before gestures, also
geometrically:** an overlay's band is derived from the frame's rectangle the
same way, so a press inside a toast has to be consumed before a hit test
runs, and placing overlays after the chrome keeps the bar's own columns the
bar's. **Gestures before the host's dispatch:** the bar, the overlays and the
gesture speak the same consume-a-key contract, so a controller that consumed
an event leaves no trace in the host's state. **The wheel is nobody's
chrome:** `read_key` intercepts `scroll_keys` before the host loop runs, so a
wheel report never reaches `Scrollbar.handle` — one that does (a host that
deleted the binding) passes through untouched. A host with a cell-level
affordance of its own — the pi demo's foldable tool calls, whose chevron row
owns its click — resolves those cells between the overlays and the gesture:
the row is the call's, every other cell is the gesture's.

### Build your own chrome — a 2-column rail

A chrome is one `Chrome(edge, size, paint)` value whose `paint` is a pure
function of the pane's last layout and the strip's length. The reference
recipe is a line-number rail: two budgeted columns on the left edge, numbered
from the layout's `offset` over its `total_rows` — no viewport attribute is
ever touched.

```python
from mocode_tui import DEFAULT_THEME, Line, Style, Theme

from mocode_tui.core.frame import Chrome


class LineNumberRail:
    """A 2-column gutter: chrome that numbers the rows it sits beside."""

    def __init__(self, *, style: Style | None = None, theme: Theme | None = None):
        self._style = style or (theme or DEFAULT_THEME).dim  # resolved once

    def chrome(self) -> Chrome:
        # "left", 2: the budget asked of the pane; the paint below fills it.
        return Chrome("left", 2, self._paint)

    def _paint(self, layout, length: int) -> list[Line]:
        # layout.offset / layout.total_rows: the pane's scroll state as it
        # was laid out — the only view a painter reads.
        first = layout.offset + 1
        rows = []
        for index in range(length):
            number = first + index
            if number > layout.total_rows:            # past the document
                rows.append(Line.filled(2))           # a blank rail cell
                continue
            rows.append(Line.from_text(f"{number:>2}"[-2:], self._style))
        return rows                                   # each row exactly 2 wide


rail = LineNumberRail().chrome()
tui.frame.pane("primary").add_chrome(rail)   # the budget negotiates at the next composition
```

That is the whole surface: `add_chrome` registers (the pane's viewport
re-wraps at the reduced width), `remove_chrome` unregisters by identity, the
compositor clips a budget that would squeeze the viewport out, and a
`size: 0` chrome is a legal no-op seam. Chromes stack — several on one edge
sit outermost-first, budgets add — so a rail beside a gutter is two chromes.

### Build your own overlay

An overlay is the other half of the registry: any object with
`paint(frame) -> layout`, registered with `tui.frame.add_overlay` and
unregistered by identity with `remove_overlay` (a missing entry raises —
test membership first to keep a `detach()` idempotent). The worked example
ships in the driver: the selection highlight is overlay #1, a `paint` that
marks the focused pane's own layout and splices the marked rows back through
`Frame.with_pane_rows` — the same column splice the compositor runs and a
toast paints with. `Toasts` is the reference *controller* over that protocol
(registration at construction, time on the pump's clock, input on its own
geometry); a minimal overlay of your own is the `Toasts.paint` shape — read
`frame.layout`, rewrite rows, hand the layout back (unchanged, when there is
nothing to paint).

## Selection

Selection is another assembly that touches the driver — the peer of
`Composer`/`Transcript` and the `chrome` controllers, not a `render(width)`
component. The mechanism is the kernel's (`mocode_tui.core.selection`: the
`Selection` model, the `highlight` overlay, `extract`) and the driver's
(`tui.selection` reads, `tui.set_selection` writes and invalidates); every
behavior is one policy object (`mocode_tui.selection`) a host opts into with
a single line. The rationale — document-space addresses, the overlay at the
composition root, the mode table, OSC 52's contract — is `docs/DESIGN.md`;
this section is the handbook: the constructor, the state machine, the
primitive, and the cookbook of replacement points.

### `SelectionGesture` — the constructor

```python
SelectionGesture(
    tui,
    *,
    on_end=copy_on_select,   # the selection-end action; None selects with no effect
    scroll_rows=2,           # rows one edge tick scrolls — and extends the head
    scroll_tick=0.05,        # seconds between edge ticks
    double_click_seconds=0.35,  # the word-select window around the last press's cell
)
gesture.handle(event) -> bool   # the consume-a-key contract: True consumed, False the host's
gesture.detach()                # cancel the ticker, drop the in-flight drag
```

The gesture is single-pointer by construction: the **left** button anchors
and extends, every other button, every key, every `Paste` and every lone
motion passes through untouched. It owns its own anchor and head addresses
and mirrors the drag into the driver through `set_selection`; it keeps no
copy of the text, the rows, or the layout. Timestamps come from the
controller's clock seam (`tui._clock()`), so the event model itself stays
timeless.

### The state machine

The host's dispatch is `if not gesture.handle(event): ...` — the same
consume-a-key contract `Input`/`Editor` answer, with one dispatch line
covering the whole feature. What the left button's reports do:

| Report | Effect |
|---|---|
| `press` (plain) | Anchors at the cell the hit test resolves. A press on blank fill, outside the last layout, or on a block removed since it retires the previous highlight and anchors nothing. A zero-width range paints nothing, so the previous highlight already yields to this press. |
| `press` on an edge row | Arms the auto-scroll ticker immediately, not only a motion: the pointer can reach the edge *before* the button goes down, and a stationary press there emits no motion to arm it with. |
| `press` again, same cell, within `double_click_seconds` | Word select: the maximal non-whitespace run around that cell on its row, measured in display columns through the same measure the kernel cuts by — a CJK character selects whole. It fires `on_end` exactly once, at the press; the release that follows finalizes nothing; and it never arms the ticker. A cell on whitespace (or past the row's text, which clamps to the last column) has no run and degrades to a plain press — a double-click between words behaves like a click. |
| `motion` while dragging | Extends the head to the cell under the pointer. A motion off the content keeps the head where it is. A cleared overlay underneath the drag (a reflow, or a host write) ends the drag cleanly rather than dragging addresses that no longer point at the same glyphs. |
| `motion` onto an edge row | Arms the edge ticker; a motion onto any other in-content row disarms it; a motion off the content disarms it too. The edge zone is the viewport region's first and last rows — the scrolling window, never the pinned footer — so dragging into the composer cannot scroll the transcript. |
| `release` | Cancels the ticker and finalizes. A zero-width press-release — a click — clears the selection and never fires `on_end`: the clipboard is never clobbered by a click. A completed drag fires `on_end` exactly once, and the highlight stays until the next press so the user can verify what was copied. |
| wheel while a drag is in flight | Consumed: scrolls the viewport its signed `scroll_keys` count and co-extends the head by exactly the rows the viewport actually travelled (the wheel moves the content under a still pointer; the head follows). A binding the host deleted from `tui.scroll_keys` passes through. |
| second `press` mid-drag | Re-anchors a fresh drag from the new cell; the abandoned drag never fires `on_end`. |

The armed ticker rides the pump's existing `every(seconds, fn)` handles — the
Composer-spinner pattern, no new mechanism. Each tick scrolls `scroll_rows`
rows and moves the head by the offset the viewport actually travelled, in
document space, never by re-`hit_test`ing the previous frame's ownership
table. It stands down on edge-exit, release, `detach()`, a reflow that
cleared the overlay underneath it, and the document end (a scroll that could
not move the viewport means the content under the pointer is frozen too).
`detach()` cancels the ticker and drops the in-flight drag so a later release
cannot finalize it; the stored overlay is the driver's, and stays as the last
frame painted it.

### `copy_on_select` — the shipped `on_end`

```python
def copy_on_select(tui, selection):
    tui.screen.copy(extract(tui.document, selection, width=tui.screen.width))
```

Two lines, and the smallness is the point: every mechanism (the range walk
of `extract`, the clipboard primitive) lives in the kernel already, and the
whole policy is "which text, which screen, once". `extract` takes `width`
keyword-only — it is the width the addresses were laid out against, and
there is no honest default — and it reads the document blocks straight, so
content the viewport has scrolled past copies exactly like the visible rows.

### `Screen.copy` — the clipboard primitive

`screen.copy(text) -> bool` emits `\x1b]52;c;<base64>\a` (built in
`core.ansi.copy_clipboard`) and reports whether it wrote. A
`TerminalScreen` writes only when live — a pipe or a file has no clipboard
and the toolkit never scatters escapes at a surface that cannot render them,
so `copy` answers `False` there. A `HeadlessScreen` is live by construction
and records the bytes: that is how a test proves a copy happened, since
nothing observable comes back from a live terminal. Even a `True` is
best-effort — terminals may refuse application clipboard writes by policy —
which is why the gesture's `on_end` hook, not the primitive, is the real
contract.

### The extension cookbook

Four worked replacement points. Between them they are the whole surface a
future feature author needs — none of the recipes below reaches into the
kernel.

**(1) Drive `tui.set_selection` from your own loop.** A search feature
highlights its hit without any gesture at all: the driver's surface is one
write, and the overlay paints it.

```python
from mocode_tui.core import Selection

# Your search found "transcript" on block "b1", rendered row 0, column 15.
term = "transcript"
anchor = ("b1", 0, 15)
tui.set_selection(Selection.between(anchor, ("b1", 0, 15 + len(term))))
# The write invalidates the frame; the pump repaints, overlay included.
```

**(2) Replace `on_end` — the `/quote` example.** This is an extension
example, **not shipped chat API**: the toolkit ships no `/quote` command.
It shows the hook receiving the finished range and prefilling the composer
for an edit, through the editor's own buffer API.

```python
from mocode_tui import SelectionGesture
from mocode_tui.core import extract

def quote_on_select(tui, selection):
    """Quote the selection into the composer: extract, prefix, prefill."""
    text = extract(tui.document, selection, width=tui.screen.width)
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    composer.editor.clear()          # replace whatever is being typed
    composer.editor.insert(quoted)   # multi-line paste inserts through the same API
    tui.invalidate()

gesture = SelectionGesture(tui, on_end=quote_on_select)
```

**(3) Tune or retire the sub-gestures.** The three knobs and the `on_end`
switch, all constructor arguments:

```python
gesture = SelectionGesture(
    tui,
    on_end=None,                   # select without copying: no effect at selection end
    double_click_seconds=0.0,      # no word select: a live clock never reads inside a zero window
    scroll_rows=1, scroll_tick=0.02,   # a finer, slower edge crawl — v1 has no auto-scroll off switch
)
```

**(4) Restyle the highlight — own the composition root.** The kernel merges
the fixed `SELECTION` constant (`reverse+dim`, attribute-only, so the run's
own colors survive under the overlay) and v1 has no injection point for it.
The recipe is to own the last step of the frame instead: the overlay is a
pure function over a laid-out frame, so yours composes on the kernel's and
paints through the driver's own painter.

```python
from dataclasses import replace

from mocode_tui import Line, Segment, Style
from mocode_tui.core import highlight

MARK = Style(reverse=True, fg="#ff8800")   # your highlight: reversed, your hue

def my_overlay(layout, selection):
    """The kernel's range cut, your style — the merge happens at your call site."""
    painted = highlight(layout, selection)
    if painted is layout:
        return layout    # the kernel marked nothing (None or an empty range): lazy no-op
    return replace(layout, rows=[
        Line([
            # the kernel marks the in-range pieces by merging SELECTION
            # (reverse + dim): re-merge your own onto exactly those
            Segment(s.text, s.style.merge(MARK)) if s.style.reverse else s
            for s in row.segments
        ])
        for row in painted.rows
    ])

# At a host-owned composition root — the three lines the driver's own paint runs:
layout = tui.viewport.layout(tui.screen.width, tui.screen.height)
layout = my_overlay(layout, tui.selection)
tui.painter.paint(layout)
```

The re-merge keys on `reverse`, which is the kernel's documented mark; a
segment that was already reversed for its own reason (the editor's block
cursor) is indistinguishable from a marked one, so this seam fits content
carrying no cursor of its own. Note the boundary the recipe keeps (D7): the
theme's `selection` field styles the *component* cursors (`Select`,
`Autocomplete`, `SlashPalette`, `Tabs`, `Tree`) — that seam is per-component
`*_style=` arguments — while this overlay is the document-level one. Two
vocabularies, two mechanisms, never mixed.

## Markdown

`Markdown` (in the `mocode_tui.widgets.markdown` package) is a
**rule-registry engine**, not a regex pile. Two ordered registries do all
the work: a `BlockRule` classifies the line at the cursor — `match(lines,
i)` returns how many lines it consumes, `None` to decline — and renders
exactly those lines; an `InlineRule` recognizes one inline construct at a
position and returns `(end, segments)`. The engine walks the buffer, first
match wins, and `ParagraphRule` is the mandatory catch-all at the end of
`BLOCK_RULES`. The shipped inline registry is tried in the order
`code` → `bold` → `strike` → `italic` → `link`: the rules that share an
opening marker (bold and italic both open with `*`) are ordered
sharpest-marker-first, and a rule placed before another interrupts it.

| element | input | rendering |
|---|---|---|
| heading | `#`..`######` + space | one gold ladder from `Theme.headings`; **h1 is underlined**, h2 stands alone, h3+ keep their `###` markers (the marker is the depth cue) — no bold on the ladder |
| unordered list | `- ` / `* ` (2-space indent per level) | marker kept **verbatim** (no bullet), marker in `list_marker` purple, nesting by indent (deeper indents cap at two levels), hanging indent on wrap |
| ordered list | `N. ` | number kept verbatim, marker colored as above, nesting as above |
| block quote | `> ` | every line gets a muted `│ ` prefix; the body re-runs the block registry behind the bar and renders italic (colored/bold segments keep their own emphasis) |
| fenced code | ```` ``` ````-delimited | opening and closing fence lines render in the theme's muted; the body goes through the `Highlighter` seam (`highlighter=`, the theme's `code` style when untagged), an unclosed fence runs to the end |
| table | `\| a \| b \|` + `\|---\|---\|` | box grid via the `Table` component (uncolored `Theme.table_border`, plain header, `:--`/`--:`/`:-:` alignment, cells render inline markup, one `├─┼─┤` between every two data rows, `\|` a literal pipe) |
| thematic break | `---` / `***` on its own line | `Divider` rule capped at `divider_max_width` columns (default 80) |
| paragraph | anything else | soft line breaks join, word-wrapped |
| inline | `` `code` `` `**b**` `~~s~~` `*i*` `[t](u)` | `inline_code` pink / bold / struck (`~~…~~` is an attribute-only `Style(strike=True)`, no colour change) / italic / `link` underlined label (the url is not rendered) |

**Rendering notes:** adjacent blocks are separated by exactly one blank row
— the `gap` argument (default 1; `gap=0` restores the old direct stacking) —
and the source's own blank rows never add a second one. Table cells are
parsed with the inline engine, so `` `code` ``/`**bold**`/`[t](u)` render
inside a grid cell, and an escaped `\|` stays a literal pipe inside one cell
instead of splitting the row. A thematic break spans at most
`divider_max_width` columns (default 80, `None` = the full width). A link
renders its label only, styled with `Theme.link`; the url is dropped. Every
row a rule returns is wrapped and `fit` to `width`, so no row ever exceeds
the painting width.

**Streaming is safe by construction.** `text` is mutable — assign it one
chunk at a time — and every prefix renders: a half-open fence keeps its
body, a table is only a table once header *and* delimiter row are both
present (otherwise it is a paragraph), and an unclosed
`**`/`~~`/`` ` ``/`[t](` stays literal. `StrikeInlineRule` (exported from
`mocode_tui.widgets.markdown`) is the built-in strikethrough: it declines a
`~~` run with no partner or with empty content, so a streaming prefix is
never half-struck.

### The render context

Rules are dep-free singletons — no theme, no registry, no highlighter of
their own — so one instance serves every `Markdown`. What a rule needs to
render arrives in one frozen **`RenderContext`**
(`mocode_tui.widgets.markdown.RenderContext`), which `Markdown` builds once
at construction:

| field | meaning |
|---|---|
| `theme` | the resolved `Theme` (`DEFAULT_THEME` when none was passed) |
| `highlighter` | the fenced-code engine, or `None` (the fence then derives one from the theme) |
| `divider_max_width` | the thematic-break cap the component was built with |
| `block_rules` | the **live** block registry of the document being rendered |
| `inline_rules` | the **live** inline registry |

Because the context carries the *live* registries, a custom rule reaches
every built-in block — quote bodies, list continuations and the paragraph
catch-all that yields to higher-priority rules all re-run the same registry
— with no re-binding of any kind. That is what replaced the old `with_*`
cloning conventions: extending is "implement the protocol, read the ctx".

### A custom inline rule, end to end

The smallest useful extension is one `InlineRule`. An inline rule is
`name` + `match(text, pos, ctx)`; it returns `(end, segments)` when the
construct starts at `pos` and `None` to decline. A style that sets a color
is absolute; an attribute-only style merges onto the surrounding run's base
style.

```python
from mocode_tui import Markdown
from mocode_tui.core.lines import Segment
from mocode_tui.widgets.markdown import INLINE_RULES


class MentionRule:
    """@handle in the theme's accent -- one inline rule, end to end."""
    name = "mention"

    def match(self, text, pos, ctx):
        if text[pos] != "@":
            return None                      # decline: not ours
        end = pos + 1
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1
        if end == pos + 1:
            return None                      # a lone "@" is not a mention
        return end, [Segment(text[pos + 1 : end], ctx.theme.accent)]


md = Markdown("hi @shipped", inline_rules=[MentionRule(), *INLINE_RULES])
for row in md.render(40):
    print(row.text)                        # "hi shipped"
    print([(s.text, s.style.fg) for s in row.segments])
```

That is the whole integration surface:

- **Register by prepending.** `inline_rules=[MyRule(), *INLINE_RULES]`
  (and `block_rules=[MyBlockRule(), *BLOCK_RULES]`) — order is the match
  priority, so put a rule before any rule whose marker it opens with.
- **Read what you need off `ctx`.** `ctx.theme` follows the component's
  `theme=`, so the rule restyles with the document instead of hard-coding a
  color.
- **No cloning.** A custom block rule reaches quote bodies and list items
  automatically, and the paragraph catch-all yields to it, because the
  context carries the live registry.

**Math is the documented extension point, not a feature.** `$...$` slots in
as one more `InlineRule` (and `$$...$$` display equations as one more
`BlockRule`); the registries are the only integration surface, so nothing in
the engine needs to change when it lands.

### Highlighting

`Markdown(..., highlighter=...)` — and any component that takes the seam —
accepts a **`Highlighter`**: any object with `highlight(code, lang) ->
list[Line]`. The built-in `RegexHighlighter` (in
`mocode_tui.widgets.syntax`) colors 16 languages — Python, JavaScript,
TypeScript, bash/shell, JSON, YAML, TOML, Markdown, diff, Rust, Go, C, C++,
HTML/XML, CSS and SQL — under 32 tag keys, aliases included, with five token
classes: `comment` muted + italic, `string` success, `number` warning,
`keyword` the accent's hue, `builtin` the theme's `code` ice blue. **No
token carries weight** — code stays weight-neutral, so the only bold left in
a default render is the `**…**` syntax itself, and the only struck run is
`~~…~~`. Matching is per-line and first-match-wins, and text no rule claims
keeps the theme's `code` style.

`default_highlighter()` shares the stock instance (building one compiles
every rule, so components share rather than rebuild),
`RegexHighlighter(theme=…, languages=…)` restyles or extends the table, and
`highlight(code, lang)` is the convenience entry point. Injecting your own
object replaces the engine entirely — the protocol is the integration
surface.

## Building your own component

A component is one class with `render(width)`. The protocol is
`mocode_tui.Component`:

```python
from mocode_tui import DIM, Line, Segment, Style, SUCCESS


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

`ProgressBar` grew up into a library component (`mocode_tui.ProgressBar`,
with `theme=`, `width_chars=` and re-clamping `fraction`); the recipe is
still the shape a custom one takes.

Rules of thumb:

- **Measure, don't guess.** Use `Line(...).width` (or `Segment` counts) for
  display width — never `len()`, which miscounts wide characters. The
  toolkit's own truth is `visible_width` (wcwidth), exported at the package
  root together with `wrap_text`; `Line.width` is its per-row face and
  `ellipsize_tail` lives in `mocode_tui.core` / `mocode_tui.core.text`.
- **Always `fit(width)`** the rows you return so a tight screen truncates
  with a `…` instead of wrapping or overflowing.
- **Resolve styles once.** Take `style=` / `theme=` and resolve
  explicit > theme > `DEFAULT_THEME` in `__init__`, not in `render`.
- **Keep it pure.** `render` must not paint, sleep, read keys, or mutate
  global state — the same component renders in any width and caches like any
  other.
- **Drive it through the driver.** Put it in a block
  (`tui.add(ProgressBar(0.4))`), mutate it over time, and call
  `tui.invalidate()`; the pump and diff handle the rest.

`ProgressBar` and any other class shaped like this drop straight into
`Document.add`, `Row`, `Column`, and `Panel` — which is exactly how the
built-ins are assembled.
