"""pi_demo: a full-screen "pi-style" coding-assistant UI built on mocode-tui.

Run it interactively on a real terminal::

    uv run python examples/pi_demo.py   # Enter send, c-j newline, / palette, Ctrl-C quit

or pipe anything into it (``< /dev/null`` counts): the same conversational
body replays headless from a :class:`ScriptedKeys` script and prints the final
screen as plain text -- which makes the piped run a tiny smoke test::

    python examples/pi_demo.py < /dev/null; echo exit=$?

Every "assistant turn" is fake: ``asyncio.sleep`` only paces the illusion, and
the tool output is canned.  Those sleeps live *only* here -- the library and
its tests are sleep-free by contract.  The footer is the library's
:class:`Composer` (rules + editor + palette slot + status line) and the body is
a :class:`Transcript`; the demo imports nothing beyond the ``mocode_tui``
package root and the standard library.
"""
from __future__ import annotations

import asyncio
import sys
from itertools import cycle
from pathlib import Path

from mocode_tui import (
    ACCENT,
    Composer,
    DIM,
    Divider,
    EditBlock,
    HeadlessScreen,
    Key,
    Markdown,
    Message,
    MUTED,
    NONE,
    Notice,
    Option,
    ScriptedKeys,
    Style,
    SUCCESS,
    Table,
    Text,
    ToolBlock,
    Transcript,
    TUI,
    WARNING,
)

VERSION = "0.2.0"

# Headless replay geometry.  The live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 108, 60

# Fake-turn pacing (seconds).  Only this module sleeps.
THINK_DELAY = 0.35
REPLY_DELAY = 0.45
WORK_DELAY = 0.35
TOOL_DELAY = 0.2
STREAM_DELAY = 0.03
# The Markdown reply streams one source line per frame: word-by-word would
# need many more frames for a 24-row document and blow the 6-10s budget.
MD_STREAM_DELAY = 0.09

# The pinned status line's two sides (the pi UI status row).  The right side
# rides the model /model selects -- StatusLine.left/right are plain
# attributes a host rewrites in place.
_STATUS_LEFT = "19.9k \u21921.4k R32k CH98.0% $0.003 1.0%/1.0M (auto)"
_MODELS = (
    "(commandcode) deepseek/deepseek-v4.1-flash-fast \u2022 medium",
    "(sandbox) deepseek/deepseek-v4.1-flash-fast \u2022 high",
)
_MODEL = 0

# The slash palette's commands, handed to the Composer's SlashPalette.
_COMMANDS = (
    Option("/help", value="help", hint="What this demo can do"),
    Option("/model", value="model", hint="Switch the fake model"),
    Option("/clear", value="clear", hint="Empty the transcript"),
    Option("/md", value="md", hint="Render the Markdown fixture"),
    Option("/quit", value="quit", hint="Leave the demo"),
)

_HELP = (
    "Commands: /help /model /clear /md /quit.  Enter sends, c-j breaks a line, "
    "Ctrl-C quits -- every guard rail in this footer is the library's "
    "Composer."
)

# The Markdown rendering fixture the /md command shows: the engine's
# acceptance surface, loaded from this file's directory (the way the retired
# examples/markdown_demo.py used to open it).
SOURCE = Path(__file__).with_name("Markdown-Rendering-Test.md")

# Assistant answer bodies, as Markdown source.  The first (rich) turn
# exercises every block type -- h1/h2 headings, a paragraph with inline
# code/bold/italic/link, nested unordered + ordered lists, a block quote,
# python and bash fences, an aligned GFM table, and a thematic break -- and
# wraps to well over 24 rows; the short turn answers in a different shape
# (a one-liner, a list, a quote) so no two turns read alike.
_REPLY_RICH = """\
# mocode-tui, top to bottom

I read the whole toolkit this morning. It is a **full-screen block-document
UI kit**: an alt-screen render loop that diffs one row at a time, a
self-managed scrollback, and a pinned `Composer` + status footer -- see the
[component tables](https://example.invalid/mocode-tui/docs).

## What this demo scaffolds

- a pi-style transcript
  - user, thinking, and assistant messages
  - tool calls with canned output
- docs that stay honest
  1. component tables in `docs/COMPONENTS.md`
  2. a streaming-safe `Markdown` engine
- *one* commit per wave, English message

> The demo imports nothing beyond the `mocode_tui` package root and the
> standard library -- the library itself stays sleep-free by contract.

```python
from mocode_tui import Markdown

md = Markdown(text)     # mutable .text: assign one chunk at a time
md.text += "## more"    # every prefix renders; no row exceeds width
```

```bash
$ uv run pytest -q
........................................................................ [100%]
… passed, 1 skipped
$ python examples/pi_demo.py < /dev/null; echo exit=$?
exit=0
```

| wave | theme | status |
|:-----|:------:|-------:|
| W10 | transcript rhythm | done |
| W12 | markdown engine | merged |
| W6  | chat layer | merged |
| W7  | curated API | this wave |

---

Concretely: scaffold the demo, wire the transcript to a fake model, and
keep the docs honest.
"""
_REPLY_SHORT = """\
Short answer, then:

- the transcript keeps every block in the self-managed scrollback

> Nothing here is real model output -- the sleeps only pace the illusion.
"""

# Thinking preambles, rotated so consecutive turns never think alike.
_THINKINGS = (
    "Reading the repo top to bottom, then planning this turn\u2026",
    "Skimming the transcript, weighing two scaffolds for the reply\u2026",
    "Checking the docs against the code before answering\u2026",
)
_THINKING_CYCLE = cycle(_THINKINGS)


# ---------------------------------------------------------------------------
# Static regions
# ---------------------------------------------------------------------------
def _build_banner(tui: TUI) -> None:
    """The opening body: header, intro, [Skills], and the update notice."""
    tui.add(Text("\u03c0 mocode-tui", style=ACCENT))
    tui.add(Text(f"v{VERSION}", style=MUTED))
    tui.add(Text("Enter send  \u00b7  c-j newline  \u00b7  / palette  \u00b7  Ctrl-C quit",
                 style=DIM))
    tui.add(Text(""))
    tui.add(Text("A full-screen block-document TUI toolkit: an alt-screen render "
                 "loop, a self-managed scrollback, and a pinned footer.", style=DIM))
    tui.add(Text(""))
    tui.add(Text("[Skills]", style=WARNING.merge(Style(bold=True))))
    tui.add(Text("- render: line-diffed alt-screen painter\n"
                 "- viewport: scrollback + pinned footer\n"
                 "- chat: Composer, Transcript, Message/ToolBlock/EditBlock\n"
                 "- keys: scripted + raw terminal decoding\n"
                 "- deps: wcwidth only at runtime", style=DIM))
    tui.add(Text(""))
    # The update-notice rules stay: pi itself frames its update notice.
    tui.add(Divider(style=WARNING))
    tui.add(Text("Update Available", style=WARNING.merge(Style(bold=True))))
    tui.add(Text(f"v0.1.0 \u2192 v{VERSION}: Theme, keymaps, syntax "
                 "highlighting, and the chat layer."))
    tui.add(Text("https://example.invalid/mocode-tui/releases",
                 style=Style(fg="#bc8cff")))
    tui.add(Divider(style=WARNING))
    tui.add(Text(""))


def _build_footer(tui: TUI) -> Composer:
    """The pinned tail: the library's Composer, wired to the fake model."""
    composer = Composer(commands=list(_COMMANDS)).attach(tui)
    composer.statusline.left = (_STATUS_LEFT,)
    composer.statusline.right = (_MODELS[_MODEL],)
    return composer


# ---------------------------------------------------------------------------
# Fake model turn
# ---------------------------------------------------------------------------
async def _stream(tui: TUI, handle, text: str) -> None:
    """Grow one message word per frame, invalidating the doc each step."""
    for index, word in enumerate(text.split(" ")):
        handle.append(word if index == 0 else f" {word}")
        tui.invalidate()
        await asyncio.sleep(STREAM_DELAY)
    handle.seal()
    tui.flush()


async def _stream_markdown(tui: TUI, md: Markdown, text: str) -> None:
    """Grow ``md`` one source line per frame, invalidating each step.

    The engine renders every prefix safely -- a half-open fence keeps its
    body to the end, a table waits for its delimiter row, an unclosed inline
    marker stays literal -- so line-at-a-time growth never shows a broken
    block, and it keeps a 24-row document inside the demo's 6-10s budget.
    """
    lines = text.split("\n")
    for end in range(1, len(lines) + 1):
        md.text = "\n".join(lines[:end])
        tui.invalidate()
        await asyncio.sleep(MD_STREAM_DELAY)
    tui.flush()


async def _answer(tui: TUI, transcript: Transcript, composer: Composer,
                  question: str, *, rich: bool) -> None:
    """One fake assistant turn appended under the pinned footer."""
    # The Transcript keeps the rhythm: every block is followed by exactly
    # one blank row, so blocks never touch and no two blanks ever stack.
    transcript.append(Message("user", question))
    await asyncio.sleep(THINK_DELAY)
    # Thinking streams word by word, same mechanism as the reply below, and
    # the preamble rotates so no two turns think the same sentence.
    thinking = transcript.stream("thinking")
    await _stream(tui, thinking, next(_THINKING_CYCLE))
    await asyncio.sleep(THINK_DELAY)
    transcript.append(Text("Plan", style=Style(bold=True)))
    reply = Markdown("")
    transcript.append(reply)
    await _stream_markdown(tui, reply, _REPLY_RICH if rich else _REPLY_SHORT)
    # The streaming text is feedback enough while it flows; the visible work
    # after it -- pacing plus the tool-call blocks -- is the Composer's
    # working spinner.  The ``finally`` keeps it honest on cancellation.
    composer.set_working(True)
    try:
        await asyncio.sleep(REPLY_DELAY)
        if rich:
            await asyncio.sleep(WORK_DELAY)
            transcript.append(ToolBlock(
                "$ echo hello from mocode-tui && ls examples",
                ["hello from mocode-tui",
                 "examples/:",
                 "  pi_demo.py     # this demo",
                 "  README.md      # the toolkit tour",
                 "$ echo $MOCODE_ENV && uname -s",
                 "demo-env",
                 "Windows_NT"],
                tone="tool", footer="Took 0.4s"))
            await asyncio.sleep(TOOL_DELAY)
            transcript.append(ToolBlock(
                "codemode  run scaffold_demo()",
                ["\u2192 seeded the transcript skeleton",
                 "\u2192 wrote examples/pi_demo.py",
                 "\u2192 sealed blocks, cached rows at width",
                 "\u2192 wired the composer's working spinner",
                 "\u2192 kept every sleep inside the demo"],
                tone="code", footer="Took 0.6s"))
            transcript.append(Table(
                ["tool", "result"],
                [[("write", NONE), ("\u2713 created examples/pi_demo.py", SUCCESS)],
                 [("edit", NONE), ("\u2713 refreshed the transcript", SUCCESS)],
                 [("table", NONE), ("\u2713 rendered this summary", SUCCESS)]],
            ))
            transcript.append(EditBlock(
                "examples/pi_demo.py",
                context=["import asyncio",
                         "from mocode_tui import Composer, Transcript"],
                added=["async def chat(tui):",
                       "    await answer(tui, 'scaffold the demo', rich=True)"],
            ))
    finally:
        composer.set_working(False)
    tui.flush()


def _show_fixture(tui: TUI, transcript: Transcript) -> None:
    """The ``/md`` command: append the rendering fixture, opened at its top.

    The fixture is the engine's acceptance surface -- one sealed Markdown
    block under a notice header.  The window sticks to the transcript's
    tail, so a document this long would open at its last rows; a hit test
    on the fresh layout locates the block's topmost painted row, and the
    window scrolls up by however far that row sits below the block's first
    row -- public scroll API only, no private viewport state.
    """
    md = Markdown(SOURCE.read_text(encoding="utf-8"))
    transcript.append(Notice(f"Markdown rendering fixture · {SOURCE.name}"))
    block = transcript.append(md)
    block.seal()  # static content: render once per width
    tui.flush()  # lay the new block out before scrolling
    for y in range(tui.screen.height):
        hit = tui.hit_test(1, y + 1)
        if hit is not None and hit.block is block:
            tui.scroll_up(hit.row - y)  # the block's first row to the window top
            tui.invalidate()
            return


def _run_command(tui: TUI, value: str, transcript: Transcript, composer: Composer) -> bool:
    """Run a palette selection (or a typed command); ``False`` when quitting."""
    global _MODEL
    if value == "clear":
        transcript.clear()
    elif value == "md":
        _show_fixture(tui, transcript)
    elif value == "model":
        _MODEL = (_MODEL + 1) % len(_MODELS)
        composer.statusline.right = (_MODELS[_MODEL],)
    elif value == "quit":
        return False
    else:  # help
        transcript.append(Message("assistant", _HELP))
    return True


# ---------------------------------------------------------------------------
# The one interactive body, shared by the live and scripted paths
# ---------------------------------------------------------------------------
async def chat(tui: TUI) -> None:
    global _ANSWERED
    _ANSWERED = False
    _build_banner(tui)
    composer = _build_footer(tui)
    transcript = Transcript(tui)
    editor, palette = composer.editor, composer.palette
    turns: set[asyncio.Task[None]] = set()  # in-flight answer turns
    composer.anchor_cursor(tui)
    tui.flush()  # the very first frame already carries the IME anchor

    while True:
        event = await tui.read_key()
        if event is None:
            break  # key source exhausted (piped replay) or terminal closed
        # The palette owns only navigation and dismissal; every other key
        # falls through to the editor.  The two are decoupled, pi-style: the
        # menu never eats the keyboard.
        if palette.is_open:
            selected = palette.handle_key(event)
            if selected is not False:
                if isinstance(selected, str):
                    editor.clear()
                    if not _run_command(tui, selected, transcript, composer):
                        break
                composer.anchor_cursor(tui)
                tui.invalidate()
                continue
        if editor.handle_key(event, tui.screen.width):
            pass  # an editing key: the editor consumed it
        elif event.name == "c-c":
            break
        elif event.name == "enter":
            text = editor.value.strip()
            editor.clear()
            if text.startswith("/"):
                if not _run_command(tui, text, transcript, composer):
                    break
            elif text:
                # Answer in the background: the loop keeps read_key()ing, so
                # typing previews live while a turn streams.  Each turn owns
                # its own blocks -- concurrent turns may interleave in the
                # document, but no turn writes into another's blocks.
                task = asyncio.create_task(
                    _answer(tui, transcript, composer, text, rich=not _answered()))
                turns.add(task)
                task.add_done_callback(turns.discard)
        # A leading slash owns the palette: typing one opens it, losing the
        # slash closes it.  Editing keys never re-open a dismissed palette --
        # only a freshly typed slash does -- so dismissing it with enter or
        # escape sticks while the typed command stays put.
        if editor.value.startswith("/") and not palette.is_open:
            palette.open()
        else:
            palette.sync_query(editor.value)
        composer.anchor_cursor(tui)  # every keypress re-pins the IME cursor
        tui.invalidate()

    if turns:
        # Let in-flight turns finish so the transcript (and the piped dump)
        # ends complete before the session stops -- a mid-turn quit would
        # leave the last answer's blocks half-written.
        await asyncio.gather(*turns)
    tui.stop()


_ANSWERED = False


def _answered() -> bool:
    """Whether an answer has already run -- the first turn is the rich one."""
    global _ANSWERED
    value = _ANSWERED
    _ANSWERED = True
    return value


# ---------------------------------------------------------------------------
# Entry point: live on a TTY, scripted replay everywhere else
# ---------------------------------------------------------------------------
def _script():
    """Three questions, one slash-palette visit (open, navigate, dismiss),
    then Ctrl-C."""
    events: list = []
    for ch in "Scaffold the pi-style demo for this toolkit":
        events.append(Key(ch, ch))
    events.append(Key("enter"))
    for ch in "and refresh the docs":
        events.append(Key(ch, ch))
    events.append(Key("enter"))
    for ch in "and one more turn":
        events.append(Key(ch, ch))
    events.append(Key("enter"))
    events.append(Key("/", "/"))  # a leading slash opens the palette
    events.append(Key("q", "q"))  # typing keeps working: the two are decoupled
    events.append(Key("down"))  # navigate the palette
    events.append(Key("escape"))  # dismiss it; the typed text stays
    events.append(Key("backspace"))  # clear the typed command again
    events.append(Key("backspace"))
    events.append(Key("c-c"))
    return events


def _headless() -> None:
    """Replay ``chat`` headless, then mirror run()'s piped plain-text dump."""
    tui = TUI(screen=HeadlessScreen(HEADLESS_W, HEADLESS_H),
              keys=ScriptedKeys(_script()), interactive=False)
    asyncio.run(tui.run(chat))
    lines = [row.text for row in tui.rows()]
    while lines and not lines[-1].strip():
        lines.pop()  # trailing blank rows above the content are not content
    sys.stdout.write("\n".join(lines) + "\n")


def main() -> None:
    if sys.stdout.isatty():
        asyncio.run(TUI().run(chat))  # real terminal: alt screen + RawTerminalKeys
    else:
        _headless()  # piped: scripted replay + plain-text dump


if __name__ == "__main__":
    main()
