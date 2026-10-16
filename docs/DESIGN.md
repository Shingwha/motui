# Design

How the toolkit turns a document of blocks into a full-screen, scrollable,
diffed TUI. Every claim here matches the shipped modules under
`src/mocode_tui/`.

## The four layers under one driver

Four layers compose the toolkit, plus seven top-level modules that sit above
the kernel precisely because they compose it with the `keys` layer:

```
mocode_tui
├── app.py       the TUI driver: the composition root (imports core + keys)
├── gesture.py   SelectionGesture + copy_on_select: the mouse-selection policy tier
├── pointer.py   Pointer: the pointer tier (hover tracking, stationary clicks)
├── search.py    Find: the search tier (its own query row, the matches, the reveal)
├── focus.py     FocusRing: the widget-focus tier (targets, cycle, routing, clicks)
├── chrome.py    Scrollbar + Toasts + Tooltip + Stats: the chrome/overlay assembly tier
├── testing.py   headless_tui / snapshot: the developer helpers
├── core/        the kernel: primitives, events, document model, render core,
│                the interaction protocols, the frame, the selection kernel
├── keys/        input: the byte decoder, the keymaps, the key sources
└── widgets/     the generic component library (render(width) components)
```

Dependencies point one way. `core` imports nothing from `keys`, `widgets`
or the top-level modules. `keys` imports `core` (the event model
in `core.events`) only. `widgets` imports `core`, and `Input`/`Editor` also
reach for `keys.keymap` for their default keymap tables.
`app.py`, `gesture.py`, `pointer.py`, `search.py`, `focus.py`, `chrome.py`
and `testing.py` are
at the top level because they are the composition root, the interaction
policy tiers and the developer helper: each is free to pull in `core` *and*
`keys`, which is why the driver tier never lives inside `core`. `chrome.py` imports
the driver and the kernel and nothing below it imports it: it is where
scrollbar and toast *policy* lives,
over mechanisms the kernel owns (the pane's chrome budget, the layout's
`offset`/`total_rows`, the pump's `every` handles).

Each package re-exports its own public surface, so `from mocode_tui import …`
is the curated one-line face (66 names) and `mocode_tui.core` / `.keys` /
`.widgets` / `.app` / `.chrome` / `.gesture` / `.focus` / `.pointer` /
`.search` / `.testing` are the per-layer faces. `tests/test_api_root.py` pins
all of them — the root and every layer facade.

- **core** — `style`/`theme` (the styling defaults, the color-capability
  story and the `Themed` base),
  `text`/`lines`/`ansi` (measuring, the `Text` component in `lines`, rows,
  escape bytes), `events` (`Key`,
  `Paste`, `MouseEvent`, the `KeySource` protocol, `ScriptedKeys`), `block`
  (the frozen `Component` protocol, the interaction protocols `Clickable` /
  `Activable` / `Focusable` / `Hoverable` / `Container` with the pure
  `descend` walk, `Block`,
  `Document`), and
  `screen`/`viewport`/`painter` plus the selection kernel (`Selection`,
  `highlight`, `extract`) — the render core.
- **keys** — `decoder` (the pure `bytes -> events` state machine), `keymap`
  (the key-name to editing-action tables, all three of them) and
  `sources`/`console`
  (`ScriptedKeys` lives in `core.events`; `RawTerminalKeys` and the Windows
  plumbing live here).
- **widgets** — the generic library, each file one component family
  (`layout` the containers, `decor` the rules/notices/panels,
  `button`/`checkbox`/`link` the action primitives, `statusline`
  the two-column status row, `palette` the self-contained command palette);
  nothing here touches a screen, painter, key or app.
- **focus** (`focus.py`) — the widget-focus tier, the peer of `gesture.py`
  and `pointer.py`:
  `FocusRing` registers the components a host may focus, cycles them and
  flips their `focused` flag, routes the keys a focused target owns, and runs
  the click policy.  Focus is a *layer*, never a component's responsibility:
  components carry one flag and one dim-when-unfocused render rule
  (`docs/COMPONENTS.md` has the routing and click tables).

## Coordinates: everything is 0-based

Every cell index in the toolkit is **0-based**, with no exceptions. A
`MouseEvent.y`/`x` is the 0-based row/column of the terminal cell the
report refers to: the decoder subtracts 1 from the SGR report's 1-based
fields as it builds the event, so an event's own `x`/`y` go straight into
`TUI.hit_test(x, y)`. `Hit.row`/`Hit.col` are 0-based within the block's own
rows; the layout's `row_blocks` is a 0-based screen-row table; `Painter` writes
at 1-based escape rows (`cursor_position(index + 1, 1)`) only because the
terminal protocol is 1-based there; the panel and selection heights, the
row indices of `Markdown` rendering — all 0-based. The one thing that is
*not* a coordinate is the terminal protocol itself, and it is converted at
exactly one place per direction.

## The naming charter

These names are the binding contract of the API. Old names are gone — no
shims, no aliases.

| Concept | Name |
|---|---|
| Paint one frame | `TUI.paint()` / `Painter.paint(layout)` |
| Push OS stream bytes | `Screen.flush()` (the only true flush) |
| End-of-stream finalize | `KeyDecoder.finish()` |
| Current frame rows | `TUI.rows` / `Painter.rows` properties |
| Mouse coordinates | all cells 0-based; the decoder subtracts 1; `hit_test(x, y)` takes 0-based |
| Consume one event | `handle(event) -> bool` everywhere (`Input` / `Editor` / `TextBuffer` / `Palette` / the frame controllers); the wrap geometry comes from the component's last render, never from the event |
| Menu selection | `activate()` takes the item under the cursor into `chosen`; the host reads it once, `move()` / a re-filter clear it |
| Click interaction | `click(row, col) -> bool`; the component resolves its own cell arithmetic (title offsets, window scroll, the strip's segment widths included; `col` has no default) |
| Hover | `hover: bool` on the component -- the peer of `focused` -- plus the optional `hover_at(row, col) -> bool` where the component has rows: the `Pointer` tier writes both, `row < 0` means the pointer left, and the answer says whether the render changed |
| Inline payload | `Segment.link` (the url the terminal is told -- `Line.styled()` wraps that run in the OSC 8 pair -- and part of the segment's value) and `Segment.action` (the application's name for a click on the run; metadata, excluded from equality); the pure `action_at(line, col) -> (action, start, end) \| None` resolves a column against a row, and a component's hit testing reads its **last render's row table** through it |
| Container drill-down | `Container.child_at(row, col) -> (component, row, col) \| None` reads the container's **last render** geometry (the `TextBuffer.move_up` precedent); the pure `descend(component, row, col)` walks it to the deepest leaf, and the `Pointer` / `FocusRing.click` dispatch on that leaf, never the wrapper |
| Widget focus | `focused: bool` on the component (its one focus surface) + `FocusRing` (the tier: registration, cycling, routing, the click policy); an unfocused cursor renders `cursor_style.merge(theme.dim)` |
| Pointer tier | `Pointer(tui, *, ring=None, hover=True)`: the hover tracking and the stationary click beside `SelectionGesture`; hover needs `TUI(hover=True)` (DECSET 1003), and a mounted ring owns what a click means; a motion that names a button is a drag (the gesture's), the button-free one moves the hover |
| Tooltip | the leaf's `hint: str` is the protocol — the empty default means none, and `Button` / `Checkbox` / `Link` declare the slot — and `Tooltip(tui, pointer, *, theme=None)` is the overlay that reads it off the hovered leaf and paints one theme-`toast` band beside the pointer, clamped into the frame; registered at construction, `detach()` unregisters |
| List movement / activation | `move(delta)` / `activate()` / `select(index)`; a menu's step **wraps** (its ends meet; `wrap=False` clamps), a tab strip / tree / **table** / **list** step **clamps** -- a data view stops at its edge (D10) |
| Form widgets (D15) | `Radio(labels, *, index=0, ...)`: one `(•)` selection, `move`/`click`/`activate` all land the pick in `chosen` (a clamped step **is** the choice); `Slider(value=0, *, minimum=0, maximum=10, step=1, ...)`: the value snaps to the `step` grid on assignment, `click(row, col)` maps a track column onto it and `activate()` confirms it into `chosen` (a moved step clears one); `Collapsible(title, body, *, open=True, ...)`: only the title row folds -- `click`/`activate` flip `open` and mirror the new state into `chosen`; `ShortcutBar(items, *, separator=" · ")`: chrome only, one fitted row of `(key, label)` hints, no interaction, no `chosen` |
| Data views (D17) | `Diff(before, after, *, context=3, theme=None)`: the line-level unified view -- the LCS runs once, in the constructor, and the rows are `@@` headers, ` `/`-`/`+` lines and `…` elisions; **display-only**, no interaction protocol, and past `LCS_LIMIT` (20 000 line pairs) the whole text is replaced in two hunks; `List(items=(), *, window=8, theme=None, focused=False, prefix_jump=True)`: a cursor over a long sequence rendered as a window -- `move` **clamps** (a data view, D10), `home`/`end` jump to the edges, `click`/`activate` land the item in `chosen`, `handle` consumes `up`/`down`/`home`/`end` and a single printable as the case-insensitive prefix jump, and `▸` plus the `↑ N more` / `↓ N more` counter rows are the whole rendered shape |
| Data gestures (D17) | `Table.sort_by(col, *, reverse=False) -> bool`: the *host's* reorder by a column's rendered text -- stable, and the cursor, a pending `chosen` and the pointer's mark follow the record; `Table.set_widths(widths \| None)` pins per-column budgets (`None` restores the measured widths, the render clamps); `Table.header_line(width) -> Line \| None` is the grid's header row alone, byte-identical, for a host that pins it. `Tree.filter(query \| None) -> bool`: a case-insensitive substring prune that keeps every hit's ancestors open -- the `expanded` flags are read, never written; `Tree.jump(char) -> bool`: the wrapping type-ahead over the visible rows. A Markdown task item (`- [ ]` / `- [x]`) renders a `☐` / `☑` box as one action span, `"todo:<flat index>"` -- the task's ordinal across the document, stamped after the render cache -- so a click lands the payload in `chosen` and the host rewrites its own `text`; `Markdown.fences() -> list[tuple[str, str]]` lists the document's `(lang, code)` fences, parsed from `text` |
| Grapheme corners (D17) | `core/text.py` stays the one width truth: combining marks (a compact Mn/Me range table at the scanner's side, with `wcwidth` as the fallback), variation selectors (VS1..VS16 and the VS17..VS256 supplement), the zero-width joiner and regional-indicator pairs are the four continuation classes -- deliberately not a full UAX #29 segmentation; every other character follows `wcwidth` |
| Freeze a block | `seal()` (`Block`) |
| Controller mounting | constructed mounted -- `Scrollbar(tui)`, `Toasts(tui)`, `Tooltip(tui, pointer)`, `Stats(tui, pointer=…)`; `detach()` unmounts |
| Dev stats | `Stats(tui, *, pointer=None, theme=None)`: the top-right band stack of `painter.frames`, the frame rate over a window of at least a second off `tui.clock()` (the session's own sample rule -- no new timer), the events the host feeds through `handle(event)` (counting only; ``True`` is a repaint cue) with the last name, and the hovered leaf's class beside the pointer's cell; `pointer` is a plain attribute a host that rebuilds its pointer points at |
| Text and cursor | `.text` for content (mutable); `cursor -> (row, col)` on `Input` / `Editor`, a single-line shell reporting row 0; `click(row, col)` docks the caret -- `TextBuffer.place` maps the rendered cell back to the logical position (a wide cluster, a click past the row's text and the prompt's indent each resolve there) |
| Text selection | the buffer's own flat-offset `anchor` (`None` = no selection) + one `select_*` method per shift chord (`s-left`/`s-right`/`s-up`/`s-down`/`s-home`/`s-end`), each extending over the matching plain move's own column/wrap semantics; `c-a` is `select_all` (the line start is `home`); `selected_text` / `selection_range()` (a normalized `(start, stop)` pair, `None` when empty) / `clear_selection()`; every plain move drops the selection, every write point deletes it first -- `insert` replaces it in one history step |
| System messages | `tui.system(text)` |
| Viewport row range | `tui.viewport_rows(pane_id=None) -> (first, last) \| None` |
| Pump / clock seam | `tui.clock()` and `tui.tick(now)` (public; a test injects time through them) |
| Theme resolution | explicit `style=` > theme field > `DEFAULT_THEME`, resolved once at construction through the shared `Themed` base |
| Keymap tables | one home, `keys/keymap.py`: `DEFAULT_INPUT_KEYMAP` → `DEFAULT_EDITOR_KEYMAP` → `EDITOR_SUBMIT_KEYMAP` |
| Frame structure change | `Frame.revision` counts each mutation; the driver retiles on it |
| Command palette | `Palette(commands, *, theme=None, max_rows=8)`: the self-contained slash menu -- its own query `Input` row over a filtered `Autocomplete`, opening and closing on the host's `/` and `escape` |
| Query filtering | `set_query` on both `Autocomplete` and `Palette` |
| Reveal an address | `TUI.reveal(bid, row) -> bool` brings a document address on screen (centered when the edges allow, clamped at either end; unknown `bid` answers `False`), over `Viewport.scroll_to(offset)` -- the absolute jump, clamped like the bottom edge |
| Search | `Find(tui, *, theme=None)`: the search tier -- its own query `Input` row, `matches` as `(bid, row, start, end)` addresses, the wrapping `index`, the reveal of the current match, and the overlay marking every match (the current one under `hover`); no `chosen` (a continuing state) |
| Cursor pin | `Painter.set_cursor(row, col)`; a host anchors a field's cursor with `Input` / `Editor`'s `cursor_position(width)` |
| Bottom-pinned query | removed; `snapshot()` marks `,top` / `,bottom` from `block.pin` |
| Truncation family | `Line.fit` is the public face; `ellipsize_tail` stays public; the rest internal |
| Available child width locals | `inner` |
| Color capability | `ColorMode` (`"truecolor"`/`"256"`/`"16"`/`"none"`); `detect_color_mode(env)` probes it, `sgr_prefix(style, mode)` resolves one style, `lines.styled_with(line, mode)` renders one row — the cached `Style.prefix()` / `Line.styled()` stay capability-free |
| Focus reports | `focus_in` / `focus_out` — the decoder's names for `ESC[I` / `ESC[O`, opt-in through `focus_events=True` |
| Shift chords | `s-up` / `s-down` / `s-left` / `s-right` / `s-home` / `s-end` — the `ESC[1;2X` letters, hyphen chords like `c-` |
| Window title, cursor shape | `TUI.set_title(text)` (OSC 2, control bytes scrubbed) / `TUI.set_cursor_shape(shape)` (DECSCUSR: block/beam/underline/default) |
| Record / replay | `RecordingKeys(source, path)` appends every served event as one JSONL line -- `{"ms": …, "event": {"kind": "key" \| "paste" \| "mouse", …}}`, a mouse report's own class riding as `report`; an EOF is not recorded and the file ends there. `ReplayKeys(path, *, speed=1.0)` serves the events back, waiting the stamp deltas × `speed`, and `speed=0` waits never (the zero-sleep test contract) |
| Key event names | unchanged (hyphen for chords, underscore for words); the shift family is `s-*` |

## Style resolution, once at construction

Components resolve **explicit `style=` > theme field > `DEFAULT_THEME`**
exactly once, at construction, and store the resolved `Style` — or the
resolved `Theme` as `self._theme` when the choice is state-dependent (a
mutable `role`, `tone` or `level` attribute). The shared `Themed` base
(`core/theme.py`) carries that resolution and the `_pick` lookup every
component uses, so a `render(width)` call looks its styles up rather than
resolving them and a component renders identically no matter what it costs
to build. Constructors take `style=` / `theme=` exactly as their sketches
show — the resolution rule is the contract, not the signature.

## The screen model

Four layers stack into one frame each repaint:

```
Document ──▶ Viewport ──▶ Painter ──▶ Screen
 (blocks)     (window        (row diff    (bytes:
              + footer)      + erase)      alt/leave)
```

**`TerminalScreen`** wraps a real stream (`sys.stdout` by default). It is
*live* iff `stream.isatty()` **and** `enable_vt()` succeeds — on Windows a
VT probe runs because a stream that cannot render escapes is treated as
non-live. Liveness is decided once, at construction; size is cached and
only re-sampled by `refresh_size()`.

- `enter()` = `enter_alt_screen() + hide_cursor() + enable_mouse_tracking() +
  enable_bracketed_paste()` (+ `enable_focus_events()` when
  `focus_events=True`) — alt screen, hidden cursor, mouse reporting on
  (modes 1000 + 1002 + 1006 — what each buys is in the Selection section) and
  bracketed paste on (DECSET 2004 — what it buys is in the Keys section);
  `leave()` disables both pairs in the exact reverse order, then shows the
  cursor and leaves the alternate screen. `TerminalScreen(mouse=False)` /
  `TerminalScreen(paste=False)` leave their own pair out, for hosts that
  manage that mode themselves; `focus_events=True` adds DECSET 1004 — off by
  default, in last and out first.
- `color_mode` is the screen's declared color capability (the *Terminal
  capabilities* section below): `TerminalScreen` probes the environment for
  `"auto"`, `HeadlessScreen` defaults to a definite `"truecolor"`, and the
  painter reads the resolved mode off the screen.
- non-live: `enter`/`leave` are empty writes, so a piped run stays pure text.

**`HeadlessScreen`** is an in-memory recorder: `live` is always `True`, every
byte lands in `output`, and `width`/`height` are settable so a test can
simulate a resize. It interprets no escapes.

**VT degradation** is the only *liveness* downgrade: a live-able terminal
that fails the VT probe behaves exactly like a pipe (the non-live path); the
color mode is a separate, painter-level story (below).

A `Screen` implements `write`/`flush` — the only raw sink bytes in the
toolkit — plus `copy` (the best-effort OSC 52 clipboard write the Selection
section prices) and `refresh_size`. Every escape byte is still built in
`core.ansi`; a custom screen brings its own tracking settings, which is why
`TUI(mouse=False)` only affects the default `TerminalScreen`.

## Terminal capabilities

A handful of protocol capabilities ship on one rule: **the library declares,
the host decides, and no default changes what was already sent.** Every
sequence is built in `core.ansi` (the single byte source), and each switch
either defaults off or leaves the default path byte-for-byte as it was.

**Synchronized output (DECSET 2026).** `Painter` brackets every *non-empty*
frame: `begin_sync_update()` + the joined payload + `end_sync_update()`, in
the single write and single flush the painter has always made. A terminal
that knows the mode holds the row rewrites and swaps them in with one
repaint — no half-painted frame — and a terminal that does not ignores both
bytes, so the pair is harmless everywhere. On by default (`Painter(sync=...)`
/ `TUI(sync=False)` turn it off): the anti-tearing is the point, and the
zero-byte contract is untouched — an unchanged frame composes an empty
payload and no write happens at all, switch or no switch.

**Focus reporting (DECSET 1004).** `TerminalScreen` / `HeadlessScreen` take
`focus_events=False` — off by default, because the reports are **state the
host owns**: the `Pointer` tier still watches mouse reports only, and
scrubbing a hover (or pausing an animation) on losing focus is a host's own
choice, not a toolkit policy. When on, `enable_focus_events()` rides the
enter bracket after the paste pair and `disable_focus_events()` leads the
leave bracket (the strict reverse), so no reporting mode is left on. The
decoder names the reports `focus_in` (`CSI I`) and `focus_out` (`CSI O`).

**Color mode.** `ColorMode` is `"truecolor" | "256" | "16" | "none"`. The
screen declares one: `TerminalScreen(color_mode="auto")` resolves
`detect_color_mode()` once at construction — `NO_COLOR` set to a non-empty
value (the no-color.org convention: an empty variable is no preference) or
`TERM=dumb` → `"none"`, `COLORTERM` `truecolor`/`24bit` → `"truecolor"`,
`TERM` naming `256color` → `"256"`, anything else → `"truecolor"` (the
historical answer, so a terminal nothing is known about keeps the palette
the styles are authored in). `HeadlessScreen` defaults to a definite
`"truecolor"` rather than probing, so a test's bytes never depend on the
machine; `TUI(color_mode=...)` forwards only when set. The painter reads the
mode and picks the byte path:

- `"truecolor"` → `Line.styled()`, the row's own cache — byte-for-byte what
  every earlier release emitted;
- any other mode → `lines.styled_with(line, mode)`, which renders fresh
  through `sgr_prefix(style, mode)`: a hex or tuple color is quantized by
  `quantize` (the xterm 256 palette's 6x6x6 cube and 24-step gray ramp for
  `"256"`; the standard xterm 16-color reference table for `"16"`), a named
  color keeps its base code, and `"none"` drops fg/bg while every attribute
  (bold/dim/italic/underline/reverse/strike) survives.

The caches stay **capability-free**: a `Style.prefix()` or `Line.styled()`
memoized for one terminal is never served to another, because downgraded
bytes are computed outside them. Detection is environment-only by design —
no DA/DSR/OSC 11 query-response dance (see *Deliberately out of scope*).

**Window title (OSC 2).** `set_window_title(text)` scrubs every C0 control
character from `text` first — a raw ESC or BEL inside a title would inject
escape bytes or cut the string short at the bell — and `TUI.set_title(text)`
writes it. A host-owned gesture: the driver never titles a window by itself
(the gallery titles one per page).

**Cursor shape (DECSCUSR).** `cursor_shape(shape)` maps `block`, `beam`,
`underline` and `default` to the steady parameter (`CSI 2 q`, `6 q`, `4 q`,
`0 q`); an unknown shape raises `KeyError` rather than guessing.
`TUI.set_cursor_shape(shape)` writes it. The library only *declares* which
shape a component wants — `Input` and `Editor` carry `cursor_shape = "beam"`
— and the host reads the focused leaf (`getattr(leaf, "cursor_shape",
"block")`) and calls the method.

The two window gestures write through `screen.write` **without a liveness
gate** (unlike the session bracket and `copy`): a headless screen or a test
double records them, so they are assertable without a terminal, and a host
that sets a title on a pipe is taken at its word. Nothing is ever sent on the
library's own behalf.

**Inline hyperlinks (OSC 8).** No switch, no capability probe: a
`Segment.link` is bytes about a *run the user can see*, so the run's own
rendering carries them — `Line.styled()` wraps that segment's text in
`hyperlink_open(url)` … `hyperlink_close()` (ST-terminated, the url's C0
bytes scrubbed, the pair closed inside the segment so no hyperlink crosses a
boundary), and a terminal that does not know OSC 8 ignores both halves. The
bytes come from `core.ansi` like every other escape the toolkit emits, and a
row with no link renders byte-for-byte as it always did. `Markdown`'s
`[label](url)` rule hangs the url on the label as both `link` (the
terminal's door — a native cmd+click opens it) and `action` (the
application's door: a click lands the url in `Markdown.chosen`, which the
host reads once).

**Shift chords (`CSI 1;2`).** The decoder names `ESC [ 1;2 X` — X in
`A/B/C/D/H/F` — `s-up` / `s-down` / `s-right` / `s-left` / `s-home` /
`s-end`: the toolkit's chord spelling (the `c-` convention, hyphenated).
Every other parameter string, the bare forms included, keeps its historical
answer — the letter family's base key.

## Documents and blocks

The unit of content is a **`Block`**: a stable `id`, a **`Component`**
(`render(width) -> list[Line]`), a `pin` (`None`/`"top"`/`"bottom"`), and a
two-state lifecycle. `Document` is an ordered, id-addressable collection —
`add` (auto id `b0`, `b1`, …; duplicates raise), `get`, `remove`,
`blocks()`.

The lifecycle is exactly `OPEN` or `SEALED` — there is deliberately **no
COMMITTED state**: a full-screen rewrite has no terminal history to append
into, so a block is either still being written (`OPEN`) or frozen
(`SEALED`). `block.seal()` freezes it (`OPEN → SEALED`; sealing twice raises
`ValueError`). Sealed
blocks are rendered once per width and cached, so long finished transcripts
are cheap; open blocks (streaming text, a live input) re-render every
layout.

## The viewport

`Viewport.layout(width, height)` renders the document and returns a
`ScreenLayout`: `rows` (exactly `height`) and `viewport_rows` (the scrolling
region alone).

- **Fixed regions.** Blocks carrying `pin="top"` render, in document order,
  into a top region above the scrolling window; `pin="bottom"` blocks into a
  footer below it; unpinned blocks fill the scrolling body. The window height
  is the screen height minus the fixed regions' rows, so neither fixed
  region ever scrolls away. When both overflow, the footer is kept first,
  then the top region, and the window may be empty.
- **Scroll state.** `offset` clamps into `[0, max(0, total body rows -
  window height)]`. A fresh viewport **sticks to the
  bottom** (shows the tail); scrolling up detaches it, and it re-attaches at
  the bottom edge or via `scroll_to_bottom()`. An absolute jump lands
  through `Viewport.scroll_to(offset)` — the same clamp, and a landing on
  the bottom edge re-attaches exactly as a scroll down that reached it —
  and `TUI.reveal(bid, row)` scrolls the focused pane so a document address
  is on screen, centered when the document's edges allow.
- **more-below marker.** When scrolled away with content still below the
  window, the viewport's last row becomes the module marker
  `mocode_tui.core.viewport.MORE_BELOW` (`─ more below ─`, muted) — a
  public constant, re-exported from `mocode_tui.core` so a host never
  re-types the literal. It keeps the row ownership of the body row it
  covers, so a click there still resolves to that block.
- Short documents blank-pad the viewport below the content so the footer
  stays put; the sealed-row cache is invalidated whenever the width changes.

Every `layout` also rebuilds the read-only ownership table
`row_blocks` — screen row to `(block id, row within that block)`, or `None`
for a row no block owns — the viewport's half of routing. The frame builds
the screen-wide one over it (next section), which is what the mouse hit test
resolves through.

## The frame model

Everything that claims screen space outside the document flow partitions one
screen through one mechanism (`core/frame.py`). The constitution below is the
design step itself: deciding *which kind* of claim a feature makes is the
whole decision, and blurring the three is how patches are born.

**The three space claims.**

1. **Pane** — an exclusive rectangle of the frame, owning its own
   `Viewport`/`Document`: independent scroll, independent sealed cache,
   independent hit domain. A transcript | preview split is two panes; the
   separator between them is inter-pane chrome. Many panes partition the
   frame.
2. **Chrome** — a small band *inside* a pane's rectangle (edge columns or
   rows), acquired by budget negotiation: the chrome declares how many edge
   cells it wants, the pane lays its viewport out in what remains and the
   content re-wraps at the reduced width — content is never hidden under
   chrome. Chrome renders from pane view state (`offset`/`total_rows`) and
   may route input. A scrollbar (one column), a line-number rail (three), a
   hit-tick rail; several chromes stack, their budgets add.
3. **Overlay** — claims nothing, painted last over the composed frame.
   Toasts, the selection highlight, a jump-to-bottom chip: pure
   `frame -> frame` transforms, plus the lifecycle and input that live in
   controller objects, never in the kernel.

The decision rule — **is the feature a rectangle the document lives in, a
band inside one, or a paint over all of them?** A new pane means new scroll
state and a new hit domain; a band means a budget and a pure
`paint(layout, length)`; an overlay means a `paint(frame) -> layout` and no
budget at all. Mechanisms live in the kernel, policy one level up
(`chrome.py`, `gesture.py`, the driver): the kernel owns where panes sit,
which cells each claims, which edge cells its chrome reserves, and the order
overlays paint in — it gains no timers, no event policy, and no opinion about
what a scrollbar looks like.

**Panes and splits.** A `Rect` is a frozen `(x, y, width, height)` value, and
`Split(orientation, ratios, min_size)` is the division algebra over it:
`Split.rects(rect)` tiles the rectangle into one child per ratio (floors,
then the last child takes the remainder, with a `min_size` floor), which is
why a tiling is structure, not geometry — the same recorded split re-divides
whenever the frame retiles. `Pane.division` / `Pane.children` hold that
record once the pane is divided.
`tui.split("vertical"|"horizontal", *, ratios=(1, 1),
min_size=1, separator=True)` (one code path with `Pane.split`) divides the
focused pane and returns the children in paint order: the first child keeps
the split pane's id, document, viewport and chrome, every child after it
opens over a fresh empty document, and focus stays where it was. The
separator cell is the last cell of the pane before it, budgeted as that
pane's chrome — never a gap — and the driver themes it (the theme's `accent`
beside the focused pane, its `border` otherwise, the tmux convention);
`separator=False` leaves the panes abutting with no cell spent.
`Pane.close()` is the division's symmetric, the un-split: a leaf leaves its
parent's tiling, with siblings left the parent re-divides its rectangle over
the survivors (the ratios trimmed to the surviving count, in order), and with
one survivor left the parent collapses back to a leaf — its own id and
rectangle kept, the survivor's window taken — so a closed split is gone from
the composition and the single-pane pass-through composes to the pane's own
layout again.

**The compositor.** `Frame.compose(width, height)` runs, per region, chrome
budget negotiation first, then the pane's viewport laid out in the inner
rectangle, then the granted bands spliced back over it; the band's rows land
last of the regions. The painted rows are spliced into the frame rows at each
pane's columns, and the ownership table records, per screen row, which pane
claims which columns and the document address inside it — a pane claims its
whole rectangle, its chrome band rows included. `tui.hit_test` routes through
that table, so a split frame resolves exactly as its panes compose. A lone
pane whose rectangle is the whole frame and carries no budgeted chrome
composes to its pane's own layout — the single-pane row stream is the
viewport's own by pass-through, not by re-derivation.

**Budget negotiation.** Each chrome asks for `size` cells across its edge;
the pane's budgets add per edge, opposite edges both subtract, and a budget
that would leave the viewport under one cell in either axis is clipped to
what remains — first come, first served (the divider first, then
registration order), so chrome never eats a pane whole. Chromes on one edge
stack outward from it: a divider is outermost by definition — it divides the
gap between two panes, so it may not sit inside another band, whatever was
registered before the split that added it — and the rest stack inward in
registration order. `size: 0` is a legal no-op seam, the shape a custom
renderer grows from.

**The overlay registry.** `Frame.add_overlay` appends, `remove_overlay`
unregisters by identity, and a missing entry raises `ValueError` on both
unregisters (`Pane.remove_chrome` is the chrome half of the same symmetry) —
an unregister is a claim about what the registry carries, and a silent miss
would hide a controller detaching the wrong band. `apply_overlays` runs the
registry in registration order over the composed layout; the driver's
selection highlight is overlay #1, and the shipped controllers (`Toasts`,
`Tooltip`, `Stats`) register themselves at construction. A controller keeps
its own `detach()` idempotent by testing
membership first. The registry lives on the frame for the frame's whole
life: a retile rewrites pane rectangles in place rather than rebuilding the
frame, so nothing carries across.

**Retile, in place.** `Frame.retile(rect, band=...)` re-divides the recorded
tree onto a new frame rectangle — each top-level pane takes the rectangle and
re-divides it down its `division` — and panes are objects rather than values
rebuilt per frame, so a pane keeps its id, its viewport, its chrome registry
and its focus target across the change: the owner retiles and carries
nothing. That is why the split landed this way rather than the obvious
rebuild-and-carry: a rebuilt pane would have to re-register every chrome and
overlay onto it, re-seed each viewport's scroll state, and re-point every
host's `Pane` references, and every one of those carries is a place a
resize could drop one — the in-place rewrite makes a resize a no-op for
everything but the rectangles. The frame counts its structure changes
(`Frame.revision`: a split, a close, a chrome or overlay registration, the
band), and the driver records the last tiling with the revision it ran at,
so a same-size paint retiles only when the tree actually changed or the
computed tiling moved (the band's height follows its content).

**Focus and the wheel.** `frame.focused_pane` is the pane keys and the scroll
facades route to (the first, until `focus`/`pane.focus()` moves it; the band
never holds focus). The mouse half is a replaceable policy:
`tui.focus_policy` (default `_press_focuses_a_pane`) runs on every event
`read_key` hands back and focuses the pane a button press resolves to
through the ownership table — never a wheel notch, which scrolls without
stealing focus. A host swaps the callable for its own
`(tui, event) -> Pane | None`. The wheel is nobody's chrome: `read_key`
intercepts `scroll_keys` before the host loop runs and routes a wheel report
to the pane *under the pointer* (chrome columns and all), falling back to the
focused pane when the report names none; the page keys carry no pointer and
always scroll the focused pane. On a one-pane frame every one of these is
today's behavior by identity.

**The band.** One optional `Pane` the frame reserves beneath the pane area
(`tui.add_band(viewport)` / `remove_band()`): its own viewport, its rows
painted below every pane across the full frame width, its cells in the
ownership table — a footer block resolves through `hit_test` exactly as a
pane's rows do — but it takes neither focus nor splits, and a wheel over it
scrolls the focused pane. This is where a host-pinned footer lives: the box
keeps its own document and viewport and
parks that viewport in the band instead of pinning its blocks into the
transcript, so a split never cuts the footer in half and the single-pane
render matches a pinned footer row for row.

**Selection scope (the frame group's D7).** Selection stays single-document:
the gesture's addresses, the highlight and the extract walk all key on one
document's block ids, and a drag anchors in — and never leaves — the pane
the press hit, which the gesture holds by id and re-resolves through the
frame (an in-place retile rides along, a collapse keeps the survivor's id, a
pane that leaves the tiling ends the drag). The driver stores that pane
beside the range (`set_selection(sel, pane=...)`, `tui.selection_pane`), so
the overlay paints the document the addresses actually name — a split's
second child holds a `b0` exactly as the first does — and a host's `on_end`
reads the same pane's document and layout width. Cross-pane ranges are a
documented future extension — the addresses are document-local already, so
the door is open by construction.

## The painter

`Painter` is a **pure differ**: it owns no document and no scroll state.
One frame arrives as the `ScreenLayout` the caller laid out, and
`Painter.paint(layout)` writes only what changed.

- **(Re)size → full repaint.** A `\x1b[2J` clear-screen, then every row.
- **Steady state → per-row diff.** Each row is compared to the previous
  frame; only rows that changed are written, as `\x1b[{row};1H` + `\x1b[K`
  (erase line) + the styled row. **An unchanged frame writes zero bytes.**
- **Non-live → silent.** The painter still computes the logical rows (so the
  `.rows` property is queryable on a piped run) but writes nothing.
- **One write, one flush — bracketed; rows follow the screen's mode.** Every
  non-empty frame leaves as a single write wrapped in the
  synchronized-update pair (DECSET 2026, on by default; see *Terminal
  capabilities*), and each row renders for the capability the screen
  declares: the cached `Line.styled()` on the truecolor path, a fresh
  `styled_with` in the downgraded modes.
- **IME anchor.** `set_cursor(row, col)` pins the terminal cursor (the IME
  candidate window follows the input box, not the streaming text) at 0-based
  coordinates; the anchor is the frame epilogue — appended after a frame
  that wrote anything, written alone by a frame that only moved it. A
  non-live screen never receives it.

`Painter` has no throttle of its own — it paints exactly when told to. The
driver's `TUI.throttle` is the only throttle: it decides when a frame is
due, and `TUI.paint()` paints one immediately, bypassing it. `.rows` always
returns exactly `screen.height` rows (empty before the first paint), and the
ownership table a click resolves through stays on the viewport that laid the
frame out, so no caller ever reaches through a private seam.

## The driver

`TUI` owns a screen, a document, a viewport over it, a painter, and an
optional key source — all readable as public attributes (`tui.screen`,
`tui.document`, `tui.viewport`, `tui.painter`, `tui.keys`,
`tui.scroll_keys`, `tui.throttle`, `tui.interactive`).

- **Facade.** `add`/`get`/`remove`/`system` mirror the document and
  invalidate the frame on every mutation. `system(text)` adds a muted system
  block — external output becomes document content, never a raw write
  behind the painter's back.
- **Frames.** `paint()` paints one frame now, bypassing the throttle;
  `invalidate()` marks dirty and wakes the pump; `rows` hands back the
  current target screen; `every(seconds, fn)` runs a periodic callback and
  returns a cancellable `EveryHandle`.
- **`run(body)` lifecycle.** It attaches a raw key source (when
  interactive), starts the pump, and awaits `body(self)` — the library never
  builds its own event loop, so the caller owns `asyncio.run`.
  `enter`/`leave` bracket the session on a live screen, **including on
  exceptions and `stop()`**. A `KeyboardInterrupt` from the body is treated
  as `stop()`. Teardown always flushes a final frame before leaving.
- **Pump / clock.** The pump repaints at most one frame per throttle window
  when dirty, and runs due `every` callbacks. `clock()` is the
  `time.monotonic()` seam the pump reads (a test replaces the method to
  drive time) and `tick(now)` advances the pump one step — due callbacks,
  then one frame — returning the delay until the next wake; the library
  itself never sleeps.
- **Theme.** `TUI(theme=...)` (read back as `tui.theme`) is the theme the
  driver's own chrome reads — the split's separator; widgets take their own
  `theme=` and are never themed from here.
- **Protocol surface.** `TUI(sync=True)` hands the painter the
  synchronized-update bracket (DECSET 2026); `TUI(focus_events=True)` opens
  DECSET 1004 on the default screen; `TUI(color_mode=...)` overrides the
  default screen's `"auto"` environment probe; and `set_title(text)` /
  `set_cursor_shape(shape)` are the two host-owned window gestures (OSC 2 /
  DECSCUSR). Each contract is in *Terminal capabilities*.

In call order (not a runnable script — every call is on the driver, and the
`read_key` await below happens inside an async body):

```python
tui.add(comp, id="x", pin=None)        # append a block; pin: "top"/"bottom"/None
tui.get("x"); tui.remove("x")         # address by id; invalidate
tui.system("system line")             # muted system block (no raw writes)
tui.invalidate(); tui.paint()         # mark dirty / paint one frame now
tui.rows                              # the current frame: exactly screen.height rows
tui.every(0.1, fn)                    # periodic callback, cancellable handle
tui.clock(); tui.tick(now)            # the time seam, and one pump step at `now`
tui.scroll_up(2); tui.scroll_to_bottom()
tui.viewport_rows()                   # the focused pane's window as (first, last), or None
tui.split("vertical", ratios=(2, 1))  # split the focused pane; returns the children
tui.add_band(viewport)                # park a footer viewport in the frame's bottom band
tui.set_title("my app")               # OSC 2 window title (control bytes scrubbed)
tui.set_cursor_shape("beam")          # DECSCUSR: block/beam/underline/default
tui.stop()                            # ask run() to finish
```

The split, focus and band surface is the frame model's driver face and is
specified in the frame section above: `tui.split` (one code path with
`Pane.split`), the replaceable `tui.focus_policy`, `tui.focus_at(x, y)`, the
`tui.frame` property (the seam the assembly tier reads), and
`tui.viewport_rows(pane_id=None)`.

### Mouse: the wheel, clicks, and the hit test

SGR mouse reports (`\x1b[<b;x;yM/m`, mode 1006) decode into `MouseEvent`, a
frozen `Key` subclass carrying the report's `button`, its **0-based** `x`/`y`
coordinates and its `kind` — `"press"`, `"release"` or `"motion"`. The
**vertical wheel** routes as `wheel_up`/`wheel_down` (bound in `scroll_keys`,
so it scrolls; a wheel report is discrete and stays `kind="press"`); **button
presses** decode as `left`/`middle`/`right` and pass through `read_key()`
untouched — the driver never dispatches a click itself. Since the selection
wave, **releases and motion reports decode too** and flow to the host with
their kind attached: a motion report's low bits name the held button (0/1/2)
or are **3** when no button is held — the button-free motion, which the
decoder normalizes to `MouseEvent("none", button=0)`. Anything matching
*every* mouse event must now tolerate that flow. A button-free motion takes
both wire paths the same way: on VT terminals it needs DECSET 1003
(`TUI(hover=True)`), and on the Windows console-record path the same switch
opens the synthesized report (`keys.console`). Inside the async body (the
mouse snippet's `await` needs a running loop):

```python
event = await tui.read_key()
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)     # 0-based coords go straight in
    if hit is not None:
        hit.block.component.click(hit.row, hit.col)  # e.g. a Select: block-internal cell
```

`TUI.hit_test(x, y)` resolves a report to a `Hit` — the `Block` under the
cell and 0-based `row`/`col` within its own rows — through the **frame's**
ownership table, which every composition rebuilds in painting order: which
pane claims the cell, and the document address inside that pane, so a split
frame resolves exactly as its panes compose (a chrome band row resolves to
the pane with no address, and the band joins the table too). A row no block
owns (the blank fill below short content), a cell outside the last layout,
and a block removed since that layout all resolve to `None`. What stays
dropped in the decoder: the horizontal wheel, unknown button codes and
malformed reports — that branch is the seam future mouse kinds land in.
`TUI.hit_component(x, y)` is the same resolution continued through every
`Container.child_at` (`descend`) to the deepest leaf — the cell a host
dispatches a click to.

### Hover, and the pointer

**1002 vs 1003: the mode decides what motion a host ever sees.**
`enable_mouse_tracking()` writes 1000 + a motion mode + SGR 1006, and the
motion mode is the fork. **1002** (button-event tracking, the default)
reports motion only while a button is held — exactly the raw material
`SelectionGesture` needs, and why drag selection was built without any hover
story. **1003** (any-event tracking) reports button-free motion too, which is
what hover needs: a pointer that only moves is never heard under 1002. The
mode is therefore opt-in: `TUI(hover=True)` (or `TerminalScreen(hover=True)` /
`HeadlessScreen(hover=True)` for a custom screen) swaps 1003 in, the default
stays 1000+1002+1006, and a host that never builds a `Pointer` pays nothing.
`leave()` disables 1003 unconditionally — a terminal left in 1003 floods the
shell with motion reports after the session ends.

**Why hover can afford 1003.** The event storm is the price, and where it
lands is what makes it affordable: every report costs one `hit_test` against
the frame's ownership table, and the pointer calls `invalidate()` only when
the hover target actually changes — the entered, left or moved-to-another-row
case. A mouse resting on a cell emits nothing: no change, no bytes, the
painter's zero-byte rule intact.

**The pointer tier.** `Pointer(tui, *, ring=None, hover=True)` is the observe
half of the mouse pair: the host routes every report through it beside the
gesture, and its answer is a repaint cue, never a dispatch claim —
`if pointer.handle(event): tui.invalidate()`. Three contracts hold it
together (`docs/COMPONENTS.md` has the wiring):

- *Hover needs the mode.* The pointer cannot ask the terminal for 1003
  itself: under 1002 it never receives a button-free motion report and
  nothing happens. `Pointer(..., hover=False)` builds the click-only pointer
  for a host that wants stationary clicks while keeping the smaller mode.
- *The gesture keeps its reports.* A press is only remembered (the pointer's
  answer stays `False`); a motion that is a drag — one whose `name` is a
  button name (`left`/`middle`/`right`; under 1002 every motion names the
  held button, and 1003's button-free move is normalized to
  `name="none"`/`button=0`) or whose `button` is nonzero — drops the
  remembered press and touches no hover, so a drag's reports are the
  gesture's alone; only the release of a press that landed on its own cell —
  a **stationary click** — dispatches. The name is what makes the
  distinction exact where the raw button code cannot: a held left button and
  a button-free move are both low bits 0. Both tiers see the same event
  stream without either starving the other.
- *The click descends, then dispatches like the ring.* The cell resolves
  through `tui.hit_test` and walks `descend` to the deepest leaf. With a
  mounted `FocusRing` the leaf runs the ring's own click policy (dispatch,
  focus, second click activates); without a ring the pointer dispatches the
  deepest `Clickable` leaf itself — a mouse-only page needs no ring.
  `Pointer.clear()` drops the hover and the pending click after a pane switch
  or a resize: best-effort by design, because the pointer is not handed
  window events itself.

**`descend` reads the last render's geometry.** A container answers
`child_at(row, col)` from the rectangles its last `render(width)` recorded —
the same precedent `TextBuffer.move_up` sets for the wrap geometry a key
follows — so a container that has never rendered declines every cell and no
hit test ever invents a layout. Containers route coordinates and nothing
else: they do not proxy `handle` / `move` / `activate` / `focused`, so
keyboard focus registers the leaf while the click still descends through the
wrapper. A malformed container that answers with itself cannot loop: the walk
is depth-guarded.

**Hover state is a component flag, not a controller call.** `hover: bool`
(the `Hoverable` protocol) is the exact peer of `focused: bool`: a component
renders by it and never learns a manager exists. A component with rows may
add `hover_at(row, col) -> bool` so the pointer can mark the row under it
(the menus, the tree, the table and the tab strip do; `row < 0` clears the
mark), answering whether the render changed — which is how the pointer keeps
its no-change-no-bytes rule at row granularity too.

### Scroll facades + scroll-key interception

`read_key()` absorbs every event in the `scroll_keys` table —
`page_up`/`page_down` and the wheel by default — scrolling by the table's
signed row count (negative up: the page keys move one row, the wheel three
per notch) and continuing the read, so callers never see them. The table is
a public per-instance dictionary: rebind a count
(`tui.scroll_keys["wheel_down"] = 1`) or `del` an entry to hand the event
back to the caller. `TUI(mouse=False)` leaves mouse tracking off on the
default screen.

The viewport a scroll-key event moves is the one D5 names (the frame section):
a wheel report scrolls the pane **under the pointer** — resolved through the
frame's ownership table, chrome columns and all — and falls back to the
focused pane when the report names no pane or the pointer is over the band
(the band holds no scroll state of its own); a page key carries no pointer
and always scrolls the focused pane. On a one-pane frame every one of those
is the same viewport either way.

Escape hatch: `await tui.keys.read()` reads the raw source directly,
bypassing both the scroll-key interception and the non-live guard.

## Selection

Mouse text selection over the block document, with copy on selection end.
The feature exists because enabling mouse reporting takes the terminal's
native selection away from that moment on — once the application asks for
reports, the terminal stops doing its own drag-select and the application
owes the user a replacement. What follows is the reasoning behind that
decision (D1–D8) and the tiers it landed in (D3).

**D1 — Selection lives in document space, not screen space.** A selection is
a range of `(block_id, row_in_block, col)` addresses
(`core.selection.SelectionAnchor`), built with
`Selection.between(anchor, head)`. Screen rows shift when scrolling; document
addresses do not. This single decision buys the feature's headline
behaviors: select → scroll → the highlight is still where the text is, and
copy extracts the **full** selected range even for parts scrolled out of view
(something a real terminal cannot do — we own the document model). It also
makes drag-to-edge auto-scroll pure arithmetic (D4). The rejected
alternative, screen-space `(row, col)` ranges, breaks on every scroll and
forces selection tracking into the scroll path.

**D2 — Selection is an overlay, not content.** Components stay pure
`render(width) -> list[Line]` and know nothing about selection. The highlight
is a pure function applied to the **laid-out** frame at the composition root:
the driver wraps it as overlay #1 of the frame's registry —
`highlight(frame.pane_layout(pane.id), selection)` spliced back
through `Frame.with_pane_rows`, the step `TUI._paint_at` runs between
composition and paint. The consequences that matter:

- the sealed-row cache stays pristine (the overlay runs after the cache
  read, so selection changes never thrash it — `highlight` builds new `Line`
  values over the layout's rows and touches nothing the viewport, the blocks
  or the components hold, and returns the layout unchanged for
  `selection=None` with no allocation at all);
- the painter's per-row diff gives incremental repaint for free — only the
  rows the overlay touched are rewritten;
- the painted frame (`tui.rows`) carries the highlight, so a headless test
  drives a real gesture and asserts the marked rows without a terminal;
- the same overlay shape is the future home of search highlighting and URL
  hot-zones (one gate for a family of features).

**D3 — Mechanism in the kernel, policy in an assembly controller.** The
three-tier shape the toolkit already uses (cf. Viewport / TUI / Scrollbar):

| Tier | Home | Contents | Character |
|---|---|---|---|
| mechanism | `core/selection.py`, `core/ansi.py`, `core/screen.py` | the `Selection` model, the `highlight` overlay, `extract`, the OSC 52 primitive `Screen.copy` | pure, timeless, side-effect-free |
| driver facade | `app.py` | `tui.selection` (read) + `tui.set_selection(...)` (write + invalidate) | minimal imperative surface |
| policy | `gesture.py` (top level) | `SelectionGesture` (press/drag/release/auto-scroll/word-then-line click) + `copy_on_select`, the default action | every behavior swappable |

The kernel gets **no timers, no event policy, no clipboard opinion**.
Copy-on-release is a default *function argument* (`on_end=copy_on_select`),
never a kernel `if`. `TUI` never attaches the gesture itself — a host opts in
with one explicit line, the constructed-mounted-controller philosophy: the
driver decides nothing about interaction policy.

**The modes, and what each buys.** `enable_mouse_tracking()` turns on three
modes with one call (`\x1b[?1000h\x1b[?1002h\x1b[?1006h`; `leave` disables
them in reverse), and `TerminalScreen(mouse=False)` leaves the pair out for
hosts that manage tracking themselves:

| Mode | Buys |
|---|---|
| 1000 | button-press and wheel reports — what viewport scrolling and click dispatch need |
| 1002 | motion reports while the pointer moves with a button held — the raw material of a drag; it cost one mode and is why the gesture exists as policy |
| 1003 | all motion, button-free included (low bits 3; the decoder normalizes it to `MouseEvent("none", button=0)`) — what hover needs, so it is the opt-in swap (`TUI(hover=True)`) for a host that builds a `Pointer`; the default stays 1002 (the Hover, and the pointer section) |
| 1006 | the SGR encoding (`CSI < b;x;y M/m`) the decoder parses: press vs release rides the final byte (`M` / `m`) rather than an off-by-32 button code, and the coordinates are not capped at 223 |

On the Windows console path the same competition is settled one layer down:
`keys.console.windows_input_mode()` clears `ENABLE_QUICK_EDIT_MODE` (setting
`ENABLE_EXTENDED_FLAGS` alongside, which Windows requires for the change to
stick) so the console host stops intercepting the mouse for its own text
selection; `close()` restores the saved mode wholesale.

**D4 — A stationary pointer emits no events; auto-scroll is time-driven.**
Mode 1002 reports motion only on cell changes, so a pointer held still at the
bottom edge sends nothing — a drag there cannot be advanced by events. Edge
auto-scroll therefore runs on the pump's existing `every(seconds, fn)`
handles (the working-spinner pattern), not on any new mechanism. Each tick
advances the selection head **in document space** (`head_row += n`), never by
re-`hit_test`ing — a hit test would read the *previous* frame's ownership
table and turn the tick into a latency feedback loop. The identity underneath
is one line: scrolling `n` rows shifts the content under a fixed screen row by
exactly `n` document rows, so the ticker moves the head by the offset the
viewport actually travelled (which also folds the document-end clamp and the
block-boundary crossing into one walk). The ticker stands down on edge-exit,
release, detach, a reflow that cleared the overlay underneath it, and the
document end. Time enters through `tui.clock()`, the pump's public seam: the
ticker's schedule and the click-count window both read it, so the event
model stays timeless and a test drives time without sleeping.

**D5 — The edge zone is the scrolling region's border, not the screen's.**
The pinned footer (the band) rows are not scrollable content; dragging
into them must not scroll. The gesture asks the driver —
`tui.viewport_rows()` reports the focused pane's window as `(first, last)`
frame rows, the placement the last composition left behind with chrome
subtracted and the band and any fixed region excluded — which is what keeps
those rows out of the edge zone. A press that lands on an edge row arms
the ticker too, not only a motion: the pointer can reach the edge *before*
the button goes down, and a stationary press there emits no motion at all.

**D6 — Copy is best-effort OSC 52; the hook is the contract.**
`Screen.copy(text) -> bool` emits `\x1b]52;c;<base64>\a` (`core.ansi.copy_clipboard`)
on live screens only; a non-live screen writes nothing and answers `False`,
while the headless screen records the bytes and answers `True` — that is how
a test proves a copy happened. Terminal support for application clipboard
writes varies and some terminals refuse it by policy, so even a `True` is a
courtesy: the real contract is the gesture's `on_end` hook. `copy_on_select`
is the shipped default — two lines, `extract` + `Screen.copy` — and a host
with stronger needs replaces it (see the cookbook in
`docs/COMPONENTS.md`).

**D7 — Two kinds of selection, one vocabulary, two mechanisms.**
Document-level selection (this section) is a viewport overlay over read-only
content. Intra-component selection — selecting text inside `Input`/`Editor` —
is `TextBuffer` state rendered by the component itself. They share the
`SELECTION` style constant (`reverse`) and the coordinate vocabulary,
never the mechanism. Writing the boundary down now is what prevents the
future "shove editor selection into the overlay" patch.

**D8 — Documented v1 semantics for the hard edges.**
- **Reflow clears.** A width change (`_paint_at` notices `screen.width !=
  _layout_width`) sets the selection to `None`: column addresses no longer
  point at the same glyphs. Char-offset anchoring is rejected because
  markdown renders non-1:1 with its source.
- **Streaming addresses cells, not content identity.** A selection over an
  `OPEN` block lands on whatever occupies those addresses when the overlay
  runs — terminal-grid semantics; `extract` reads the same cells.
- **Vanished addresses resolve to nothing.** An address whose block was
  removed yields nothing at overlay/extract time (the `hit_test` precedent:
  defensive `None`/skip, never an error), and a range missing an endpoint
  never widens to swallow the document.
- **One range.** The model may hold spans internally; the v1 API exposes the
  single `anchor…head` range. An empty press-release at one cell clears the
  selection and does **not** touch the clipboard.

**The click vocabulary: click, word, line.** Repeated presses at one cell are
counted in the controller — the last press's cell, its `tui.clock()` reading
and the run length — inside one `double_click_seconds` window, so the event
model stays timeless and a test drives the count without sleeping. The second
press selects the maximal non-whitespace run around the cell (the word), the
third the row's whole visible line (the hit block's own row, measured at the
pane's laid-out width, never across blocks), and the fourth starts the count
over. Both completed spans fire `on_end` once, at their own press, and the
release that follows finalizes nothing; a cell with no run to select (word) or
no cells at all (line) degrades to a plain press, which is what a double-click
between words should do. `double_click_seconds=0.0` retires the count — a live
clock never reads inside a zero window — and both spans go through the same
display-column measure the kernel cuts by, so a CJK character selects whole.

The surface, end to end:

```python
# mechanism (kernel; on the root and the core facade)
from mocode_tui import Selection, extract, highlight
Selection.between(anchor, head)               # anchors are (block_id, row, col)
highlight(layout, selection)                  # pure overlay, merges SELECTION
extract(document, selection, *, width) -> str  # full range, off-screen included

# driver facade
tui.selection                                # Selection | None (read)
tui.selection_pane                           # the document's pane, or None
tui.set_selection(sel, pane=...)             # write + invalidate; None clears

# policy (root-public; the host opts in with one line)
from mocode_tui import SelectionGesture, copy_on_select
gesture = SelectionGesture(tui)               # on_end=copy_on_select by default
if not gesture.handle(event):                 # the consume-one-event contract
    ...                                       # the host's own dispatch
gesture.detach()

# screen primitive
screen.copy(text) -> bool                    # OSC 52; False when non-live
MouseEvent.kind                              # "press" | "release" | "motion"
```

`docs/COMPONENTS.md` documents the gesture's full state machine and the four
replacement points a host swaps (its own `set_selection` loop, its own
`on_end`, the sub-gesture knobs, the highlight style).

## Keys

`KeyDecoder` is a pure, total `bytes -> events` machine: incremental UTF-8,
control names (`c-a`…`c-z`, `enter`, `tab`, `backspace`, `escape`, `space`),
CSI navigation (arrows / home / end / **page_up**/**page_down**, with the one
named modifier form — `ESC [ 1;2 X`, the shift chords `s-*` — and every
other parameter string ignored), bracketed paste (`\x1b[200~ … \x1b[201~`,
whose end marker closes the paste **wherever a feed boundary falls**: the
scan holds a trailing partial marker back instead of folding it into the
payload, so no marker byte ever lands in the payload and no byte past a
marker is swallowed), and SGR mouse reports; the focus reports DECSET 1004
sends decode to `focus_in` / `focus_out`. Unknown input is dropped or
degraded, never fatal.
`finish()` ends a stream: a truncated UTF-8 sequence surfaces as U+FFFD and
an unclosed bracketed paste is delivered verbatim as one final `Paste`.

`KeySource` is `async read() -> Key | Paste | None` (`None` = EOF):

- **`ScriptedKeys`** (in `core.events`) replays a fixed event list, then
  reports EOF forever (a `None` item is a one-shot EOF signal). Tests and
  scripted sessions drive the whole toolkit this way.
- **`RawTerminalKeys`** reads a real terminal: POSIX `termios.setraw`, or on
  Windows a `GetConsoleMode`/`ReadConsoleInputW` record path; when the
  terminal cannot be switched to raw mode it falls back to cooked line mode
  (`.cooked_fallback`). A daemon reader thread feeds an executor-backed
  queue, so `read()` stays async without the thread touching asyncio.
- **`RecordingKeys` / `ReplayKeys`** (`mocode_tui.keys.recorder`, D11) are
  the event-level recording pair — decorators over the protocol, not over
  bytes, because the Windows console path has no single byte seam a live
  session's input passes through. `RecordingKeys` appends each served event
  to a JSONL file (`{"ms": …, "event": …}`, the model's own fields) and an
  EOF stops the file; `ReplayKeys` serves the file back, waiting the stamp
  deltas scaled by `speed`, and `speed=0` never waits at all — the
  zero-sleep contract a regression test holds. Neither name is on the root:
  they are developer tools, and the `keys` facade exports them.

### Keymaps

Editing keys are not hardwired: a **keymap** (`mocode_tui.keys.keymap`) is a
plain `dict` from key event name to the name of the no-argument editing
method it triggers (`"left" -> "move_left"`). All three default tables live
in that one module with their derivation chain in view:
`DEFAULT_INPUT_KEYMAP` → `DEFAULT_EDITOR_KEYMAP` → `EDITOR_SUBMIT_KEYMAP`.
`Input` and `Editor` resolve
their keymap at construction (`keymap=None` picks the component's default)
and consume keys through **`handle(event) -> bool`**:

- a `Paste` inserts its text; a `Key` with a `char` (a printable, `space`
  included) is inserted directly — printables never need a keymap entry;
- otherwise the event's `name` is looked up in the keymap and the same-named
  method runs;
- an unbound name answers `False` and the event goes back to the host, which
  is how a submit gesture stays the host's decision.

**The wrap geometry comes from the component's last render**, not from the
key: `move_up`/`move_down` follow the wrapped rows a `render(width)` call
seeded (80 columns before the first render), so a field moves inside exactly
the geometry the user sees.

`DEFAULT_INPUT_KEYMAP` binds arrows / home / end / `c-a` / `c-e` /
`backspace` / `delete` / up / down / `c-u` / `c-z` / `c-y` and leaves
`enter` unbound;
`DEFAULT_EDITOR_KEYMAP` is that plus `enter` as `newline`. A host rebinds
single keys by handing in a copy (`{**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}`)
or drops a binding by `del`-ing its entry. An editor whose host takes the
submit gesture resolves
`EDITOR_SUBMIT_KEYMAP`: the editor default minus `enter`, with `c-j` as
`newline` in its place — the decoder emits no `c-enter` name, so the return
key is the only clean submit gesture. The `keys` facade exports all three
tables.

**The editing history is the buffer's own** (D15). Every write point —
`insert` / `backspace` / `delete` / `newline` / `clear` — snapshots
`(lines, row, col)` **before** it mutates onto a bounded stack (100 steps,
`TextBuffer.UNDO_LIMIT`), and a new change drops the redo tail, so `redo`
never re-applies a change an edit has moved past. `c-z` / `c-y` walk the
stack through the keymap: two methods (`undo()` / `redo()`, both
`-> bool`) a host may also drive directly. Runs of **single-character
inserts** merge into one step — the keystrokes of one typed word, with no
other operation or move between them — while a move, a click's caret
docking, another write point or a multi-character `insert` (a paste)
breaks the run: a paste is one step, however many lines it carries.

**The text-internal selection is the buffer's anchor** (D15). `c-a` is
`select_all` — the caret walks to the text end with the anchor parked at 0
(the plain **`home`** carries the line start, and `c-a`'s old `home`
binding is gone) — and the shift chords `s-left` / `s-right` / `s-up` /
`s-down` / `s-home` / `s-end` extend the selection from the anchor to
wherever the matching plain move would land: the moves' own column and
wrap semantics, one `select_*` method per chord. `selected_text`,
`selection_range()` (a normalized `(start, stop)` flat pair, `None` when
empty) and `clear_selection()` are the host's views; every **plain** move
— a click's caret docking included — drops the selection, and every write
point deletes it first: typing replaces the selected range (one history
step covers both halves), and `backspace` / `delete` / `newline` land at
the range's start. The field renders the range as `merge(theme.selection)`
over the row's own style, the block cursor still painted underneath it —
on a cell both cover, the selection band wins.

### Paste semantics

The screen asks the terminal for **bracketed paste** on entry
(`enable_bracketed_paste`, DECSET 2004 — the byte pair is in the screen
section, and `paste=False` turns it off for a host that wants the mode
itself). With 2004 on, the terminal wraps every paste in
`\x1b[200~` … `\x1b[201~`, and the decoder turns that bracket into **one
`Paste` event** — never the keystrokes the pasted text would have been typed
as. That is the whole fix for the multi-line paste: `Paste` and `enter` have
disjoint jobs, so three pasted lines can no longer become three or more
submissions. A `Paste` is content: `Editor` inserts it verbatim, the
single-line `Input` folds its newline runs into spaces, and neither can
submit, because no library keymap binds a submit gesture and the host's
submit gesture watches `enter` only. A paste of N lines is one event, one
user message, one repaint — and only the return key sends, once.

**Two input paths cannot bracket, and the library does not guess.** A legacy
Windows console that cannot provide VT input re-reads a paste as a burst of
key records (`keys/console.py`: `VK_RETURN` → `enter`, one per line break);
a cooked pipe or a redirect (`RawTerminalKeys`' cooked-line fallback) hands
the program the pasted text line by line, each line followed by its newline.
On both paths the paste arrives as text plus `enter` keys — line by line,
and so **submit by submit**. Those newlines are indistinguishable from typed
returns, so the toolkit does not heuristically merge them: the degradation
is documented, not papered over. On a modern terminal (Windows Terminal /
conpty, where `keys/console.py` enables `ENABLE_VIRTUAL_TERMINAL_INPUT`, or
any POSIX raw terminal) the bytes reach `KeyDecoder` and the bracket does
its job.

## Highlighting

`mocode_tui.widgets.syntax` is the built-in syntax highlighting: an ordered
table of per-language regex rules resolved against a theme's semantic
colors, turning `(code, lang)` into one `Line` per logical line. Sixteen
languages ship (Python, JavaScript, TypeScript, bash/shell, JSON, YAML,
TOML, Markdown, diff, Rust, Go, C, C++, HTML/XML, CSS, SQL) under 32 tag
keys, aliases included; matching is per-line and first-match-wins, and text
no rule claims keeps the theme's `code` style.

Five token classes, all weight-free: comment (muted + italic), string
(success), number (warning), keyword (the accent hue), builtin (the `code`
color). The only bold left in a default render is the `**…**` syntax itself;
the only struck run is `~~…~~`. Both are attribute-only styles that merge
onto whatever band they sit in.

The seam is the protocol, not the engine: **`Highlighter`** is any object
with `highlight(code, lang) -> list[Line]`, and `Markdown(…,
highlighter=…)` accepts one wholesale — `RegexHighlighter(theme=…,
languages=…)` customizes the built-in, `default_highlighter()` shares the
stock instance (building one compiles every rule, so components share rather
than rebuild), `highlight(code, lang)` is the convenience entry point.
Zero dependencies by contract: the module is pure `re` over the kernel.

## The non-TTY contract

A **non-live** screen (pipe / file) changes `run()`'s whole behaviour:

1. **Run-time is silent** — no escapes, no alt screen, nothing behind the
   painter's back.
2. **`read_key()` always returns `None`** on a non-live screen, even with a
   key source attached (that is why a headless session drives its own replay
   and dumps the screen itself).
3. **On exit the final screen is dumped as plain text** — the `height` rows
   of the last frame, trailing blanks trimmed, on the exception path too
   (before the error is re-raised).
4. **The capability switches cannot break 1-3.** `sync`, `focus_events` and
   `color_mode` are screen/painter contracts and none of them adds a byte a
   non-live run would not otherwise send: the bracket wraps a payload that
   is already zero bytes when nothing changed, the focus pair lives inside
   the session bracket a non-live screen never writes, and color is a
   *rendering* choice — a live screen's mode decides the SGR parameters
   (`"none"` keeps the text and the attributes), while the piped dump reads
   row text and is color-blind either way. The library's own no-color path
   is simply the probe answering `"none"`, so
   `NO_COLOR=1 uv run python examples/demo.py --pages` exits 0 like every
   other piped run. The two window gestures (`TUI.set_title` /
   `TUI.set_cursor_shape`) are the deliberate exception: they write when the
   **host** asks, liveness gate aside, and a headless recorder captures them
   so a test can assert them (see *Terminal capabilities*).

`HeadlessScreen` is the in-memory counterpart: a recorder that is *live by
construction*, so `headless_tui`/`snapshot` (`mocode_tui.testing`, above the
kernel) can drive a real driver and assert on structure without a terminal.

A non-TTY **input** path is the other non-live case: when
`RawTerminalKeys` cannot switch the terminal to raw and falls back to cooked
line mode, or stdin is a pipe or a redirect, the bytes arrive line by line —
a multi-line paste becomes text plus one `enter` per break, and the host's
submit gesture fires line by line. Bracketed paste needs the terminal, so
this path has no bracket to read and the library does not guess (see the
Paste semantics note in the Keys section).

## Deliberately out of scope

- A document memory cap / history trimming: the document stays resident in
  full, and nothing is ever evicted.
- A VT-settle timeout across split reads, and SIGWINCH-beyond-resize
  handling: the screen is only re-sampled by `refresh_size()`.
- Runtime colour negotiation by **query and response** (DA/DSR/OSC 11): no
  terminal is interrogated — capability comes from the environment alone
  (`detect_color_mode`), the palette stays authored in 24-bit truecolor and
  downgraded at paint time, and a VT probe still only gates streams that
  cannot render escapes at all.
- Drag-to-resize dividers and cross-pane selection: drag selection ships —
  the Selection section's `SelectionGesture` consumes the press / motion /
  release reports mode 1002 delivers — and scrollbar dragging ships with it
  (the frame section: the bar consumes the left button over its strip), and a
  pane closes for real (`Pane.close()`: the split collapses and the divider
  goes with the adjacency it divided, handing the transcript its cells back).
  What stays out is everything that would
  *re-divide* or *span* the frame: dragging a divider to a new ratio (ratios
  are fixed at split time today), and a selection whose range crosses two
  panes (selection stays single-document — the frame group's D7 — with a
  host's `on_end` resolving the focused pane's document as the host-layer
  bridge). The horizontal wheel stays dropped too, and multi-range
  selection stays at one `anchor…head` range (D8).
- Hover beyond the pointer tier: hover ships — `Pointer`, with DECSET 1003 as
  the opt-in `TUI(hover=True)` switch and the default kept at
  1000+1002+1006 (the Hover, and the pointer section) — and what stays out is
  its edges: hover never crosses a pane (a pane switch or a resize clears it,
  best-effort), a held button moves no hover, the pointer is not handed
  window events, and hovering never scrolls or dispatches (the stationary
  click is its only dispatch; `docs/COMPONENTS.md` has the wiring).
- Math rendering in Markdown: the rule registries in
  `mocode_tui.widgets.markdown` are the documented extension point
  (see `docs/COMPONENTS.md`).
- Any sleep in the library or its tests: time flows through the pump's
  clock, which a test injects.
- Backward compatibility: no shim, no alias, no deprecation period — a
  renamed name is deleted with its last consumer.
