# Architecture

motui is built from one direction of dependency and five kinds of object:
pure values, optional media, renderers, terminal edges, and policy. This page describes the
layers, the object model, the lifecycle and the places a host is expected to
extend. The normative rules are in [CONTRACT](CONTRACT.md); the component
catalogue is in [WIDGETS](WIDGETS.md).

## 1. Layers and dependency rules

```
                     motui (root facade, 40 names)
        ┌──────────────┬───────────────┬──────────────────┐
        │              │               │                  │
   motui.widgets   motui.app       motui.terminal     motui.testing
     (48 names)    (19 names)        (17 names)         (5 names)
        │              │               │                  │
        │              │               └────────┐         │
        │              │                        │         │
        │         motui.pixel (13 names)       │         │
        │              │                        │         │
        └──────────────┴───────────┬────────────┴─────────┘
                                   │
                            motui.kernel (61 names)
```

The rules are enforced by `import-linter` (five contracts in
`pyproject.toml`):

| Rule | Meaning |
|---|---|
| `kernel has no I/O` | `motui.kernel` may not import `os`, `sys`, `io`, `ctypes`, `termios`, `tty`, `select` or `asyncio` |
| `kernel is a leaf` | `motui.kernel` may not import `motui.pixel`, `motui.widgets`, `motui.app`, `motui.terminal` or `motui.testing` |
| `pixel depends only on the kernel` | the raster medium knows no widgets, app, terminal or testing layer |
| `widgets may not import terminal or app` | components depend on the kernel and the optional pixel medium |
| `terminal may not import widgets, app or pixel` | the terminal edge knows bytes, screens and events, not components or rasters |

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
| `layout.py` | `Constraints`, `ScrollAxis`, `Scroll`, `ScreenLayout`, `Viewport`, `Scrollable`, `RowSpan` |
| `frame.py` | `Rect`-based `Pane`, `Split`, `Frame`, `Chrome`, `Separator` |
| `hit.py` | `Hit` |
| `overlay.py` | the ordered overlay layers and registry |
| `selection.py` | `Selection`, `highlight`, `extract` |
| `keymap.py` | `Keymap`, the input/editor key tables |

### pixel

`raster.py` (`Raster` and its verbs, private slot/heat grids,
`at()`), `palette.py` (`PixelPalette`), `quantize.py` (layered rasters to
kernel `Line`s), `types.py` (`Marker`, `PixelLayer`, colors and the braille
constants). It imports the kernel only. `PixelCanvas` in the widget layer is
the adapter; the demo never touches a raster byte array.

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
`canvas.py`, `pixel_canvas.py` (`PixelCanvas`, `LayerName`), `mark.py`,
`syntax.py`, `strip.py` and `cursor.py`.

### app

`runtime.py` (706 lines) is the session: terminal, painter, clock, timers,
pump, dirty flag and run lifecycle. `workspace.py` (894 lines) owns what is
on screen: document, frame, panes, docks, hit testing and selection.
`application.py` (643 lines) is `App`: it composes the runtime, the
workspace and the default controllers. `router.py` (357 lines) holds the
default handler chain (`DEFAULT_HANDLERS`) and implements the wheel, drag,
mouse, focus, page-key and binding tiers.

The controllers are `FocusManager`, `Pointer`, `SelectionGesture`,
`Scrollbar`, `Toasts`, `Tooltip`, `Stats`, `Find`, `Modal` and
`CommandPalette` in the remaining `app/*.py` modules. They are assembled on
the workspace: a controller host has to resolve panes, hit cells and the
frame, and the workspace is the object that owns them.

### demo

`cli.py` (entry modes), `preview.py` (deterministic text/painter
snapshots), `registry.py` (`SPECS`/`SCENES`/`TILES`), `scene.py` (`Scene`,
`SceneSpec`), `shell.py` (`Showcase`: phase, wipe, help, status),
`common.py`, `minis.py` and `sections/` (one scene per module; splash and
motion are packages). The demo is not a public facade.

### testing

`headless_tui` wires a recording `HeadlessScreen` and a `ScriptedEvents`
source to a real `Runtime` and returns a `Harness` -- one flat test driver
whose content members resolve to the workspace and whose session members
resolve to the runtime. `snapshot` renders the document structure;
`Emulator` consumes painter bytes and rebuilds the cell grid.

## 3. Ownership and construction

Engine values are frozen, keyword-only and fully defaulted, so a later 2.x
field addition does not move a caller's arguments.

| Object | Owns | Constructed by |
|---|---|---|
| `Cell` / `Segment` / `Line` / `Surface` | content and geometry | components and kernel |
| `Section` | id, widget, placement, sizing, one row cache | `Document.add` (including `sizing=Sizing.FILL`) |
| `Document` | an ordered set of sections | host, `Pane`, `Workspace` |
| `Pane` | rect, viewport, chrome, optional split | `Workspace` |
| `Frame` | panes, docks, overlays, focus, composition caches | `Workspace` |
| `Widget` | parent/children, theme, styles, flags, hooks | host |
| `Terminal` | one screen, one event source, clipboard | `App` or host |
| `Runtime` | terminal, clock, timers, painter, pump, session | `App` or host |
| `Workspace` | document, frame, panes, docks, hit and selection | `Runtime` |
| `App` | runtime, workspace, terminal, default controllers | host |

`Surface.of` and `Surface.clipped` are the supported builders; the
dataclass fields exist for readers. `Section` is constructed by `Document`,
`Pane` and `Frame` by the workspace, and `ScreenLayout` by `Frame.compose`
or `Viewport.layout`; a host reads those values rather than building its
own. `Constraints`, `TerminalOptions`, `Styles`, `Theme` and the event
values are ordinary public constructors.

The workspace exposes six thin session delegates for the controllers it
hosts: `clock`, `every`, `refresh`, `screen`, `painter` and
`copy_to_clipboard`. They are how a controller reaches the pump and the
terminal without a second constructor argument. They are not public
application API; a host uses `app.runtime` for the session and
`app.workspace` for the content.

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
        App.dispatch(event)           # the handler chain, first claim wins
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
Section.rows(Constraints)            # the section's row cache
  Component.render(Constraints)      # -> Surface
Viewport.layout(width, height)       # -> ScreenLayout (rows + row ownership)
Frame.compose(width, height)         # panes, docks, chrome, overlays
Painter.paint(ScreenLayout)          # per-row diff -> Screen
```

`Section` caches rows by `(width, max_height, widget.generation)`. A
`Widget` bumps `generation` with `touch()`; a pure component has no
counter, so its section renders fresh on every layout. `Viewport` keeps a
private incremental body index keyed on the same generation counters,
re-measures only changed sections and locates the window by bisect.

`ScreenLayout.row_blocks` and `block_order` carry the ownership table with
the layout, so hit testing, selection highlighting and extraction never
reach back into a live viewport.

## 6. Event dispatch

`App.dispatch` runs the handler tuple in `App.handlers`, which is
`DEFAULT_HANDLERS` by default and an explicit tuple when the host passes
`handlers=`. `auto=False` leaves the tuple empty unless the host passed
`handlers=`. Each handler answers whether it consumed the event; the first
`True` ends dispatch. The order is a public contract:

1. open `CommandPalette`
2. open `Modal` layers, newest first
3. open `Find`
4. `Toasts`
5. controllers added with `App.mount`, in mount order
6. wheel: horizontal scroller in the hit chain, then vertical scroller,
   then the hit pane, then the focused pane's viewport
7. drag in flight
8. mouse: selection gesture, pointer, pane focus on press
9. focused control through `FocusManager`
10. page keys
11. `App.bind` callbacks, then `tab` / `s-tab`
12. host hooks `on_key`, `on_mouse`, `on_event`

A `ResizeEvent` is broadcast to every mounted widget's `on_resize` before
the list above and then keeps travelling: the broadcast informs, it never
consumes. A host that needs a different policy passes its own
`handlers=(...)`.

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
- **`Frame.revision` is structural.** It counts split, close, chrome and
  overlay mutations so a composition can reuse its tiling. It is not a row
  cache and not a content counter; content caching reads
  `widget.generation`.
- **Take** is pull-based. `take()` reads the pending value once and clears
  it. `None` means "nothing pending"; `False` and `0` are real results.
  There is no per-widget result callback.
- **Overlays** are ordered by layer name: `background`, `content`,
  `selection`, `chrome`, `overlay`, `modal`, `tooltip`, `toast`.
- **Panes** are workspace objects, not values. Splitting or closing rewrites
  the frame's tree in place; the frame keeps its identity, overlays and
  focus, and each pane keeps its viewport and chrome.
- **Docks** are pane-like regions above and below the pane area. They are
  hit-testable and selectable but take neither focus nor splits.
- **Scroll** is a value: `Viewport.scroll` and `ScrollPanel.scroll` answer
  an immutable `Scroll` whose `x`/`y` are `ScrollAxis` values. The window
  stores the clamped offset; a resize clamps it again from the previous
  extent.
- **Visible ranges** answer a `RowSpan(first, last)` (`motui.kernel.layout`),
  a frozen half-open range of screen rows.

## 8. Extension points

| Add | Do this | Do not |
|---|---|---|
| a component | a new `Widget` subclass (or just `render`) in `widgets/`, plus tests | change the kernel |
| a container | implement `children` and `Container.child_at` | guess children from attributes |
| a controller | a class taking the workspace host; register with `App.mount` | edit `DEFAULT_HANDLERS`' order |
| a dispatch tier | a `Handler(app, event) -> bool` and `App(handlers=(...))` | monkey-patch `App.dispatch` |
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

These are real properties of the 2.1 tree, not aspirations:

- The split stopped short of the design targets. `app/runtime.py` is 706
  lines (target 450), `app/workspace.py` 894 (target 450) and
  `app/application.py` 643 (target 250); `app/router.py` is 357 lines of
  migrated dispatch. The public seams are stable; the file split is not the
  design's final shape.
- The workspace exposes six thin runtime delegates (`clock`, `every`,
  `refresh`, `screen`, `painter`, `copy_to_clipboard`) because the
  controllers are hosted on it. They are documented as a controller seam,
  not as public API.
- `Fill` is the document form `sizing=Sizing.FILL`; the value class
  `motui.kernel.document.Fill` exists, but there is no `PaneContent` union.
  `App.fill(component)` is the pane-level convenience.
- `Placement` and `Sizing` live in `motui.kernel.document`; they are not
  re-exported from `motui.kernel` or the root. `TerminalOptions` is
  exported by `motui.terminal`, not by the root.
- Semantic golden frames are the only golden gate: ten showcase scenes in
  `tests/golden/semantic/`, each at its registry preview phase. There is no
  byte-level golden set.
- Document-flow horizontal scrolling is limited to `ScrollPanel` over
  non-wrapping content; panes scroll vertically only.
- `tools/framebench.py` is excluded from pyright; it is a benchmark
  harness rather than library code.

## 10. Deliberate non-goals

Images and other terminal media protocols, horizontal scrolling of the
document flow (horizontal windows are limited to `ScrollPanel` over
non-wrapping content), a grid layout, a global render environment, a
measure/render split, per-widget result callbacks and a message bus are
2.x or later. See [MIGRATION](MIGRATION.md) and the [ADRs](adr/README.md)
for the reasoning.
