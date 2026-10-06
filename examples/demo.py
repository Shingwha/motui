"""demo: a conversational tour of mocode-tui, the library's living front page.

Run it on a real terminal (Enter sends, c-j breaks a line, a leading ``/``
opens the palette, tab cycles focus, drag selects, Ctrl-C quits)::

    uv run python examples/demo.py

or pipe anything in (``< /dev/null`` counts): the same body replays headless
from a :class:`ScriptedKeys` script and prints the final screen as plain
text, so the piped run is a smoke test::

    uv run python examples/demo.py < /dev/null; echo exit=$?

Everything the "assistant" says is local and canned -- no network, no model.
The interactive stream pauses a few milliseconds per chunk so the growth is
visible; the headless replay never sleeps (it yields with ``sleep(0)``), so
the piped run stays instant -- the library and its tests are sleep-free by
contract, and this file's pacing lives on the interactive path only.  It
imports nothing beyond the ``mocode_tui`` package root and the stdlib.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import replace
from pathlib import Path

from mocode_tui import (
    ACCENT, Autocomplete, Column, Composer, Confirm, DEFAULT_THEME, DIM, Divider,
    EveryHandle, HeadlessScreen, Input, Key, Markdown, Message, MouseEvent, Notice,
    Option, Padding, Pane, Panel, ProgressBar, Row, SUCCESS, ScriptedKeys, Scrollbar,
    Select, Selection, SelectionGesture, Spacer, Spinner, Style, Table, Tabs, Text,
    Toasts, Transcript, Tree, TreeNode, TUI, WARNING, extract,
)

# Headless replay geometry.  The live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 110, 70

# Pacing in seconds (interactive sessions only -- the headless replay yields).
WORD_DELAY = 0.03    # per streamed word of the thinking preamble
LINE_DELAY = 0.04    # per streamed Markdown source line
FPS_INTERVAL = 0.5   # the frame-rate sampling period
PREVIEW_TICK = 0.1   # the preview pane's live ticker

PLACEHOLDER = "Ask about this toolkit -- or type / for the commands"

#: Three themes, two built with ``dataclasses.replace`` (nothing global is mutated).
THEMES = (
    ("default", DEFAULT_THEME),
    ("amber", replace(
        DEFAULT_THEME, accent=Style(fg="#e8a020"), heading=Style(fg="#e8a020"),
        selection=Style(bg="#3a2d12"), user_bg=Style(bg="#3a2d12"),
    )),
    ("violet", replace(
        DEFAULT_THEME, accent=Style(fg="#9d7cd8"), heading=Style(fg="#9d7cd8"),
        selection=Style(bg="#2a2140"), user_bg=Style(bg="#2a2140"),
    )),
)

#: The palette's commands; every one is exercised by the piped replay.
COMMANDS = (
    Option("/help", value="help", hint="This command list"),
    Option("/components", value="components", hint="Render the widget catalogue"),
    Option("/md", value="md", hint="Render the Markdown fixture"),
    Option("/split", value="split", hint="Toggle the live preview pane"),
    Option("/close", value="close", hint="Close the preview pane"),
    Option("/theme", value="theme", hint="Cycle replacement themes"),
    Option("/fps", value="fps", hint="Toggle the frame-rate readout"),
    Option("/clear", value="clear", hint="Empty the transcript"),
    Option("/quit", value="quit", hint="Leave the demo"),
)

HELP = (
    "Commands:\n"
    + "\n".join(f"  {option.label:<13} {option.hint}" for option in COMMANDS)
    + "\nEnter sends, c-j breaks a line, a leading / opens this palette, "
    "tab (or a click) switches pane focus, drag selects and release copies "
    "through OSC 52, Ctrl-C quits."
)

THINKING = "Reading this toolkit top to bottom before answering\u2026"

#: The first answer: a longer self-description, streamed as Markdown.
REPLY_LONG = """\
# A full-screen toolkit in one process

This screen is a **block document**: every row is a `Block` inside one
addressable `Document`, the visible part is a `Viewport` window, and the
footer is a `Composer` parked in the frame's bottom band.

- `core` -- rows, styles, events, the document, the painter, the frame
- `keys` -- raw bytes to events, and the three keymap tables
- `widgets` -- the component library (`Table`, `Tree`, `Tabs`, ...)
- `chat` -- `Composer`, `Transcript`, `Message`, `ToolBlock`

```python
from mocode_tui import Composer, Key, Message, Transcript, TUI

async def chat(tui: TUI) -> None:
    body = Transcript(tui)          # the scrolling stream
    footer = Composer(tui)          # mounted at construction
    while (key := await tui.read_key()) is not None:
        footer.editor.handle(key)   # editing keys; enter is unbound
        if isinstance(key, Key) and key.name == "enter":
            body.append(Message("user", footer.editor.text))
            footer.editor.clear()

asyncio.run(TUI().run(chat))
```

| layer   | owns                                        |
|:--------|:--------------------------------------------|
| core    | the row primitive, the frame, the selection |
| chat    | the coding-agent pieces                     |

> Local and canned: the demo never calls a model, and nothing you type
> leaves this process.
"""

#: Every later answer: the short shape, so no two turns read alike.
REPLY_SHORT = """\
Everything on screen is a `Block` in one `Document`: the catalogue, the
fixture, this reply, and the pinned header -- the footer is a `Composer` in
the frame's bottom band.

Try `/split` for a second pane, `/theme` to replace the theme, or `/md`
for the rendering fixture.

> Still local, still canned -- no model involved.
"""

FIXTURE = Path(__file__).with_name("Markdown-Rendering-Test.md")

#: The session's in-flight background turns (interactive sessions only).
_TASKS: set[asyncio.Task[None]] = set()


class _State:
    """What the loop, the tickers and the commands share."""

    __slots__ = ("answered", "composer", "fps", "fps_at", "fps_frames",
                 "fps_on", "preview", "preview_tick", "theme")

    def __init__(self, tui: TUI) -> None:
        self.theme = 0
        self.answered = False
        self.fps = 0.0
        self.fps_on = True
        self.fps_frames = tui.painter.frames
        self.fps_at = tui.clock()
        self.composer: Composer | None = None
        self.preview: Pane | None = None
        self.preview_tick: EveryHandle | None = None


def _current(state: _State) -> tuple[str, object]:
    """The (name, theme) pair the session is on."""
    return THEMES[state.theme]


def _show_fps(state: _State) -> None:
    """Publish the readout (or its off state) on the status line's right."""
    composer = state.composer
    if composer is None:
        return
    composer.statusline.right = (f"{state.fps:.1f} fps",) if state.fps_on else ("fps off",)


def _fps_tick(tui: TUI, state: _State) -> None:
    """One sample: frames since the last tick over the wall interval; no
    invalidate, so the readout never measures its own repaints."""
    now, frames = tui.clock(), tui.painter.frames
    state.fps = (frames - state.fps_frames) / max(now - state.fps_at, 1e-6)
    state.fps_frames, state.fps_at = frames, now
    _show_fps(state)


def _banner(tui: TUI, state: _State) -> None:
    """The header, pinned top: it survives scrolling and even ``/clear``."""
    _, theme = _current(state)
    tui.add(Text("mocode-tui \u00b7 a live tour of the toolkit", style=theme.accent), pin="top")
    tui.add(Text(
        "enter sends \u00b7 c-j newline \u00b7 / commands \u00b7 tab focus "
        "\u00b7 drag selects \u00b7 ctrl-c quits", style=DIM,
    ), pin="top")
    tui.add(Divider(theme=theme), pin="top")


def _mount_footer(tui: TUI, state: _State) -> Composer:
    """Mount the ``Composer`` footer on the session's current theme."""
    _, theme = _current(state)
    composer = Composer(tui, theme=theme, placeholder=PLACEHOLDER, commands=list(COMMANDS))
    composer.statusline.left = ("mocode-tui demo \u00b7 local replies, no network",)
    state.composer = composer
    _show_fps(state)
    return composer


async def _beat(tui: TUI, delay: float) -> None:
    """Pace one chunk: the delay interactive, a bare yield headless --
    ``sleep(0)`` still yields to the pump, without any real time passing."""
    await asyncio.sleep(delay if tui.interactive else 0)


async def _stream_markdown(tui: TUI, md: Markdown, text: str) -> None:
    """Grow ``md`` one source line per beat, invalidating at every prefix."""
    lines = text.split("\n")
    for end in range(1, len(lines) + 1):
        md.text = "\n".join(lines[:end])
        tui.invalidate()
        await _beat(tui, LINE_DELAY)
    tui.paint()


async def _answer(tui: TUI, state: _State, transcript: Transcript, question: str) -> None:
    """One local turn: echo, think, stream the reply, seal; the first turn
    gets the long self-description, later turns the short one."""
    transcript.append(Message("user", question))
    thinking = transcript.stream("thinking")
    for index, word in enumerate(THINKING.split(" ")):
        thinking.append(word if index == 0 else f" {word}")
        tui.invalidate()
        await _beat(tui, WORD_DELAY)
    thinking.seal()
    composer = state.composer
    composer.set_working(True)
    try:
        rich, state.answered = not state.answered, True
        md = Markdown("")
        block = transcript.append(md)
        await _stream_markdown(tui, md, REPLY_LONG if rich else REPLY_SHORT)
        block.seal()
    finally:
        composer.set_working(False)
    tui.paint()


async def _dispatch(tui: TUI, state: _State, transcript: Transcript, question: str) -> None:
    """Answer in the background interactive, inline headless (the headless
    replay awaits each turn so the scripted and transcript orders agree)."""
    if not tui.interactive:
        await _answer(tui, state, transcript, question)
        return
    task = asyncio.create_task(_answer(tui, state, transcript, question))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)


def _catalogue(transcript: Transcript, theme) -> None:
    """The ``/components`` command: the widget catalogue in one sealed block.

    Covers what an earlier demo never showed -- Tree, Tabs, Panel, Row/Column,
    ProgressBar, Select, Confirm, Input, Autocomplete -- plus styled Table
    cells, Spinner, Notice, Divider and a filled Padding.
    """
    spinner = Spinner("working")
    spinner.advance()
    select = Select(
        [Option("first", hint="hint one"), Option("second", hint="hint two"),
         Option("third", hint="hint three")],
        title="Select", theme=theme,
    )
    select.move(1)
    auto = Autocomplete(
        options=[Option("/help", hint="commands"), Option("/components", hint="widgets"),
                 Option("/clear", hint="empty")],
        max_rows=3, theme=theme,
    )
    auto.set_query("/")
    auto.move(1)
    tree = Tree(
        [TreeNode("mocode_tui", [
            TreeNode("core", [TreeNode("lines"), TreeNode("painter")], expanded=True),
            TreeNode("widgets", [TreeNode("table"), TreeNode("tree")]),
            TreeNode("chat", [TreeNode("composer")]),
        ], expanded=True)],
        theme=theme,
    )
    catalogue = Column([
        Text("the widget catalogue", style=theme.accent),
        Divider(theme=theme, label="Table"),
        Table(
            ["component", "state"],
            [["Table", ("styled cells", SUCCESS)], ["Markdown", ("streams safely", SUCCESS)],
             ["Scrollbar", ("chrome", ACCENT)], ["Toasts", ("overlay", WARNING)]],
            theme=theme,
        ),
        Spacer(1),
        Divider(theme=theme, label="Tree \u00b7 Tabs \u00b7 Panel \u00b7 Row/Column"),
        tree,
        Tabs(["overview", "components", "keys"], active=1, theme=theme),
        Row(
            [Panel(Text("a Panel around Text", style=DIM), title="Panel", theme=theme),
             Panel(Tabs(["a", "b", "c"], active=2, theme=theme), title="Panel", theme=theme)],
            widths=[32, None],
        ),
        Spacer(1),
        Divider(theme=theme, label="ProgressBar \u00b7 Select \u00b7 Confirm \u00b7 Input"),
        Row([ProgressBar(0.25, label="25%", width_chars=14, theme=theme),
             ProgressBar(0.5, label="50%", width_chars=14, theme=theme),
             ProgressBar(1.0, label="done", width_chars=14, theme=theme)]),
        Row(
            [select, Confirm("confirm a destructive action?", danger=True, theme=theme)],
            widths=[28, None],
        ),
        Input(prompt="\u276e ", placeholder="a single-line Input, shown static here", theme=theme),
        Spacer(1),
        Divider(theme=theme, label="Autocomplete \u00b7 Spinner \u00b7 Notice \u00b7 Padding"),
        auto,
        Text(f"{spinner.frame} {spinner.text}  (Spinner is frames + text; "
             "a host composes the row)", style=theme.accent),
        Notice("an info Notice", level="info", theme=theme),
        Notice("a warn Notice", level="warn", theme=theme),
        Padding(Text("Padding: inset text over a filled band"), left=2, top=1,
                fill_style=theme.user_bg),
    ])
    transcript.append(catalogue).seal()


def _fixture(transcript: Transcript) -> None:
    """The ``/md`` command: the rendering fixture as one sealed Markdown block."""
    transcript.append(Notice(f"Markdown fixture \u00b7 {FIXTURE.name}")).seal()
    transcript.append(Markdown(FIXTURE.read_text(encoding="utf-8"))).seal()


def _open_preview(tui: TUI, state: _State) -> None:
    """The ``/split`` half that opens a live preview pane.

    The right pane opens over a fresh document with *live* components ticked
    by ``tui.every``, plus filler rows for its own wheel scroll; the block
    stays unsealed so they re-render every frame.
    """
    _, theme = _current(state)
    _, right = tui.split("vertical", ratios=(2, 1))
    state.preview = right
    spinner = Spinner("live")
    bar = ProgressBar(0.0, label="preview", width_chars=14, theme=theme)
    line = Text(f"{spinner.frame} {spinner.text}", style=theme.accent)
    right.document.add(Column([
        Text("preview pane", style=theme.accent),
        Tabs(["live", "row", "wheel"], active=0, theme=theme),
        line,
        bar,
        Spacer(1),
        Tree([TreeNode("frame", [TreeNode("Pane"), TreeNode("chrome")], expanded=True)], theme=theme),
        Divider(theme=theme),
        Text("the wheel scrolls the pane under the pointer", style=DIM),
        *(Text(f"preview row {i:02d}") for i in range(20)),
    ]))
    state.preview_tick = tui.every(
        PREVIEW_TICK, lambda: _preview_tick(tui, state, spinner, bar, line)
    )
    tui.invalidate()


def _preview_tick(tui: TUI, state: _State, spinner: Spinner, bar: ProgressBar, line: Text) -> None:
    """One preview beat: step the spinner, advance the bar, repaint."""
    if state.preview is None:
        return
    spinner.advance()
    bar.fraction = (bar.fraction + 0.07) % 1.0
    line.text = f"{spinner.frame} {spinner.text}"
    tui.invalidate()


def _close_preview(tui: TUI, state: _State) -> None:
    """Close the preview pane (the ``/close`` and second-``/split`` path)."""
    if state.preview is None:
        return
    if state.preview_tick is not None:
        state.preview_tick.cancel()
        state.preview_tick = None
    state.preview.close()  # the kernel's un-split: the pane hands its cells back
    state.preview = None
    if tui.selection_pane is None:
        tui.set_selection(None)  # a selection in the closed pane lost its addresses
    tui.invalidate()


def _switch_theme(tui: TUI, state: _State, transcript: Transcript) -> None:
    """The ``/theme`` command: cycle the ``replace(DEFAULT_THEME, ...)`` variants.

    Themes resolve once, at construction -- the documented model, not a
    global stylesheet -- so this rebuilds the footer on the next variant and
    appends a themed marker.  Older blocks keep their construction theme.
    """
    state.theme = (state.theme + 1) % len(THEMES)
    name, theme = _current(state)
    typed = state.composer.editor.text
    state.composer.detach()
    composer = _mount_footer(tui, state)
    if typed:
        composer.editor.insert(typed)
    transcript.append(Divider(
        theme=theme,
        label=f"theme {state.theme + 1}/{len(THEMES)} \u00b7 {name}",
        label_style=theme.accent,
    )).seal()
    tui.invalidate()


def _copy_to_toast(toasts: Toasts):
    """The selection ``on_end``: copy the range through OSC 52 and toast the
    answer -- only when the screen answered ``True`` (a pipe has no clipboard)."""

    def on_end(tui: TUI, selection: Selection) -> None:
        pane = tui.selection_pane
        document = tui.document if pane is None else pane.document
        region = None if pane is None else tui.frame.region(pane.id)
        width = tui.screen.width if region is None else region.width
        text = extract(document, selection, width=width)
        if tui.screen.copy(text):
            toasts.show(f"Copied {len(text.splitlines())} lines")

    return on_end


def _cycle_focus(tui: TUI) -> None:
    """Tab: focus the next pane in the frame's order (wrapping around)."""
    panes = tui.frame.panes
    focused = tui.frame.focused_pane
    if focused is None or not panes:
        return
    ids = [pane.id for pane in panes]
    if focused.id in ids:
        panes[(ids.index(focused.id) + 1) % len(panes)].focus()


def _run(tui: TUI, state: _State, transcript: Transcript, value: str) -> bool:
    """Run one chosen (or typed) command; ``False`` when it asks to quit."""
    name = value[1:] if value.startswith("/") else value
    if name == "help":
        transcript.append(Message("assistant", HELP))
    elif name == "components":
        _catalogue(transcript, _current(state)[1])
    elif name == "md":
        _fixture(transcript)
    elif name == "split":
        if state.preview is None:
            _open_preview(tui, state)
        else:
            _close_preview(tui, state)
    elif name == "close":
        _close_preview(tui, state)
    elif name == "theme":
        _switch_theme(tui, state, transcript)
    elif name == "fps":
        state.fps_on = not state.fps_on
        _show_fps(state)
    elif name == "clear":
        transcript.clear()
        tui.system("transcript cleared \u2014 the pinned header stays")
    elif name == "quit":
        return False
    else:
        transcript.append(Message("assistant", f"Unknown command {name!r}."))
    tui.invalidate()
    return True


async def chat(tui: TUI) -> None:
    state = _State(tui)
    _banner(tui, state)
    _mount_footer(tui, state)
    transcript = Transcript(tui)
    toasts = Toasts(tui)
    scrollbar = Scrollbar(tui)
    gesture = SelectionGesture(tui, on_end=_copy_to_toast(toasts))
    tui.every(FPS_INTERVAL, lambda: _fps_tick(tui, state))
    state.composer.anchor_cursor()
    tui.paint()  # the very first frame already carries the IME anchor

    while True:
        if not tui.interactive:
            # The replay never sleeps, so it outruns the pump's repaint
            # throttle: compose between events, or a scripted click would
            # hit-test against the frame as it stood two commands ago.
            tui.paint()
        event = await tui.read_key()
        if event is None:
            break  # source exhausted (piped replay) or terminal closed
        # The documented dispatch order: chrome, then overlays, then the
        # content gesture -- each answers the consume-one-event contract.
        if scrollbar.handle(event) or toasts.handle(event) or gesture.handle(event):
            state.composer.anchor_cursor()
            tui.invalidate()
            continue
        composer = state.composer
        palette = composer.palette
        if palette.is_open and palette.handle(event):
            chosen = palette.chosen
            palette.chosen = None  # the host reads the pick exactly once
            if chosen is not None:
                composer.editor.clear()
                if not _run(tui, state, transcript, str(chosen)):
                    break
            state.composer.anchor_cursor()  # /theme may have rebuilt the footer
            tui.invalidate()
            continue
        editor = composer.editor
        if editor.handle(event):
            pass  # an editing key: the editor consumed it
        elif event.name == "c-c":
            break
        elif event.name == "tab":
            _cycle_focus(tui)
        elif event.name == "escape":
            _close_preview(tui, state)
        elif event.name == "enter":
            text = editor.text.strip()
            editor.clear()
            if text.startswith("/"):
                if not _run(tui, state, transcript, text):
                    break
            elif text:
                await _dispatch(tui, state, transcript, text)
        # The leading slash owns the palette; /theme may have rebuilt the
        # footer, so re-read its pieces before touching them.
        composer = state.composer
        editor, palette = composer.editor, composer.palette
        if editor.text.startswith("/") and not palette.is_open:
            palette.open()
        else:
            palette.set_query(editor.text)
        composer.anchor_cursor()  # every keypress re-pins the IME cursor
        tui.invalidate()

    if _TASKS:
        # Let in-flight turns finish so the transcript (and the dump) ends whole.
        await asyncio.gather(*_TASKS)
    tui.stop()


def _script() -> list:
    """The piped replay: every command, two turns, a drag, then quit."""
    events: list = []

    def type_text(text: str) -> None:
        events.extend(Key(ch, ch) for ch in text)

    def command(name: str) -> None:
        type_text(name)
        events.append(Key("enter"))  # the open palette consumes it and picks

    def mouse(name: str, x: int, y: int, kind: str = "press") -> None:
        events.append(MouseEvent(name, button=0, x=x, y=y, kind=kind))

    command("/help")
    type_text("what can this toolkit do?")
    events.append(Key("enter"))
    command("/components")
    command("/md")
    command("/split")
    # Focus the preview by press, let its wheel scroll it, tab back.
    px, py = HEADLESS_W - 12, 10
    mouse("left", px, py)
    mouse("left", px, py, "release")
    events.append(Key("tab"))
    mouse("wheel_down", px, py)
    command("/close")
    command("/theme")
    command("/fps")  # off
    command("/fps")  # ...and on again
    command("/clear")
    type_text("summarize the tour")
    events.append(Key("enter"))
    command("/components")  # repopulate the cleared transcript for the dump
    # A drag over the catalogue: press, motion, release -- the gesture's
    # on_end copies the range through OSC 52 and the toast answers.
    mouse("left", 6, 30)
    mouse("left", 54, 33, "motion")
    mouse("left", 54, 33, "release")
    events.append(Key("c-c"))
    return events


def _headless() -> None:
    """Replay ``chat`` headless, then mirror run()'s piped plain-text dump."""
    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H),
              keys=ScriptedKeys(_script()), interactive=False)
    asyncio.run(tui.run(chat))
    lines = [row.text.rstrip() for row in tui.rows]
    while lines and not lines[-1].strip():
        lines.pop()  # trailing blank rows above the content are not content
    sys.stdout.write("\n".join(lines) + "\n")


def main() -> None:
    if sys.stdout.isatty():
        asyncio.run(TUI(theme=THEMES[0][1]).run(chat))  # real terminal: alt screen
    else:
        _headless()  # piped: scripted replay + plain-text dump


if __name__ == "__main__":
    main()
