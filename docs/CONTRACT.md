# Contract

This page is the short normative layer for motui 2.1.2. It states the rules
the implementation and the tests are written against; it is not a tutorial.
[ARCHITECTURE](ARCHITECTURE.md) explains the mechanisms, [WIDGETS](WIDGETS.md)
explains how to build with them, and [MIGRATION](MIGRATION.md) holds the 1.x
name table and the removal list. Where this page and the shipped code
disagree, the code is wrong and the change that touches it must make the code
match.

The optional pixel medium (`motui.pixel`, `PixelCanvas`) is provisional in
2.1.2: it may change in a minor until it is frozen. The stable core is the
kernel without pixel, terminal, widgets without `PixelCanvas`, and app.
The demo is not a public contract.

## 1. Values and immutability

- `Size`, `Pos`, `Rect`, `Constraints`, `ScrollAxis`, `Scroll`, `RowSpan`,
  `ScreenLayout`, `Cell`, `Segment`, `Line`, `Surface`, `Style`, `Theme`,
  `Styles`, `Glyphs`, `Border` and every event are frozen values.
- `Line`, `Selection`, `ScrollAxis`, `Scroll` and `ScreenLayout` refuse
  attribute assignment. Build a variant with a method (`Line.clip`,
  `ScrollAxis.reveal`, `Scroll.with_x`) or `dataclasses.replace`.
- Engine values are keyword-only, fully defaulted and grow additively.
  `Surface`, `Constraints`, `ScrollAxis` and `Scroll` are the growth probe
  targets: a new defaulted field must not require a caller edit.
- `Surface.of` and `Surface.clipped` are the supported surface builders.
  Direct field construction is accepted but does not grant the row
  invariant; readers must not assume it.
- A layout is a snapshot: `ScreenLayout.rows`, `body_rows`, `row_blocks`
  and `block_order` are tuples.

## 2. Geometry and scroll

- Every cell coordinate is 0-based. `Rect` holds `x`, `y`, `width`,
  `height` plus `right`, `bottom`, `area`, `contains` and `intersect`.
- `Axis.X` divides width (left/right); `Axis.Y` divides height
  (top/bottom). `Rect.split`, `Split` and every `split` door take the same
  enum. A string axis raises `ValueError`; there are no direction strings.
- `Split(axis, weights=(1, 1), min_size=1)` partitions a rectangle: one
  child per weight, children abutting, `min_size` the floor each child is
  raised to. `weights` are shares (`(2, 1)` gives the first pane twice the
  cells), not fractions.
- `ScrollAxis(offset, content, viewport, sticky)` is one immutable axis.
  `max_offset` is `content - viewport` floored at 0; `clamp(previous_extent)`
  answers a new axis, tail-following when `sticky` and the caller's previous
  bottom was reached. `reveal(first, last)` and `thumb` are the other verbs.
- `Scroll(x, y)` is the two-axis value. The vertical axis defaults to
  `sticky=True`. `Viewport.scroll` and `ScrollPanel.scroll` answer it;
  `Scroll.with_x` / `with_y` replace one axis.
- `Viewport.layout(width, height)` produces exactly `height` rows: fixed
  top rows, the scrolling body, fixed bottom rows. Body rows are blank
  padded below the content so the fixed regions stay at the screen edges.
- `ScreenLayout.row_blocks` is the ownership table: one
  `(section_id, row_within_section)` or `None` per screen row, in painting
  order. `block_order` lists every document section in order so two
  addresses can be ordered without embedding order in ids.
- `Hit.row`/`Hit.col` are 0-based within the section's own rows;
  `Hit.col` is measured against the pane's inner rect. A hit outside the
  screen or a pane is `None`, never clamped. Section ids are unique across
  the whole frame, not only within one document.
- `RowSpan(first, last)` is an inclusive range of screen rows: the
  visible body rows a pane reports from its last composition.

## 3. Row model and the content gate

```python
@dataclass(frozen=True, slots=True)
class Segment:
    text: str
    style: Style = Style()
    link: str | None = None
    action: str | None = None

@dataclass(frozen=True, slots=True)
class Cell:
    char: str = " "
    style: Style = Style()
    link: str | None = None
    action: str | None = None
```

- `Segment` and `Cell` construction is the one content door. Control
  characters (C0, DEL, C1) are deleted; a tab becomes one space. `link`
  and `action` pass the same gate, and an empty result becomes `None`.
- `link` participates in equality; `action` does not (it never reaches a
  byte). Both survive `with_style`, cuts, wraps and coalescing.
- `Segment.width` is the display width through `text.visible_width`.
  Width is never computed from `len()`.

`Line` is one immutable visual row:

| Member | Rule |
|---|---|
| `Line.from_text(text, style=None)` | one segment; `""` is an empty row |
| `text` / `width` / `segments` | plain text, display width, tuple view |
| `reflow(mode, width) -> list[Line]` | the one width response |
| `clip(mode, width) -> Line` | the single-row form of `reflow` |
| `pad(width)` | append spaces; never truncates |
| `fill(width, style=NONE)` | grow with `style` underneath the content |
| `Line.filled(width, style=NONE)` | a fresh row of spaces |
| `merge_span(start, end, style)` | merge a style over a column range |
| `overlay(base)` | paint this row on top of `base`; a transparent cell keeps the base |
| `+` | concatenate runs |

`WrapMode` is the width vocabulary:

| Mode | Rows | Behavior |
|---|---|---|
| `WORD` | 1..N | word-aware wrap, over-long runs hard-broken |
| `CHAR` | 1..N | hard character wrap |
| `ELLIPSIS` | 1 | tail cut with a one-column `...` marker |
| `CLIP` | 1 | hard cut, no marker |
| `OVERFLOW` | 1 | the row unchanged, even wider than the limit |

Module-level row utilities remain for code that does not own a `Line`
value: `action_at(line, col)`, `cut_line(line, start, end)`,
`slice_line(line, start, end)`, `wrap_line(line, width)`. `text.width`,
`text.wrap`, `text.spans`, `text.fit`, `text.ellipsize`, `text.index_at`
and `text.bounds` are the measurement vocabulary.

## 4. Surface invariants

- `Surface(width=w, rows=(...))` is a block of rows at one content width.
- `Surface.of(rows, width)` clips every row at a cell boundary and pads
  short rows to exactly `width`.
- `Surface.clipped(rows, width)` clips every row and leaves short rows
  short; it is the byte-stable builder components use.
- `Surface.blank(size)` returns `height` empty rows of width 0; it does
  not pad each row.
- A surface row is never wider than `surface.width`. `OVERFLOW` content is
  the deliberate exception on the component side: a component may answer a
  wider `Surface`, and a container clips it at its own edge.
- `Surface.overlay(base)` paints this surface on top of `base`, row by row.
  The result is `max(self.width, base.width)` by `max(self.height,
  base.height)`, normalized with `Surface.of`. `self` is the top layer; a
  missing row is an empty one.
- `Surface` is a read-only sequence of `Line` values (`len`, indexing,
  iteration).

## 5. Component protocol

```python
class Component(Protocol):
    def render(self, c: Constraints) -> Surface: ...
```

- `Constraints.width` is required and non-negative; `max_height` is
  `None` for natural height or a non-negative row budget.
- A component must honor `max_height` itself. `Section` enforces it again
  as a final guard, along with a width clip, but a well-behaved component
  already fits.
- `Surface.width` is the content width. Rows may be shorter (the painter
  pads by clearing the row); `OVERFLOW` is the one mode that may be wider.
- Rendering is pure with respect to time: no clock reads, no I/O, no
  terminal bytes. Animation writes state and calls `touch()`.
- Caching is automatic for a `Widget`: `Section` keys its row cache on
  `(width, max_height, widget.generation)` and `touch()` moves the
  generation. A pure component without a `generation` counter is rendered
  fresh on every call.

Interactive components share one hierarchy in `motui.widgets.base`:

```text
Widget
├── ResultWidget          # _result + take()
│   ├── ActionWidget      # disabled / hint / activate / toggle / on_action
│   │   └── Collapsible
│   ├── CursorWidget      # index / selected / select / move / home / end
│   ├── Text / Markdown   # inline action payload
│   ├── Form
│   └── Dialog
├── Drawing               # width / height / resize / fit / surface / render
│   ├── Canvas
│   └── PixelCanvas
└── Container             # children / child_at
    ├── Row / Column / Stack
    └── Padding / Panel / Align / ScrollPanel
```

`Drawing` is the internal base of `Canvas` and `PixelCanvas`; it is not
exported from `motui.widgets`.

- `ResultWidget` owns one pending value, initialized to the private
  sentinel `_MISSING`. `take()` answers the pending value and clears it.
  A legal `None` payload and an empty slot both answer `None`; the caller
  distinguishes them by whether it called `take()` at all (the dialog
  cancel signal). Only `activate()` and `toggle()` write pending.
- `ActionWidget` adds `disabled`, `hint`, `activate()` and `toggle()`.
  Its `on_action` routes exactly `activate` and `toggle`; every other name
  declines.
- `CursorWidget` owns the `Cursor` arithmetic and five subclass hooks:
  `_entry_count`, `_entry_at`, `_cursor_disabled`, `_cursor_wraps` and
  `_page_size`. `index` is an assignable `int` (the setter delegates to
  `select()`, and an empty collection answers `0`); `selected` is a
  read-only item answered by `_entry_at(index)`.
- `keymap` is a `Keymap` descriptor. The class attribute answers the class
  table; the instance attribute answers that instance's own copy.
  Assigning a mapping on an instance replaces only its copy.
  `Widget.__init__` installs that copy from `type(self).keymap`.
- Every cursor verb clears a pending result before it moves: a move is a
  state change, not a pick. `activate()`/`toggle()` are the only writers.

## 6. Document and Section

```python
class Section:
    id: str
    widget: Component
    placement: Placement       # FLOW | TOP | BOTTOM
    sizing: Sizing             # NATURAL | FILL
```

- `Document.add(component, *, id=None, placement=FLOW, sizing=NATURAL)`
  answers the `Section`. A missing id is generated as `b0`, `b1`, ... with
  collisions skipped. Duplicate ids raise `ValueError`.
- `Document.get(id)` and `Document.remove(id)` answer the same `Section`;
  a missing id raises `KeyError`.
- At most one `FILL` section exists, it must be `Placement.FLOW`, and no
  flow section may follow it. `TOP`/`BOTTOM` sections are natural height.
- `App.add`, `Workspace.add` and `Pane.add` all answer a `Section`;
  `App.get`/`remove` and `Workspace.get`/`remove` do too.
- The section row cache is keyed `(width, max_height, widget.generation)`
  and lives on the section. It dies with the section; nothing prunes it
  globally. `rows(c)` returns a copy the caller owns, `rows_view(c)`
  borrows the cache, and `row_count(c)` returns the height.
- In-place mutation of a widget's list or buffer must call `touch()`; an
  attribute assignment does it automatically.
- `Fill` remains a document form: `sizing=Sizing.FILL`, optionally through
  `App.fill(component)` / `Workspace.fill(component)`. There is no
  `PaneContent` union in 2.0.
- `Placement` and `Sizing` live in `motui.kernel.document` in this
  release; they are not re-exported from `motui.kernel`.

## 7. Frame and Pane

- A `Pane` is a workspace object: it has a stable id, a rectangle, a
  viewport and a tuple of `Chrome` bands. Split and close mutate the frame
  tree in place; pane identity survives.
- A `Split` holds `axis`, `weights` and `min_size`; `Frame.retile`
  re-divides the same tree for a new screen size.
- A `Chrome` names its `edge` (`"left"`, `"right"`, `"top"`,
  `"bottom"`), its size, its painter and its `scope` (`"pane"` or
  `"body"`). A body band spans only the pane's scrolling window.
- Docks are pane-like rectangles above and below the pane area. They are
  hit-testable and selectable, but never take focus and never split.
- `Frame.compose(width, height)` is the only composition entry. It
  applies chrome budgets, pane content, granted bands and the overlay
  registry in that order.
- `Frame.revision` counts structural mutations (split, close, chrome,
  overlay, band) so a composition can reuse its tiling. It is not a row
  cache; content invalidation uses `widget.generation`.
- Overlay layers are ordered: `background`, `content`, `selection`,
  `chrome`, `overlay`, `modal`, `tooltip`, `toast`.

## 8. Widgets: capabilities, hooks and the tree

```python
class Widget:
    parent: Widget | None
    children: list[Widget]
    theme: Theme | None
    styles: Styles | None
    focused: bool
    hover: bool
    generation: int

    focusable = False
    clickable = False
    hoverable = False
    activatable = False
    focus_scope = False
    keymap = Keymap({})

    def walk(self) -> Iterator[Widget]: ...
    def touch(self) -> None: ...
    def group(self, name: str) -> object: ...

    def on_key(self, e: KeyEvent) -> bool: ...
    def on_mouse(self, e: MouseEvent) -> bool: ...
    def on_paste(self, e: PasteEvent) -> bool: ...
    def on_resize(self, e: ResizeEvent) -> None: ...
    def on_focus(self, gained: bool) -> None: ...
    def on_click(self, pos: Pos) -> bool: ...
    def on_hover(self, pos: Pos | None) -> bool: ...
    def on_drag(self, pos: Pos, phase: str) -> bool: ...
    def on_action(self, name: str) -> bool: ...
    def take(self) -> object | None: ...
```

- A hook returns `True` only when it consumed the input. Unknown actions
  and disabled controls return `False`, so routing continues.
- A capability flag is a promise: when `focusable`, `clickable`,
  `hoverable` or `activatable` is `True`, the matching door exists and is
  callable without raising. `focus_scope` keeps focus routing inside the
  subtree.
- `on_action` routes this fixed vocabulary: `prev`, `next`, `first`,
  `last`, `page_prev`, `page_next`, `activate`, `toggle`, `open`, `close`.
  `activate`/`toggle` delegate to their verbs; `prev`/`next` answer
  `move(-1)`/`move(1)`; `first`/`last` answer `home()`/`end()`;
  `page_prev`/`page_next` step by `_page_size`. Unknown names and disabled
  targets answer `False`. State-changing actions clear a pending result;
  only `activate`/`toggle` write one.
- `children` is the only tree. Assigning it points every child that has a
  `parent` attribute at this widget. `walk()` is preorder, includes `self`,
  de-duplicates by identity and visits a non-widget child.
- Assigning any public attribute calls `touch()`, which increments
  `generation` on this widget and every ancestor. `parent` and underscore
  attributes do not touch. In-place mutation of a list or buffer requires
  an explicit `touch()`.
- `keymap` is the `Keymap` descriptor from §5: `type(widget).keymap` is
  the class table, `widget.keymap` is the instance copy, and the router
  reads the instance copy. Assigning a mapping to `widget.keymap` replaces
  only that copy.
- `index` is assignable (delegating to `select`); `selected` is read-only.
  The vocabulary is:

| Axis | Contract |
|---|---|
| states | `index`, `selected`, `marked`, `value`, `checked`, `open`, `text`; state stays readable after `take()` |
| verbs | `activate`, `toggle`, `select`, `move`, `advance`, `take` |
| action names | `prev`, `next`, `first`, `last`, `page_prev`, `page_next`, `activate`, `toggle`, `open`, `close` |
| results | `bool`, an item/value, a table row object, a `TreeNode`, a label, a `dict`, an inline payload, a list of values |

- The focus ring is the preorder list of `focusable` nodes rooted at every
  pane and dock document. A `focus_scope` node joins the ring itself and
  stops the descent. The focus tier falls back to `on_action("activate")`
  for both `enter` and `space` on an `activatable` target; a text field
  consumes both keys itself.
- `take()` reads one one-shot result and clears it. `None` means "nothing
  pending"; `False`, `0` and `""` are real results. The pending sentinel
  distinguishes a legal `None` payload internally; the caller distinguishes
  it by having called `take()`.
- There is no per-widget result callback. Collect with `walk()` plus
  `take()`.
- Styles resolve through `Theme.group(name)` at render time. `Widget.group`
  is the per-widget door: an explicit `styles` override wins whole, then
  the widget's `theme`, then `DEFAULT_THEME`.
- Composition widgets are ordinary widgets: `Stack` overlays its children
  bottom to top, `Align` anchors one child, and `Drawing` is the internal
  sized/cached base of `Canvas` and `PixelCanvas`. Their geometry rules are
  in §9 and [ARCHITECTURE §8](ARCHITECTURE.md#8-composition-and-drawing).

## 9. Component semantics contract

This section is the shared vocabulary. [WIDGETS](WIDGETS.md) maps it to
constructors; where a table and a shipped signature disagree, the code is
normative and the table is the bug.

### 9.1 Construction

- The main content is the single positional parameter; every other
  parameter is keyword-only. The tail order is `glyphs`, `theme`, `styles`,
  `keymap`; an omitted tail parameter is absent from the signature.
- Explicit exceptions: `Diff(before, after)`, `Field(name, component)`,
  `ButtonSpec(label, value=None)`, `Option(label, value=None)` and
  `TreeNode(label, children=())` keep a second positional parameter (their
  remaining fields stay positional-or-keyword); `StatusLine(*, left, right)`
  and `Divider(*, ...)` have no main content; `Sparkline(values, *)` keeps
  its raw sequence.
- `Row`/`Column`/`Stack` take `children` positionally; `Padding`, `Panel`,
  `Align`, `ScrollPanel` and `Collapsible` take their one `child`/`body`
  positionally.
- `Canvas(*, width=0, height=0, plot_marker="cell", ...)` and
  `PixelCanvas(*, width=0, height=0, marker=..., palette=None, ...)` are
  keyword-only and take no `styles`: raw cells do not resolve role groups.
- `PixelCanvas(palette=None)` derives `PixelPalette.from_theme(theme)`;
  an explicit palette always wins.
- `ProgressBar(value=0.0, *, maximum=1.0, ...)`; `maximum` is positive and
  `value` clamps into `[0, maximum]`.

### 9.2 State

| Name | Type | Access | Meaning | Components |
|---|---|---|---|---|
| `index` | `int` (0 when empty) | read/write | cursor row | Tabs, MenuBar, NavList, List, Table, Tree, Select, MultiSelect, RadioGroup, CheckboxGroup, Autocomplete, ContextMenu, Form, Dialog |
| `selected` | item or `None` | read-only | item under the cursor (Table row, Tree `TreeNode`, Form `Field`) | the same cursor family |
| `marked` | `MarkSet` of source rows | read/write | sticky multi-selection | List, Table, MultiSelect, CheckboxGroup |
| `value` | `int` / `float` | read/write | scalar value | Slider, ProgressBar |
| `checked` | `bool` | read/write | boolean mark | Checkbox |
| `open` | `bool` | read/write | fold or dropdown | `TreeNode`, `Collapsible`, `ComboBox` |
| `text` | `str` | read/write | text content | Text, Input, Editor, Markdown |

The old tree-root, node-fold, dropdown-flag and public label-list
attributes are removed. `Table.index` is always an `int` (never `None`),
`ProgressBar.fraction` is read-only (constructed from `value` and
`maximum`), and `Canvas.plot_marker` replaces the old marker attribute.

### 9.3 Verbs

| Verb | Semantics | Returns |
|---|---|---|
| `activate()` | main operation: press, pick, submit or fold | `bool` |
| `toggle()` | flip a boolean, a mark or a fold | `bool` |
| `select(index)` | place the cursor exactly (clamped; disabled rows refuse) | `bool` |
| `move(delta)` | step the cursor or value over disabled rows | `bool` |
| `advance()` | next animation frame (`Spinner` only) | `None` |
| `take()` | read the one-shot result | `object \| None` |

`on_action` follows this table:

| Name | Effect |
|---|---|
| `prev` / `next` | `move(-1)` / `move(1)`; the verb's real result, not "key consumed" |
| `first` / `last` | `home()` / `end()` |
| `page_prev` / `page_next` | `move(-_page_size(...))` / `move(+_page_size(...))` |
| `activate` / `toggle` | the matching verb; the only writers of a pending result |
| `open` / `close` | set `open` where the state exists; otherwise `False` |

A state change (`select`, `move`, `home`, `end`, open/close, a cursor
click) clears a pending result. A disabled control, a disabled row and an
unknown action answer `False` and never raise.

### 9.4 Results

| Family | `take()` answers |
|---|---|
| Button / Link | `bool` (activation) |
| Checkbox / Collapsible | `bool` (new checked/open state) |
| Select / RadioGroup / Autocomplete / ComboBox / ContextMenu | the chosen option's `value` (its label when `value is None`) |
| MultiSelect / CheckboxGroup | the marked values in row order |
| List | the activated item (`str`) |
| Table | the activated row object (never an index) |
| Tree | the activated `TreeNode` |
| Tabs / MenuBar / NavList | the activated label/item (`str`) |
| Form | the submitted `dict[str, object]` |
| Dialog | the pressed button's `ButtonSpec.value` |
| Text / Markdown | the inline action payload (`str`) |
| Slider / Input / Editor | no `take()`; their state is the answer |

`take()` reads once and clears. `_MISSING` is the internal empty slot, so a
legal `None` payload is still a result the caller can recognize by having
called `take()`.

### 9.5 Style resolution

The theme is still shared role groups, not a per-component recipe.

| Rule | Contract |
|---|---|
| `SurfaceStyles.control` | field and neutral-button floor |
| `SurfaceStyles.accent` / `danger` | primary/danger button floors |
| `SurfaceStyles.inactive` | unfocused cursor band |
| `ControlStyles` | only `hover`, `focus`, `active`, `disabled`, plus `overlay(hovered=, focused=, pressed=, disabled=)` |
| precedence | `disabled > pressed > focused > hovered`; the answer is merged over the component's own base |
| `ButtonKind.NEUTRAL` | `surfaces.control` + `text.base` |
| `ButtonKind.PRIMARY` | `surfaces.accent` + `text.inverse` |
| `ButtonKind.GHOST` | no floor + `content.accent` |
| `ButtonKind.DANGER` | `surfaces.danger` + `text.inverse` |
| field floor | Input/Editor rows sit on `surfaces.control` |
| dialog floor | Dialog interior cells sit on `surfaces.raised` |
| links/strips | Link, Tabs and MenuBar show focus through `controls.overlay(focused=True)` |
| flat | `Theme.flat()` maps every `surfaces.*` token to `NONE` and keeps state legible through attributes |

`ControlStyles.base`, `ControlStyles.active` and `ControlStyles.band()` are
removed; the action family's one band is `action_band(kind, theme, ...)`.

### 9.6 Keys

| Table | Binding |
|---|---|
| `CURSOR_KEYMAP` | `up`/`left` → `prev`; `down`/`right` → `next`; `home`/`end` → `first`/`last`; `page_up`/`page_down` → `page_prev`/`page_next` |
| `TREE_KEYMAP` | the cursor table with `left` → `close` and `right` → `open` |
| mark-carrying rows | `space` → `toggle` on List, Table, MultiSelect and CheckboxGroup |
| text fields | `Input`/`Editor` keep their own `TextBuffer` tables (`DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP`, `EDITOR_SUBMIT_KEYMAP`) |
| focus fallback | `enter` and `space` activate an `activatable` target after the widget's own `on_key` declines |

`Keymap` is the descriptor from §5: the class body spells the family table
once (`keymap = Keymap({...})`), and each instance gets a copy. Rebinding
`widget.keymap["j"] = "next"` touches one instance, never the class.

## 10. Runtime, Workspace, App and Terminal

- `App(theme=None, terminal=None, throttle=0.03, auto=True, title="",
  on_selection=None, handlers=None)`. `terminal` is a `TerminalOptions`;
  there are no separate `mouse`/`hover`/`screen`/`keys` arguments.
- `Runtime(terminal, *, throttle=0.03, interactive=False, theme=None)` owns
  the session (terminal, painter, clock, timers, pump, dirty flag) and
  exposes `workspace`. It has no `add`/`get`/`frame`/`hit`/`split`/`fill`/
  `rows` of its own.
- `Workspace` owns the document, frame, panes, docks, selection and hit
  test: `add/fill/get/remove/system/split/dock/undock/scroll_*/reveal/
  pane_at/visible_range/hit/hit_leaf/set_selection`. The six session
  delegates `clock/every/refresh/screen/painter/copy_to_clipboard` are the
  controller host seam; a host uses `App.runtime` for the session.
- `TerminalOptions` is frozen and keyword-only: `stream`, `input`, `mouse`,
  `paste`, `focus_events`, `color_mode`, `sync`, `screen`.
- `MouseMode` is exactly `OFF`, `BUTTON`, `DRAG`, `MOVE`. It maps to the
  screen's mouse/hover switches once, at terminal construction.
- `App.run()` / `run_async()` / `run_session(body)` own the session. The
  runtime enters the screen, starts the pump, calls `on_start`, loops, calls
  `on_stop` and tears down exactly once.
- `App.dispatch` runs `App.handlers`: `DEFAULT_HANDLERS` by default, an
  explicit tuple when passed, `()` when `auto=False` and no handlers were
  passed. Each `Handler(app, event) -> bool` returns whether it consumed
  the event; the first `True` ends dispatch.
- `Runtime.every(period, fn, catch_up="skip")` and
  `Runtime.animation(hz, draw)` answer a cancellable `Timer`. Deadlines are
  absolute; `catch_up` is `"skip"` or `"coalesce"`. `invalidate()` marks
  dirty; `paint_now()` paints immediately.
- `Runtime.read_event()` is a pure read: no scroll, focus or exit policy
  beyond returning `None` at EOF.
- The dispatch order in [ARCHITECTURE §6](ARCHITECTURE.md#6-event-dispatch)
  is normative. A `ResizeEvent` is broadcast to every widget first and is
  never consumed by the broadcast.
- `Screen` is an ABC: `width`, `height`, `live`, `size`, `encoding`,
  `enter`, `leave`, `write`, `flush`, `refresh_size`, `close` and
  `copy_to_clipboard` (default `False`). `color_mode` is a class
  capability. A custom screen subclasses it; consumers treat it as a
  protocol.
- A non-live screen writes no bytes, keeps the logical rows and receives a
  final plain-text dump at teardown.
- One paint is one write and one flush, optionally wrapped in the
  synchronized-update pair. An unchanged frame writes zero bytes.

## 11. Errors

| Situation | Answer |
|---|---|
| duplicate section id | `ValueError` |
| missing section or command | `KeyError` |
| a non-`Axis` split axis, or `Axis` outside X/Y | `ValueError` |
| a non-`Placement` dock placement, or `Placement.FLOW` | `ValueError` |
| `FILL` outside the flow, a second `FILL`, or flow after `FILL` | `ValueError` |
| unknown `WrapMode` / unknown scroll `axis` | `ValueError` |
| unknown `Align` anchor, bad Dialog `align` | `ValueError` |
| non-positive `ProgressBar.maximum`, unknown `ButtonKind`/pixel `Marker` | `ValueError` |
| negative width or height budget | `ValueError` |
| `open_palette` with a non-`CommandRegistry` | `TypeError` |
| disabled control, disabled row or a miss | `False`, never an exception |
| twice-docked placement, duplicate pane edge | `RuntimeError` |
| `App.toast` with `auto=False` | `RuntimeError` |
| render failure | propagate; the painter never catches it |

A negative drawing size is not an error: `Drawing.resize` clamps both
dimensions at zero, and an unchanged size is a no-op.

## 12. Public surface

The public facades and their current `__all__` sizes are:

| Facade | Names |
|---|---|
| `motui` | 40 |
| `motui.kernel` | 61 |
| `motui.pixel` | 13 |
| `motui.terminal` | 17 |
| `motui.widgets` | 51 |
| `motui.app` | 19 |
| `motui.testing` | 5 |

`tools/api.py --check` pins 244 rows: the 206 exported names above plus 38
recorded public method signatures on the pinned provisional classes
(`PixelCanvas` 26, `pixel.Raster` 12). A name lives in exactly one facade;
there are no alias modules and no forwarding packages.
`motui.terminal.ansi` is private: it is the only place escape bytes are
constructed, and it is not re-exported.

The 2.0/2.1/2.1.2 removal list and the replacements are in
[MIGRATION](MIGRATION.md). No alias is provided for a removed name.
