# Design

This page explains why motui works the way it does. Each section states the
problem, the mechanism that answers it, and the trade-off that shaped it.
The rules a host writes code against are in
[`docs/COMPONENTS.md`](COMPONENTS.md); the non-negotiable ones are in
[`docs/CONTRACT.md`](CONTRACT.md).

## The problem: a screen is data, not a widget tree

A full-screen terminal application has one hard constraint: at the end of a
frame, every cell must have a value. A retained widget tree makes that fact
implicit: widgets own children, layout is negotiated by parents, and the
final cells emerge from a graph of side effects. That model is excellent for
event bubbling and incremental invalidation, and expensive for everything
else: layout becomes a framework feature, testing needs a running event
loop, and the answer to "what will row 7 contain?" is buried in a tree walk.

motui starts from the other end. The unit of content is a **block**: an id,
a component, and the rows the component answers at a width. A **component**
is anything with one method:

```python
def render(self, width: int) -> list[Line]: ...
```

A **document** is an ordered collection of blocks. A **viewport** turns a
document into exactly the rows a rectangle can hold. A **frame** composes
viewports, chrome, docks and overlays into one screen. A **painter** diffs
those rows against the last frame and writes only the changes.

The consequences are deliberate:

- rendering is a pure function of component state and width, so it is
  testable without a terminal;
- hit testing reads the rows that were actually painted, not a second
  layout calculation;
- scrolling is arithmetic over document rows, not a special widget mode;
- the app keeps the event loop and decides what every input means; `App`
  runs the default policy and `TUI` hands the loop to a custom host.

**The trade-off.** There is no automatic parent/child layout engine, no
message bus and no per-widget event bubbling. Containers are explicit
components (`Row`, `Column`, `Padding`, `Panel`, `ScrollView`), and the host
routes events. In exchange, every layer is inspectable, and the library can
run the same code headless.

**Extend here.** New content starts as a component with `render(width)`. New
grouping starts as a container with `child_at(row, col)`.

## Layers and the dependency direction

Dependencies point one way:

```
core  ->  widgets  ->  app
testing (above app and core)
```

| Layer | May import | Contents |
|---|---|---|
| `motui.core` | stdlib, `wcwidth` | values, styles, palettes, themes, glyphs and borders, events, document model, screen, viewport, painter, frame, selection, chrome, clipboard, the byte decoder/keymaps/key sources, `Widget`, `ScrollState`, `Cursor` and `Hit` |
| `motui.widgets` | `core` | the component library, Markdown rules, syntax highlighting |
| `motui.app` | `core`, `widgets` | `App`, `TUI`, focus, pointer, gesture, find, modal, palette, overlays, scrollbar, commands |
| `motui.testing` | `app`, `core` | `headless_tui`, `snapshot`, `ScriptedEvents` |

The root module is a curated face of 41 names. Every other public name lives
at exactly one layer namespace; `tests/test_api.py` pins every facade.

**No Host seam.** The controllers and the driver are in the same layer, so
the old `Host` protocol and its component factories are gone. `App` holds a
`TUI` and composes `FocusManager`, `Pointer`, `SelectionGesture`, `Toasts`,
`Tooltip`, `Find`, `Modal` and `CommandPalette` directly; `TUI` reads events
and owns the document, frame and pump, but runs no interaction policy. A
controller takes `tui` (or nothing) in its constructor and calls the driver
surface it needs.

**The trade-off.** `app` is the only composition root. A host that wants a
different policy either subclasses `App` and overrides `dispatch`/`on_*`, or
sets `auto=False` and drives `tui` itself with its own controllers. There is
no second driver surface to keep in sync.

**Extend here.** A new controller goes in `motui.app`; a new mechanism used
by both widgets and controllers goes in `motui.core`.

## Theme, ColorPalette and glyphs

The 1.x theme was one flat dataclass of semantic tokens, and the structural
marks were split between module constants and per-component constructor
arguments. Two costs followed. Brand colors and semantic roles were the
same knobs, so changing a brand hue meant repeating the value across
`accent`, `heading`, `link` and the control band; and a 16-color
terminal lost the intended hue when the truecolor value was quantized.
Glyphs had the mirror problem: a host could not swap the vocabulary once,
because every widget named its own marks.

**The mechanism is two authoring layers and one separation.**

`Color` pairs an authoring value with an ANSI anchor:

```python
Color("#53c8f0", ansi="bright_cyan")
```

The `256` and `truecolor` modes paint the authoring value; the `16` mode
uses the anchor first and quantizes only when it is `None`; `none` keeps
attributes and drops color. A bare hex or tuple color still works -- it is
simply a color with no anchor.

`ColorPalette` is the creation layer: 18 fields describing the brand's ink,
muted/faint text, lines, five surfaces, accent, status trio, code, heading,
link, inline code and marker. It is frozen and has one consumer,
`Theme.from_palette`. The two shipped palettes are `DARK_PALETTE` and
`LIGHT_PALETTE`.

`Theme` is the application layer: ten frozen role groups, each field one
`Style`. The split between `ColorPalette` and `Theme` is what lets a brand
change stay in one value while components keep asking for semantic roles.

| Group | Fields | What it answers |
|---|---|---|
| `text` | `base`, `muted`, `faint`, `inverse`, `disabled`, `caret`, `selection` | foreground text roles |
| `surfaces` | `base`, `raised`, `hover`, `active`, `selected` | background regions |
| `borders` | `base`, `grid`, `focus`, `danger` | frames, grids and emphasis |
| `controls` | `base`, `hover`, `focus`, `active`, `disabled` | button-like bands |
| `rows` | `base`, `hover`, `active`, `inactive`, `selected`, `marked`, `disabled` | every vertical row widget |
| `status` | `success`, `warning`, `danger`, `info` | outcomes |
| `content` | `accent`, `link`, `code`, `inline_code`, `headings`, `marker`, `quote`, `strong`, `emphasis`, `strike` | Markdown and prose |
| `chrome` | `divider`, `scrollbar`, `scrollbar_thumb` | dividers and scroll chrome |
| `overlays` | `scrim`, `toast`, `tooltip` | modal and floating layers |
| `syntax` | `comment`, `keyword`, `string`, `number`, `builtin` | token classes |

The field defaults are the Ink & Signal dark theme, so `Theme()` is
`Theme.dark()` and `DEFAULT_THEME` needs no factory call. The other
constructors are deliberate:

| Constructor | Source | Intent |
|---|---|---|
| `Theme.dark()` | `DARK_PALETTE` | the shipped default |
| `Theme.light()` | `LIGHT_PALETTE` | a light terminal |
| `Theme.flat()` | dark, surfaces flattened | position without background paint |
| `Theme.auto(env=None)` | `TERM_BACKGROUND`, then `COLORFGBG` | choose light or dark without a global setting |
| `Theme.from_palette(p)` | any `ColorPalette` | a brand theme |

`flat` keeps the dark text and accent roles but sets every `surfaces.*`
token to `NONE`; the engaged and selected rows reverse, hover underlines
and the unfocused cursor dims, so hierarchy survives on a terminal with no
background control. `auto` is a pure read: it never writes `os.environ`
and never sets a module-level theme.

`RowStyles.band` and `ControlStyles.band` are the one place the precedence
lives. Rows resolve `disabled > hovered > (active ? (focused ? active :
inactive)) > selected > marked > base`; controls resolve `disabled >
active > focused > hovered > base`. The pointer's band is more immediate
than the cursor's, which is why hover outranks the active branch; a
disabled row outranks everything.

### Widget and Styles

Every themed control inherits `Widget`, which owns the four mutable inputs
the runtime writes: `theme`, `styles`, `focused` and `hover`. `theme=None`
means "inherit the App theme"; `styles: Styles | None` overrides whole role
groups and leaves every `None` group to the theme. `Widget` also supplies
the interaction verbs as no-ops (`handle`, `click`, `drag`, `hover_at`,
`activate`, `take_result`, `revision`) and `group(name)` as the one lookup
that honours the override.

`Styles` is a frozen dataclass with one optional field per theme group
(`text`, `surfaces`, `borders`, `controls`, `rows`, `status`, `content`,
`chrome`, `overlays`, `syntax`). A non-`None` group replaces that group
wholesale for the widget; a `None` group follows the theme.

The key property is **render-time resolution**: a widget reads the role
groups it paints when it renders, not once at construction. Assigning
`App.theme` walks the mounted components and writes the new value into every
`Widget` whose own `theme is None`; a mounted widget repaints without being
rebuilt, and an explicit `theme=` stays a local override. `revision()` must
therefore include `theme` and `styles`, or a block's row cache would swallow
the change.

`Text` is the deliberate exception: it is a core renderer, not a `Widget`,
and resolves one explicit `style=` over `theme.text.base` at construction.
Pure renderers (`Row`, `Column`, `Spacer`) also stay outside `Widget`;
`Component`'s one `render` method is the only mandatory protocol.

**Glyphs are content, not style.** `Glyphs` is a frozen vocabulary of 31
fields, and `Border` is a frozen 14-mark box style. The separation is the
point: swapping a theme never changes geometry, and swapping a glyph never
changes color. Each component takes one `glyphs: Glyphs = GLYPHS` value
instead of a per-mark argument, so a host can reskin the vocabulary in one
place. `Panel`, `Dialog` and `Table` additionally accept a `Border`
(`square`, `rounded`, `heavy`, `double`, `ascii`, `none`), which keeps a
borderless box occupying the same cells. `seat("")` is the escape hatch: an
empty glyph seats nothing and its geometry collapses, while `Border.none()`
paints spaces and keeps the reserved geometry.

**The trade-off.** A host now builds two values instead of one, and a
custom brand palette must also name the inverse text color (the page color
`surface` leaves transparent). In exchange, a brand change is one small
value, a seasonal theme is a pure function, and the glyph vocabulary is
independent of color capability.

**Extend here.** A new semantic role joins the matching group (and
`Theme.from_palette` when it derives from the palette); a new mark joins
`Glyphs`; a new box style is a `Border` classmethod. Components read the
group field, never a palette field.

## Coordinates and hit testing

Every cell index is **0-based**. The terminal's mouse report is 1-based, so
`KeyDecoder` subtracts 1 when it builds a `MouseEvent`; the painter adds 1
only when it emits a cursor-position escape. Nothing else converts.

`TUI.hit(x, y)` resolves a screen cell through the frame's ownership table:

```python
Hit(pane, block, row, col, chain=())
```

- `row` and `col` are 0-based inside the block's own rows.
- `col` is measured against the pane's **inner rectangle** (chrome
  subtracted), not the outer pane rectangle.
- `chain` is the ancestor walk `descend_chain` resolved: one
  `(component, row, col)` per level, outermost first, in each component's
  own coordinates.
- `leaf`, `leaf_row` and `leaf_col` are derived properties over the tail of
  `chain`; an empty chain answers `None` / `0` / `0`.
- A cell outside the screen, outside every pane, or over blank fill is
  `None`. Coordinates are never clamped to the nearest block.

Containers make the descent possible. `Container.child_at(row, col)` returns
`(child, row, col)` in the child's coordinates, or `None` for cells the
container owns itself (borders, padding, gaps). The geometry comes from the
container's **last render**; a container that has never rendered declines
every cell, so a hit test never invents a layout. `descend_chain` is
depth-guarded against a malformed container that returns itself, and
`descend` is its leaf-only convenience.

Block ids are unique across the whole frame, not merely within one document.
A split's second pane does not get a second `b0`; automatic ids are picked
over every pane's document.

**Focus owners and click routing.** `App` registers focus *owners*, not
every interactive leaf. A widget that routes its children's keys through
its own `handle` sets `owns_focus = True` (`Form`, `ComboBox`); the App then
registers the compound and skips its subtree. A click is split into two
halves along `Hit.chain`: the deepest leaf gets its action (`click`), and
every ancestor gets `focus_at(row, col)` to move its internal cursor (a
form's field index, a dialog's button index). The focus tier focuses the
nearest registered ancestor. A container never activates from a click on
its background; activation belongs to the leaf. This is why clicking a
form's email row moves the form cursor and the next keystroke lands there,
without registering every field as a competing focus target.

**The trade-off.** Hit testing trusts painted geometry rather than
recomputing layout. That keeps clicks exact and cheap, but it means a host
must paint before dispatching the first click after a structural change.

**Extend here.** A new container implements `child_at` from its last
render's rectangles. Nothing else is required: a container never proxies
`handle`, `move`, `activate` or `focused`.

## Events and the decoder

Every input is an `Event`. There is no catch-all "key" type:

| Type | Fields | Notes |
|---|---|---|
| `KeyEvent` | `key`, `char`, `modifiers`, `kind` | `kind` is `press`, `repeat` or `release` |
| `MouseEvent` | `button`, `x`, `y`, `kind`, `modifiers` | `button` is a string; `kind` includes `wheel` |
| `PasteEvent` | `text` | literal text, never re-read as keys |
| `ResizeEvent` | `width`, `height` | produced by the decoder or source |
| `FocusEvent` | `focused` | opt-in focus reports |

`KeyEvent.key` is the routing identity:

- a printable key is its own character (`a`, `中`, `!`); space is `space`
  with `char=" "`;
- controls are `c-a` .. `c-z`; carriage return is `enter`, line feed is
  `c-j`;
- editing keys are `tab`, `backspace`, `insert`, `delete`, `home`, `end`,
  `page_up`, `page_down`; arrows are `up`, `down`, `left`, `right`;
- function keys are `f1` .. `f24`; escape is `escape`;
- chords prefix with `c-`, `a-`, `s-`, in that order: `c-s-left`,
  `a-s-up`, `c-a-s-tab`.

The structured `modifiers` set records the same fact when an escape
sequence carries it; plain UTF-8 text does not infer Shift. A mouse report
is never a key: `isinstance(event, KeyEvent)` matches the keyboard only.

`EventSource` is one method:

```python
async def read(self) -> Event | None: ...
```

`None` means EOF and remains `None` on later reads. `RawTerminalKeys` reads
a real terminal (POSIX raw mode, or the Windows console record API) and
falls back to cooked line mode when raw mode is unavailable. `ScriptedEvents`
in `motui.testing` replays a fixed list, then reports EOF forever.

The decoder is pure and total. It handles incremental UTF-8, C0 controls,
CSI letters and `~` sequences, SS3, modifier parameters, kitty's
`CSI codepoint;mods u`, xterm's modifyOtherKeys, bracketed paste, focus
reports, resize reports and SGR/X10/urxvt mouse reports. `finish()` flushes
a truncated UTF-8 sequence and an unclosed paste without dropping bytes.
Unknown input degrades or is dropped; it never raises.

Bracketed paste is one `PasteEvent`, even across feed boundaries. That is
what keeps a multi-line paste from becoming several submissions. Two input
paths cannot bracket: a legacy Windows console and a cooked pipe deliver
text plus one `enter` per line. The library does not guess; the host sees
the degradation and decides.

**The trade-off.** Events carry no timestamps. Time is supplied by
`tui.clock()`, so tests can drive click counts, timers and auto-scroll
without sleeping.

**Extend here.** A new escape sequence goes in `motui.core.decoder`; a new
input transport goes in `motui.core.sources`. Add the event type to
`motui.core.events` only when the model itself changes.

## The driver lifecycle

`App` is the default entry point: it owns one `TUI` and mounts the default
interaction policy around it. `TUI` remains the low-level runtime -- screen,
frame, pump and document facade -- and runs no interaction policy of its own.

`App`'s constructor forwards the driver switches and adds the policy
switches:

| Option | Effect |
|---|---|
| `screen=` | a `TerminalScreen` by default; `HeadlessScreen` for tests |
| `keys=` | an `EventSource`; `RawTerminalKeys` is attached when interactive |
| `throttle=` | the minimum seconds between pump-driven frames |
| `interactive=` | whether a source is attached and the screen enters/leaves |
| `mouse=`, `hover=` | 1000/1002/1006 reporting, or 1003 for free motion |
| `focus_events=` | enable `FocusEvent` reports (DECSET 1004) |
| `sync=` | bracket frames in synchronized-update (DECSET 2026) |
| `color_mode=` | override the environment probe for the default screen |
| `theme=` | the application theme, propagated to mounted widgets |
| `auto=` | `False` mounts no default controllers; `app.tui` stays usable |
| `on_selection=` | replaces the selection gesture's `on_end` |

`TUI` takes the same driver switches (`screen`, `keys`, `throttle`,
`interactive`, `mouse`, `hover`, `focus_events`, `sync`, `color_mode`,
`theme`) and no policy switches.

Both expose the same three entry points:

```python
await app.run_session(body)   # run your coroutine, then tear down
await app.run_async()         # run until app.quit()
app.run()                     # synchronous wrapper around run_async()
```

`App` calls `on_start()` once before the loop and `on_stop()` once after it,
whatever ended the run. `run_session` enters the screen when it is live,
starts the pump, awaits `body(app)`, and always tears down: on normal return,
on an exception, and on `quit()`. A `KeyboardInterrupt` from the body is
treated as `quit()`. Every run resets timers, selection and the painter's
diff base; an owned key source is closed at teardown and reattached on the
next run, so the same app can run more than once.

`App.dispatch` is the default policy, in documented order: palette, modal,
find, toasts, mounted controllers, wheel (nearest `Scrollable` in
`Hit.chain`), mouse (in-flight drag, gesture, pointer, pane focus), the
focused widget, page keys (focused `Scrollable`, else the focused pane),
`bind`ings and `tab` cycling, then `on_key` / `on_mouse` / `on_event`.

A host that wants its own order sets `auto=False` or drives `TUI` directly.
Inside that loop:

```python
event = await tui.read_event()   # None at EOF or when the screen is not live
tui.refresh()                    # mark dirty; the pump paints
tui.exit()                       # unblock reads and end the run
```

`read_event` is a **pure read**: wheel reports, page keys and mouse presses
come back exactly as the source reported them. There is no `scroll_keys`
table and no focus policy in the driver; both live in `App`.

The pump repaints at most one frame per throttle window when dirty, and runs
due `every(seconds, fn)` callbacks. `clock()` is the monotonic seam;
`tick(now)` advances one step and returns the delay until the next wake.
The library never sleeps.

On a **non-live** screen (a pipe or file), the run stays silent, `read_event`
returns `None` even with a source attached, and teardown dumps the final
screen as plain text. That is how the demo's piped replay works.

**The trade-off.** `App` owns the default event loop, the dispatch order and
the mounted controllers. A host that wants a different policy still gets the
whole driver below it, at the cost of routing wheel, page, pointer and focus
itself.

**Extend here.** A new controller goes in `motui.app` and is either mounted
by `App` or wired by a host through `mount`; a new capability switch belongs
in `TUI.__init__` and, when the policy needs it, in `App.__init__`.

## Documents, blocks and caching

`Document` is an ordered, id-addressable collection. `add` generates `b0`,
`b1`, ... when no id is given and raises on a duplicate; `get` and `remove`
raise `KeyError` when missing; `blocks()` returns a snapshot.

A `Block` has no lifecycle state and no `seal()`. It is an id, a component,
a pin and one row cache. `Block.rows(width)` is the cached read;
`Block.render(width)` is the uncached door, "render it again, now":

- a component that implements `Revisioned` and returns a non-`None`
  snapshot is cached by `(width, revision)`;
- a component without `revision` -- or one whose `revision()` answers
  `None` -- re-renders on every read, because the block has no way to see
  that its content changed.

`Block.rows` returns a fresh list of the same immutable `Line` values, so
callers own the list but not the rows.

The snapshot is the contract that makes caching safe. `Revisioned.revision()`
must return a **value** covering every mutable input `render(width)` reads:
a copy, cheap compared with rendering, and equal values at one width must
mean equal rows. A hovered span, a streamed `text` assignment, a cursor move,
a mark flip or a `theme`/`styles` reassignment changes the snapshot, the
cache misses, and the block repaints. Returning `None` switches the memory
off.

**The trade-off.** A component author must remember the snapshot. The reward
is that streaming text, live fields and hovered rows do not re-wrap the
document on every frame, while an unrevisioned component stays correct by
re-rendering.

**Extend here.** A new stateful component implements `Revisioned` with a
tuple of its row inputs. A new cache belongs to the block, never to the
layout side.

## Viewport and docks

`Viewport.layout(width, height)` is the only place a document becomes screen
rows. It returns a `ScreenLayout`:

| Field | Meaning |
|---|---|
| `rows` | exactly `height` rows for this rectangle |
| `body_rows` | the scrolling body alone, fixed regions excluded |
| `row_blocks` | screen row -> `(block id, row in block)`, or `None` |
| `block_order` | the block ids in paint order |
| `offset`, `total_rows` | the scroll state the layout used |
| `width`, `height` | the rectangle the rows were measured in |
| `viewport_start` | where the body begins inside the rows |

All four row containers are tuples: a layout is one immutable value.

Pinned blocks (`pin="top"` / `"bottom"`) render into fixed regions outside
the scrolling body. When both regions overflow, the footer is kept first,
then the top region, and the body may be empty. A fresh viewport sticks to
the bottom; scrolling up detaches it, and landing on the bottom edge
re-attaches it. `Viewport.scroll_to(offset)` is an absolute jump with the
same clamp. `TUI.reveal(bid, row)` brings a document address on screen,
centered when the document's edges allow, and returns `False` for an unknown
block.

Between layouts the viewport keeps a private body index: every body block's
height, the prefix sums over those heights, and the block ids in document
order, keyed on the document's mutation count and the width -- either key
moving rebuilds the whole index. Within a key, each layout re-probes every
body block's revision snapshot (one value comparison per block; a block
without a usable snapshot is re-measured every frame, which re-renders it,
as it always did), re-measures only the blocks whose snapshot moved, and
bisects the prefix sums to find the blocks the window covers, slicing their
rows from the block caches. The blocks own the row caches; the index owns
only geometry -- heights and prefix sums, no rows.

`TUI.visible_range(pane=None)` reports the visible body as **screen rows**,
including the pane's top-pin offset. It reads the last composition, never a
fresh layout.

A **dock** is different from a pin:

| | `pin` | `dock` |
|---|---|---|
| lives in | one document's viewport | the frame, outside every pane |
| width | the pane's inner width | the full frame width |
| scrolls | with its region's rules | never; it is outside the split area |
| focus / split | part of the pane | takes neither |
| API | `app.add(..., pin="top")` / `tui.add(..., pin="top")` | `app.dock(component, edge=...)` / `tui.dock(component, edge=...)` |

`tui.dock(component, edge="top"|"bottom", size=None)` builds a frame-level
viewport around the component and parks it in a dock; `App.dock` is the same
call with the App theme applied first. `size=None` derives the height from
content; an empty dock claims no rows and paints nothing; one dock per edge.
Docks join the ownership table, so a footer block resolves through `hit`
like any other block, but a wheel over a dock scrolls the focused pane.
`undock(edge)` releases it.

**The trade-off.** Pins are per-document and scroll with the viewport's fixed
regions; docks are per-frame and survive splits. The host chooses which
guarantee it needs.

**Extend here.** A new pinned behavior belongs in `Viewport.layout`; a new
frame-level region belongs in `Frame` and `TUI.dock`/`_retile`.

## Scroll state and the widget bar

`ScrollState` is the one geometry every scrolling surface shares:
`offset`, `content_height`, `viewport_height` and `stick_to_bottom`, with
`max_offset()`, `clamp()`, `scroll_to()`, `scroll_by()`, `reveal()` and the
single thumb formula:

```
length = min(track, max(min_length, round(viewport * track / content)))
travel = max(1, track - length)
span   = max(1, content - viewport)
start  = min(travel, max(0, round(offset * travel / span)))
```

`Scrollable` (`scroll_state`, `scroll_to`, `scroll_by`) is the narrow
read/write face. `Viewport`, `Pane` (delegating to its viewport) and
`ScrollView` all implement it, and both kinds of scrollbar read their state
through it.

`ScrollView(child, *, height=None, offset=0, bar=False, ...)` is the
widget-level window. With `bar=True` it reserves the last column for a
track/thumb: a press on the thumb starts a drag mapped through
`ScrollState.scroll_to`, a press on the track pages by a viewport, and a
wheel over the view reaches the scroll state. The pane-level `Scrollbar` is
still frame chrome -- one budgeted column acquired from the pane -- but it
shares the same state and thumb formula, so the two never disagree.

## Wrapped tables

`Table(..., wrap=True)` (the default) treats a column budget as a wrapping
width, not an ellipsis limit. The header and every cell are wrapped with
`wrap_line`; a record can occupy several visual rows, each with its own
left/right grid borders and row band, and the inter-row rule follows the
record's last visual row. `max_col_width=40` caps a column, `min_col_width=3`
floors it, and `wrap=False` keeps the pre-1.2 natural-width / shrink /
ellipsis behavior byte for byte.

Hit testing reads the last layout's `(record, visual line)` map, so
`click`/`hover_at` resolve any visual row back to its data row.
`header_line(width)` remains the single-line header view for hosts that pin
it; `header_lines(width)` returns the whole wrapped block. Markdown tables
use the same default.

## Frame composition and overlay layers

Everything that claims screen space outside the document flow makes exactly
one of three claims:

| Claim | Shape | Cost |
|---|---|---|
| **Pane** | an exclusive rectangle with its own viewport and document | a split and a separator |
| **Chrome** | a band inside a pane's rectangle, acquired by budget negotiation | edge cells; content re-wraps at the reduced width |
| **Overlay** | a paint over the composed frame | no layout budget |

`Rect` is a frozen `(x, y, width, height)` value; `Split` divides a rectangle
by ratios with a `min_size` floor. A `Pane` is a mutable runtime object with
identity equality: it keeps its id, viewport, chrome and scroll state across
resizes, and a host's handle keeps addressing the same pane. `tui.split`
divides the focused pane (or an explicit one), returns the children in paint
order, and leaves focus where it was. The first child keeps the split pane's
document; later children start empty. The optional 1-cell separator is
budgeted chrome on the pane before the gap, not a gap between panes.
`Pane.close()` unsplits: siblings re-divide, and a surviving only child
collapses into its parent.

`Frame.compose(width, height)` negotiates chrome budgets first, lays each
pane's viewport out in its inner rectangle, splices granted chrome strips
back over it, places docks, and finally applies overlays. It also builds the
screen-wide ownership table that `hit` resolves through. `Pane.inner_rect`
is the rectangle the viewport used, chrome subtracted; `Pane.band(chrome)`
is the rectangle one chrome was granted. Both read the same memoized
negotiation the compositor painted, so a scrollbar's press test is exact.

Each composed row assembles from its **plan** -- the ordered writes its
regions make into it -- and every write runs through `splice_row`, so the
row stays exactly `width` columns wide whatever wrote into it. The plan is
the memo key: a plan equal to one the previous composition ran hands back
the row already built (rows are immutable values), and a row whose plan is
a single write covering the whole width is that line as it stands, no
splice at all -- together these make an unchanged frame a walk instead of
a splice and let a scrolled frame's shifted rows skip their rebuild. The
memo of plans is replaced whole each composition, so a plan no frame has
wanted for two compositions dies with it. The plan and ownership-table
containers are the frame's buffers between compositions instead: at an
unchanged height every row is cleared in place and refilled, at a new
height they are rebuilt to it. The division of labor: the **memo** caches
composed row values keyed by what produced them; the **buffers** only
spare the per-frame container allocation.

Overlays are pure `paint(frame) -> layout` transforms registered on the
frame:

```python
LAYERS = (
    "background", "content", "selection", "chrome",
    "overlay", "modal", "tooltip", "toast",
)
```

`Frame.add_overlay(overlay, layer="overlay")` appends; same-layer overlays
paint in registration order; an unknown layer raises `ValueError`. The
driver's selection highlight is registered in the `selection` layer, `Find`
paints in `overlay`, a `Modal` in `modal`, a `Tooltip` in `tooltip` and
`Toasts` in `toast`. A pane-relative overlay never writes outside its pane.
`detach()` on the shipped controllers is idempotent: it tests membership
before unregistering.

The wheel and pane focus are `App` policy over the frame: a wheel walks
`Hit.chain` backwards to the nearest `Scrollable` (the `ScrollView` bar and
content included), falls back to the hit pane, then to the focused pane; a
button press focuses the pane under the pointer through the default mouse
tier. `TUI` itself performs neither. On a one-pane frame every route is the
same by identity.

**The trade-off.** Panes are objects rather than values so that split, close
and resize never invalidate a host's handles. The price is that the frame
must retile carefully and count its structural revisions; the driver only
retiles when the tree or the computed tiling actually moved.

**Extend here.** A new pane-like region is a `Pane` and a `Split`; a new band
inside a pane is a `Chrome`; a new paint over everything is an overlay with
an explicit layer.

## The painter

`Painter` is a pure differ. It owns no document and no scroll state; one
frame arrives as a `ScreenLayout` and `paint(layout)` writes only what
changed.

- **Resize or first frame:** clear the screen and write every row.
- **Steady state:** compare each row with the previous frame and write only
  the changed rows, each as a cursor move, an erase-line, and the styled
  row. An unchanged frame writes **zero bytes**.
- **Non-live screen:** compute the logical rows but write nothing, so
  `tui.rows` remains queryable on a piped run.
- **One write, one flush:** a non-empty frame is a single write wrapped in
  the synchronized-update pair (unless disabled), followed by one flush.
- **Cursor anchor:** `set_cursor(row, col)` pins the terminal cursor for IME
  and accessibility; the anchor is written after a frame that wrote
  anything, or alone by a frame that only moved it.
- **Color capability:** rows render for the screen's mode. Truecolor uses
  the cached `Line.styled()`; `256`, `16` and `none` render fresh through
  `sgr_prefix(style, mode)` and `styled_with`. Caches stay independent of
  the terminal.

`Painter.rows` is normalized to exactly `screen.height` rows after a paint:
extra rows are truncated, missing rows are blank `Line` values.

**The trade-off.** The painter has no throttle of its own; it paints exactly
when told. The driver's throttle decides when a frame is due, and
`TUI.paint()` paints immediately when a host needs that.

**Extend here.** A new byte sequence belongs in `motui.core.ansi`; a new
rendering path belongs in `motui.core.lines` or `Painter`, not in a
component.

## Selection and focus

Selection is **document space**, not screen space. A selection is a pair of
`(block_id, row, col)` anchors built with `Selection.between(anchor, head)`.
Scrolling moves screen rows but not document addresses, so a highlight
follows its text and an extraction returns the full range even when part of
it is offscreen. `extract(document, selection, width=...)` reads the blocks
directly; `width` is the width the addresses were laid out against and has
no honest default.

The highlight is an overlay, not content. `highlight(layout, selection,
style=...)` marks the laid-out rows; the driver registers it in the
`selection` layer and reads `theme.text.selection`. Components stay pure and the
block cache stays untouched. A width change clears the selection, because
column addresses no longer name the same glyphs; vanished blocks resolve to
nothing rather than raising; one range (`anchor` to `head`) is the public
model.

`SelectionGesture` turns mouse reports into that model. Press anchors,
motion extends, release finalizes and calls `on_end` (by default
`copy_on_select`), a second press selects the word, a third the visible line,
and edge drags auto-scroll through `tui.every` ticks. `tui.selection`,
`tui.selection_pane` and `tui.set_selection(..., pane=...)` are the driver's
surface. Selection stays inside one pane.

Focus has two independent levels. **Pane focus** belongs to the frame and is
driven by the App's mouse tier (`tui.split` divides panes and leaves focus
where it was). **Widget focus** belongs to `FocusManager`, which `App`
mounts by default:

- targets are registered explicitly; `App.add` registers every interactive
  widget it mounts, `App.focus` addresses one by block id or component, and
  `App.set_focus_targets` replaces the ring;
- the constructor focuses nothing and writes no flag;
- a `Focusable` target has one read-write `focused: bool`, which the
  manager rewrites on every move;
- `handle(event)` dispatches to the focused target first, then maps
  `up`/`left` to `move(-1)`, `down`/`right` to `move(+1)` and `enter` to
  `activate()`;
- `click(hit)` descends to the leaf, dispatches `click`, focuses a
  registered target on the first click and activates it on the second;
- `push_trap` / `pop_trap` narrow and restore the target set, which is how
  stacked modals return focus correctly.

`Pointer` owns hover and the stationary click; it needs `hover=True`
(DECSET 1003) on the driver's screen for button-free motion. A component
renders its own `hover` flag and may implement `hover_at(row, col)` for
row-level marking. The pointer's `True` is a repaint cue, never a claim that
the event was consumed. A leaf's `hint: str` is the tooltip protocol;
`Tooltip` paints it beside the pointer without the pointer knowing.

**The trade-off.** Focus is a layer, not a component responsibility. A
component declares one flag and one rendering rule; the App decides who is
focused and what a click means. A host driving `TUI` directly must mount the
manager and route the cycle key itself.

**Extend here.** A new selection action is an `on_end` callable; a new focus
behavior is a `FocusManager` method or an `App.dispatch` rule.

## Value semantics

The library separates values you can share from objects you can mutate:

- `Style`, `Color`, `Segment`, `ColorPalette`, `Theme`, `Styles`, `Glyphs`
  and `Border` are frozen, slotted dataclasses, hashable and safe to cache.
- `Theme` is frozen at both levels: each of its ten role groups is a frozen
  value, and `content.headings` is a tuple. `replace(theme, group=...)` is
  the only way to make a variant; there are no derived mappings left.
  `Styles` is the per-widget group override; its `None` fields inherit.
- `Widget` is deliberately mutable: `theme`, `styles`, `focused` and
  `hover` are the four inputs the runtime writes. A widget is rethemed in
  place rather than rebuilt.
- `ScrollState` and `Cursor` are mutable state primitives owned by one
  surface; their verbs clamp and report whether anything moved. They are
  not shared between surfaces.
- `Pane` is deliberately **not** a value: `eq=False` keeps identity
  equality, and the frame mutates it in place across splits and resizes.
- `ScreenLayout.rows`, `body_rows`, `row_blocks` and `block_order` are
  tuples; the constructor normalizes any iterable, so a hand-built layout
  may pass lists and still be immutable.
- `Revisioned.revision()` must return a value snapshot; mutable fields go in
  copied.
- `Painter.rows` is always exactly `screen.height` rows after a paint.

**The trade-off.** The host pays a little ceremony to build new themes and
snapshots, and gets predictable equality, safe caches and no hidden shared
state. There is no global theme, no global registry and no mutation that
reaches another application in the same process.

**Extend here.** If state is read by `render(width)`, put a copy in
`revision()`; if it is shared across frames, make it frozen.

## What is deliberately out of scope

- A Textual-style retained widget tree, message bus or CSS-like layout.
- Charts, date/colour pickers, a grid layout engine and draggable split
  dividers.
- Cross-pane selection and horizontal wheel scrolling.
- Full UAX #29 grapheme segmentation; the width scanner covers combining
  marks, variation selectors, zero-width joiners and regional indicators,
  then defers to `wcwidth`.
- Runtime colour negotiation by terminal query; capability comes from the
  environment.
- A document memory cap: the document stays fully resident.
- A form inside a `Dialog`: the dialog is a box with a button row, and the
  host owns validation.
- Keymap mnemonics, alias syntax or multi-stroke chords.
- Any sleep in the library or its tests.
- Backward-compatibility shims: a removed name is deleted with its last
  consumer.
