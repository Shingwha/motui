# Design

How the toolkit turns a document of blocks into a full-screen, scrollable,
diffed TUI. Every claim here matches the shipped modules under
`src/mocode_tui/`.

## The four layers under one driver

Four layers compose the toolkit, plus two top-level modules that sit above
the kernel precisely because they compose it with the `keys` layer:

```
mocode_tui
├── app.py       the TUI driver: the composition root (imports core + keys)
├── testing.py   headless_tui / snapshot: the developer helpers
├── core/        the kernel: primitives, events, document model, render core
├── keys/        input: the byte decoder, the keymaps, the key sources
├── widgets/     the generic component library (render(width) objects)
└── chat/        the pi-style coding-agent layer (components + controllers)
```

Dependencies point one way. `core` imports nothing from `keys`, `widgets`,
`chat` or the two top-level modules. `keys` imports `core` (the event model
in `core.events`) only. `widgets` imports `core`, and `Input`/`Editor` also
reach for `keys.keymap` for their default keymap tables. `chat` imports all
three. `app.py` and `testing.py` are at the top level because they are the
composition root and the developer helper: each is free to pull in `core`
*and* `keys`, which is what killed the old `core.app`/`core.testing` upward
imports and the layering cycle they made.

Each package re-exports its own public surface, so `from mocode_tui import …`
is the curated one-line face (63 names) and
`mocode_tui.core` / `.keys` / `.widgets` / `.chat` / `.app` / `.testing` are
the per-layer faces. `tests/test_api_root.py` pins all seven.

- **core** — `style`/`theme` (the styling defaults), `text`/`lines`/`ansi`
  (measuring, the `Text` component, rows, escape bytes), `events` (`Key`,
  `Paste`, `MouseEvent`, the `KeySource` protocol, `ScriptedKeys`), `block`
  (the frozen `Component` protocol, `Block`, `Document`),
  `screen`/`viewport`/`painter` (the render core).
- **keys** — `decoder` (the pure `bytes -> events` state machine), `keymap`
  (the key-name to editing-action tables) and `sources`/`console`
  (`ScriptedKeys` lives in `core.events`; `RawTerminalKeys` and the Windows
  plumbing live here).
- **widgets** — the generic library, each file one component family; nothing
  here touches a screen, painter, key or app.
- **chat** — `Message`/`ToolBlock`/`EditBlock` (pure components), plus
  `StatusLine`/`SlashPalette` and the `Composer`/`Transcript` controllers,
  which do touch the driver: that assembly is what the layer exists for.

## Coordinates: everything is 0-based

Every cell index in the toolkit is **0-based**, with no exceptions. A
`MouseEvent.y`/`x` is the 0-based row/column of the terminal cell the
report refers to: the decoder subtracts 1 from the SGR report's 1-based
fields as it builds the event, so an event's own `x`/`y` go straight into
`TUI.hit_test(x, y)`. `Hit.row`/`Hit.col` are 0-based within the block's own
rows; `viewport.row_blocks` is a 0-based screen-row table; `Painter` writes
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
| Query filtering | `set_query` on both `Autocomplete` and `SlashPalette` |
| Cursor pin | `Painter.set_cursor(row, col)`; `Composer.anchor_cursor(tui)` stays |
| Bottom-pinned query | removed; `snapshot()` marks `,top` / `,bottom` from `block.pin` |
| Truncation family | `Line.fit` is the public face; `ellipsize_tail` stays public; the rest internal |
| Available child width locals | `inner` |
| Consume a key | `handle_key(event)` everywhere; the wrap geometry comes from the component's last render, never from the event |
| Key event names | unchanged (hyphen for chords, underscore for words) |

## Style resolution, once at construction

Components resolve **explicit `style=` > theme field > `DEFAULT_THEME`` exactly once, at construction, and store the resolved `Style` — or the
resolved `Theme` as `self._theme` when the choice is state-dependent (a
mutable `role`, `tone` or `level` attribute). The render-time
`self.theme or DEFAULT_THEME` boilerplate is gone from the toolkit: a
`render(width)` call looks its styles up rather than resolving them, so a
component renders identically no matter what it costs to build.
Constructors still take `style=` / `theme=` exactly as before — the
resolution rule changed, not the signature.

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

- `enter()` = `enter_alt_screen() + hide_cursor() + enable_mouse_tracking()`
  — alt screen, hidden cursor, and SGR 1006 mouse reporting on;
  `leave()` = `disable_mouse_tracking() + show_cursor() + leave_alt_screen()`
  is the exact reverse (tracking off first).
  `TerminalScreen(mouse=False)` leaves the pair out.
- non-live: `enter`/`leave` are empty writes, so a piped run stays pure text.

**`HeadlessScreen`** is an in-memory recorder: `live` is always `True`, every
byte lands in `output`, and `width`/`height` are settable so a test can
simulate a resize. It interprets no escapes.

**VT degradation** is the only screen-level downgrade: a live-able terminal
that fails the VT probe behaves exactly like a pipe (the non-live path).

A `Screen` implements `write`/`flush` — the only raw sink bytes in the
toolkit — plus `refresh_size`. A custom screen brings its own tracking
settings, which is why `TUI(mouse=False)` only affects the default
`TerminalScreen`.

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
`ValueError`); `set_component` swaps the component in any state. Sealed
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
  is `viewport_height = height - top_rows - footer_rows`, so neither fixed
  region ever scrolls away. When both overflow, the footer is kept first,
  then the top region, and the window may be empty.
- **Scroll state.** `offset` clamps into
  `[0, max(0, total - viewport_height)]`. A fresh viewport **sticks to the
  bottom** (shows the tail); scrolling up detaches it, and it re-attaches at
  the bottom edge or via `scroll_to_bottom()`.
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
for a row no block owns — which is the single seam the mouse hit test
resolves through.

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

- **Facade.** `add`/`get`/`remove`/`print` mirror the document and
  invalidate the frame on every mutation. `print(text)` adds a muted system
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
  when dirty, and runs due `every` callbacks. `_clock()` is a
  `time.monotonic()` seam tests inject to drive time; the library itself
  never sleeps.

In call order (not a runnable script — every call is on the driver, and the
`read_key` await below happens inside an async body):

```python
tui.add(comp, id="x", pin=None)        # append a block; pin: "top"/"bottom"/None
tui.get("x"); tui.remove("x")         # address by id; invalidate
tui.print("system line")              # muted system block (no raw writes)
tui.invalidate(); tui.paint()         # mark dirty / paint one frame now
tui.rows                              # the current frame: exactly screen.height rows
tui.every(0.1, fn)                    # periodic callback, cancellable handle
tui.scroll_up(2); tui.scroll_to_bottom()
tui.stop()                            # ask run() to finish
```

### Mouse: the wheel, clicks, and the hit test

SGR mouse reports (`\x1b[<b;x;yM/m`, mode 1006) decode into `MouseEvent`, a
frozen `Key` subclass carrying the report's `button` and its **0-based**
`x`/`y` coordinates. The **vertical wheel** routes as
`wheel_up`/`wheel_down` (bound in `scroll_keys`, so it scrolls); **button
presses** decode as `left`/`middle`/`right` and pass through `read_key()`
untouched — the driver never dispatches a click itself. Inside the async
body (the mouse snippet's `await` needs a running loop):

```python
event = await tui.read_key()
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)   # 0-based coords go straight in
    if hit is not None:
        hit.block.component.click(hit.row) # e.g. a Select: block-internal row
```

`TUI.hit_test(x, y)` resolves a report to a `Hit` — the `Block` under the
cell and 0-based `row`/`col` within its own rows — through the viewport's
`row_blocks` ownership table, which every `layout` rebuilds in painting
order (top region, window, bottom region). A row no block owns (the blank
fill below short content), a cell outside the last layout, and a block
removed since that layout all resolve to `None`. What stays dropped in the
decoder: button releases, motion with or without a button held (drag), the
horizontal wheel, and malformed reports — that branch is the seam future
mouse kinds land in.

### Scroll facades + scroll-key interception

`read_key()` absorbs every event in the `scroll_keys` table —
`page_up`/`page_down` and the wheel by default — scrolling by the table's
signed row count (negative up: the page keys move one row, the wheel three
per notch) and continuing the read, so callers never see them. The table is
a public per-instance dictionary: rebind a count
(`tui.scroll_keys["wheel_down"] = 1`) or `del` an entry to hand the event
back to the caller. `TUI(mouse=False)` leaves mouse tracking off on the
default screen.

Escape hatch: `await tui.keys.read()` reads the raw source directly,
bypassing both the scroll-key interception and the non-live guard.

## Keys

`KeyDecoder` is a pure, total `bytes -> events` machine: incremental UTF-8,
control names (`c-a`…`c-z`, `enter`, `tab`, `backspace`, `escape`, `space`),
CSI navigation (arrows / home / end / **page_up**/**page_down**, with
modifier parameters ignored), bracketed paste (`\x1b[200~ … \x1b[201~`), and
SGR mouse reports. Unknown input is dropped or degraded, never fatal.
`finish()` ends a stream: a truncated UTF-8 sequence surfaces as U+FFFD and
an unclosed bracketed paste is delivered verbatim as one final `Paste`.

`KeySource` is `async read() -> Key | Paste | None` (`None` = EOF):

- **`ScriptedKeys`** (in `core.events`) replays a fixed event list, then
  reports EOF forever (a `None` item is a one-shot EOF signal). Tests and
  demos drive the whole toolkit this way.
- **`RawTerminalKeys`** reads a real terminal: POSIX `termios.setraw`, or on
  Windows a `GetConsoleMode`/`ReadConsoleInputW` record path; when the
  terminal cannot be switched to raw mode it falls back to cooked line mode
  (`.cooked_fallback`). A daemon reader thread feeds an executor-backed
  queue, so `read()` stays async without the thread touching asyncio.

### Keymaps

Editing keys are not hardwired: a **keymap** (`mocode_tui.keys.keymap`) is a
plain `dict` from key event name to the name of the no-argument editing
method it triggers (`"left" -> "move_left"`). `Input` and `Editor` resolve
their keymap at construction (`keymap=None` picks the component's default)
and consume keys through **`handle_key(event) -> bool`**:

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
`backspace` / `delete` / up / down / `c-u` and leaves `enter` unbound;
`DEFAULT_EDITOR_KEYMAP` is that plus `enter` as `newline`. A host rebinds
single keys by handing in a copy (`{**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}`)
or drops a binding by `del`-ing its entry. `chat.Composer` ships
`COMPOSER_KEYMAP`: the editor default minus `enter`, with `c-j` as `newline`
in its place — the decoder emits no `c-enter` name, so the return key is the
only clean submit gesture.

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
   key source attached (that is why the headless demo drives its own replay
   and dumps the screen itself).
3. **On exit the final screen is dumped as plain text** — the `height` rows
   of the last frame, trailing blanks trimmed, on the exception path too
   (before the error is re-raised).

`HeadlessScreen` is the in-memory counterpart: a recorder that is *live by
construction*, so `headless_tui`/`snapshot` (`mocode_tui.testing`, above the
kernel) can drive a real driver and assert on structure without a terminal.

## Deliberately out of scope

- A document memory cap / history trimming: the document stays resident in
  full, and nothing is ever evicted.
- A VT-settle timeout across split reads, and SIGWINCH-beyond-resize
  handling: the screen is only re-sampled by `refresh_size()`.
- Runtime colour negotiation: the palette is 24-bit truecolor and a VT probe
  only gates streams that cannot render escapes at all.
- Mouse drag and scrollbar dragging: presses decode and `hit_test` resolves
  them, but releases, motion and the horizontal wheel are dropped by the
  decoder and SGR 1002 motion tracking is never enabled.
- Math rendering in Markdown: the rule registries in
  `mocode_tui.widgets.markdown` are the documented extension point
  (see `docs/COMPONENTS.md`).
- Any sleep in the library or its tests: time flows through the pump's
  clock, which a test injects.
- Backward compatibility: no shim, no alias, no deprecation period — a
  renamed name is deleted with its last consumer.
