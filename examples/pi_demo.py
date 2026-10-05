"""pi_demo: a full-screen "pi-style" coding-assistant UI built on mocode-tui.

Run it interactively on a real terminal::

    uv run python examples/pi_demo.py          # Enter send, /menu commands, Ctrl-C quit

or pipe anything into it (``< /dev/null`` counts): the same conversational
body replays headless from a :class:`ScriptedKeys` script and prints the final
screen as plain text -- which makes the piped run a tiny smoke test::

    python examples/pi_demo.py < /dev/null; echo exit=$?

Every "assistant turn" is fake: ``asyncio.sleep`` only paces the illusion, and
the tool output is canned.  Those sleeps live *only* here -- the library and
its tests are sleep-free by contract.  The demo imports nothing beyond the
``mocode_tui`` package root and the standard library.
"""
from __future__ import annotations

import asyncio
import sys
from itertools import cycle

from mocode_tui import (
    ACCENT,
    BORDER,
    DIM,
    MUTED,
    NONE,
    SUCCESS,
    WARNING,
    Block,
    Divider,
    EditBlock,
    HeadlessScreen,
    Input,
    Key,
    Line,
    Markdown,
    Message,
    Option,
    Paste,
    ScriptedKeys,
    Segment,
    Select,
    Spinner,
    Style,
    Table,
    Text,
    ToolBlock,
    TUI,
)

VERSION = "0.6.0"

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

# The working spinner's frame cycle, driven by ``TUI.every``.
SPINNER_INTERVAL = 0.08

# The pinned footer's two-sided dim bar (the pi UI status line).
_STATUS_LEFT = "19.9k \u21931.4k R32k CH98.0% $0.003 1.0%/1.0M (auto)"
_STATUS_RIGHT = "(commandcode) deepseek/deepseek-v4.1-flash-fast \u2022 medium"

# Assistant answer bodies, as Markdown source.  The first (rich) turn
# exercises every W12 block type -- h1/h2 headings, a paragraph with inline
# code/bold/italic/link, nested unordered + ordered lists, a block quote,
# python and bash fences, an aligned GFM table, and a thematic break -- and
# wraps to well over 24 rows; the short turn answers in a different shape
# (a one-liner, a list, a quote) so no two turns read alike.
_REPLY_RICH = """\
# mocode-tui, top to bottom

I read the whole toolkit this morning. It is a **full-screen block-document
UI kit**: an alt-screen render loop that diffs one row at a time, a
self-managed scrollback, and a pinned `Input` + status footer -- see the
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
202 passed, 1 skipped in 0.86s
$ python examples/pi_demo.py < /dev/null; echo exit=$?
exit=0
```

| wave | theme | status |
|:-----|:------:|-------:|
| W10 | transcript rhythm | done |
| W12 | markdown engine | merged |
| W13 | rich demo | this wave |

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

# The slash menu (Select) the /menu command opens.
_MENU = (
    Option("/help", value="help", hint="What this demo can do"),
    Option("/model", value="model", hint="Switch the fake model"),
    Option("/clear", value="clear", hint="Empty the scrollback"),
    Option("/quit", value="quit", hint="Leave the demo"),
)


# ---------------------------------------------------------------------------
# Demo-local components (ordinary ``render(width)`` objects; no new library API)
# ---------------------------------------------------------------------------
class _Row:
    """One row built from ``(text, Style)`` parts (fit to ``width``)."""

    __slots__ = ("_parts",)

    def __init__(self, *parts: tuple[str, object]) -> None:
        self._parts = [(text, style) for text, style in parts]

    def render(self, width: int) -> list:
        line = Line(Segment(text, style) for text, style in self._parts if text)
        return [line.fit(width)]


class _StatusRow:
    """A dim footer row: left text, right text, the gutter computed in between."""

    __slots__ = ("_left", "_right")

    def __init__(self, left: str, right: str) -> None:
        self._left = left
        self._right = right

    def render(self, width: int) -> list:
        used = Line.from_text(self._left).width + Line.from_text(self._right).width
        gutter = max(1, width - used - 1)  # one trailing column of right margin
        text = f"{self._left}{' ' * gutter}{self._right}"
        return [Line.from_text(text, DIM).fit(width)]


class _WorkSlot:
    """The footer's ``working`` status: a label on the top rule.

    Enter never blocks (each turn is a background task), so turns may
    overlap -- the slot is therefore ref-counted.  The first working turn
    labels the ``footer-top`` divider (``frame + " Working"``) and starts
    a ``TUI.every`` frame cycle; the last turn to finish clears the label
    and cancels the handle.  The status rides the divider that is always
    there, so the tail never changes height: the input box is exactly top
    rule + input row + bottom rule at rest and while working alike (no
    ``_Nothing`` zero-row placeholder needed anymore).
    """

    __slots__ = ("_busy", "_divider", "_handle", "_spinner", "_tui")

    def __init__(self, tui: TUI) -> None:
        self._tui = tui
        self._divider: Divider = tui.get("footer-top").component
        self._spinner = Spinner("Working")
        self._busy = 0
        self._handle = None

    def enter(self) -> None:
        """One more turn starts working; raise the label on the first."""
        self._busy += 1
        if self._busy == 1:
            self._handle = self._tui.every(SPINNER_INTERVAL, self._advance)
            self._label()

    def leave(self) -> None:
        """One turn finished; drop the label when the last one does."""
        self._busy = max(0, self._busy - 1)
        if self._busy == 0:
            self._divider.label = ""
            self._tui.invalidate()
            if self._handle is not None:
                self._handle.cancel()
                self._handle = None

    def _label(self) -> None:
        """Paint the spinner's current frame into the divider's label."""
        self._divider.label = f"{self._spinner.frame} Working"
        self._tui.invalidate()

    def _advance(self) -> None:
        """Step the braille cycle and re-label the divider."""
        self._spinner.advance()
        self._label()


# ---------------------------------------------------------------------------
# Static regions
# ---------------------------------------------------------------------------
def _build_banner(tui: TUI) -> None:
    """The opening transcript: header, intro, [Skills], and the update notice."""
    tui.add(_Row(("\u03c0 ", ACCENT), ("mocode-tui ", NONE), (f"v{VERSION}", MUTED)))
    tui.add(Text("Enter send  \u00b7  /menu commands  \u00b7  Ctrl-C quit", style=DIM))
    tui.add(Text(""))
    tui.add(Text("A full-screen block-document TUI toolkit: an alt-screen render "
                 "loop, a self-managed scrollback, and a pinned footer.", style=DIM))
    tui.add(Text(""))
    tui.add(Text("[Skills]", style=WARNING.merge(Style(bold=True))))
    tui.add(Text("- render: line-diffed alt-screen painter\n"
                 "- viewport: scrollback + pinned footer\n"
                 "- components: Message, ToolBlock, EditBlock, Table, ...\n"
                 "- keys: scripted + raw terminal decoding\n"
                 "- deps: wcwidth only at runtime", style=DIM))
    tui.add(Text(""))
    # The update-notice rules stay: pi itself frames its update notice.
    tui.add(Divider(style=WARNING))
    tui.add(Text("Update Available", style=WARNING.merge(Style(bold=True))))
    tui.add(Text(f"v0.5.0 \u2192 v{VERSION}: pi-style Message/ToolBlock/Table components."))
    tui.add(Text("https://example.invalid/mocode-tui/releases",
                 style=Style(fg="#bc8cff")))
    tui.add(Divider(style=WARNING))
    tui.add(Text(""))


def _build_footer(tui: TUI) -> None:
    """The pinned tail (document order is screen order): the four-piece set.

    ``footer-top`` is the BORDER-styled rule that carries the working label
    (``── ⠋ Working ───``) while any turn works, ``input`` is the prompt-less
    field (pi shows no ``\u276e``), ``footer-bottom`` closes the box with a
    pure rule, and ``footer-status`` is the two-sided dim status bar.
    Working never grows the tail -- the status rides the top rule's label,
    so the input box is exactly top rule + input row + bottom rule.
    """
    tui.add(Divider(style=BORDER, label_style=ACCENT), id="footer-top", pin="bottom")
    tui.add(Input(prompt=""), id="input", pin="bottom")
    tui.add(Divider(style=BORDER), id="footer-bottom", pin="bottom")
    tui.add(_StatusRow(_STATUS_LEFT, _STATUS_RIGHT), id="footer-status", pin="bottom")


# ---------------------------------------------------------------------------
# Fake model turn
# ---------------------------------------------------------------------------
def _add_block(tui: TUI, component) -> Block:
    """Append one transcript block, then the blank line that follows it.

    The uniform W10 step: every transcript block is followed by exactly one
    ``Text("")`` spacer, so blocks never touch and the transcript reads as
    evenly spaced blocks (the pi rhythm).  It replaces W9's hand-placed
    spacer points; the banner and the pinned footer keep their own spacing
    and are added through ``tui.add`` directly.
    """
    block = tui.add(component)
    tui.add(Text(""))
    return block


async def _stream(tui: TUI, msg: Message, text: str) -> None:
    """Grow ``msg`` one word per frame, invalidating the doc each step."""
    acc = ""
    for word in text.split(" "):
        acc = f"{acc} {word}" if acc else word
        msg.text = acc
        tui.invalidate()
        await asyncio.sleep(STREAM_DELAY)
    tui.flush()


async def _stream_markdown(tui: TUI, md: Markdown, text: str) -> None:
    """Grow ``md`` one source line per frame, invalidating each step.

    W12's engine renders every prefix safely -- a half-open fence keeps its
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


async def _answer(tui: TUI, question: str, *, rich: bool,
                 work: _WorkSlot) -> None:
    """One fake assistant turn appended under the pinned footer."""
    # Uniform step (W10): every block is followed by exactly one blank line,
    # so blocks never touch and no two blanks ever stack up.  There is no
    # closing divider -- pi's blocks are separated by that blank line alone.
    _add_block(tui, Message("user", question))
    await asyncio.sleep(THINK_DELAY)
    # Thinking streams word by word, same mechanism as the reply below, and
    # the preamble rotates so no two turns think the same sentence.
    thinking = Message("thinking", "")
    _add_block(tui, thinking)
    await _stream(tui, thinking, next(_THINKING_CYCLE))
    await asyncio.sleep(THINK_DELAY)
    _add_block(tui, Text("Plan", style=Style(bold=True)))
    reply = Markdown("")
    _add_block(tui, reply)
    await _stream_markdown(tui, reply, _REPLY_RICH if rich else _REPLY_SHORT)
    # The streaming text is feedback enough while it flows; the visible work
    # after it -- pacing plus the tool-call blocks -- is the footer spinner's
    # slot.  The ``finally`` keeps the slot honest if the turn is cancelled.
    work.enter()
    try:
        await asyncio.sleep(REPLY_DELAY)
        if rich:
            await asyncio.sleep(WORK_DELAY)
            _add_block(tui, ToolBlock(
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
            _add_block(tui, ToolBlock(
                "codemode  run scaffold_demo()",
                ["\u2192 seeded the transcript skeleton",
                 "\u2192 wrote examples/pi_demo.py",
                 "\u2192 sealed blocks, cached rows at width",
                 "\u2192 wired the footer spinner slot",
                 "\u2192 kept every sleep inside the demo"],
                tone="code", footer="Took 0.6s"))
            _add_block(tui, Table(
                ["tool", "result"],
                [[("write", NONE), ("\u2713 created examples/pi_demo.py", SUCCESS)],
                 [("edit", NONE), ("\u2713 refreshed the transcript", SUCCESS)],
                 [("table", NONE), ("\u2713 rendered this summary", SUCCESS)]],
            ))
            _add_block(tui, EditBlock(
                "examples/pi_demo.py",
                context=["import asyncio",
                         "from mocode_tui import Message, ToolBlock, Table"],
                added=["async def chat(tui):",
                       "    await _answer(tui, 'scaffold the demo', rich=True)"],
            ))
    finally:
        work.leave()
    tui.flush()


# ---------------------------------------------------------------------------
# The one interactive body, shared by the live and scripted paths
# ---------------------------------------------------------------------------
def _anchor(tui: TUI) -> None:
    """Pin the terminal cursor -- the IME candidate window -- to the input.

    The painter leaves the terminal cursor on the last row it rewrote, which
    mid-stream is the transcript's middle, and the Windows IME pops its
    candidate window there.  Re-pin it to the input field's cursor cell on
    every keypress and before the first frame: from then on every frame ends
    with the anchor escape.

    The pinned tail counts bottom-up as status / bottom rule / input /
    top rule: the input box never changes height (the working status rides
    the top rule's label), so the input's last visual row is always
    ``height - 3`` and its first row is ``height - 2 - input_rows``.
    """
    field: Input = tui.get("input").component
    width = tui.screen.width
    vrow, vcol = field.cursor_position(width)
    rows = len(field.render(width))
    tui.painter.set_cursor_anchor(tui.screen.height - 2 - rows + vrow, vcol)


async def chat(tui: TUI) -> None:
    global _ANSWERED
    _ANSWERED = False
    _build_banner(tui)
    _build_footer(tui)
    field: Input = tui.get("input").component
    menu: dict | None = None  # {"id", "select"} while a slash menu is open
    work = _WorkSlot(tui)  # the footer spinner, shared by every turn
    turns: set[asyncio.Task[None]] = set()  # in-flight answer turns
    _anchor(tui)
    tui.flush()  # the very first frame already carries the IME anchor

    while True:
        event = await tui.read_key()
        if event is None:
            break  # key source exhausted (piped replay) or terminal closed
        try:
            if isinstance(event, Paste):
                field.insert(event.text)
                tui.invalidate()
                continue
            name = event.name

            if name == "c-c":
                break

            if menu is not None:
                # While a slash menu is open it owns up/down/enter/escape.
                if name == "up":
                    menu["select"].move(-1)
                elif name == "down":
                    menu["select"].move(1)
                elif name in ("enter", "escape"):
                    tui.remove(menu["id"])
                    menu = None
                    field.clear()
                tui.invalidate()
                continue

            if name == "enter":
                text = field.text.strip()
                field.clear()
                tui.invalidate()
                if text == "/menu":
                    block = tui.add(
                        Select(list(_MENU), title="", label_style=Style(fg="#bc8cff")),
                        id="slash-menu",
                        pin="top",
                    )
                    menu = {"id": "slash-menu", "select": block.component}
                elif text.startswith("/"):
                    pass  # unknown command: a demo has nothing to run
                elif text:
                    # Answer in the background: the loop keeps read_key()ing, so
                    # typing previews live while a turn streams.  Each turn owns
                    # its own blocks -- concurrent turns may interleave in the
                    # document, but no turn writes into another's blocks.
                    task = asyncio.create_task(
                        _answer(tui, text, rich=not _answered(), work=work))
                    turns.add(task)
                    task.add_done_callback(turns.discard)
                continue

            if name == "backspace":
                field.backspace()
            elif name == "left":
                field.move_left()
            elif name == "right":
                field.move_right()
            elif name == "home":
                field.home()
            elif name == "end":
                field.end()
            elif event.char:
                field.insert(event.char)
            tui.invalidate()
        finally:
            _anchor(tui)  # every keypress re-pins the IME cursor

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
    """Three questions, one /menu visit (navigate + close), then Ctrl-C."""
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
    for ch in "/menu":
        events.append(Key(ch, ch))
    events.append(Key("enter"))
    events.append(Key("down"))
    events.append(Key("enter"))
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
