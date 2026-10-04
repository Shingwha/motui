# Design

How the toolkit turns a document of blocks into a full-screen, scrollable,
diffed TUI. Every claim here matches the shipped modules under
`src/mocode_tui/`.

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

- `enter()` = `enter_alt_screen() + hide_cursor()` = `\x1b[?1049h` then hide.
- `leave()` = `show_cursor() + leave_alt_screen()`.
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

`Painter` accepts a `throttle` for API stability but never blocks; the driver
decides when a frame is due.

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
- **Scroll facades + page-key interception.** `read_key()` absorbs
  `page_up`/`page_down` — each one scrolls the viewport and the read continues,
  so callers never see them. Escape hatch: `await tui.keys.read()` reads the raw
  source directly, bypassing both the page-key interception and the non-live
  guard.

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

Mouse-wheel scrolling (SGR 1006), a document memory cap / history trimming (the
document stays resident in full), a VT-settle timeout across split reads, and
SIGWINCH-beyond resize handling. See `docs/COMPONENTS.md` for what you can build
yourself.

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
