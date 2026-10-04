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

from mocode_tui import (
    DIM,
    MUTED,
    NONE,
    SUCCESS,
    Divider,
    EditBlock,
    HeadlessScreen,
    Input,
    Key,
    Line,
    Message,
    Option,
    Paste,
    ScriptedKeys,
    Segment,
    Select,
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

# The pinned footer's two-sided dim bar (the pi UI status line).
_STATUS_LEFT = "19.9k \u21931.4k R32k CH98.0% $0.003 1.0%/1.0M (auto)"
_STATUS_RIGHT = "(commandcode) deepseek/deepseek-v4.1-flash-fast \u2022 medium"

# Assistant answer bodies.  The first (rich) turn exercises every block type.
_REPLY_RICH = (
    "I read the toolkit top to bottom. mocode-tui is a full-screen "
    "block-document UI kit: an alt-screen render loop that diffs one row at a "
    "time, a self-managed scrollback, and a pinned Input + status footer. "
    "Concretely I can scaffold the pi-style demo, wire the transcript to a "
    "fake model, and keep the docs honest."
)
_REPLY_SHORT = (
    "Done -- the transcript keeps every block in the self-managed scrollback; "
    "PageUp/PageDown scrolls it, the footer stays put."
)

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


class _Nothing:
    """A placeholder that renders zero rows: the idle ``working`` footer slot.

    While a turn works it is swapped for a :class:`Spinner` (one row, the box
    grows by one line); at rest it must contribute no row at all, so the
    input box is exactly top rule + input row + bottom rule.
    """

    __slots__ = ()

    def render(self, width: int) -> list:
        return []


# ---------------------------------------------------------------------------
# Static regions
# ---------------------------------------------------------------------------
def _build_banner(tui: TUI) -> None:
    """The opening transcript: header, intro, [Skills], and the update notice."""
    accent = Style(fg="bright_cyan", bold=True)
    tui.add(_Row(("\u03c0 ", accent), ("mocode-tui ", NONE), (f"v{VERSION}", MUTED)))
    tui.add(Text("Enter send  \u00b7  /menu commands  \u00b7  "
                 "PageUp/PageDown scroll  \u00b7  Ctrl-C quit", style=DIM))
    tui.add(Text(""))
    tui.add(Text("A full-screen block-document TUI toolkit: an alt-screen render "
                 "loop, a self-managed scrollback, and a pinned footer.", style=DIM))
    tui.add(Text(""))
    tui.add(Text("[Skills]", style=Style(fg="yellow", bold=True)))
    tui.add(Text("- render: line-diffed alt-screen painter\n"
                 "- viewport: scrollback + pinned footer\n"
                 "- components: Message, ToolBlock, EditBlock, Table, ...\n"
                 "- keys: scripted + raw terminal decoding\n"
                 "- deps: wcwidth only at runtime", style=DIM))
    tui.add(Text(""))
    tui.add(Divider(style=Style(fg="yellow")))
    tui.add(Text("Update Available", style=Style(fg="yellow", bold=True)))
    tui.add(Text(f"v0.5.0 \u2192 v{VERSION}: pi-style Message/ToolBlock/Table components."))
    tui.add(Text("https://example.invalid/mocode-tui/releases",
                 style=Style(fg="magenta")))
    tui.add(Divider(style=Style(fg="yellow")))
    tui.add(Text(""))


def _build_footer(tui: TUI) -> None:
    """The pinned tail (document order is screen order): the input box.

    ``footer-top`` (blue rule) opens the box, ``working`` is the spinner slot
    (zero rows at rest), ``input`` is the field, ``footer-bottom`` (blue rule)
    closes the box, and ``footer-status`` is the two-sided dim status bar.
    """
    tui.add(Divider(style=Style(fg="blue")), id="footer-top", pinned=True)
    tui.add(_Nothing(), id="working", pinned=True)
    tui.add(Input(placeholder="Ask mocode-tui\u2026   (/menu commands, Ctrl-C quit)"),
            id="input", pinned=True)
    tui.add(Divider(style=Style(fg="blue")), id="footer-bottom", pinned=True)
    tui.add(_StatusRow(_STATUS_LEFT, _STATUS_RIGHT), id="footer-status", pinned=True)


# ---------------------------------------------------------------------------
# Fake model turn
# ---------------------------------------------------------------------------
async def _stream(tui: TUI, msg: Message, text: str) -> None:
    """Grow ``msg`` one word per frame, invalidating the doc each step."""
    acc = ""
    for word in text.split(" "):
        acc = f"{acc} {word}" if acc else word
        msg.text = acc
        tui.invalidate()
        await asyncio.sleep(STREAM_DELAY)
    tui.flush()


async def _answer(tui: TUI, question: str, *, rich: bool) -> None:
    """One fake assistant turn appended under the pinned footer."""
    tui.add(Message("user", question))
    await asyncio.sleep(THINK_DELAY)
    tui.add(Message("thinking", "Reading the repo and planning the turn\u2026"))
    await asyncio.sleep(THINK_DELAY)
    tui.add(Text("Plan", style=Style(bold=True)))
    reply = Message("assistant", "")
    tui.add(reply)
    await _stream(tui, reply, _REPLY_RICH if rich else _REPLY_SHORT)
    await asyncio.sleep(REPLY_DELAY)
    if rich:
        await asyncio.sleep(WORK_DELAY)
        tui.add(ToolBlock(
            "$ echo hello from mocode-tui && ls examples",
            ["hello from mocode-tui", "pi_demo.py"],
            tone="tool", footer="Took 0.1s"))
        await asyncio.sleep(TOOL_DELAY)
        tui.add(ToolBlock(
            "codemode  run scaffold_demo()",
            ["\u2192 seeded the transcript skeleton",
             "\u2192 wrote examples/pi_demo.py",
             "\u2192 sealed blocks, cached rows at width"],
            tone="code", footer="Took 0.3s"))
        tui.add(Table(
            ["tool", "result"],
            [[("write", NONE), ("\u2713 created examples/pi_demo.py", SUCCESS)],
             [("edit", NONE), ("\u2713 refreshed the transcript", SUCCESS)],
             [("table", NONE), ("\u2713 rendered this summary", SUCCESS)]],
        ))
        tui.add(EditBlock(
            "examples/pi_demo.py",
            context=["import asyncio",
                     "from mocode_tui import Message, ToolBlock, Table"],
            added=["async def chat(tui):",
                   "    await _answer(tui, 'scaffold the demo', rich=True)"],
        ))
    tui.add(Text("\u22ee Working", style=DIM))
    tui.add(Divider())
    tui.flush()


# ---------------------------------------------------------------------------
# The one interactive body, shared by the live and scripted paths
# ---------------------------------------------------------------------------
async def chat(tui: TUI) -> None:
    global _ANSWERED
    _ANSWERED = False
    _build_banner(tui)
    _build_footer(tui)
    field: Input = tui.get("input").component
    menu: dict | None = None  # {"id", "select"} while a slash menu is open
    turns: set[asyncio.Task[None]] = set()  # in-flight answer turns

    while True:
        event = await tui.read_key()
        if event is None:
            break  # key source exhausted (piped replay) or terminal closed
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
                block = tui.add(Select(list(_MENU), title="/ commands"),
                                id="slash-menu")
                menu = {"id": "slash-menu", "select": block.component}
            elif text.startswith("/"):
                pass  # unknown command: a demo has nothing to run
            elif text:
                # Answer in the background: the loop keeps read_key()ing, so
                # typing previews live while a turn streams.  Each turn owns
                # its own blocks -- concurrent turns may interleave in the
                # document, but no turn writes into another's blocks.
                task = asyncio.create_task(
                    _answer(tui, text, rich=not _answered()))
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
    """Two questions, one /menu visit (navigate + close), then Ctrl-C."""
    events: list = []
    for ch in "Scaffold the pi-style demo for this toolkit":
        events.append(Key(ch, ch))
    events.append(Key("enter"))
    for ch in "and refresh the docs":
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
