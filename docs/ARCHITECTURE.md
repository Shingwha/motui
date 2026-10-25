# Architecture

motui is built from one direction of dependency and four kinds of object:
pure values, renderers, terminal edges, and policy. This page describes the
layers, the object model, the lifecycle and the places a host is expected to
extend. The normative rules are in [CONTRACT](CONTRACT.md); the component
catalogue is in [WIDGETS](WIDGETS.md).

## 1. Layers and dependency rules

```
                     motui (root facade, 40 names)
        ┌──────────────┬───────────────┬──────────────────┐
        │              │               │                  │
   motui.widgets   motui.app       motui.terminal     motui.testing
     (46 names)    (16 names)        (17 names)         (4 names)
        │              │               │                  │
        └──────────────┴───────┬───────┴──────────────────┘
                               │
                        motui.kernel (61 names)
```

The rules are enforced by `import-linter` (four contracts in
`pyproject.toml`):

| Rule | Meaning |
|---|---|
| `kernel has no I/O` | `motui.kernel` may not import `os`, `sys`, `io`, `ctypes`, `termios`, `tty`, `select` or `asyncio` |
| `kernel is a leaf` | `motui.kernel` may not import `motui.widgets`, `motui.app`, `motui.terminal` or `motui.testing` |
| `widgets may not import terminal or app` | components depend on the kernel only |
| `terminal may not import widgets or app` | the terminal edge knows bytes, screens and events, not components |

`motui.testing` sits outside both `widgets` and `app`; it composes the
runtime and the terminal for tests. The root facade re-exports a curated
subset and defines no behavior of its own.

## 2. Modules

### kernel

| Module | Responsibility |
|---|---|
| `geom.py` | `Size`, `Pos`, `Rect`, `Axis`; rectangle algebra and split geometry |
| `cell.py` | `Cell`, `Segment`, `Line`, `Surface`; the content gate and the row operations |
| `text.py` | `WrapMode`; width, wrapping, truncation, cluster and tab rules |
| `style.py` | `Style`, `Color`, `ColorMode`, SGR prefix |
| `theme.py` | `Theme` (ten role groups), `ColorPalette`, `Styles`, `DEFAULT_THEME` |
| `glyphs.py` | `Glyphs`, `GLYPHS`, `Border` |
| `events.py` | `Event`, `KeyEvent`, `MouseEvent`, `PasteEvent`, `ResizeEvent`, `FocusEvent`, `EventSource` |
| `document.py` | `Component`, `Section`, `Document`, `Placement`, `Sizing`, `Fill` |
| `layout.py` | `Constraints`, `ScrollAxis`, `Scroll`, `ScreenLayout`, `Viewport`, `ScrollState`, `Scrollable` |
| `frame.py` | `Rect`-based `Pane`, `Split`, `Frame`, `Chrome`, `Separator` |
| `hit.py` | `Hit` and `RowRange` |
| `overlay.py` | the ordered overlay layers and registry |
| `selection.py` | `Selection`, `highlight`, `extract` |
| `keymap.py` | `Keymap`, the input/editor key tables |

### terminal

`screen.py` (`Screen` ABC, `TerminalScreen`, `HeadlessScreen`,
`TerminalOptions`, `MouseMode`), `terminal.py` (`Terminal`, `Capability`),
`decoder.py` (`KeyDecoder`), `keys.py` (`RawTerminalKeys`), `win32.py`,
`capability.py`, `clipboard.py`, `paint.py` (`Painter`), `render.py`
(`styled_line`) and `ansi.py` (private escape constructors; not exported).

### widgets

`base.py` (`Widget`, `Container`, `HasResult`, `Cursor`, `MarkSet`),
`text.py` (`Text`), `markdown/` (`Markdown`, rule registries, syntax seam),
`diff.py`, `rows.py` (`Notice`, `StatusLine`, `ShortcutBar`), `textfield.py`
(`Input`, `Editor`), `textbuf.py` (the editing engine), `choice.py`,
`list.py`, `table.py`, `tree.py`, `tabs.py`, `menubar.py`, `navlist.py`,
`autocomplete.py`, `combobox.py`, `form.py`, `indicators.py`, `layout.py`,
`decor.py`, `collapsible.py`, `action.py`, `dialog.py`, `scroll.py`,
`canvas.py`, `mark.py`, `syntax.py`, `strip.py` and `cursor.py`.

### app

`runtime.py` is the driver: clock, timers, pump, screen, frame, document,
selection and session lifecycle. `workspace.py` is the stateless facade over
one runtime. `application.py` is `App`. The tiers are `focus.py`,
`pointer.py`, `gesture.py`, `find.py`, `modal.py`, `command_palette.py`,
`overlays.py`, `scrollbar.py` and `commands.py`.

### testing

`headless_tui` builds a `Runtime` over a recording `HeadlessScreen` and a
`ScriptedEvents` source; `snapshot` renders the document structure;
`Emulator` consumes painter bytes and rebuilds the cell grid.

## 3. Ownership and construction

Engine values are frozen, keyword-only and fully defaulted, so a later 2.x
field addition does not move a caller's arguments.

| Object | Owns | Constructed by |
|---|---|---|
| `Cell` / `Segment` / `Line` / `Surface` | content and geometry | components and kernel |
| `Section` | id, widget, placement, sizing, one row cache | `Document.add` (including `sizing=Sizing.FILL`) |
| `Document` | an ordered set of sections | host, `Pane`, workspace |
| `Pane` | rect, viewport, chrome, optional split | `Frame` |
| `Frame` | panes, docks, overlays, focus, composition caches | `Runtime` |
| `Widget` | parent/children, theme, styles, flags, hooks | host |
| `Terminal` | one screen, one event source, clipboard | `App` or host |
| `Runtime` | terminal, clock, timers, painter, frame, session | `App` or host |
| `Workspace` | a delegating view of one runtime | `Runtime.workspace` |
| `App` | runtime, workspace, terminal, default tiers | host |

`Surface.of` and `Surface.clipped` are the supported builders; the
dataclass fields exist for readers. `Section` is constructed by `Document`,
`Pane`/`Frame` by the runtime, and `ScreenLayout` by `Frame.compose` or
`Viewport.layout`; a host reads those values rather than building its own.
`Constraints`, `TerminalOptions`, `Styles`, `Theme` and the event values are
ordinary public constructors.

## 4. Lifecycle

```
App.run()
  asyncio.run(App.run_async())
    Runtime.run_session(App._loop)
      Runtime._enter_run: reset, attach keys, Terminal.enter
      start pump task
      App.on_start()
      loop:
        paint once when non-interactive
        Runtime.read_event()          # pure read
        App.dispatch(event)           # first claim wins
        Runtime.refresh()
      App.on_stop()
      Runtime._teardown: stop pump, leave, dump a non-live final screen
```

- `App.run_async()` and `App.run_session(body)` own the same bracket.
- `Runtime.exit()` ends a session; it unblocks a pending read, stops the
  pump and lets teardown run. It is safe from any task.
- A runtime can run more than once. Each run resets timers, selection and
  the painter's diff base; an owned key source is closed and reattached.
- The library never sleeps. `Runtime.clock()` is the time source;
  `Runtime.advance(dt)` moves virtual time; `App.every` and
  `App.animation` schedule against absolute deadlines with
  `catch_up="skip"` or `"coalesce"`.
- One frame is one `Painter.paint` call: one write (wrapped in the
  synchronized-update pair unless `sync=False`) and one flush. An unchanged
  frame writes zero bytes. A non-live screen records logical rows and stays
  silent.

## 5. Rendering pipeline

```
Section.rows(Constraints)            # the section's own row cache
  Component.render(Constraints)      # -> Surface
Viewport.layout(width, height)       # -> ScreenLayout (rows + row ownership)
Frame.compose(width, height)         # panes, docks, chrome, overlays
Painter.paint(ScreenLayout)          # per-row diff -> Screen
```

`Viewport` keeps a private incremental body index keyed on the document's
mutation count and the constraints. It probes each body section's
`revision()` snapshot, re-measures only changed sections and locates the
window by bisect. A section whose component answers no snapshot is
re-rendered on every layout; that is the price of not being able to prove
equality.

`ScreenLayout.row_blocks` and `block_order` carry the ownership table with
the layout, so hit testing, selection highlighting and extraction never
reach back into a live viewport.

## 6. Event dispatch

`App.dispatch` is the default policy. The order is a public contract and
the first claim wins:

1. open `CommandPalette`
2. open `Modal` layers, newest first
3. open `Find`
4. `Toasts`
5. controllers added with `App.mount`, in mount order
6. wheel: horizontal scroller in the hit chain, then vertical scroller,
   then the hit pane, then the focused pane's viewport
7. mouse: drag in flight, selection gesture, pointer, pane focus on press
8. focused control through `FocusManager`
9. page keys
10. `App.bind` callbacks, then `tab` / `s-tab`
11. host hooks `on_key`, `on_mouse`, `on_event`

A `ResizeEvent` is broadcast to every mounted widget's `on_resize` before
the list above and then keeps travelling: the broadcast informs, it never
consumes. `auto=False` mounts no tiers; the host drives the runtime and
calls its own policy.

## 7. Object model details

- **Focus** is derived from the tree. A widget joins the ring by setting
  `focusable = True`; leaves are visited in preorder. `App.focus`,
  `App.focus_next` and `App.focus_previous` are the public ring entries;
  `FocusManager` is the internal tier.
  `focus_scope = True` keeps routing inside a container's subtree (`Form`,
  `Dialog`, `ComboBox`).
- **Invalidation** is automatic. Assigning any public widget attribute
  calls `touch()`, which increments `generation` along the parent chain.
  Underscore attributes and `parent` are plumbing and stay silent. Mutating
  a list or buffer in place requires an explicit `touch()`.
- **Take** is pull-based. `take()` reads the pending value once and clears
  it. `None` means "nothing pending"; `False` and `0` are real results.
  There is no per-widget result callback.
- **Overlays** are ordered by layer name: `background`, `content`,
  `selection`, `chrome`, `overlay`, `modal`, `tooltip`, `toast`.
- **Panes** are runtime objects, not values. Splitting or closing rewrites
  the frame's tree in place; the frame keeps its identity, overlays and
  focus, and each pane keeps its viewport and chrome.
- **Docks** are pane-like regions above and below the pane area. They are
  hit-testable and selectable but take neither focus nor splits.

## 8. Extension points

| Add | Do this | Do not |
|---|---|---|
| a component | a new `Widget` subclass (or just `render`) in `widgets/`, plus tests | change the kernel |
| a container | implement `children` and `Container.child_at` | guess children from attributes |
| a controller | a class taking `(runtime, ...)`; register with `App.mount` | edit `App.dispatch`'s order |
| a terminal switch | add it to `TerminalOptions` | add it to `App`, `Runtime` and `Screen` separately |
| a terminal capability | a defaulted `Screen` property or an injected collaborator | a placeholder field |
| a theme group | add a field to `Theme` | hard-code colors in a component |
| a command | a `Command` value plus `CommandRegistry.bind(app)` | a second key-binding mechanism |
| a new media pipeline | a future terminal/graphics seam with injected rendering | change `Component` or `Surface`'s public contract |

The value types grow additively: a new field with a default is a minor
change. `tools/growth.py` proves that by adding temporary defaulted fields
to `Surface`, `Constraints`, `ScrollAxis` and `Scroll` in a copy of the
tree and running the gates there.

## 9. Known limits in this release

These are real properties of the 2.0 tree, not aspirations:

- `app/runtime.py` is still large (about 1,600 lines). The runtime has not
  been split into the `session`/`layout`/`documents`/`protocol` modules
  sketched during design. The public seams described above are stable; the
  file layout is not.
- `Workspace` is a thin, stateless facade: its methods delegate to
  `Runtime`, which still owns the state and most of the bodies.
- `Fill` is the document form `sizing=Sizing.FILL`; there is no
  `PaneContent` union. `App.fill(component)` is the pane-level convenience.
- `ScrollPanel` and the pane chrome still use `ScrollState` as their
  mutable scroll geometry. The 2.0 immutable `Scroll`/`ScrollAxis` values
  exist and carry the same thumb formula, but replacing `ScrollState`
  everywhere is scheduled after 2.0.
- `App` still accepts the 1.x constructor arguments (`mouse`, `hover`,
  `color_mode`, `screen`, `keys`, `focus_events`, `sync`); they are folded
  into `TerminalOptions`. New code should pass `terminal=`.
- `split` and `dock` still accept the 1.x direction strings; they are
  documented compatibility entries, not the recommended surface.
- Both byte-level and semantic golden sets are kept. The semantic set is
  the primary rendering contract; the 57 byte topics remain an extra
  regression gate.
- `Placement` and `Sizing` live in `motui.kernel.document`; they are not
  re-exported from `motui.kernel` or the root in this release.
- `TerminalOptions` is exported by `motui.terminal`, not by the root.

## 10. Deliberate non-goals

Images and other terminal media protocols, horizontal scrolling of the
document flow (horizontal windows are limited to `ScrollPanel` over
non-wrapping content), a grid layout, a global render environment, a
measure/render split, per-widget result callbacks and a message bus are
2.x or later. See [MIGRATION](MIGRATION.md) and the [ADRs](adr/README.md)
for the reasoning.
