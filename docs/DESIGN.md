# Design

How the toolkit turns a document of blocks into a full-screen, scrollable,
diffed TUI. Every claim here matches the shipped modules under
`src/mocode_tui/`.

## The four layers

```
mocode_tui
├── core/      the kernel: primitives, document model, render core, driver
├── keys/      input: event model, decoder, keymaps, key sources
├── widgets/   the generic component library (render(width) objects)
└── chat/      the pi-style coding-agent layer (components + controllers)
```

Dependencies point one way: `chat` and `widgets` import `core` and `keys`;
`core` imports neither `keys` nor the component layers (the driver's `Paste`
routing aside, `core.app` reads the key *events* through the `keys` event
model only); `keys` imports nothing but the kernel's row primitives where it
needs them. Each package re-exports its own public surface, so
`from mocode_tui import …` is the curated one-line face and
`mocode_tui.core` / `.keys` / `.widgets` / `.chat` are the per-layer faces.
`tests/test_api_root.py` pins all five.

- **core** — `style`/`theme` (the styling defaults), `text`/`lines`/`ansi`
  (measuring, rows, escape bytes), `block` (the frozen `Component` protocol,
  `Block`, `Document`), `screen`/`viewport`/`painter` (the render core),
  `app` (the `TUI` driver) and `testing` (the headless helpers).
- **keys** — `events` (`Key`, `Paste`, `MouseEvent`), `decoder` (the pure
  `bytes -> events` state machine), `keymap` (the key-name to editing-action
  tables) and `sources`/`console` (`ScriptedKeys`, `RawTerminalKeys`, the
  Windows plumbing).
- **widgets** — the generic library, each file one component family; nothing
  here touches a screen, painter, key or app.
- **chat** — `Message`/`ToolBlock`/`EditBlock` (pure components), plus
  `StatusLine`/`SlashPalette` and the `Composer`/`Transcript` controllers,
  which do touch the driver: that assembly is what the layer exists for.

## The screen model

Four layers stack into one frame each repaint:

```
Document ──▶ Viewport ──▶ Painter ──▶ Screen
 (blocks)     (window        (row diff    (bytes:
              + footer)      + erase)      alt/leave)
```

**`TerminalScreen`** wraps a real stream (`sys.stdout` by default). It is
*live* iff `stream.isatty()` **and** `enable_vt()` succeeds — on Windows a VT
probe runs because a stream that cannot render escapes is treated as non-live.
Liveness is decided once, at construction; size is cached and only re-sampled by
`refresh_size()`.

- `enter()` = `enter_alt_screen() + hide_cursor() + enable_mouse_tracking()`
  — alt screen, hidden cursor, and SGR 1006 mouse reporting on;
  `leave()` = `disable_mouse_tracking() + show_cursor() + leave_alt_screen()`
  is the exact reverse (tracking off first).
  `TerminalScreen(mouse=False)` leaves the pair out.
- non-live: `enter`/`leave` are empty writes, so a piped run stays pure text.

**`HeadlessScreen`** is an in-memory recorder: `live` is always `True`, every
byte lands in `output`, and `width`/`height` are settable so a test can simulate
a resize. It interprets no escapes.

**VT degradation** is the only screen-level downgrade: a live-able terminal that
fails the VT probe behaves exactly like a pipe (non-live path below).

## Documents and blocks

The unit of content is a **`Block`**: a stable `id`, a **`Component`**
(`render(width) -> list[Line]`), and a two-state lifecycle. `Document` is an
ordered, id-addressable collection — `add` (auto id `b0`, `b1`, …; duplicates
raise), `get`, `remove`, `blocks()`.

The lifecycle is exactly `OPEN` or `SEALED` — there is deliberately **no
COMMITTED state**: a full-screen rewrite has no terminal history to append into,
so a block is either still being written (`OPEN`) or frozen (`SEALED`).
`block.seal()` freezes it (`OPEN → SEALED`; sealing twice raises `ValueError`);
`set_component` swaps the component in any state. Sealed blocks are rendered
once per width and cached, so long finished transcripts are cheap; open blocks
(streaming text, a live input) re-render every layout.

## The viewport

`Viewport.layout(width, height)` renders the document and returns a
`ScreenLayout`: `rows` (exactly `height`) and `viewport_rows` (the scrolling
region alone).

- **Fixed regions.** Blocks carrying `pin="top"` render, in document order,
  into a top region above the scrolling window; `pin="bottom"` blocks into a
  footer below it; unpinned blocks fill the scrolling body. The window height is
  `viewport_height = height - top_rows - footer_rows`, so neither fixed region
  ever scrolls away. When both overflow, the footer is kept first, then the top
  region, and the window may be empty.
- **Scroll state.** `offset` clamps into `[0, max(0, total - viewport_height)]`.
  A fresh viewport **sticks to the bottom** (shows the tail); scrolling up
  detaches it, and it re-attaches at the bottom edge or via `scroll_to_bottom()`.
- **more-below marker.** When scrolled away with content still below the window,
  the viewport's last row becomes `─ more below ─` (muted), so you never wonder
  what you missed.
- Short documents blank-pad the viewport below the content so the footer stays
  put; the sealed-row cache is invalidated whenever the width changes.

## The painter

`Painter.flush()` paints one frame. `rows()` always returns exactly
`screen.height` rows.

- **(Re)size → full repaint.** A `\x1b[2J` clear-screen, then every row.
- **Steady state → per-row diff.** Each row is compared to the previous frame;
  only rows that changed are written, as `\x1b[{row};1H` + `\x1b[K` (erase line)
  + the styled row. **An unchanged frame writes zero bytes.**
- **Non-live → silent.** The painter still computes the logical rows (so
  `rows()` is queryable on a piped run) but writes nothing.
- **IME anchor.** `set_cursor_anchor(row, col)` pins the terminal cursor (the
  IME candidate window follows the input box, not the streaming text); the
  anchor is the frame epilogue — appended after a frame that wrote anything,
  written alone by a frame that only moved it. A non-live screen never
  receives it.

`Painter` has no throttle of its own — it paints exactly when told to. The
driver's `TUI.throttle` is the only throttle: it decides when a frame is
due, and `flush()` paints one immediately, bypassing it. The painter also
forwards the resident viewport's read-only state — `row_blocks` (the row
ownership table) among it — so callers never reach through to a private seam.

## The driver

`TUI` owns a document, a painter, a screen, and an optional key source.

- **Facade.** `add`/`get`/`remove`/`print` mirror the document and invalidate the
  frame on every mutation. `print(text)` adds a muted system block — external
  output becomes document content, never a raw write behind the painter's back.
  `flush()` paints now (bypassing the throttle); `invalidate()` marks dirty and
  wakes the pump.
- **`run(body)` lifecycle.** It attaches the screen and a raw key source (when
  interactive), starts the pump, and awaits `body(self)` — the library never
  builds its own event loop, so the caller owns `asyncio.run`. `enter`/`leave`
  bracket the session on a live screen, **including on exceptions and `stop()`**.
  A `KeyboardInterrupt` from the body is treated as `stop()`. Teardown always
  flushes a final frame before leaving.
- **Pump / clock.** `_pump` repaints at most one frame per throttle window when
  dirty, and runs due `every(seconds, fn)` callbacks (cancellable handles).
  `_clock()` is a `time.monotonic()` seam tests inject to drive time.
- **Scroll facades + scroll-key interception.** `read_key()` absorbs every
  event in the `scroll_keys` table — `page_up`/`page_down` and the wheel by
  default — scrolling by the table's signed row count (negative up: the page
  keys move one row, the wheel three per notch) and continuing the read, so
  callers never see them. The table is a public per-instance dictionary:
  rebind a count (`tui.scroll_keys["wheel_down"] = 1`) or `del` an entry to
  hand the event back to the caller. `TUI(mouse=False)` leaves mouse tracking
  off on the default screen (a custom screen brings its own settings).
  Escape hatch: `await tui.keys.read()` reads the raw
  source directly, bypassing both the scroll-key interception and the non-live
  guard.

### Mouse: the wheel, clicks, and the hit test

SGR mouse reports (`\x1b[<b;x;yM/m`, mode 1006) decode into `MouseEvent`, a
frozen `Key` subclass carrying the report's `button` and its 1-based `x`/`y`
coordinates. The **vertical wheel** routes as `wheel_up`/`wheel_down` (bound in
`scroll_keys`, so it scrolls); **button presses** decode as
`left`/`middle`/`right` and pass through `read_key()` untouched — the driver
never dispatches a click itself:

```python
event = await tui.read_key()
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)   # 1-based coords go straight in
    if hit is not None:
        hit.block.component.click(hit.row) # e.g. a Select: block-internal row
```

`TUI.hit_test(x, y)` resolves a report to a `Hit` — the `Block` under the cell
and 0-based `row`/`col` within its own rows — through the painter's
`row_blocks` ownership table, which every `Viewport.layout` rebuilds in
painting order (top region, window, bottom region). A row no block owns (the
blank fill below short content), a cell outside the last layout, and a block
removed since that layout all resolve to `None`. What stays dropped in the
decoder: button releases, motion with or without a button held (drag), the
horizontal wheel, and malformed reports — that branch is the seam future mouse
kinds land in.

## Keys

`KeyDecoder` is a pure, total `bytes -> events` machine: incremental UTF-8,
control names (`c-a`…`c-z`, `enter`, `tab`, `backspace`, `escape`, `space`),
CSI navigation (arrows / home / end / **page_up**/**page_down**, with modifier
parameters ignored), and bracketed paste (`\x1b[200~ … \x1b[201~`). Unknown
input is dropped or degraded, never fatal. It assumes — documented for the
pipe-byte path — that a complete escape sequence arrives within one `feed`.

`KeySource` is `async read() -> Key | Paste | None` (`None` = EOF):

- **`ScriptedKeys`** replays a fixed event list, then reports EOF forever (a
  `None` item is a one-shot EOF signal). Tests and demos drive the whole toolkit
  this way.
- **`RawTerminalKeys`** reads a real terminal: POSIX `termios.setraw`, or on
  Windows a `GetConsoleMode`/`ReadConsoleInputW` record path; when the terminal
  cannot be switched to raw mode it falls back to cooked line mode (`.cooked_fallback`).
  A daemon reader thread feeds an executor-backed queue, so `read()` stays async
  without the thread touching asyncio.

### Keymaps

Editing keys are not hardwired: a **keymap** (`mocode_tui.keys.keymap`) is a
plain `dict` from key event name to the name of the no-argument editing method
it triggers (`"left" -> "move_left"`). `Input` and `Editor` resolve their keymap
at construction (`keymap=None` picks the component's default) and consume keys
through `handle_key(key, width) -> bool`:

- a `Paste` inserts its text; a `Key` with a `char` (a printable, `space`
  included) is inserted directly — printables never need a keymap entry;
- otherwise the event's `name` is looked up in the keymap and the same-named
  method runs;
- an unbound name answers `False` and the event goes back to the host, which is
  how a submit gesture stays the host's decision.

`DEFAULT_INPUT_KEYMAP` binds arrows / home / end / `c-a` / `c-e` / backspace /
delete / up / down / `c-u` and leaves `enter` unbound; `DEFAULT_EDITOR_KEYMAP`
is that plus `enter` as `newline`. A host rebinds single keys by handing in a
copy (`{**DEFAULT_INPUT_KEYMAP, "c-j": "clear"}`) or drops a binding by
`del`-ing its entry. `chat.Composer` ships `COMPOSER_KEYMAP`: the editor
default minus `enter`, with `c-j` as `newline` in its place — the decoder emits
no `c-enter` name, so the return key is the only clean submit gesture.

## Highlighting

`mocode_tui.widgets.syntax` is the built-in syntax highlighting: an ordered
table of per-language regex rules resolved against a theme's semantic colors,
turning `(code, lang)` into one `Line` per logical line. Five token classes
(comment / string / number / keyword / builtin) cover ~25 languages; matching
is per-line and first-match-wins, and text no rule claims keeps the theme's
`code` style.

The seam is the protocol, not the engine: **`Highlighter`** is any object with
`highlight(code, lang) -> list[Line]`, and components that take
`highlighter=` (the `Markdown` fence rule among them) accept it wholesale —
`RegexHighlighter(theme=…, languages=…)` customizes the built-in, and
`default_highlighter()` shares the stock instance (building one compiles every
rule, so components share rather than rebuild). `highlight(code, lang)` is the
convenience entry point. Zero dependencies by contract: the module is pure `re`
over the kernel.

## The non-TTY contract

A **non-live** screen (pipe / file) changes `run()`'s whole behaviour:

1. **Run-time is silent** — no escapes, no alt screen, nothing behind the
   painter's back.
2. **`read_key()` always returns `None`** on a non-live screen, even with a key
   source attached (that is why the headless demo drives its own replay and
   dumps the screen itself).
3. **On exit the final screen is dumped as plain text** — the `height` rows of
   the last frame, trailing blanks trimmed, on the exception path too (before
   the error is re-raised).

`HeadlessScreen` is the in-memory counterpart: a recorder that is *live by
construction*, so `headless_tui`/`snapshot` can drive a real driver and assert
on structure without a terminal.

## Deliberately out of scope

A document memory cap / history trimming (the document stays resident in
full), a VT-settle timeout across split reads, and SIGWINCH-beyond resize
handling. **Math** is a documented extension point, not a feature: the Markdown
rule registries are where `$…$` lands. **Mouse drag and scrollbar dragging**
stay out: presses decode and `hit_test` resolves them, but releases, motion and
the horizontal wheel are dropped by the decoder and SGR 1002 motion tracking is
never enabled — a scroll-drag would need both. See `docs/COMPONENTS.md` for
what you can build yourself.

### Mouse wheel: added 2026-10-05 (W16)

"No mouse-wheel scrolling (SGR 1006)" used to be a non-goal. **2026-10-05,
revised by W16**: the toolkit now pairs SGR 1006 tracking with the alt-screen
lifecycle, decodes wheel reports into `MouseEvent`s, and scrolls on them
through the `scroll_keys` table. **2026-10-05, revised again by W5**: button
presses decode too, and `TUI.hit_test` resolves them to the block under the
cell. What stays out of scope is mouse *drag*: the decoder still drops releases
and motion.

### Color: truecolor, not 16-color

The W1 palette was a frozen 16-color named set, and "true 256/RGB color" used to
be listed as a non-goal. **2026-10-04, revised by W11**: the user asked for a
softer, more readable palette, and the only blue in a 16-color terminal palette
is pure blue — it cannot read as "soft". `Style.fg`/`bg` therefore also accept
`#rrggbb` strings and `(r, g, b)` tuples, which emit 24-bit SGR parameters
(`38;2;r;g;b` / `48;2;r;g;b`), and the semantic constants moved to the soft
GitHub-dark truecolor set (see the palette table in `docs/COMPONENTS.md`).
Reason this is safe: the target environment is Windows 11 + Windows Terminal,
whose ConPTY passes VT sequences through to the terminal unchanged, and every
modern terminal (Windows Terminal, ConEmu, iTerm2, Kitty, …) renders 24-bit
color; the VT probe in `TerminalScreen` already gates liveness for streams that
cannot render escapes at all. The named 16-color set keeps working — truecolor
is a superset, not a replacement — so nothing that worked before breaks. What
stays out of scope is runtime color *negotiation* (querying the terminal's
reported capabilities); the palette simply assumes a 24-bit renderer.

### Theme: added 2026-10-05 (W1)

The palette started as loose per-module constants — a user band in one file,
tone bands in another, a heading ladder private to the markdown engine.
**2026-10-05, revised by W1**: every one of those defaults is a field of the
frozen `Theme` dataclass, derived tables included, and every component
resolves explicit `style=` > `theme=` field > `DEFAULT_THEME` at render. The
semantic colors live on as the exported `core.style` constants; the bands and
structural tables live only in `Theme`.

### Markdown palette: revised 2026-10-05 (W3)

The W1 theme still colored every markdown construct out of two constants:
headings climbed an accent ladder (accent, accent+underline, muted, …), inline
code borrowed the blue `code` token, list markers and quote bars borrowed
`muted`, links were accent-underlined with a muted ` (url)` tail, and the
table header and first column were bold. **2026-10-05, revised by W3**: the
palette is per-construct — `heading` gold with a `heading`/`muted` ladder
(no bold, no underline), `link` colored + underlined and label-only,
`inline_code` pink, `list_marker` purple, quote bodies italic on the
unchanged muted bar, `first_column` and `DEFAULT_HEADER_STYLE` plain. **Bold
is reserved for the `**…**` syntax itself**; the resolution order
(explicit > theme field > `DEFAULT_THEME`) and the `dataclasses.replace`
customization path are untouched, so one `replace` still restyles the whole
toolkit. The same wave merged the Markdown rendering demo into
`examples/pi_demo.py` as its `/md` slash command — one demo, one entry point
— and retired `examples/markdown_demo.py` (the fixture
`examples/Markdown-Rendering-Test.md` stays, as the engine's acceptance
surface).
