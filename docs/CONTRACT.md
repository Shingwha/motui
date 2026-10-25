# Contract

This page is the short normative layer for motui 2.0. It states the rules
the implementation and the tests are written against; it is not a tutorial.
[ARCHITECTURE](ARCHITECTURE.md) explains the mechanisms, [WIDGETS](WIDGETS.md)
explains how to build with them, and [MIGRATION](MIGRATION.md) holds the 1.x
name table and the removal list. Where this page and the shipped code
disagree, the code is wrong and the change that touches it must make the code
match.

## 1. Values and immutability

- `Size`, `Pos`, `Rect`, `Constraints`, `ScrollAxis`, `Scroll`,
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

## 2. Geometry

- Every cell coordinate is 0-based. `Rect` holds `x`, `y`, `width`,
  `height` plus `right`, `bottom`, `area`, `contains` and `intersect`.
- `Axis.X` divides width (left/right); `Axis.Y` divides height
  (top/bottom). `Rect.split` and `Split.rects` take the same enum.
- `Split` uses `orientation` strings (`"vertical"` divides by width,
  `"horizontal"` divides by height) and ratios; `min_size` is a floor.
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
- A component that wants the section row cache answers `revision()`. The
  snapshot must have value semantics and cover every input the rows read.
  `None` means "no snapshot" and disables caching for that component.

## 6. Document and Section

```python
@dataclass
class Section:
    id: str
    widget: Component          # component is an alias
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
- The section row cache is keyed `(width, max_height, revision)` and lives
  on the section. It dies with the section; nothing prunes it globally.
  `rows(c)` returns a copy the caller owns, `rows_view(c)` borrows the
  cache, and `row_count(c)` returns the height.
- `Fill` remains a document form. `App.fill(component)` clears the pane
  document and adds the component with `sizing=Sizing.FILL`; there is no
  `PaneContent` union in 2.0.
- `Placement` and `Sizing` live in `motui.kernel.document` in this
  release; they are not re-exported from `motui.kernel`.

## 7. Frame and Pane

- A `Pane` is a runtime object: it has a stable id, a rectangle, a
  viewport and a tuple of `Chrome` bands. Split and close mutate the frame
  tree in place; pane identity survives.
- A `Split` holds orientation, ratios and `min_size`; `Frame.retile`
  re-divides the same tree for a new screen size.
- A `Chrome` names its `edge` (`"left"`, `"right"`, `"top"`,
  `"bottom"`), its size, its painter and its `scope` (`"pane"` or
  `"body"`). A body band spans only the pane's scrolling window.
- Docks are pane-like rectangles above and below the pane area. They are
  hit-testable and selectable, but never take focus and never split.
- `Frame.compose(width, height)` is the only composition entry. It
  applies chrome budgets, pane content, granted bands and the overlay
  registry in that order.
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
    keymap: Mapping[str, str] = {}

    def walk(self) -> Iterator[Widget]: ...
    def touch(self) -> None: ...

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
- `children` is the only tree. Assigning it points every child that has a
  `parent` attribute at this widget. `walk()` is preorder, includes `self`,
  de-duplicates by identity and visits a non-widget child.
- Assigning any public attribute calls `touch()`, which increments
  `generation` on this widget and every ancestor. `parent` and underscore
  attributes do not touch. In-place mutation of a list or buffer requires
  an explicit `touch()`.
- An instance `keymap` merges over the class table at the routing site:
  `{**type(widget).keymap, **widget.keymap}`.
- The focus ring is the preorder list of `focusable` nodes rooted at every
  pane and dock document. A `focus_scope` node joins the ring itself and
  stops the descent.
- `take()` reads one one-shot result and clears it. `None` means "nothing
  pending"; `False`, `0` and `""` are real results. State attributes
  (`selected`, `checked`, `text`, `open`) stay readable and are not
  cleared by `take()`.
- There is no per-widget result callback. Collect with `walk()` plus
  `take()`.

## 9. Runtime, App and Terminal

- `App(terminal=TerminalOptions(...))` is the recommended construction.
  The 1.x arguments remain accepted and are folded into `TerminalOptions`;
  a supplied `terminal=` wins over them.
- `TerminalOptions` is frozen and keyword-only: `stream`, `input`, `mouse`,
  `paste`, `focus_events`, `color_mode`, `sync`, `screen`.
- `MouseMode` is exactly `OFF`, `BUTTON`, `DRAG`, `MOVE`. It maps to the
  screen's mouse/hover switches once, at terminal construction.
- `App.run()` / `run_async()` / `run_session(body)` own the session. The
  runtime enters the screen, starts the pump, calls `on_start`, loops, calls
  `on_stop` and tears down exactly once.
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

## 10. Errors

| Situation | Answer |
|---|---|
| duplicate section id | `ValueError` |
| missing section or command | `KeyError` |
| `pin` and `placement` together | `ValueError` |
| `FILL` outside the flow, a second `FILL`, or flow after `FILL` | `ValueError` |
| unknown `WrapMode` / unknown scroll `axis` | `ValueError` |
| negative width or height budget | `ValueError` |
| disabled control, disabled row or a miss | `False`, never an exception |
| `App.toast` with `auto=False` | `RuntimeError` |
| render failure | propagate; the painter never catches it |

## 11. Public surface

The public facades and their current `__all__` sizes are:

| Facade | Names |
|---|---|
| `motui` | 40 |
| `motui.kernel` | 61 |
| `motui.terminal` | 17 |
| `motui.widgets` | 46 |
| `motui.app` | 16 |
| `motui.testing` | 4 |

`tools/api.py --check` pins every exported name and signature (184 rows).
A name lives in exactly one facade; there are no alias modules and no
forwarding packages. `motui.terminal.ansi` is private: it is the only place
escape bytes are constructed, and it is not re-exported.

The 2.0 removal list, the names that remain as compatibility entries and
their replacements are in [MIGRATION](MIGRATION.md). No alias is provided
for a removed name.
