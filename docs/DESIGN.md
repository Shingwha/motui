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
- the host keeps the event loop and decides what every input means.

**The trade-off.** There is no automatic parent/child layout engine, no
message bus and no per-widget event bubbling. Containers are explicit
components (`Row`, `Column`, `Padding`, `Panel`, `ScrollView`), and the host
routes events. In exchange, every layer is inspectable, and the library can
run the same code headless.

**Extend here.** New content starts as a component with `render(width)`. New
grouping starts as a container with `child_at(row, col)`.

## Layers and the Host seam

Dependencies point one way:

```
kernel  ->  keys  ->  widgets  ->  commands
                               ->  interaction  ->  app
testing (/app, /kernel)
```

| Layer | May import | Contents |
|---|---|---|
| `motui.kernel` | stdlib, `wcwidth` | rows, styles, palettes, themes, glyphs and borders, events, document model, screen, viewport, painter, frame, selection, chrome, clipboard, `Host` |
| `motui.keys` | `kernel` | byte decoder, keymaps, raw and console event sources |
| `motui.widgets` | `kernel`, `keys.keymap` | the component library, Markdown rules, syntax highlighting |
| `motui.commands` | `widgets.choice` | `Command`, `CommandRegistry`; no screen, no widgets beyond `Option` |
| `motui.interaction` | `kernel`, `Host` | focus, pointer, gesture, find, modal, palette, overlays, scrollbar |
| `motui.app` | everything below | `TUI`, the driver and composition root |
| `motui.testing` | `app`, `kernel` | `headless_tui`, `snapshot`, `ScriptedEvents` |

The root module is a curated face of 37 names. Every other public name lives
at exactly one layer namespace; `tests/test_api.py` pins every facade.

**The Host seam.** Interaction tiers need a running driver, but `app`
imports `interaction` to mount it. The cycle is broken by
`motui.kernel.host.Host`, a narrow protocol the driver structurally
satisfies:

```python
class Host(Protocol):
    screen: Screen
    frame: Frame
    document: Document              # the focused pane's document
    selection: Selection | None
    selection_pane: Pane | None
    scroll_keys: dict[str, int]
    painter: Painter

    def refresh(self) -> None: ...
    async def read_event(self) -> Event | None: ...
    def clock(self) -> float: ...
    def every(self, seconds: float, fn: Callable[[], object]) -> EveryHandle: ...
    def hit(self, x: int, y: int) -> Hit | None: ...
    def reveal(self, bid: str, row: int) -> bool: ...
    def set_selection(self, selection: Selection | None, *, pane=None) -> None: ...
    def visible_range(self, pane=None) -> RowRange | None: ...
    def copy_to_clipboard(self, text: str) -> bool: ...
    def make_input(self, **kwargs: object) -> QueryInput: ...
    def make_autocomplete(self, options: Sequence[object], **kwargs: object) -> FilterList: ...
```

The two factories are what keep `interaction` from importing `widgets`:
`Find` and `CommandPalette` build their query rows through the host instead of
constructing an `Input` directly.  `QueryInput`, `FilterList` and
`OptionLike` are the narrow protocols in `motui.kernel.host` that name what
those factories return, so the tier types its fields without importing the
widget layer.

**The trade-off.** The protocol is wider than the minimum every tier needs,
because a narrower seam would force one protocol per controller. It is still
much smaller than `TUI`, and it is the only driver surface a tier may rely
on.

**Extend here.** A new tier goes in `motui.interaction`, imports `kernel`
and `Host`, and asks the host for any component it needs.

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
Hit(pane, block, row, col, leaf, leaf_row, leaf_col)
```

- `row` and `col` are 0-based inside the block's own rows.
- `col` is measured against the pane's **inner rectangle** (chrome
  subtracted), not the outer pane rectangle.
- `leaf` is the deepest component under the cell when `hit_leaf` or
  `descend` resolved one.
- A cell outside the screen, outside every pane, or over blank fill is
  `None`. Coordinates are never clamped to the nearest block.

Containers make the descent possible. `Container.child_at(row, col)` returns
`(child, row, col)` in the child's coordinates, or `None` for cells the
container owns itself (borders, padding, gaps). The geometry comes from the
container's **last render**; a container that has never rendered declines
every cell, so a hit test never invents a layout. `descend` is depth-guarded
against a malformed container that returns itself.

Block ids are unique across the whole frame, not merely within one document.
A split's second pane does not get a second `b0`; automatic ids are picked
over every pane's document.

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

**Extend here.** A new escape sequence goes in `motui.keys.decoder`; a new
input transport goes in `motui.keys.sources`. Add the event type to
`motui.kernel.events` only when the model itself changes.

## The driver lifecycle

`TUI` owns the screen, the frame, the pump and the document facade. Its
constructor is a set of capability switches, not app configuration:

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
| `focus_policy=` | which pane a button press focuses |
| `theme=` | the theme the driver's own chrome reads |

There are three entry points:

```python
await tui.run_session(body)   # run your coroutine, then tear down
await tui.run_async()         # run until tui.exit()
tui.run()                     # synchronous wrapper around run_async()
```

`run_session` enters the screen when it is live, starts the pump, awaits
`body(tui)`, and always tears down: on normal return, on an exception, and
on `exit()`. A `KeyboardInterrupt` from the body is treated as `exit()`.
Every run resets timers, selection and the painter's diff base; an owned key
source is closed at teardown and reattached on the next run, so the same
`TUI` can run more than once.

Inside the loop, the host reads one event at a time:

```python
event = await tui.read_event()   # None at EOF or when the screen is not live
tui.refresh()                    # mark dirty; the pump paints
tui.exit()                       # unblock reads and end the run
```

`read_event` intercepts the `scroll_keys` table (page keys and the wheel by
default), scrolls the correct viewport, and continues reading. It also runs
the focus policy on mouse presses: a press focuses the pane under the
pointer, a wheel notch scrolls without stealing focus. The table is a plain
per-instance dict; rebind or delete entries to regain an event.

The pump repaints at most one frame per throttle window when dirty, and runs
due `every(seconds, fn)` callbacks. `clock()` is the monotonic seam;
`tick(now)` advances one step and returns the delay until the next wake.
The library never sleeps.

On a **non-live** screen (a pipe or file), the run stays silent, `read_event`
returns `None` even with a source attached, and teardown dumps the final
screen as plain text. That is how the demo's piped replay works.

**The trade-off.** The host owns the event loop, the body and the dispatch
order. The library cannot hide a bug in an async task you did not write, and
it cannot surprise you with a thread.

**Extend here.** A new run mode belongs in `app.py`; a new capability switch
belongs in `TUI.__init__` and, if a tier needs it, in `Host`.

## Documents, blocks and caching

`Document` is an ordered, id-addressable collection. `add` generates `b0`,
`b1`, ... when no id is given and raises on a duplicate; `get` and `remove`
raise `KeyError` when missing; `blocks()` returns a snapshot.

A `Block` has exactly two lifecycle states: `OPEN` and `SEALED`. There is no
committed state, because a full-screen rewrite has no terminal history to
append into. `block.seal()` freezes content; sealing twice raises.

Each block owns its row cache. `Block.rows(width)` is the one read that may
return a memory:

- a **sealed** block is always cached by width;
- an **open** block is cached only when its component implements
  `Revisioned` and `revision()` returns a non-`None` snapshot;
- without a snapshot, an open block re-renders on every read.

`Block.render(width)` is the uncached door: "render it again, now".
`Block.rows` returns a fresh list of the same immutable `Line` values, so
callers own the list but not the rows.

The snapshot is the contract that makes caching safe. `Revisioned.revision()`
must return a **value** covering every mutable input `render(width)` reads:
a copy, cheap compared with rendering, and equal values at one width must
mean equal rows. A hovered span, a streamed `text` assignment, a cursor move
or a mark flip changes the snapshot, the cache misses, and even a sealed
block repaints. Returning `None` switches the memory off for an open block.

**The trade-off.** A component author must remember the snapshot. The reward
is that streaming text, live fields and hovered rows do not re-wrap the
document on every frame, and a sealed block is not stale.

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
| API | `tui.add(..., pin="top")` | `tui.dock(viewport, edge=...)` |

`tui.dock(viewport, edge="top"|"bottom", size=None)` parks a viewport in a
frame-level dock. `size=None` derives the height from content; an empty dock
claims no rows and paints nothing; one dock per edge. Docks join the
ownership table, so a footer block resolves through `hit` like any other
block, but a wheel over a dock scrolls the focused pane. `undock(edge)`
releases it.

**The trade-off.** Pins are per-document and scroll with the viewport's fixed
regions; docks are per-frame and survive splits. The host chooses which
guarantee it needs.

**Extend here.** A new pinned behavior belongs in `Viewport.layout`; a new
frame-level region belongs in `Frame` and `TUI.dock`/`_retile`.

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

The wheel and pane focus are driver policy over the frame: `read_event`
routes a wheel report to the pane under the pointer (chrome columns
included), falling back to the focused pane; a press focuses the pane
through the replaceable `tui.focus_policy`. On a one-pane frame every route
is the same by identity.

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

**Extend here.** A new byte sequence belongs in `kernel.ansi`; a new
rendering path belongs in `kernel.lines` or `Painter`, not in a component.

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

Focus has two independent levels. **Pane focus** belongs to the frame:
`frame.focused_pane`, `tui.split`, `tui.focus_policy`. **Widget focus**
belongs to `FocusManager`:

- targets are registered explicitly; the constructor focuses nothing and
  writes no flag;
- a `Focusable` target has one read-write `focused: bool`, which the
  manager rewrites on every move;
- `handle(event)` dispatches to the focused target first, then maps
  `up`/`left` to `move(-1)`, `down`/`right` to `move(+1)` and `enter` to
  `activate()`;
- `click(hit)` descends to the leaf, dispatches `click`, focuses a
  registered target on the first click and activates it on the second;
- `push_trap` / `pop_trap` narrow and restore the target set, which is how
  stacked modals return focus correctly.

`Pointer` owns hover and the stationary click; it needs `TUI(hover=True)`
(DECSET 1003) for button-free motion. A component renders its own `hover`
flag and may implement `hover_at(row, col)` for row-level marking. The
pointer's `True` is a repaint cue, never a claim that the event was consumed.
A leaf's `hint: str` is the tooltip protocol; `Tooltip` paints it beside the
pointer without the pointer knowing.

**The trade-off.** Focus is a layer, not a component responsibility. A
component declares one flag and one rendering rule; the host decides who is
focused and what a click means. The cost is that a host must mount the
manager and route the cycle key itself.

**Extend here.** A new selection action is an `on_end` callable; a new focus
behavior is a `FocusManager` method or a host-side dispatch rule.

## Value semantics

The library separates values you can share from objects you can mutate:

- `Style`, `Color`, `Segment`, `ColorPalette`, `Theme`, `Glyphs` and `Border`
  are frozen, slotted dataclasses, hashable and safe to cache.
- `Theme` is frozen at both levels: each of its ten role groups is a frozen
  value, and `content.headings` is a tuple. `replace(theme, group=...)` is
  the only way to make a variant; there are no derived mappings left.
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
