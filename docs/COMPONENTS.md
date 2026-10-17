## Contents

- [The render protocol](#the-render-protocol)
- [The controller verbs](#the-controller-verbs)
- [The driver, in call order](#the-driver-in-call-order)
- [The component catalogue](#the-component-catalogue)
- [Style and Theme](#style-and-theme)
- [The frame tier](#the-frame-tier)
- [Selection](#selection)
- [Focus](#focus)
- [Markdown](#markdown)
- [Building your own component](#building-your-own-component)
- [Testing](#testing)
## The render protocol
- **`render(width)` returns rows.** One `Line` per visual row, each already
  wrapped and sized. A component never paints, scrolls, or touches a screen.
- **`width` is the full painting width** — on a real screen that is
  `screen.width`; a `Row`/`Column` child gets the width its parent gives it. The
  painter only counts rows; components own their own wrapping and truncation.
- **`Line`** is an immutable run of styled **`Segment`**s (`text` + `Style` + the
  two inline payloads below), with `width` (display columns via wcwidth),
  `fit(width)` (truncate-with-ellipsis) and `pad_to(width)`. `Line`, `Segment` and
  `Style` live in the kernel (`motui.kernel.lines` / `motui.kernel.style`) and are
  exported at the package root.
- **A segment can carry an inline payload: `link` and `action`.** `link` is an url
  the **terminal** is told about — `Line.styled()` wraps that segment's text in the
  OSC 8 pair, so a terminal opens a real hyperlink (its own cmd+click included);
  `action` is the name the **application** gives to a click on that run. `link` is
  part of the segment's value (a changed link repaints the row); `action` is
  metadata that never reaches a byte, so it is excluded from equality. The pure
  `motui.kernel.action_at(line, col) -> (action, start, end) | None` resolves which
  run a column landed on (display columns, left-closed and right-open); a
  component's hit testing reads its **last render's row table** through it, never
  the host's coordinates.
- **Sealing is a lifecycle fact, and the row cache reads it.** `BlockState` is
  `OPEN`/`SEALED` only, and the same `render(width)` runs in both states: a sealed
  block is frozen and its rows are always cached, while an open block is cached only
  while its component answers a row revision (below) — without one it re-renders per
  call.
- **The block owns its row cache: `Block.rows(width)` in, `Block.render(width)` raw.**
  Every path that wants "the rows this block has at this width" reads `Block.rows` —
  the viewport's layout and height walk, `reveal`'s address arithmetic, the search
  walk, the gesture walk, `Selection.extract` — and the cache is keyed
  `(width, revision())` and lives on the block, so it dies with the block: nothing is
  pruned on the layout side, and a removed block's id reused by a new block starts
  clean. A hit hands back a fresh list of the very same immutable `Line` values, and
  `Block.render(width)` stays the uncached door for "render it again, now".
- **A row revision is a value snapshot.** `Revisioned.revision() -> object` (the
  protocol sits in `motui.kernel` beside the other block protocols) answers
  everything a component's rows depend on — `Text` its text, style and hover span;
  `Table` and the choice widgets their rows, cursor and marks; a field the buffer's
  `version` plus the cursor and flags. Two equal snapshots at one width promise equal
  rows, which is what lets the block hand its older rows back; a moved snapshot (a
  hover, a streamed assignment, a keystroke) misses and re-renders — and since
  sealing freezes the content, not the snapshot, that is also how a **sealed** block's
  hover reaches the screen. A component without the protocol keeps the older rule:
  open blocks re-render per layout, sealed blocks are frozen by width alone. The
  snapshot must be a value (mutable fields go in copied) and must cost far less than
  the render it guards.
- **Editing keys arrive as events, not coordinates.** `Input` / `Editor` /
  `Palette` / `ComboBox` consume an event through `handle(event)` and answer
  `True` when they consumed it. The wrap geometry `move_up`/`move_down` follow comes from the
  component's last render (80 columns before the first render), never from the
  event. A key's `name` is the decoder's spelling: the arrows
  `up`/`down`/`left`/`right`, `home`/`end`, `page_up`/`page_down`, `enter`,
  `escape`, `tab`, `backspace`, `space`, the controls `c-a`…`c-z`, and the shift
  chords `s-up`/`s-down`/`s-left`/`s-right`/`s-home`/`s-end` (the `ESC [ 1;2 X`
  letters) — a hyphen for chords, an underscore for words.
- **Interaction is a set of small protocols, not a manager.** A component declares
  what it can do and the host (or an assembly tier) writes it: `Clickable`
  (`click(row, col) -> bool`), `Activable` (`activate() -> bool`), `Focusable`
  (`focused: bool`), `Hoverable` (`hover: bool`, plus the optional row-level
  `hover_at(row, col) -> bool`) and `Container` (`child_at(row, col) -> (component,
  row, col) | None`). A component never learns a manager exists, and a container
  only routes coordinates: it proxies no `handle` / `move` / `activate` /
  `focused`.

Every component below is importable from the component library's own facade,
`motui.widgets`; the root's curated 33 names — listed in `README.md` and pinned by
`tests/test_api_root.py` — are the subset an application starts with.
## The controller verbs

Interactive components add controller methods beside the render protocol; the
host routes input, and the component owns its own arithmetic.

| Method | Components | Contract |
|---|---|---|
| `handle(event) -> bool` | `Input` / `Editor` / `Palette` / `ComboBox` / `List` | `True` = consumed; `False` hands the event back to the host, which is where the submit gesture lives. A `List` consumes `up`/`down`/`home`/`end` and (with `prefix_jump`, the default) a single printable character — a jump to the first item starting with it, case-insensitively — and declines everything else |
| `click(row, col) -> bool` | `Input` / `Editor` / `Select` / `Tabs` / `Tree` / `Table` / `Autocomplete` / `Radio` / `Slider` / `Collapsible` / `List` / `Text` / `Markdown` | `row`/`col` are 0-based in the component's own render; title offsets, window scroll, the strip's segment widths and the row's meaning are the component's arithmetic, never the host's (`col` carries no default and a row-shaped component that ignores it says so in its docstring). A text field places the caret: the shell restores its rendered window and `TextBuffer.place` maps the cell back to the logical position (wide clusters fold onto their character, a click past a row's text onto its end, the prompt's indent onto the row's start); a table reads the row it landed on off its own row layout, so a rule or the header takes no click; a `List` reads its windowed row layout the same way — a counter row carries no item — and a hit lands that item in `chosen`; `Radio` selects the row it landed on and `Slider` maps the column onto its track (both write `chosen`), `Collapsible` flips `open` only on its title row; `Text`/`Markdown` resolve the cell against their **last render's row table** through `action_at` and consume only a cell inside a segment that carries an `action` (`Markdown`'s links land their url in `chosen`, a task item's `☐`/`☑` box its `"todo:<flat index>"` payload) — a plain run declines and the host's own policies still get their turn |
| `hover: bool` | `Button` / `Checkbox` / `Link` / `Select` / `Autocomplete` / `Input` / `Editor` / `Table` / `Tabs` / `Tree` / `Radio` / `Slider` / `Collapsible` / `List` / `Text` / `Markdown` | the pointer tier's flag, the peer of `focused`: `Pointer` sets it while the pointer is over the leaf and the component renders by it (the theme's `hover` band over its whole block — for per-row marks use `hover_at`). Hover needs `TUI(hover=True)` (DECSET 1003): under the default 1002 a button-free motion is never reported. On `Text`/`Markdown` the flag paints nothing by itself: their highlight is the inline span, so the flag is only the protocol's own |
| `hover_at(row, col) -> bool` | `Select` / `Autocomplete` / `Tabs` / `Tree` / `Table` / `Radio` / `Slider` / `Collapsible` / `List` / `Text` / `Markdown` | the optional row-level half of hover: mark the row under the pointer in the component's own coordinates and answer whether the render changed; `row < 0` means the pointer left and clears the mark byte-for-byte back to the un-hovered output. The inline pair marks the **span** under the pointer instead of a whole row: the hit is a segment with an `action`, the highlight is the theme's `hover` merged over that segment on the render's copy, and a move within one span answers `False` |
| `hint: str` | `Button` / `Checkbox` / `Link` (and any host component that declares one) | the tooltip's protocol, read with `getattr` and nothing more: `Tooltip` paints the non-empty string under the pointer as a one-line band, and the empty default (what every leaf without the attribute reads as) means no hint. Nothing renders by it — the component never learns a tooltip exists |
| `child_at(row, col) -> (Component, row, col) \| None` | `Row` / `Column` / `Padding` / `Panel` | the container's coordinate door, read off the container's **last render** (the `TextBuffer.move_up` precedent): the child that owns the cell, re-expressed in the child's own coordinates, or `None` for the container's own cells (borders, pads, gaps, the blank filler below a shorter child). `Pointer` and `FocusRing.click` run `descend` first, so a click through a wrapper lands on the leaf; containers never proxy the leaf's verbs |
| `move(delta) -> bool` | `Select` / `Autocomplete` / `Tabs` / `Tree` / `Table` / `Radio` / `Slider` / `List` | the menus (`Select` / `Autocomplete`) **wrap** their ends and take `wrap=False` to clamp; `Tabs` / `Tree` clamp, and so do `Table` / `Radio` / `Slider` / `List` — a data view, a radio group and a stepped value stop at their edges, a menu is a cycle (D10); `True` when the cursor moved; a plain menu's step clears a pending `chosen` (a `commit=True` select writes the row it landed on, a `multi=True` one leaves `chosen` to its marks, and a `Radio` step writes its new selection: the step **is** the choice) |
| `select(index) -> bool` | `Tabs` | clamped into range; `True` when the selection changed (setting a value is not activation) |
| `activate() -> bool` | `Select` / `Autocomplete` / `Tree` / `Table` / `Radio` / `Slider` / `Collapsible` / `List` | the one activation verb: a menu takes the option under its cursor into `chosen` (`False` for an empty list; the host reads `chosen` once, and `move` / a re-filter clear it), the tree expands/collapses the node under its cursor (`False` on a leaf), the table takes the data row's index into `chosen` (`False` for an empty table), the list takes the item under its cursor (`False` for an empty list), the radio takes its selected label/payload, a `multi` select flips the cursor row's mark and recomputes `chosen` from the marks (`toggle()` is the same gesture), the slider confirms its current value (all always `True` on a non-empty control), and the collapsible flips `open`, mirroring the new state into `chosen` |
| `toggle() -> bool` | `Select` (`multi`) / `CheckGroup` / `Table` / `List` | flip the cursor row's mark in the component's public `MarkSet` (`marked`), answering whether there was a row to flip; nothing else moves -- the cursor, `chosen` and the hover are their own state. On a `multi` select `activate()` **is** this gesture (it recomputes `chosen` from the marks); on the data views the library binds no key, so the host routes its own (the demo's `space`) |
| `sort_by(col, *, reverse=False) -> bool` | `Table` | reorder the data rows by column `col`'s **rendered text** (plain string order, stable; a column the headers do not cover reads as the empty string) -- the cursor, a pending `chosen` and the pointer's mark follow the *record* into its new position, never the row number, and `True` says the order moved. The widget never sorts itself: the host calls it and the next `render` paints the new order |
| `filter(query) -> bool` | `Tree` | prune the *visible* rows to the labels holding `query` (case-insensitive substring) plus their ancestors, drawn open; `None` clears, an empty string matches all, and `True` says the rows moved. The user's `expanded` flags are read, never written, so clearing restores the tree the user built |

A click reaches a component through the driver: `hit_test` resolves the cell to a
`Hit`, and the host calls `hit.block.component.click(hit.row, hit.col)` — the
block-internal cell, already the coordinates the table above expects. A click
through a wrapper takes one more step: `hit_component(x, y)` (or a `descend`
call) walks every container's `child_at` first, and the leaf is what gets the
click. Hover needs `TUI(hover=True)` (DECSET 1003; `docs/DESIGN.md` has the
rationale), and the `Pointer` tier writes the flags. A host that wants the
toolkit to route for it opts into `FocusRing` (one line; see [Focus](#focus)
below), which dispatches the keys a focused target owns, cycles the focus and
runs the click policy — the components themselves stay exactly as this table
describes them.
## The driver, in call order
The surface a host drives, in the order the sections below use it. Every call is on
the `TUI` the body receives; the semantics of each are in `docs/DESIGN.md`.

```python
tui.add(comp, id="x", pin=None)        # append a block (auto id "b0"…); pin: "top"/"bottom"/None
tui.get("x"); tui.remove("x")         # address by id; invalidate
tui.system("system line")             # muted system block (no raw stdout writes)
tui.invalidate(); tui.paint()         # mark dirty / paint one frame now
tui.rows                              # the current frame: exactly screen.height rows
tui.every(0.1, fn)                    # periodic callback, returns a cancellable handle
tui.clock()                           # the pump's monotonic clock (the one time seam)
tui.tick(now)                         # advance the pump: due callbacks, then one frame
event = await tui.read_key()          # next key; page keys and the wheel scroll and are absorbed
tui.scroll_up(2); tui.scroll_to_bottom()
tui.reveal("b3", 12)                  # bring a document address on screen (centered, clamped)
tui.viewport.scroll_to(offset)        # the pane's window: an absolute jump, clamped
tui.viewport_rows()                   # the focused pane's window as (first, last), or None
tui.split("vertical", ratios=(2, 1))  # tile the focused pane: first child keeps the document
tui.add_band(viewport)                # park a footer viewport in the frame's bottom band
tui.set_title("my app")               # OSC 2 window title (control bytes scrubbed)
tui.set_cursor_shape("beam")          # DECSCUSR: block/beam/underline/default
tui.hit_test(x, y)                    # a 0-based cell -> the block under it (or None)
tui.hit_component(x, y)               # ...or the deepest leaf: child_at descends every container
tui.selection; tui.set_selection(sel) # the document-space selection overlay; None clears
tui.stop()                            # ask run() to finish
```

`TUI().run(body)` brackets `enter`/`leave`, runs a throttle/repaint pump, and — on
a non-live screen (pipe/file) — stays silent during the run and dumps the final
screen as plain text on exit. `TUI(theme=...)` sets the theme the driver's own
chrome reads; `TUI(hover=True)` opens DECSET 1003 for a `Pointer`, and the default
mouse mode stays 1000+1002+1006. `read_key` intercepts the `scroll_keys` table
(`tui.scroll_keys`, rebind or `del` entries to hand an event back) and returns
`None` on a non-live screen even with a source attached.

Every non-empty frame is bracketed by DECSET 2026 (synchronized output) by default
— `TUI(sync=False)` drops the pair — and rows render for the screen's colour
capability: `TUI(color_mode="truecolor"|"256"|"16"|"none")` overrides the
environment probe (`NO_COLOR`, `TERM`, `COLORTERM`) the default screen's `"auto"`
runs. `TUI(focus_events=True)` opens DECSET 1004, so the decoder hands the host
`focus_in` / `focus_out`. A mouse click resolves through the driver — the host
dispatches, inside the async body:

```python
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)             # 0-based coords; None when no block owns the cell
    if hit is not None:
        hit.block.component.click(hit.row, hit.col)  # e.g. a Select: it ignores the column
```
## The component catalogue

Each family below is one table of constructor sketch -> capabilities; the
focused notes for `Diff` and `List` follow the tables.
### Text and structure

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. `theme` is read for one thing: the `hover` band an inline span merges. `Hoverable` + `Clickable` over the row table of its last render: `hover_at(row, col)` marks the span under the pointer (a segment with an `action`) and `click(row, col)` lands that payload in `chosen` (read once by the host; a plain run declines). The default rows are verbatim and carry no payloads — a subclass that returns its own `Line` values from `_rows_for` inherits the hit testing unchanged. `render` remembers its last wrap while `_revision()` — text, style, the hover span and the band it merges — and the width stand still, so a block repainted frame after frame re-wraps nothing while its state holds; `_revision()` is the subclass seam too (add the subclass's own state, or return `None` to switch the memory off), and it is the snapshot `Block.rows` keys on, so a sealed `Text` still repaints a moved hover. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None, gap=1, divider_max_width=80)` | Rule-registry engine: paragraphs, `#`–`######` headings, fenced code, lists, block quotes, GFM tables, thematic breaks, inline `` `code` ``/`**bold**`/`~~strike~~`/`*italic*`/`[t](u)`; unknown constructs degrade to paragraph. A link's label segment carries `link=url` (OSC 8 bytes around the label — a real terminal hyperlink) and `action=url`; the component is `Hoverable` + `Clickable`: a click on a label lands the url in `chosen` (read once by the host) and the pointer's span takes the `hover` band. See [Markdown](#markdown) below. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None, theme=None, max_width=None)` | Full-width rule from one repeated character; a `label` embeds `char*2 + " " + label + " " + char*fill` (e.g. `── ⠋ Working ───`) across the full width, an over-wide label is ellipsize'd to `width - 4`, and `label`/`label_style`/`max_width` are mutable attributes. |
| `Diff` | `Diff(before, after, *, context=3, numbers=False, theme=None)` | A line-level **unified diff**, computed once at construction: an `@@ -a,b +c,d @@` header per hunk (the theme's `muted`), a leading space for a kept line (the default style), `-` for a deletion (the theme's `error` hue, no weight) and `+` for an insertion (the theme's `success`), `… N lines` where hunks skip lines; every row is `fit` to the painting width. The walk trims the common head and tail, then runs the LCS over what remains — `LCS_LIMIT` (20 000) is **one DP comparison's** budget, not the whole text's — splitting an over-budget region at the lines both sides hold exactly once, and replacing one with no such line in **one** hunk (every `before` line, then every `after` line). `numbers=True` adds a line-number gutter (off by default); texts that split to the same lines render no rows. Assigning `before`/`after`/`context`/`numbers`/`theme` rebuilds the rows and `render(width)` caches its fitted rows per width. Display-only — no `chosen`, no cursor, no interaction protocol. See below. |
| `Notice` | `Notice(text, *, level="info", theme=None)` | One message row; `warn`/`error` prepend a styled label from the theme's `notice_levels`. Any other level degrades to plain `info`. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None, theme=None)` | Child inside a single-line box; titled top border when it fits. The frame is a pure function of the child's rows and the box's own parameters, so it is **remembered per child-row identity** (the child's rows by object, plus the width, the title and the resolved border style): a host repainting the same child wraps the rows once and re-reads the child's own memory. A hit hands back fresh copies of the same immutable rows and refreshes the `child_at` geometry exactly as a miss does. |
| `Row` | `Row(children, *, widths=None, gap=1)` | Side-by-side columns (fixed/flex widths), tallest child sets the height. The assembly is remembered per child-row identity too (each child's rows by object, plus the column widths, the gap and the width): a repainting row re-splices nothing while its children stood still. |
| `Column` | `Column(children, *, gap=0)` | Vertical stack with `gap` blank rows between children. Remembered per child-row identity, like `Row`'s. |
| `Spacer` | `Spacer(rows=1)` | Blank rows — the transcript rhythm's building block. |
| `Padding` | `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None)` | A child inset on all four sides; with `fill_style` set the blank areas are painted and merge *under* the child's colors (a filled user-band pattern). The fill is never themed. The inset is remembered per child-row identity (plus the clipped insets, the fill and the width), so a repainting host skips the fill merge wholesale. |
| `Collapsible` | `Collapsible(title, body, *, open=True, title_style=None, hover_style=None, focus_style=None, theme=None, focused=False)` | A titled section that folds its body away: the title row renders `▾ title` / `▸ title` (the marker's two columns are the body's inset), and while `open` the `body` component's rows follow — the body renders at `width - 2`, so a nested `Panel`, a field or a layout works unchanged. `click(row, col)` flips the state on the title row (`row 0`; a body row is not the control; the column is ignored) and `activate()` is the same flip; each mirrors the new state into `chosen` (the host reads it once and resets). `hover_at(row, col)` marks the title row (`row < 0` clears), `title_style` defaults to the theme's `accent`, `focused=True` merges `focus_style` (the theme's `cursor`) over the title. The open body's inset rows are remembered per body-row identity (plus the width and the body's indent), while the one title row re-renders every call so its hover and focus markings never stale. |
### Input and choice

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Input` | `Input(*, prompt="❮ ", placeholder="", mask="", style=None, prompt_style=None, cursor_style=None, focused=True, theme=None, keymap=None)` | Single-line cursor-editable field (`insert`/`backspace`/`delete`/`move_*`/`home`/`end`/`clear`); up/down follow wrapped rows; an empty focused field shows its placeholder dim and **no cursor cell** (the block appears with the first typed character; an empty field with no placeholder shows the block alone). Keys route through the component's **keymap** at `handle(event)`, answering `True` when consumed — the driver feeds keys, it reads none. A multi-line `Paste` is folded into the single line: every run of newlines becomes one space (`"a\r\nb"` pastes as `"a b"`), so a paste never adds a row; an explicit `insert("\n")` keeps its newline. `.text` and `.cursor -> (row, col)` read the buffer; `cursor_position(width)` reports the block-cursor cell for an IME anchor; `click(row, col)` places the caret at that rendered cell. A non-empty `mask` is the display-only secret field: every rendered character is replaced by glyphs of the mask's first character while `.text` stays plain, the caret geometry (the block cursor's cell, `cursor_position`, `click`) measured against the masked row and the selection band remapped the same way; it is a construction parameter, so a host that wants a reveal switch redraws from `.text` itself. `focused` is the flag the focus tier writes (`FocusRing`), so a ring of fields toggles their block cursors without the fields changing. `c-z`/`c-y` walk the buffer's **bounded undo/redo** (`TextBuffer.UNDO_LIMIT` = 100 steps; every write point snapshots before it mutates, a new change drops the redo tail, and runs of single-character inserts merge into one step — `field.undo()`/`redo()` drive the same history). **`c-a` is `select_all`** and the shift chords `s-left`/`s-right`/`s-home`/`s-end` extend the text-internal selection (`anchor`, `selected_text`, `selection_range()`, `clear_selection()`): typing replaces the selected range in one history step, a plain move or a caret-docking click drops it, and the field renders it as `merge(theme.selection)` with the block cursor riding underneath. The buffer underneath carries its own memories: wrapped spans are remembered per `(line text, inner width)`, a content change bumps a monotonic `TextBuffer.version` and re-wraps only the edited line, and the assembled visual rows are remembered under `(version, width, indent)` — so a move over unmoved geometry rebuilds nothing, and the rendered rows are remembered while `revision()` (the buffer's version, the cursor, the selection, focus/hover, the placeholder) and the width hold. |
| `Editor` | `Editor(*, text="", placeholder="", mask="", style=None, cursor_style=None, theme=None, keymap=None, focused=True, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; a non-empty `mask` is the same display-only mask as `Input`'s (the text stays plain, the caret geometry does not move); `.text` and `.cursor -> (row, col)` read the buffer; `newline`/`insert` (a multi-line `Paste` keeps its newlines verbatim) / merged `backspace`; `max_rows` caps the rendered rows with a sliding window on the cursor; `click(row, col)` places the caret, the window's first rendered row added back onto `row` first so "the third row on screen" always means the third rendered row. The placeholder rule matches `Input`'s. `enter` is unbound in the host-submit keymap (`EDITOR_SUBMIT_KEYMAP`) so it stays the host's submit gesture. `focused` is the flag the focus tier writes, exactly as on `Input`. `c-z`/`c-y` and `undo()`/`redo()` walk the same bounded history as `Input`'s (one step per write point; a pasted multi-line block is one step). `c-a`/`s-left`/`s-right`/`s-up`/`s-down`/`s-home`/`s-end` drive the same text-internal selection — `s-up`/`s-down` extend over the wrapped rows, keeping the inner column. The buffer memories and the row `revision()` are the same ones `Input` describes: a keystroke re-wraps the edited line rather than the buffer, a move re-slices the window over unchanged geometry, and the rendered rows are remembered while the buffer's `version`, the cursor, the window and the flags hold. |
| `Select` | `Select(options=(), *, title="", max_rows=8, wrap=True, marker="→", commit=False, multi=False, marked=(), window=False, focused=True, label_style=None, selected_style=None, description_style=None, title_style=None, theme=None)` | The list family's one base (D1): vertical `Option(label, value, description)` rows with the cursor row led by `marker` (default `→`) in `selected_style` (default: the theme's `accent`), every description in one column measured over the whole option list. `move(delta)` wraps the ends (`wrap=False` clamps) and clears a pending `chosen`, `index` clamps on assignment, `selected` reads, `activate()` takes the cursor's option into `chosen` (the host reads it once), `click(row, col)` answers a mouse hit (the column is ignored: a row owns the width); a list longer than `max_rows` renders a window that keeps the cursor visible plus an `(i/n)` counter row (top-stick by default, centred under `window=True` -- both the `CursorWindow` arithmetic the `List` renders through); `focused=False` renders the cursor row in `selected_style.merge(theme.dim)` (the description column keeps its own `dim`). The five knobs are the whole variation catalog: `wrap` (a menu cycles, a data view clamps), `window` (a top-stick menu window or a centred one), `marker` (the cursor glyph), `commit=True` makes the cursor the choice (a move or a click writes the row it landed on into `chosen`, and `activate()` still does), and `multi=True` is the multiple selection (every row carries the `[x] `/`[ ] ` mark, `marked` is the public `MarkSet`, `toggle()` flips the cursor row's mark and `chosen` is the marked rows' values in row order -- `activate()` is the same gesture). `Autocomplete` is a `Select` whose `_rows()` are its matches; `Radio` and `CheckGroup` are its two form presets. |
| `Radio` | `Radio(labels, *, index=0, label_style=None, selected_style=None, hover_style=None, focus_style=None, theme=None, focused=False)` | The single-choice group -- a `Select` preset (`wrap=False`, `commit=True`, the `(•)` marker) with its own row and band rule: one row per label, `label` as a plain string (the label is the value) or an `Option` (a label with its own payload — `chosen` carries the value), the selected row led by `(•)` in `selected_style` (the theme's `accent`). `index` is the selection (clamped on assignment; `selected` reads the label), `move(delta)` steps it **clamped** — a step that moved writes the new selection into `chosen` — and `click(row, col)` (the column is ignored) and `activate()` are the other two doors to `chosen` (host reads once). `hover_at(row, col)` marks the row under the pointer (`row < 0` clears), `focused=True` merges `focus_style` (the theme's `cursor`) over the selected row. |
| `CheckGroup` | `CheckGroup(labels, *, marked=(), index=0, label_style=None, selected_style=None, hover_style=None, focus_style=None, theme=None, focused=False)` | The multiple-choice group -- the other `Select` preset (`multi=True`, `wrap=False`, `commit=False`): one row per label (a plain string is the value, an `Option` carries its own payload), every row led by the menu's marker seat and the `[x] `/`[ ] ` mark, and `chosen` is the marked rows' values in row order (`None` while nothing is marked). `move` clamps, `click` / `activate` / `toggle` all flip the cursor row's mark -- the return key *is* the mark gesture -- and the bands are `Radio`'s: the hover row merges `hover_style`, the cursor row merges `focus_style` (the theme's `cursor`) while focused, the pick never dimmed. `marked` is the public `MarkSet` a host may seed and read. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, wrap=True, label_style=None, selected_style=None, description_style=None, theme=None)` | The filter layer of the menu family: a `Select` subclass whose **rows are the current matches** — `set_query(text)` keeps prefix matches first, then substring matches (case-sensitive; an empty query matches all), resets the cursor and clears a pending `chosen`. The window, `(i/n)` counter, description column (measured over the whole option universe, so it never jumps while filtering), wrapping cursor and `activate()`/`chosen` are the inherited `Select` behaviour. The engine `Palette` is built on. |
| `ComboBox` | `ComboBox(options=(), *, text="", max_rows=8, theme=None, max_drop_rows=6)` | The form's **pick-or-type**: the component's own `Input` (`.input`) over an `Autocomplete` of the field's text (`.list`). `open()` / `close()` / `is_open` drive the dropdown; `handle(event)` routes `down` / `up` (the list's cursor, wrapping like every menu), `enter` (the highlighted option's **value** into `chosen`, its label written back into the field, the dropdown closed) and `escape` (closed with `chosen` `None`) while open, and every other event is the field's -- a consumed field event re-filters the list, so the matches follow what is typed. A pointer report is declined (the mouse belongs to the host's tiers; a `MouseEvent` carries `left` / `right` names that are editing doors only for a real keypress). `render(width)` is the field's rows: the dropdown paints through a host-mounted `Modal` -- mount `Modal(tui, combo.list, anchor=one row under the field)`, route `combo.handle` before `modal.handle`, keep the two open states in step; the class docstring is that recipe in full. `chosen` is read once; `max_rows` is the list's own window (what a host embedding `.list` standalone gets) and `max_drop_rows` the dropdown's -- the smaller of the two is what the open dropdown renders. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |
### Action primitives

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Button` | `Button(label, *, style=None, hover_style=None, focus_style=None, theme=None, focused=False)` | The smallest interactive unit: one row, `" label "`, `fit` to the painting width. The base style is `style` or the theme's `accent`; `hover` merges `hover_style` or the theme's `hover`, `focused` merges `focus_style` or the theme's `cursor`. `click(row, col)` (any cell — the whole row is the control) and `activate()` are the same operation and both always answer `True`, landing `True` in `chosen` for the host to read once and reset. Carries the tooltip's `hint` (default `""` = none). |
| `Checkbox` | `Checkbox(label, *, checked=False, theme=None, focused=False)` | `Button`'s toggling sibling: one row, `[x] label` / `[ ] label`, same bands. `click` / `activate` flip `checked` and mirror the new value into `chosen` (read once, reset by the host); both always answer `True`. Carries the tooltip's `hint`. |
| `Link` | `Link(text, *, style=None, hover_style=None, theme=None)` | One clickable row rendered in the theme's `link` band; `hover` merges the theme's `hover`. Deliberately **not** `Activable` — a link is not a focus target's main operation (the keyboard door belongs to the widgets a ring registers). A click on any cell lands `True` in `chosen`. Carries the tooltip's `hint`. |
### Data views

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None, selected_style=None, aligns=None, focused=True, theme=None)` + `sort_by(col, *, reverse=False)` / `set_widths(widths)` / `header_line(width)` | Full box grid (`┌─┬─┐` top, a `├─┼─┤` rule between every pair of rows, `└─┴─┘` bottom) with uncolored rules by default; cells are `str`, `(str, Style)`, or styled `Segment` runs (inline markup); per-column `aligns` (`left`/`center`/`right`); natural column widths, proportional shrink + ellipsis when over width, never stretched below natural size. Optional **row cursor**: `index` is a data row (never the header or a rule; `None` by default, clamped on assignment, `None` again for an empty table) and `selected` reads that row's raw cells; the cursor row renders *every* one of its data cells in `selected_style` (default the theme's `selection`) — the header and the grid lines stay untouched, and the row count and column budgets are the same with or without a cursor. `move(delta)` steps it and **clamps** at the ends (a data view, not a menu cycle), `click(row, col)` maps a rendered row onto a data row through the table's own layout (the column is ignored; the header and the rules take no click), `activate()` takes the row's index into `chosen` (the host reads it once; `move` and a landing click clear it), `focused=False` renders the band in `selected_style.merge(theme.dim)`. The host's data gestures: `sort_by(col, reverse=…)` reorders the rows by that column's rendered text (stable; a negative or past-the-headers column reads as the empty string), `set_widths([…])` pins explicit per-column budgets (`None` restores the measured widths; a value below 1 reads as 1 and a total that does not fit shrinks proportionally, so no row ever exceeds the painting width), and `header_line(width)` hands the header row **alone** out — byte-identical to the grid's own (same budgets, same alignment pads), `None` without headers — for a host that pins it as a sticky row. The whole grid is remembered while a value snapshot of its row inputs holds — `rows` and `headers` **copied**, so an in-place cell edit or an appended record moves it, plus the pinned widths, aligns, cursor, the pointer's mark, focus and the resolved styles — and `Table.revision()` is the same snapshot, so a sealed table's hover, an in-place edit or a `set_widths` re-renders instead of staling, and the natural-column measurement rides the memory rather than being re-measured per frame. **Marking**: `marked` is the public `MarkSet` of data-row indices and `toggle()` flips the cursor row's mark (the host routes the key); while the set is non-empty every data row leads with the `[x] `/`[ ] ` prefix inside its first cell -- the frame, the rules and the row count are untouched and column 0's budget grows by it -- an empty set renders byte-for-byte what the table always did, the marks are part of `revision()`, and a `sort_by` re-order re-points them at their records like the cursor. |
| `Tabs` | `Tabs(tabs, *, active=0, active_style=None, inactive_style=None, divider="│", focused=True, theme=None, orientation="horizontal")` | A tab strip on one axis: `"horizontal"` (the default) paints one row, labels separated by `divider`, the active one emphasized; `"vertical"` paints one label per row, left-aligned, no divider — a rail. `select(index)` selects (clamped), `move(delta)` steps, `click(row, col)` maps the cell against the strip's own last render (the column of the one row, or the row of the stack), `active` reads; `focused=False` renders the active label in `active_style.merge(theme.dim)`. |
| `List` | `List(items=(), *, window=8, theme=None, focused=False, prefix_jump=True)` | A cursor over a long `items` sequence, rendered as a **window**: at most `window` item rows centred on the cursor (half a window where the ends allow), a `▸` marker on the cursor row and its width of indent elsewhere, plus an `↑ N more` / `↓ N more` counter row wherever items fall outside. `index` is the cursor (clamped on assignment), `move(delta)` steps and **clamps** at the ends (D10), `home`/`end` jump to the edges, `click(row, col)` maps a rendered row onto an item (a counter row carries none) and lands it in `chosen`, `activate()` lands the cursor row's item there for the host's one read (any consumed key clears a pending pick); `handle(event)` consumes `up`/`down`/`home`/`end` and a single printable character as a **prefix jump** to the first item starting with it (case-insensitive; `prefix_jump=False` leaves printables to the host). `hover_at(row, col)` marks the item row under the pointer, `focused=False` renders the cursor band in `selected_style.merge(theme.dim)`. `marked` is the public `MarkSet` of item indices and `toggle()` flips the cursor row's mark: while the set is non-empty every item row carries the `[x] `/`[ ] ` prefix after the cursor's marker seat (an empty set renders the rows the list always did, and the marks are part of `revision()`); `handle` keeps declining `space`, so the host routes the mark key (the demo's `space`). See below. |
| `Tree` | `Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None, focused=True, theme=None)` with `TreeNode(label, children=(), *, expanded=False)` + `filter(query)` / `jump(char)` | Indented tree; `expanded` flips a node's children in place; `move(delta)` / `click(row, col)` steer (the column is ignored: a node row owns the width), `activate()` expands/collapses the node under the cursor (`False` on a leaf), `selected` reads; a cursor style marks the row, and `focused=False` renders that row in `cursor_style.merge(theme.dim)`. **`filter(query)`** prunes the visible rows to the labels holding `query` as a case-insensitive substring, keeps the ancestors of every hit and draws those chains open; `None` clears, an empty string matches every label, the cursor returns to the top row when the query changes, and the auto-expansion is derived, never written back — so clearing the filter restores the user's own rows and `activate()` keeps meaning "flip this node". **`jump(char)`** is type-ahead: the cursor hops to the next *visible* node whose label starts with `char` (case-insensitive, wrapping; `False` for a miss, a non-printable or a multi-character argument). |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, theme=None)` | Determinate bar: filled `█` run over shaded `░` run inside `[ ]`, clamped to `[0, 1]`; `fraction` is a mutable attribute that re-clamps on assignment. |
| `Slider` | `Slider(value=0, *, minimum=0, maximum=10, step=1, filled_style=None, empty_style=None, hover_style=None, focus_style=None, theme=None, focused=False)` | One row, `[====----] 4`: a bracketed track whose length follows `render(width)` (the filled run in the theme's `accent`, the rest dim) with the value after the closing bracket. The value lives on the `step` grid (`minimum + k * step`, the largest grid point not past `maximum`); assigning clamps **and** snaps. `move(delta)` steps whole `step`s clamped (a moved step clears a stale `chosen`), `click(row, col)` maps the column of the **last render** onto the nearest grid point, `activate()` confirms the current value into `chosen` (host reads once). `hover_at(row, col)` marks the single row; `focused=True` merges `focus_style` (the theme's `cursor`) over the whole row. |
### Footer rows and the palette

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, gap_style=None)` | Exactly one dim two-column row: left part at column 0, right part one column short of the width, computed gutter between (at least one column); `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place. Over-wide rows keep the left part and ellipsize the right tail. |
| `ShortcutBar` | `ShortcutBar(items, *, separator=" · ", key_style=None, label_style=None, theme=None)` | The key hints as chrome: one row of `(key, label)` pairs, each key in `key_style` (the theme's `accent`), its label in `label_style` (the theme's `dim`), neighbours joined by `separator`, the whole row `fit` to the painting width (an over-wide bar truncates with `…` and stops — no wrapping). An empty bar renders one empty row. **No interaction**: no `chosen`, no controller methods, no capability flags — the demo mounts it in the footer, above the status row. |
| `Palette` | `Palette(tui, commands, *, theme=None, max_rows=8)` | The **self-contained** command palette and a modal controller: its own query `Input` row (`.input`, `.list` are the composed widgets) over an `Autocomplete` filtered by that row's text, painted by a `Modal` (the `interaction` tier's) the palette builds over the frame -- opening it raises the scrim, a click outside dismisses it, and the modal owns the routing while it is open. `open()` resets the query and the list; `handle(event) -> bool` consumes up/down/enter/escape — a consumed `enter` lands the highlighted command's `value` in `chosen` (`None` when nothing matches or the palette was dismissed), and the host reads `chosen` once and dispatches it — and routes every other event through the query row. Renders zero rows while closed. |
### The modal family

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Dialog` | `Dialog(title, body, buttons, *, danger=False, width=None, align="center", border=None, border_style=None, title_style=None, shade=True, theme=None)` + `ButtonSpec(label, value=None, style=None, hover_style=None, focus_style=None, danger=False)` | The modal's **pure component** -- a resolved box, never a position: a single-line frame with the title embedded in its top edge, the `body` component rendered one pad column in from each side, a row of `Button`s built from `ButtonSpec` values (a plain string is a label; `(label, value)` tuples work too) and `shade=True` padding every row solid. It knows nothing about the screen: `render(width)` returns the rows and the host's `Modal` decides where they sit. `handle(event)` is the dialog's whole keyboard: `escape` cancels (`chosen` stays `None`), `enter` takes the focused button's **value** -- a dangerous button included: the rule (D3) is "not the default focus", never "disabled" -- and `tab` / `right` and `s-tab` / `left` walk the button cursor, clamped, never wrapping. `danger=True` gives the box the theme's `error` border and opens focused on the **last non-dangerous** button (usually the cancel), so a stray return never lands the destructive action; the button row's order is the caller's and is the keyboard order (the main action on the left, the cancel on the right). `click(row, col)` presses the button under a rendered cell (the last render's geometry), every other cell declining; `focused` reads the button the keys act on. `width` pins the box, which is otherwise `3/5` of the painting width -- never below 24, never above 72, never wider than the pane. |
| `confirm_dialog` / `prompt_dialog` (the `Prompt`, D9) | `confirm_dialog(message, *, danger=False, confirm_text="Yes", cancel_text="No", theme=None)` / `prompt_dialog(title, *, placeholder="", mask="", confirm_text="OK", cancel_text="Cancel", style=None, danger=False, theme=None)` | The two thin builders over `Dialog`. `confirm_dialog` is the classic Yes/No pair: an untitled box, a `Text` body, the confirm button first (D3) and the cancel second. `prompt_dialog` is the one-line prompt: a titled box whose body is a single-line `Input`, with `placeholder` and `mask` forwarded verbatim (so `.text` stays plain however it renders) and `style` as the **field's** band; the confirm's value is `"ok"`, the cancel's `None`. The field's keymap binds no `enter`, so under a `Modal` the return key falls through the body to the button row: the field is the payload (`dialog.body.text`) and the modal's result says whether the user took it. |
| `Modal` | `Modal(tui, dialog, *, anchor=None, scrim=True, scrim_style=None, dismiss_on_click_outside=True, theme=None)` | **Not a component: the controller** (it lives in `motui.interaction`). The blocking layer around any panel -- a `Dialog`, a `Palette`, a `ComboBox`'s list, a context menu: anything with `render` / `click` / `handle` / `chosen` fits the socket. Constructed mounted (it registers its overlay on the frame at construction, the `Toasts` lifecycle); `open()` shows the panel, resetting `chosen`; `close(value)` hides it and lands `value` as the one-shot result; `detach()` unregisters by identity (idempotent); `is_open` is the cheap guard that lets a host keep one mounted and route it unconditionally, because a **closed** modal paints nothing and consumes nothing. Open, every composed row is re-segmented through the scrim style (default the theme's attribute-`dim` veil -- colors keep their own values, the weight drops) and the panel's rows are spliced in at its rectangle: **centered** by default, or **anchored** at `anchor=(y, x)` clamped into the frame -- the ComboBox dropdown's and the future context menu's door (D2). `handle(event)` consumes **everything** while open: the panel's own keys come first, and a panel that carries a `body` hands it the keyboard ahead of the panel's own `handle` (the body-first rule that makes a prompted field work); a left press inside the panel is the panel's click, a press outside dismisses with nothing chosen (`dismiss_on_click_outside`, default `True`), and every other event is consumed and dropped -- the host's own shortcuts must be routed *before* the modal. `chosen` is the panel's result, read once and reset: the value of the button taken (`None` is a legal value), or `None` for `escape`, a dismissal or a programmatic `close()`. |

### `Diff` — the unified diff view

Two texts in, the hunks a reader wants out. `Diff` computes the line-level
edit **once, at construction** and stores the unified rows; `render(width)`
only fits them. The rows are the classic four kinds plus the elision row — a
`@@` header (the theme's `muted`), a kept line (a leading space, default
style), `-` deletions (the theme's `error` hue without weight), `+` insertions
(the theme's `success`) and a `… N lines` row (one skipped line reads
`… 1 line`) where hunks skip lines:

```python
from motui.widgets import Diff

diff = Diff(before_text, after_text, context=3, numbers=True)
rows = diff.render(80)                            # every row fit to 80
```

`context` (default 3) is how many unchanged lines surround each change; two
changes closer than twice the context merge into one hunk, ones further apart
keep the `… N lines` row between them, and `context=0` renders the changes
alone. `numbers=True` prefixes every content row with a line-number gutter — a
`same` or `-` row shows its `before` number, a `+` row its `after` number, all
padded to the widest line number in either text; `@@` and `… N lines` rows
carry no gutter, and the default `numbers=False` renders none at all.

The walk is a ladder. It trims the common head and tail line by line, then
runs the LCS over the remaining region — `LCS_LIMIT` (20 000) bounds the line
pairs **one DP comparison** may take, not the whole text. A region empty on
one side is just its deletions (or its insertions); a region past the budget
is split at the lines both of its sides hold exactly once, paired in order,
the same rule recursing into the parts; and a region with no such line
degrades to **one** hunk — every `before` line, then every `after` line — at
a total edit cost bounded by `n + m`. The split rule stays `str.splitlines()`,
so a trailing newline adds no line, and two texts that split to the same lines
render no rows at all.

Content rows carry no weight: a deletion is the theme's `error` with bold
stripped (a host's own italics and underlines survive), which keeps the
repository's rule that bold stays reserved for `**…**` — the rule
`kernel/style.py` spells out in its markdown palette comment and
`kernel/theme.py` in its heading note. `@@` and `… N lines` rows are `muted`.

`before`, `after`, `context`, `numbers` and `theme` are assignment-live: each
setter rebuilds the stored rows and drops the render cache (the `context`
setter validates first — a negative value raises `ValueError` and leaves the
state alone, and the `theme` setter re-resolves the three bands). `render(width)`
serves a same-width hit from its cache as a fresh copy and rebuilds on a
width change.

The component is **display only**: no `chosen`, no cursor, no keys; a host
that wants it in a pane scrolls the rows it rendered.
### `List` — the window over a long sequence

`List` renders `window` rows around the cursor (half a window on either side
where the ends allow, so the window slides rather than the cursor pinning an
edge), the cursor row led by `▸` and every other row indented by its width, plus
an `↑ N more` counter above and a `↓ N more` below wherever items fall outside
it:

```
↑ 496 more
  item 0496
  item 0497
▸ item 0500          six rows whatever the list length
↓ 496 more
```

The controller vocabulary is a table's: `move(delta)` **clamps** at the ends (a
data view, not a menu cycle — D10), `home`/`end` jump to the edges,
`click(row, col)` maps a rendered row back onto an item through the very window
arithmetic `render` emits, and `activate()` lands the cursor row's item in
`chosen` for the host's one read. `handle(event)` is the keyboard door —
`up`/`down`/`home`/`end`, and with `prefix_jump` (the default) a single printable
character jumping to the first item that starts with it, case-insensitively (a
consumed key whether or not an item matched).

```python
from motui import List

names = List(COMPONENT_NAMES, window=8)   # 1000 items: 8 rows + 2 counters
names.handle(Key("p", "p"))               # the first P item, one keystroke
names.activate(); names.chosen            # "Padding" — read once, then reset
```
## Style and Theme

`Style(fg=..., bg=..., ...)` is frozen and hashable (so `prefix()` is memoized per
instance) and takes a color in one of three forms:

- a **named 16-color** from `kernel.style.FG_CODES` (`"red"`, `"bright_black"`,
  …); unknown names raise `KeyError` from `prefix()`;
- a **`"#rrggbb"` string** or an **`(r, g, b)` tuple** — both emit 24-bit
  truecolor SGR (`38;2;r;g;b` / `48;2;r;g;b`). Truecolor is a superset of the
  named set, so old named styles keep working unchanged.

Attributes are `bold`, `dim`, `italic`, `underline`, `reverse`, `strike` (SGR
`9`, crossed-out); `merge(other)` OR-sets the booleans and lets `other`'s colors
win — the operation a component uses to layer an emphasis onto a base band. An
attribute-only style (no `fg`/`bg`) merges *under* whatever run it lands in,
which is how `**bold**` inside an accent heading stays accent.

**`Theme`** (a frozen dataclass, `DEFAULT_THEME` as the shipped instance) is the
one place every semantic default lives. A component takes an explicit
`style=...` (which always wins) plus `theme=Theme | None`, and resolves each
style **once, at construction**, as **explicit > theme field > `DEFAULT_THEME`** —
storing the resolved `Style` (or the resolved `Theme`, when the choice depends on
a mutable attribute). `replace(DEFAULT_THEME, accent=...)` restyles a whole
family of components at once, and nothing global is mutated. Equality is
field-wise, so a custom theme never compares equal to `DEFAULT_THEME` unless
every field matches.

| Theme field | Default | Used for |
|---|---|---|
| `dim` | dim | secondary rows, placeholders, the `Editor`'s dim states |
| `muted` | `#8b949e` gray | secondary text (thinking, quote bars, fence lines) |
| `accent` | `#58a6ff` soft blue | prompts, the working label, syntax keywords, the menu cursor row |
| `success` | `#4bb563` soft green | success, `+` rows, ✓, the `ProgressBar` fill |
| `error` | `#e5534b` soft red | errors, `-` rows, a dangerous `Dialog` |
| `warning` | `#d29922` amber | warnings, notice titles |
| `border` | no color (terminal default fg) | rules, panel borders |
| `code` | `#a5d6ff` ice blue | untagged/unknown fence code, syntax `builtin` |
| `cursor` | reverse video | the block cursor (`Input` / `Editor`) |
| `selection` | `reverse` | `Tabs` / `Tree` cursors and the `Table` row band (its `selected_style` default); pass it as a menu's `selected_style` for a reverse-video band — the menus themselves default to `accent` |
| `heading` | `#e3b341` gold | the Markdown heading ladder's base |
| `link` | `#58a6ff`, underlined | Markdown link labels (never bold) |
| `inline_code` | `#f778ba` pink | inline `` `code` `` runs |
| `list_marker` | `#bc8cff` purple | list bullets / numbers |
| `hover` | reverse video | the pointer tier's hover band (the `Hoverable` components) |
| `table_border` | no color | `Table` grid lines (`Table(border_style=...)` tints them) |
| `first_column` | no color (plain) | `Table` data rows' first column |
| `scrollbar` | dim | the `Scrollbar` track (`░` cells) |
| `scrollbar_thumb` | no color (plain fg) | the `Scrollbar` thumb (`█` cells) |
| `toast` | reverse + dim | the `Toasts` band |
| `headings` | derived from `heading` | the Markdown heading ladder (read-only property) |
| `notice_levels` | derived from `warning`/`error` | the `Notice` level labels |

The semantic colors mirror the exported `kernel.style` constants (`DIM`,
`MUTED`, `ACCENT`, `SUCCESS`, `ERROR`, `WARNING`, `BORDER`, `CODE`, `CURSOR`,
`SELECTION`, plus the markdown palette `HEADING`, `LINK`, `INLINE_CODE`,
`LIST_MARKER`); the band colors and the table defaults live only in `Theme`.
**Bold is reserved for the `**…**` syntax itself and strike for `~~…~~`**: none
of the markdown-facing defaults (the heading ladder, the link, inline code, list
markers, the table header, the table first column) is bold or struck — structure
reads by color instead of weight.
## The frame tier

The frame model's public face, all of it host policy over the driver's `tui.frame`
seam. The three space claims it implements (pane / chrome / overlay) are the
design constitution in [`docs/DESIGN.md`](DESIGN.md) — the panes-and-splits
rules, the budget negotiation and the retile contract live there.
### Panes and splits
```python
tui.split("vertical" | "horizontal", *, ratios=(1, 1), min_size=1, separator=True) -> tuple[Pane, ...]
left, right = tui.split("vertical", ratios=(2, 1))   # transcript | preview
left.document; left.viewport; left.focus()   # the Pane handle
left.split(...)                              # divide it; returns the children
left.close()                                 # the un-split: a leaf leaves
```

`tui.split` divides the **focused** pane and returns the children in paint order.
The first child keeps the split pane's id, document, viewport and chrome, so a
host's blocks and any chrome registered before the split ride the division; every
child after it opens over a fresh, empty document (`right.document.add(...)` is the
preview side). A split leaves focus where it was and re-divides the tiling
immediately, so the returned panes already hold their rectangles. The 1-cell
separator is inter-pane chrome (budgeted, never a gap) themed by focus — the
theme's `accent` beside the focused pane, its `border` otherwise. There is no
`Theme.separator` field: a host wanting a different look splits with
`separator=False` and registers its own chrome on the pane. A resize re-divides the
same tree in place: every pane keeps its viewport, its chrome and its scroll state.

Two identities hold across `close()`. **Ids**: a collapse keeps the *parent's*
id, so collapsing onto a split's first child is invisible to every id a host
holds; a survivor that was a later child takes an id that dies with the split
(`frame.pane("primary-1")` answers `None`), and a re-divide changes no id at
all. **The separator** is chrome of the pane before the gap, identified by
`Chrome.name` (`SEPARATOR_CHROME_NAME`) rather than by geometry, so it dies
with the adjacency it divided. Focus falls back when the focused pane closed —
to the collapsed parent, or to the survivor that takes the closed child's
place. The full rules (and the retile contract) are in
[`docs/DESIGN.md`](DESIGN.md). A root pane (one no split holds), a container
(an
already-split pane) and a second close of the same pane all raise `RuntimeError`.
### Scrolling the window — `scroll_to` and `reveal`
```python
tui.viewport.scroll_to(offset)     # the pane's window: an absolute jump, clamped
tui.reveal("b3", 12) -> bool       # bring a document address on screen
```

`Viewport.scroll_to(offset)` is the absolute sibling of the relative moves: the
offset clamps into `[0, max(0, total_rows - viewport_height)]`, so a target above
the document shows its first window and one past its end the last. A landing on the
bottom edge re-attaches the view (auto-follow resumes); any other landing detaches
it.

`TUI.reveal(bid, row)` is the generic "bring this document address on screen" —
what a search tier reveals its current match with. The viewport scrolled is the
focused pane's. An address **already in the window** moves nothing, and one outside
it lands **centered** when the document's edges allow it (the clamp takes over near
either end, still showing the target). `row` is 0-based within the block's own
`render` at the pane's laid-out width, and clamps into the block's rows; a block in
a fixed region never scrolls away, so it answers `True` without moving. `False` for
an unknown `bid` and for a pane with no window to show the target in, and a move
invalidates the frame.
### `Scrollbar` — the reference chrome
```python
Scrollbar(tui, *, pane=None, size=1, min_thumb=1, style=None, thumb_style=None, theme=None, scroll_tick=0.05)
scrollbar = Scrollbar(tui)            # pane=None: the frame's first pane
scrollbar.handle(event) -> bool       # the consume-one-event contract
scrollbar.detach()                    # unregister + cancel the ticker
```

Constructing the bar registers a right-edge `Chrome` on its pane (an id the frame
does not hold raises `ValueError`); the budget is negotiated at the next composition
and the pane's viewport re-wraps at the reduced width. `detach()` is the symmetric
unregister, and the registration rides a retile. The strip paints from the pane's
last layout alone — `offset` / `total_rows` are the only view state a painter reads
— and the thumb geometry is pure arithmetic over them (a small window over a long
document is a short thumb; a document that fits paints a plain track). The strip is
a pure function of that state and the resolved styles, so it is remembered under
exactly those: a repainting frame hands the same strip back, while any scroll,
retile or re-skin is a different key and paints afresh.
`handle(event)` is the bar's own gesture: a left press in the strip is consumed
(grab-and-drag on the thumb, anchored so it never jumps; a held track click pages
and repeats), every other event — every key, every paste, every wheel report, every
press outside the strip — passes through.
### `Toasts` — the reference overlay
```python
Toasts(tui, *, ttl=4.0, max_shown=3, corner="top-right", style=None, theme=None)
toasts = Toasts(tui)                  # registers the overlay on the frame
toasts.show("Copied 2 lines")         # a str, or any Component
toasts.handle(event) -> bool          # dismiss the toast under the pointer
toasts.detach()                       # unregister + cancel the ticker
```

`show` takes a plain string (wrapped in a `Text`) or any `Component`, plus an
optional per-toast `style` (it wins over the controller's) and `ttl`. A show past
`max_shown` evicts the oldest; the stack grows away from `corner`, one blank row
between neighbours, and never covers more than half the frame. The paint is the pure
half (`frame -> layout`) and the controller owns everything time- and input-shaped:
one `tui.every` ticker checks expiry against `tui.clock()`, and `handle` consumes a
press inside a toast's own rectangle to dismiss it. `detach()` unregisters the
overlay and cancels the ticker.
### `Tooltip` — the pointer's hint band
```python
Tooltip(tui, pointer, *, theme=None)
tooltip = Tooltip(tui, pointer)       # registers the overlay on the frame
tooltip.detach()                      # unregister (idempotent, by identity)
```

The second shipped overlay, and the narrowest: it owns **no input** (no `handle`, no
ticker, no state beyond the registration) and paints one row of text — the theme's
`toast` band — as wide as the hovered leaf's own `hint`, fit to the frame. The band
goes on the row under the pointer's cell, flips above it on the frame's last row,
and both axes are clamped into the frame rectangle. `pointer` is the mounted
`Pointer`, read live at paint time: `pointer.position` is the cell the band sits
beside and `pointer.hovered` the leaf whose `hint` it shows — a leaf without the
attribute, an empty (or non-`str`) hint, or a pointer that never moved hands the
layout back unchanged, the zero-byte case. A page switch — which swaps the pointer —
mounts the new pointer's tooltip and retires the old one.
### `Stats` — the developer's readout
```python
Stats(tui, *, pointer=None, theme=None)
stats = Stats(tui, pointer=pointer)   # registers the overlay on the frame
stats.detach()                        # unregister (idempotent, by identity)
stats.handle(event)                   # count one event; True is a repaint cue
stats.events; stats.last; stats.fps   # the readings a host may also read
stats.pointer = fresh_pointer         # a rebuilt pointer is pointed at, not rebound
```

The third shipped overlay (D14): a developer's readout, not an exhibit — a small
band stack in the frame's **top-right corner**, three rows as wide as their content
and filled with the theme's `toast` band. The readings are all existing fields:
`painter.frames` (read at composition time, so the frame being painted is not
counted yet) beside the frame rate over the last window of **at least a second** —
the session's own sampling rule off `tui.clock()`, no timer armed anywhere — then
the events the host fed through `handle(event)` with the last one's name (`paste`
for a paste), then the hovered leaf's class beside the pointer's last button-free
cell, `hover --` while there is nothing under it. `pointer` is a plain attribute
because the demo rebuilds its pointer per page; `set_theme(theme)` follows a re-skin
and `detach()` retires the box. `handle` consumes **nothing**: it counts the event
and answers `True` as a repaint cue, so a host routes it beside the other tiers —
never in a `consumed` chain — and repaints when it answers.
### `Find` — the search tier
```python
Find(tui, *, theme=None)
find = Find(tui)                      # registers the overlay on the frame
find.open(); find.close(); find.detach()
find.is_open; find.query; find.matches; find.index
find.handle(event) -> bool            # the consume-one-event contract while open
find.set_theme(theme)                 # rebuild the query row, keep the text
```

The search tier, and the second text input in the toolkit: a query `Input` row the
tier **owns** (no host editor feeds it), the matches that row's text finds in the
**focused pane's** document, a cursor over them and an overlay that paints them.
`open()` shows a fresh row (the query and the matches reset) and `escape` — or
`close()` — hides it; closed, it consumes nothing and paints nothing, and reopening
always starts from the empty query. Opening, typing or stepping **reveals** the
current match through `tui.reveal` (`(bid, row, start, end)` addresses at the pane's
laid-out width — another width re-wraps rows, so matches addressed at another one
paint no highlight until the next query change re-addresses them), `enter`/`down`
step to the next match and `up` to the previous one (the ends wrap), and a match in
a fixed region reveals without scrolling. The paint is the pure half: every match on
its row is cut at the hit's column boundaries and merged under the theme's
`selection` — the current one under its `hover` again — and the query row lands on
the frame's **bottom row** on the theme's `toast` band, with an `(i/n)` counter at
its right end. Routing it comes **before** the gestures and the host's keys.
### The dispatch order
One rule everywhere, and it is geometric: a host routes every event through the
chrome before any content gesture and before its own dispatch, with the overlays,
the **modal** and the search tier between the chrome and the gestures:

    chrome → overlays → the modal (while open) → find (while open)
    → gestures → the focused widget → the host's own dispatch

One tier sits *outside* the chain: the dev `Stats` overlay's counting feed (it
consumes nothing — its `True` is a repaint cue).

```python
scrollbar = Scrollbar(tui)            # chrome, first
toasts = Toasts(tui)                  # overlays, next
modal = Modal(tui, dialog)            # the blocking layer, behind the overlays
gesture = SelectionGesture(tui)       # content gestures
ring = FocusRing([menu, tree])        # widget focus, after the gestures
event = await tui.read_key()
if not scrollbar.handle(event):       # 1. chrome
    if not toasts.handle(event):      # 2. overlays
        if not modal.handle(event):   # 3. the modal, while open
            if not find.handle(event):    # 4. the search tier, while open
                if not gesture.handle(event): # 5. gestures
                    if not ring.handle(event):# 6. the focused widget
                        ...           # 7. the host's own dispatch
```

Three rules make the order exact. **Chrome first, and geometrically:** the bar's
strip is derived from its pane's rectangle, so it routes before any hit test runs —
a press that reached a hit test first would anchor a selection on the text under the
strip. **Overlays after chrome, before gestures, also geometrically:** an overlay's
band is derived from the frame's rectangle the same way, so a press inside a toast
has to be consumed before a hit test runs, and placing overlays after the chrome
keeps the bar's own columns the bar's. **Gestures before the host's dispatch:** the
bar, the overlays and the gesture speak the same consume-one-event contract, so a
controller that consumed an event leaves no trace in the host's state. **An open
modal outranks everything after it, and it is absolute:** while it is open
`Modal.handle` answers `True` to every event — the panel's own keys first, the
body's before the panel's (**body-first**: a panel with a `body` hands it the
keyboard ahead of its own `handle`, which is exactly why a `prompt_dialog`'s
field takes a printable and its `enter` still reaches the button row), a press
inside the panel is the panel's click, a press outside dismisses — so the
gestures, the ring and the host's own keys never see an event while a modal is
open. That is why a host's own quit chord belongs **before** the modal in its
dispatch (`c-c` in the demo: the modal's contract says the host handles its
shortcuts first). Two more
rules follow. **The wheel is nobody's chrome:** `read_key` intercepts `scroll_keys`
before the host loop runs, so a wheel report never reaches `Scrollbar.handle` — one
that does (a host that deleted the binding) passes through untouched. **A host with
a cell-level affordance of its own** — foldable tool calls, whose chevron row owns
its click — resolves those cells between the overlays and the gesture: the row is
the call's, every other cell is the gesture's.

`Find` is the one shipped controller routed **between the overlays and the
gestures** — after a modal panel's own slot, since a modal panel outranks a
search. While the tier is open it owns the keyboard: its own keys
(`enter`/`↑↓`/`escape`, and the query row's editing keys) are consumed before
the gestures and the host's dispatch, a printable typed at the shell reaches
the query row, and `c-c` is kept as the one gesture that always quits. A host
that also mounts a modal panel routes the panel first and opens it on a key
the open query row does not consume.

A focus ring joins after the gestures (step 4): the keys a focused widget owns
route before the host's own dispatch, and the host routes the cycle key
(`tab`) to `focus_next` itself — the ring binds nothing. The mouse takes a
different door: the gesture consumes the press, and the stationary click goes
one level further — a mounted `Pointer` resolves the cell, descends to the
leaf and runs the ring's policy, so the gesture owns the press, the pointer
owns the hover and the click, and the ring owns what the click *means*. A host
that dispatches the click itself still calls `ring.click(tui.hit_test(event.x,
event.y))` — [Focus](#focus) has the wiring.

### Build your own chrome — a 2-column rail

A chrome is one `Chrome(edge, size, paint)` value whose `paint` is a pure function
of the pane's last layout and the strip's length. The reference recipe is a
line-number rail: two budgeted columns on the left edge, numbered from the
layout's `offset` over its `total_rows` — no viewport attribute is ever touched.

```python
from motui import DEFAULT_THEME, Line, Style, Theme

from motui.kernel.frame import Chrome


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

That is the whole surface: `add_chrome` registers (the pane's viewport re-wraps at
the reduced width), `remove_chrome` unregisters by identity, the compositor clips
a budget that would squeeze the viewport out, and a `size: 0` chrome is a legal
no-op seam. Chromes stack — several on one edge sit outermost-first, budgets add —
so a rail beside a gutter is two chromes.
### Build your own overlay
An overlay is the other half of the registry: any object with
`paint(frame) -> layout`, registered with `tui.frame.add_overlay` and unregistered
by identity with `remove_overlay` (a missing entry raises — test membership first to
keep a `detach()` idempotent). The worked example ships in the driver: the selection
highlight is overlay #1, a `paint` that marks the focused pane's own layout and
splices the marked rows back through `Frame.with_pane_rows`. `Toasts` is the
reference *controller* over that protocol (registration at construction, time on the
pump's clock, input on its own geometry); `Tooltip` is the minimal one (no input, no
time, a `paint` that reads the pointer's live state and the hovered leaf's `hint`);
`Find` is the third. A minimal overlay of your own is their `paint` shape: read
`frame.layout`, rewrite rows, hand the layout back (unchanged, when there is nothing
to paint).
### Build your own container — let a custom wrapper take clicks

A component that wraps children is one `child_at` method away from being clickable
through: the container records its children's rectangles at render time and
translates a cell into the child's own coordinates. That is the whole protocol —
`Pointer` and `FocusRing.click` run `descend` first, so a cell a wrapper swallowed
would otherwise stop at the wrapper.

```python
from motui import Line
from motui.kernel import Component


class Stack:
    """A vertical composite whose children stay clickable through it."""

    def __init__(self, children: list[Component]):
        self.children = list(children)
        self._spans: list = []    # empty until the first render: every cell declines

    def render(self, width: int) -> list[Line]:
        self._spans = []          # (child, first_row, height): this render's geometry
        rows: list[Line] = []
        for child in self.children:
            child_rows = child.render(width)
            self._spans.append((child, len(rows), len(child_rows)))
            rows.extend(child_rows)
        return rows

    def child_at(self, row: int, col: int):
        for child, first, height in reversed(self._spans):   # the last painted wins
            if first <= row < first + height:
                return child, row - first, col                # the child's own cell
        return None                                           # our own cell: nobody
```

Three rules, the same the built-in containers follow. **The geometry comes from
the last render** — a stack that has never rendered declines every cell (the
`TextBuffer.move_up` precedent), and no hit test ever invents a layout. **The
coordinates are translated** — the child receives its own block-internal cell, so
its own `click`/`hover_at` arithmetic just runs. **Nothing else is proxied** —
`handle` / `move` / `activate` / `focused` stay the leaf's, so keyboard focus
registers the child itself and `Padding(Editor)` needs the editor in the ring for
keys while its click still descends.
### Build your own inline action — a row of clickable spans

A component with inline actions is one `action_at` call away from clickable **and**
hoverable: build the row's `Line` with the payloads, hand the row table of your
last render to `action_at`, and consume only what carries an `action` — a miss
declines, so the host's other policies still get their turn. The `link` half is the
terminal's: `Line.styled()` wraps the run in the OSC 8 pair, so a terminal opens a
real hyperlink over exactly that run.

```python
from motui import Line, Segment, Style
from motui.kernel import action_at    # the kernel's inline-action lookup

HOVER = Style(reverse=True)   # or the theme's ``hover`` band


class Chips:
    """One row of labelled chips; each chip is clickable and hoverable."""

    def __init__(self, chips: list[tuple[str, str]]) -> None:
        self.chips = chips                        # (label, action) pairs
        self.hover = False                        # Hoverable's one flag
        self.chosen: str | None = None            # the host reads it once
        self._rows: list[Line] = []               # last render's row table
        self._span: tuple[int, int, int] | None = None

    def _base_rows(self, width: int) -> list[Line]:
        """The row, every chip carrying its action (and a link when it has one)."""
        parts: list[Segment] = []
        for label, action in self.chips:
            if parts:
                parts.append(Segment(" \u00b7 "))
            parts.append(Segment(label, Style(underline=True), action=action))
        return [Line(parts).fit(width)]

    def render(self, width: int) -> list[Line]:
        rows = self._base_rows(width)
        self._rows = rows                         # the hit testing's geometry
        if self._span is not None:                # the hover post-transform
            index, start, end = self._span
            rows[index] = rows[index].merge_span(start, end, HOVER)
        return rows                               # a fresh list, always

    def hover_at(self, row: int, col: int) -> bool:
        hit = action_at(self._rows[row], col) if 0 <= row < len(self._rows) else None
        span = None if hit is None else (row, hit[1], hit[2])
        changed = span != self._span
        self._span = span
        return changed                            # True = repaint

    def click(self, row: int, col: int) -> bool:
        hit = action_at(self._rows[row], col) if 0 <= row < len(self._rows) else None
        if hit is None:
            return False                          # not a chip: consume nothing
        self.chosen = hit[0]
        return True
```

The same four rules the library's own `Text`/`Markdown` follow. **The hit test
reads the last render's row table** — the geometry the user is looking at, never a
re-render. **The payload is the address** — `action_at` answers
`(action, start, end)` in display columns (left-closed, right-open), so a wide
cluster owns both of its cells and a click at either one hits. **The hover is a
copy** — merge the band into the hit row (`Line.merge_span`) in `render` and leave
the row you cached alone, so clearing the hover hands back the un-hovered bytes
exactly. **A miss declines** — return `False` from `click` and the host is free to
route the cell on. And put the url in `link` too when the chip should be a real
terminal hyperlink: one component then serves the mouse and the terminal's own
cmd+click at once.
### Assembling an app — the footer-band recipe

The library ships **no app shell**: no ready-made application, no pinned input
box. A host assembles its own from three pieces — the body document the panes
render, a footer `Document` holding the input and status rows, and
`tui.add_band(viewport)`, which parks that footer's viewport in the frame's bottom
band: full width, beneath every pane, outside every split, so a pane division never
cuts it in half.

```python
from motui import Editor, StatusLine
from motui.kernel import Document, Viewport
from motui.keys import EDITOR_SUBMIT_KEYMAP

footer = Document()                           # the shell's own footer document
editor = Editor(keymap=EDITOR_SUBMIT_KEYMAP)  # enter stays the host's submit gesture
footer.add(editor, id="input")                # the pinned input row
footer.add(StatusLine(left=("ready",)), id="status")
tui.add_band(Viewport(footer))                # park the footer under the pane area
```

The runnable version — the read loop, the `enter` submit and the quit gesture —
is the `## Building your own shell` block in `README.md`, executed headless by
`tests/test_readme_examples.py`. `Document` and `Viewport` are the two deeper
seams the recipe reaches for; both stay public at `motui.kernel`. The assembly
grows with one line per tier, and each line is a decision — the dispatch order
above is what orders them:

```python
from motui import Option, Palette

palette = Palette(tui, [Option("/help", value="help", description="the command list")])
footer.add(palette, id="palette")   # a self-contained panel with its own query row
                                    # (a modal, so route it first while it is open)
scrollbar = Scrollbar(tui, pane="primary")   # chrome: budgets the pane's edge column
toasts = Toasts(tui)                         # overlays: after the chrome, before the gestures
gesture = SelectionGesture(tui)              # the drag owns press/motion/release
ring = FocusRing([editor, menu, tree])       # the focused widget's own keys, after the gestures
pointer = Pointer(tui, ring=ring)            # hover + stationary clicks (TUI(hover=True))
```

Two facts keep the assembly honest. **No component here is an app**: the footer's
`Editor` is a field and `StatusLine` is a row, and the submit — the one piece of
behavior the library refuses to own — is the host's own five lines inside the loop
above. **The band is not a pane**: it takes no focus and no split, a wheel over it
scrolls the focused pane, and its height is its content's
(`Viewport.natural_height`), so an opening palette pushes the pane area up exactly
as a pinned block would. For the exhibits-instead-of-an-app shape, `python -m
motui` is the reference the other way: the library's own demo — eleven pages with
**no input box anywhere** and a rail in a pane.
## Selection
Selection is an assembly that touches the driver — the peer of the interaction
tier's controllers (`Scrollbar` / `Toasts` / `Modal`), not a `render(width)`
component. The mechanism
is the kernel's (`motui.kernel.selection`: the `Selection` model, the `highlight`
overlay, `extract`) and the driver's (`tui.selection` reads, `tui.set_selection`
writes and invalidates); every behavior is one policy object
(`motui.interaction.gesture`) a host opts into with a single line. The rationale is
`docs/DESIGN.md`; this section is the handbook.
### `SelectionGesture` — the constructor
```python
SelectionGesture(
    tui,
    *,
    on_end=copy_on_select,   # the selection-end action; None selects with no effect
    scroll_rows=2,           # rows one edge tick scrolls — and extends the head
    scroll_tick=0.05,        # seconds between edge ticks
    double_click_seconds=0.35,  # the click-count window around the last press's cell
)
gesture.handle(event) -> bool   # True consumed, False the host's
gesture.detach()                # cancel the ticker, drop the in-flight drag
```

The gesture is single-pointer by construction: the **left** button anchors and
extends, every other button, every key, every `Paste` and every lone motion passes
through untouched. It owns its own anchor and head addresses and mirrors the drag
into the driver through `set_selection`; it keeps no copy of the text, the rows or
the layout. Timestamps come from the driver's public clock seam (`tui.clock()`).
### The state machine

The host's dispatch is `if not gesture.handle(event): ...` — the same
consume-one-event contract `Input`/`Editor` answer, with one dispatch line covering
the whole feature. What the left button's reports do:

| Report | Effect |
|---|---|
| `press` (plain) | Anchors at the cell the hit test resolves. A press on blank fill, outside the last layout, or on a block removed since it retires the previous highlight and anchors nothing. |
| `press` on an edge row | Arms the auto-scroll ticker immediately, not only a motion: the pointer can reach the edge *before* the button goes down, and a stationary press there emits no motion to arm it with. |
| `press` again, same cell, within `double_click_seconds` | Word select: the maximal non-whitespace run around that cell on its row, measured in display columns through the same measure the kernel cuts by — a CJK character selects whole. It fires `on_end` exactly once, at the press; the release that follows finalizes nothing; and it never arms the ticker. A cell on whitespace (or past the row's text, which clamps to the last column) has no run and degrades to a plain press. |
| `press` a third time, same cell, inside the window | Line select: the hit block's whole visible row at the pane's laid-out width — the row address and the span are the same block's, so it never runs past the block into its neighbour. The same completed-selection shape as the word. The **fourth** press starts the count over, so the vocabulary is click, word, line, click. |
| `motion` while dragging | Extends the head to the cell under the pointer. A motion off the content keeps the head where it is. A cleared overlay underneath the drag (a reflow, or a host write) ends the drag cleanly. |
| `motion` onto an edge row | Arms the edge ticker; a motion onto any other in-content row disarms it; a motion off the content disarms it too. The edge zone is the viewport region's first and last rows — the scrolling window, never the pinned footer. |
| `release` | Cancels the ticker and finalizes. A zero-width press-release — a click — clears the selection and never fires `on_end`: the clipboard is never clobbered by a click. A completed drag fires `on_end` exactly once, and the highlight stays until the next press so the user can verify what was copied. |
| wheel while a drag is in flight | Consumed: scrolls the viewport its signed `scroll_keys` count and co-extends the head by exactly the rows the viewport actually travelled. A binding the host deleted from `tui.scroll_keys` passes through. |
| second `press` mid-drag | Re-anchors a fresh drag from the new cell; the abandoned drag never fires `on_end`. |

The armed ticker rides the pump's existing `every(seconds, fn)` handles — the
working-spinner pattern, no new mechanism. Each tick scrolls `scroll_rows` rows and
moves the head by the offset the viewport actually travelled, in document space,
never by re-`hit_test`ing. It stands down on edge-exit, release, `detach()`, a
reflow that cleared the overlay underneath it, and the document end. `detach()`
cancels the ticker and drops the in-flight drag so a later release cannot finalize
it; the stored overlay is the driver's, and stays as the last frame painted it.
### `copy_on_select` — the shipped `on_end`
```python
def copy_on_select(tui, selection):
    tui.screen.copy(extract(tui.document, selection, width=tui.screen.width))
```

Two lines, and the smallness is the point: every mechanism (the range walk of
`extract`, the clipboard primitive) lives in the kernel already, and the whole
policy is "which text, which screen, once". `extract` takes `width` keyword-only —
it is the width the addresses were laid out against, and there is no honest default
— and it reads the document blocks straight, so content the viewport has scrolled
past copies exactly like the visible rows.
### `Screen.copy` — the clipboard primitive

`screen.copy(text) -> bool` emits `\x1b]52;c;<base64>\a` (built in
`kernel.ansi.copy_clipboard`) and reports whether it wrote. A `TerminalScreen`
writes only when live — a pipe or a file has no clipboard, so `copy` answers
`False` there. A `HeadlessScreen` is live by construction and records the bytes:
that is how a test proves a copy happened. Even a `True` is best-effort —
terminals may refuse application clipboard writes by policy — which is why the
gesture's `on_end` hook, not the primitive, is the real contract.
### The extension cookbook

Four worked replacement points, and between them the whole surface a future feature
author needs — none of the recipes below reaches into the kernel.

**(1) Drive `tui.set_selection` from your own loop.** A search feature highlights
its hit without any gesture at all: the driver's surface is one write, and the
overlay paints it.

```python
from motui.kernel import Selection

# Your search found "transcript" on block "b1", rendered row 0, column 15.
term = "transcript"
anchor = ("b1", 0, 15)
tui.set_selection(Selection.between(anchor, ("b1", 0, 15 + len(term))))
# The write invalidates the frame; the pump repaints, overlay included.
```

**(2) Replace `on_end` — the `/quote` example.** This is an extension example,
**not shipped API**: the toolkit ships no `/quote` command. It shows the hook
receiving the finished range and prefilling a host editor through the editor's own
buffer API.

```python
from motui import SelectionGesture
from motui.kernel import extract

def quote_on_select(tui, selection):
    """Quote the selection into the host editor: extract, prefix, prefill."""
    text = extract(tui.document, selection, width=tui.screen.width)
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    editor.clear()          # replace whatever is being typed
    editor.insert(quoted)   # a multi-line insert goes through the same buffer API
    tui.invalidate()

gesture = SelectionGesture(tui, on_end=quote_on_select)
```

**(3) Tune or retire the sub-gestures.** The three knobs and the `on_end` switch,
all constructor arguments:

```python
gesture = SelectionGesture(
    tui,
    on_end=None,                   # select without copying: no effect at selection end
    double_click_seconds=0.0,      # no click count: a live clock never reads inside a zero window
    scroll_rows=1, scroll_tick=0.02,   # a finer, slower edge crawl — v1 has no auto-scroll off switch
)
```

**(4) Restyle the highlight — own the composition root.** The kernel merges the
fixed `SELECTION` constant (`reverse`, attribute-only, so the run's own colors
survive under the overlay) and v1 has no injection point for it. The recipe is to
own the last step of the frame instead: the overlay is a pure function over a
laid-out frame, so yours composes on the kernel's and paints through the driver's
own painter.

```python
from dataclasses import replace

from motui import Line, Segment, Style
from motui.kernel import highlight

MARK = Style(reverse=True, fg="#ff8800")   # your highlight: reversed, your hue

def my_overlay(layout, selection):
    """The kernel's range cut, your style — the merge happens at your call site."""
    painted = highlight(layout, selection)
    if painted is layout:
        return layout    # the kernel marked nothing (None or an empty range): lazy no-op
    return replace(layout, rows=[
        Line([
            # the kernel marks the in-range pieces by merging SELECTION
            # (reverse): re-merge your own onto exactly those
            Segment(s.text, s.style.merge(MARK)) if s.style.reverse else s
            for s in row.segments
        ])
        for row in painted.rows
    ])

# At a host-owned composition root — the shape the driver's own paint runs:
layout = tui.frame.compose(tui.screen.width, tui.screen.height)
layout = my_overlay(layout, tui.selection)
tui.painter.paint(layout)
```

The re-merge keys on `reverse`, which is the kernel's documented mark; a segment
that was already reversed for its own reason (the editor's block cursor) is
indistinguishable from a marked one, so this seam fits content carrying no cursor
of its own. Note the boundary the recipe keeps (D7): the theme's `selection` field
styles the *component* cursors (`Tabs`, `Tree`, and a menu built with
`selected_style=theme.selection`) — that seam is per-component `*_style=`
arguments — while this overlay is the document-level one. Two vocabularies, two
mechanisms, never mixed.
## Focus
Focus is the second assembly that touches the driver — the peer of
`SelectionGesture`, and a *layer*, never a component's responsibility. A component
only declares that it can be focused: one read-write flag,

```python
from motui.kernel import Focusable   # the protocol: `focused: bool`

class Gauge:              # any component may be a focus target
    focused = True        # the ring rewrites this as the focus moves
```

and one rendering rule — **unfocused means the cursor style merged with
`theme.dim`**: `Select`'s marker and label (`selected_style.merge(dim)`), `Tree`'s
`cursor_style`, and `Tabs`' `active_style`. The hue survives, the weight drops, and
no new theme field appears. `Input`/`Editor` already had the flag (it draws — or
omits — their block cursor), so they satisfy the protocol unchanged.

Everything else lives in `motui.interaction.focus.FocusRing`, a host opts in with
one line, and the component never learns a manager exists:

```python
from motui import FocusRing

ring = FocusRing([menu, tree])        # the first target is focused at once
event = await tui.read_key()
if event.name == "tab":
    ring.focus_next()                 # the host owns the cycle key
elif not ring.handle(event):
    ...                               # the host's own dispatch
# a mouse hit from tui.hit_test(x, y) runs the click policy:
ring.click(hit)
```

`FocusRing(targets=(), *, wrap=True)`. Every target must satisfy `Focusable` — one
that cannot be focused raises `TypeError` at construction, before the first
keypress. A non-empty ring focuses `targets[0]` and clears every other target's
flag; an empty ring holds no focus and every method degrades safely.
`focus(target)` answers whether the focus moved (an unregistered target answers
`False` and leaves the focus alone; the current target answers `False`);
`focus_next(delta=1)` cycles through the registered order, wrapping by default,
clamping at the ends with `wrap=False`, and never moving on a single-target or empty
ring.
### The constructor and the cycle

`FocusRing(targets=(), *, wrap=True)`. Every target must satisfy `Focusable` — a
target that cannot be focused raises `TypeError` at construction, before the first
keypress. A non-empty ring focuses `targets[0]` and clears every other target's
flag; an empty ring holds no focus and every method degrades safely.
`focus(target)` answers whether the focus moved (an unregistered target answers
`False` and leaves the focus alone; the current target answers `False`);
`focus_next(delta=1)` cycles through the registered order, wrapping by default,
clamping at the ends with `wrap=False`, and never moving on a single-target or
empty ring.
### The routing table — `handle(event)`

`handle` dispatches one `Key` or `Paste`, answering whether the ring consumed it,
in this order:

| # | Condition | Action |
|---|---|---|
| 1 | the focus is empty | `False` |
| 2 | the focused target has `handle(event)` | its answer wins — a field consumes its own keys (printables, arrows, backspace) and its `Paste`, ahead of every ring verb |
| 3 | an unconsumed `Key`: `up`/`left` or `down`/`right` | `move(-1)` / `move(+1)`; with no `move` method the arrow falls back to its own verb — `move_up()`, `move_left()`, `move_down()`, `move_right()` (the text fields' shape) |
| 3 | an unconsumed `Key`: `enter` | `activate()`; a target that is not `Activable` answers `False` |
| 4 | anything else | `False` — the host keeps routing the submit gesture, the palette, quit |
### The click policy — `click(hit)`

`hit` is what `tui.hit_test(x, y)` resolves (a `Hit`: the block, the
block-internal `row`/`col`, the pane id). One click runs four steps:

| # | Condition | Action |
|---|---|---|
| 1 | the block's component is `Clickable` | `component.click(hit.row, hit.col)` — **any** clickable component, ring target or not (a page may hold mouse-only widgets beside the ring) |
| 2 | the component is in the ring and not the current focus | focus it — the first click only moves the focus |
| 3 | the component is in the ring and already focused | `activate()` when it is `Activable` — the second click activates (standard desktop semantics) |
| 4 | always | answer whether anything consumed the click (the host repaints or toasts on it) |
### The pointer's door — hover, and the dispatch order
Hover is not the ring's: the ring routes keys and owns what a click means, but it
reads no motion report and flips no hover flag. Hover is the `Pointer` tier's, and it
needs DECSET 1003 — under the default 1002 a button-free motion is never reported, so
a hover host opens the mode with `TUI(hover=True)`. The reference wiring routes every
report through the pointer beside the gesture and the ring (`docs/DESIGN.md` has the
rationale):

```python
from motui import FocusRing, Pointer, SelectionGesture

ring = FocusRing([menu, tree])        # the first target is focused at once
pointer = Pointer(tui, ring=ring)     # hover + stationary clicks (TUI(hover=True))
gesture = SelectionGesture(tui)       # the drag owns press/motion/release
event = await tui.read_key()
if pointer.handle(event):             # a motion that moved the hover, or a click
    tui.invalidate()                  # the pointer's answer: a repaint cue
if not gesture.handle(event):         # the gesture consumes the reports it owns
    if not ring.handle(event):        # then the focused target's own keys
        ...                           # the host's own dispatch
```

Three rules make the pair exact. **The pointer never consumes:** its `True` means
"what it tracks changed" (the hovered leaf entered, left or moved to another row of
itself, or a click was dispatched), never "the event is spent" — a drag's reports
reach the gesture untouched. **The click descends first:** `Pointer` resolves the
cell through `tui.hit_test`, walks `descend` to the deepest leaf, and runs exactly
the ring's click policy above (or dispatches the deepest `Clickable` leaf itself when
no ring is mounted). **The hover is state, not a callback:** the leaf's `hover` flag
(and `hover_at(row, col)` where it has rows) is written by the pointer and read by
the render; `Pointer.clear()` drops the hover after a pane switch or a resize,
best-effort by design. If a leaf carries a `hint` (the protocol above), the mounted
`Tooltip` overlay paints it beside that same cell — the pointer routes nothing extra
and the tooltip never shows in this chain. How a drag is told from a hover is the
motion's `name` (a button name, or a nonzero `button`, is a drag; `name="none"` is
the hover) — the rule and the mode table are in `docs/DESIGN.md`.

**Out of scope, deliberately**: no hover of the ring's own (the ring reads no motion
report), no hotkey beyond `tab` (the ring binds nothing; the host routes `tab` to
`focus_next`), no mouse drag (press/motion/release is `SelectionGesture`'s), and no
pane/window focus (that is the frame's — `TUI.focus_at` and the pane rectangle own
which pane gets input).

Three more "deliberately not"s the choice layers own (D6 and the wave's review):

- **Multi-select does not enter `Tree`.** A tree's rows carry a parent/child
  relation, and a marked parent is a *third* state (some children marked,
  some not) that no three-column `[x] `/`[ ] ` prefix can tell. The marks stop
  at the flat views — `Table`, `List` and the multi-select choice family — where
  a row is a row. A host that needs a tree with marks owns the half-state
  rendering itself, over `Tree`'s cursor and its own data.
- **A `Dialog` embeds no form and validates no cascade.** Its `body` is *one*
  component (`Text` from `confirm_dialog`, an `Input` from `prompt_dialog`, or
  anything with `render(width)`) and its keyboard is the button row plus
  `escape`: there is no field-to-field navigation, no per-field error row and no
  "the OK button is disabled until the body is valid". The host builds that (a
  `Column` of fields as the body, its own validation on the picks the body's
  `handle` leaves) — the dialog stays a box with buttons.
- **No keymap mnemonics.** The keymaps are name tables: an entry maps an event
  name to an editing method (`"left" -> "move_left"`), and a host rebinds by
  handing in a copy. There is no alias syntax, no modifier grammar beyond the
  decoder's own names and no chord sequence (`d d`): a multi-stroke binding is
  the host's state machine, not a keymap feature.
## Markdown
`Markdown` (in the `motui.widgets.markdown` package) is a **rule-registry engine**,
not a regex pile. Two ordered registries do all the work: a `BlockRule` classifies
the line at the cursor — `match(lines, i)` returns how many lines it consumes, `None`
to decline — and renders exactly those lines; an `InlineRule` recognizes one inline
construct at a position and returns `(end, segments)`. The engine walks the buffer,
first match wins, and `ParagraphRule` is the mandatory catch-all at the end of
`BLOCK_RULES`. The shipped inline registry is tried in the order `code` → `bold` →
`strike` → `italic` → `link`: the rules that share an opening marker (bold and
italic both open with `*`) are ordered sharpest-marker-first, and a rule placed
before another interrupts it.

| element | input | rendering |
|---|---|---|
| heading | `#`..`######` + space | one gold ladder from `Theme.headings`; **h1 is underlined**, h2 stands alone, h3+ keep their `###` markers (the marker is the depth cue) — no bold on the ladder |
| unordered list | `- ` / `* ` (2-space indent per level) | marker kept **verbatim** (no bullet), marker in `list_marker` purple, nesting by indent (deeper indents cap at two levels), hanging indent on wrap |
| task item | `- [ ]` / `- [x]` + one space (a bullet item: `1. [ ]` never takes the box) | the bullet becomes a one-column `☐` / `☑` box in the list-marker color and the whole `"☐ "` run is one **action span** whose payload is `"todo:<flat index>"` -- the task's ordinal across the document, counting the source markers in draw order (a quoted or nested task included); a click lands it in `Markdown.chosen` and the *host* rewrites its own `text`. A half-typed `- [x` stays an ordinary item |
| ordered list | `N. ` | number kept verbatim, marker colored as above, nesting as above |
| block quote | `> ` | every line gets a muted `│ ` prefix; the body re-runs the block registry behind the bar and renders italic (colored/bold segments keep their own emphasis) |
| fenced code | ```` ``` ````-delimited | opening and closing fence lines render in the theme's muted; the body goes through the `Highlighter` seam (`highlighter=`, the theme's `code` style when untagged), an unclosed fence runs to the end |
| table | `\| a \| b \|` + `\|---\|---\|` | box grid via the `Table` component (uncolored `Theme.table_border`, plain header, `:--`/`--:`/`:-:` alignment, cells render inline markup, one `├─┼─┤` between every two data rows, `\|` a literal pipe) |
| thematic break | `---` / `***` on its own line | `Divider` rule capped at `divider_max_width` columns (default 80) |
| paragraph | anything else | soft line breaks join, word-wrapped |
| inline | `` `code` `` `**b**` `~~s~~` `*i*` `[t](u)` | `inline_code` pink / bold / struck (`~~…~~` is an attribute-only `Style(strike=True)`, no colour change) / italic / `link` underlined label, with the url as the label's `link`/`action` payload (the url itself is not rendered) |

**Rendering notes.** Adjacent blocks are separated by exactly one blank row — the
`gap` argument (default 1; `gap=0` stacks blocks directly) — and the source's own
blank rows never add a second one. Table cells are parsed with the inline engine,
and an escaped `\|` stays a literal pipe inside one cell instead of splitting the
row. A thematic break spans at most `divider_max_width` columns (default 80, `None` =
the full width). A link renders its label only, styled with `Theme.link`, and keeps
the url as the label segment's payload: the row's bytes wrap the label in the OSC 8
pair and a click on the label lands the url in `Markdown.chosen`. Every row a rule
returns is wrapped and `fit` to `width`, and a payload rides through the wrap and the
truncation: every row a long label breaks across still answers the same url.

**Task markers and `fences()`.** A task box's `"todo:<i>"` ordinal is stamped onto
the finished rows **after** the `(text, width)` cache — the hover transform's rule,
so the cache's own rows keep the bare placeholder and an append-only streaming
resume numbers exactly like a whole render. The stamped rows and the span index (the
table `click` / `hover_at` hit-test against) are remembered with the `(text, width)`
render they describe, so a hit frame rebuilds neither. The *loop* is the host's: it
reads `chosen` once, flips the i-th task marker in its own `text` and assigns the
text back. `Markdown.fences()` answers the document's top-level fences as
`(lang, code)` pairs, parsed from `text` itself with the block engine's own rule (an
unclosed fence runs to the end; a quoted `` > ``` `` line is the quote body's
document) — never from the render cache or the last render's rows — so a host can
copy a code block (`screen.copy`) without walking a row.

**The memory, and the revision.** `render(width)` keeps one `(text, width)` entry; a
text that only **grew** past its last line renders a **suffix** — the tail block is
re-rendered from its own start and spliced onto the cached prefix, and a tail
paragraph re-parses and re-wraps only from its first changed word — so a reply
streaming in costs about the same per frame whatever already landed. Anything the
append-only paths cannot vouch for falls back one level at a time: a growth the
paragraph walk cannot pin re-renders the tail block whole (an unclosed fence being
closed later is exactly that), and anything that is not that shape — a shrink, a
change before the last line, a last line that did not simply grow, a width change —
renders the whole document. A miss re-parses; it never serves a stale row.
`revision()` is the text plus the hovered span — the snapshot `Block.rows` keys on —
so a **sealed** document's link or task hover still reaches the screen.

**Streaming is safe by construction.** `text` is mutable — assign it one chunk at a
time — and every prefix renders: a half-open fence keeps its body, a table is only a
table once header *and* delimiter row are both present (otherwise it is a
paragraph), and an unclosed `**`/`~~`/`` ` ``/`[t](` stays literal.
`StrikeInlineRule` (exported from `motui.widgets.markdown`) is the built-in
strikethrough: it declines a `~~` run with no partner or with empty content, so a
streaming prefix is never half-struck.
### The render context

Rules are dep-free singletons — no theme, no registry, no highlighter of their own
— so one instance serves every `Markdown`. What a rule needs to render arrives in
one frozen **`RenderContext`** (`motui.widgets.markdown.RenderContext`), which
`Markdown` builds once at construction:

| field | meaning |
|---|---|
| `theme` | the resolved `Theme` (`DEFAULT_THEME` when none was passed) |
| `highlighter` | the fenced-code engine, or `None` (the fence then derives one from the theme) |
| `divider_max_width` | the thematic-break cap the component was built with |
| `block_rules` | the **live** block registry of the document being rendered |
| `inline_rules` | the **live** inline registry |

Because the context carries the *live* registries, a custom rule reaches every
built-in block — quote bodies, list continuations and the paragraph catch-all that
yields to higher-priority rules all re-run the same registry — with no re-binding
of any kind. There are no `with_*` cloning conventions: extending is "implement the
protocol, read the ctx".
### A custom inline rule, end to end

The smallest useful extension is one `InlineRule`. An inline rule is `name` +
`match(text, pos, ctx)`; it returns `(end, segments)` when the construct starts at
`pos` and `None` to decline. A style that sets a color is absolute; an
attribute-only style merges onto the surrounding run's base style.

```python
from motui import Markdown
from motui.kernel.lines import Segment
from motui.widgets.markdown import INLINE_RULES


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

- **Register by prepending.** `inline_rules=[MyRule(), *INLINE_RULES]` (and
  `block_rules=[MyBlockRule(), *BLOCK_RULES]`) — order is the match priority, so
  put a rule before any rule whose marker it opens with.
- **Read what you need off `ctx`.** `ctx.theme` follows the component's `theme=`,
  so the rule restyles with the document instead of hard-coding a color.
- **No cloning.** A custom block rule reaches quote bodies and list items
  automatically, and the paragraph catch-all yields to it, because the context
  carries the live registry.

**Math is the documented extension point, not a feature.** `$...$` slots in as one
more `InlineRule` (and `$$...$$` display equations as one more `BlockRule`); the
registries are the only integration surface, so nothing in the engine needs to
change when it lands.
### Highlighting

`Markdown(..., highlighter=...)` — and any component that takes the seam — accepts
a **`Highlighter`**: any object with `highlight(code, lang) -> list[Line]`. The
built-in `RegexHighlighter` (in `motui.widgets.syntax`) colors 16 languages —
Python, JavaScript, TypeScript, bash/shell, JSON, YAML, TOML, Markdown, diff,
Rust, Go, C, C++, HTML/XML, CSS and SQL — under 32 tag keys, aliases included, with
five token classes: `comment` muted + italic, `string` success, `number` warning,
`keyword` the accent's hue, `builtin` the theme's `code` ice blue. **No token
carries weight** — code stays weight-neutral, so the only bold left in a default
render is the `**…**` syntax itself, and the only struck run is `~~…~~`. Matching
is per-line and first-match-wins, and text no rule claims keeps the theme's `code`
style. Each line's answer is remembered — `(line text, normalized tag) -> Line`,
bounded at `_LINE_MEMO_MAX` (4096 distinct lines; past it the table clears
wholesale) — and because matching is per-line with no cross-line state, the memory
is **complete**: a miss re-highlights the line, it can never answer a wrong one. The
stock instance is shared, so every fence it highlights feeds the same memory.

`default_highlighter()` shares the stock instance (building one compiles every
rule, so components share rather than rebuild), `RegexHighlighter(theme=…,
languages=…)` restyles or extends the table, and `highlight(code, lang)` is the
convenience entry point. Injecting your own object replaces the engine entirely —
the protocol is the integration surface.
## Building your own component
A component is one class with `render(width)`. The protocol is `motui.Component`:

```python
from motui import Line, Segment, Style
from motui.kernel import DIM, SUCCESS


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

`ProgressBar` grew up into a library component (`motui.widgets.ProgressBar`, with
`theme=`, `width_chars=` and re-clamping `fraction`); the recipe is still the shape
a custom one takes. Rules of thumb:

- **Measure, don't guess.** Use `Line(...).width` (or `Segment` counts) for display
  width — never `len()`. The toolkit's own truth is `visible_width` (wcwidth), on the
  `motui.kernel` facade together with `wrap_text`; `Line.width` is its per-row face.
- **Always `fit(width)`** the rows you return so a tight screen truncates with a `…`
  instead of wrapping or overflowing.
- **Resolve styles once.** Take `style=` / `theme=` and resolve explicit > theme >
  `DEFAULT_THEME` in `__init__`, not in `render`.
- **Keep it pure.** `render` must not paint, sleep, read keys, or mutate global
  state — the same component renders in any width, and a custom one caches like any
  other: give it a value-snapshot `revision()` and `Block.rows` remembers an open
  block's rows too (a sealed block is cached without one, an open block without one
  re-renders per layout).
- **Drive it through the driver.** Put it in a block (`tui.add(ProgressBar(0.4))`),
  mutate it over time, and call `tui.invalidate()`; the pump and diff handle the
  rest.

`ProgressBar` and any other class shaped like this drop straight into
`Document.add`, `Row`, `Column`, and `Panel` — which is exactly how the built-ins
are assembled.
## Testing
A session is a function of its events: mount the components on a `HeadlessScreen`,
hand the driver a `ScriptedKeys` source, and every byte the session would have
painted is readable from `screen.output` (`str`, not `bytes`). Nothing sleeps — the
library never waits on a clock in a test.

- **`headless_tui(width, height, script=…)`** builds a driven `TUI` on a
  `HeadlessScreen` with a `ScriptedKeys` source and `interactive=False`;
  **`snapshot(tui)`** renders the document as structured plain text (one stanza per
  block) for assertions that do not care about escape bytes. Both live in
  `motui.testing`, and the demo doubles as a smoke test in piped mode.
- **`ScriptedKeys`** replays a fixed event list and then reports EOF forever; a
  `None` item inside the list is a one-shot EOF. It is the double a test's `keys=`
  slot takes, and the source the demo's headless replay is built from.
- **`RawTerminalKeys`** is the live one: POSIX `termios`, or the Windows console
  record API, with a cooked-line fallback. A test never starts it.

**Golden frames.** The demo's own pages are pinned byte for byte on disk: one text
file per page under `tests/golden/pages/` (the page's `--pages` dump, LF endings),
recorded and diffed by `tools/golden.py` (`--check` is the default and the gate's
line, `--update` re-records the whole set). The repository's own test renders each
page through the same headless path and compares bytes, so a component change that
moves what a user sees fails by page name. Fuzz and layout invariants are the other
half of the battery: `tests/test_decoder_fuzz.py` walks a fixed
`random.Random(seed)` byte matrix through `KeyDecoder` (never raises, `pending()`
stays a bool, `finish()` clears the state, and byte-wise feeding matches whole-block
feeding over the **entire** matrix — a bracketed paste's end marker split across
feeds closes the paste wherever the boundary falls), and
`tests/test_render_invariants.py` renders the component matrix at widths `1…80`
(idempotent, never wider than the width, drift-free across a resize).
