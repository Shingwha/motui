"""pi_demo: a full-screen "pi-style" coding-assistant UI built on mocode-tui.

Run it interactively on a real terminal::

    uv run python examples/pi_demo.py   # Enter send, c-j newline, / palette, Ctrl-C quit

or pipe anything into it (``< /dev/null`` counts): the same conversational
body replays headless from a :class:`ScriptedKeys` script and prints the final
screen as plain text -- which makes the piped run a tiny smoke test::

    python examples/pi_demo.py < /dev/null; echo exit=$?

Every "assistant turn" is fake: ``asyncio.sleep`` only paces the illusion, and
the tool output is canned -- but everything streams.  A turn flows the pi way:
thinking and reply text grow chunk by chunk, each tool call opens *running*
(a live spinner title on the pump clock), streams its output rows, then flips
*done* (a check title plus a timing footer), and the streamed edit walks its
diff rows in.  Those sleeps live *only* here -- the library and its tests are
sleep-free by contract.  The footer is the library's
:class:`Composer` (rules + editor + palette slot + status line) and the body is
a :class:`Transcript`.

Since the frame-chrome wave the demo also drives the frame model's public
face: a :class:`Scrollbar` on the transcript pane (chrome), the selection
gesture's ``on_end`` copying through OSC 52 and answering with a
:class:`Toasts` band (an overlay), and the ``/preview`` command splitting the
frame into transcript | preview with tab focus switching.  Every one of those
is host policy over the package root: the demo imports nothing beyond
``mocode_tui`` (plus its ``core`` facade for the selection primitives) and the
standard library.
"""
from __future__ import annotations

import asyncio
import sys
from itertools import cycle
from pathlib import Path

from mocode_tui import (
    ACCENT,
    Block,
    Composer,
    DIM,
    Divider,
    EditBlock,
    HeadlessScreen,
    Key,
    Markdown,
    Message,
    MouseEvent,
    MUTED,
    Notice,
    Option,
    Pane,
    ScriptedKeys,
    Scrollbar,
    Spinner,
    Style,
    SUCCESS,
    Table,
    Text,
    Toasts,
    ToolBlock,
    Transcript,
    TUI,
    WARNING,
)
from mocode_tui.core import Selection, extract
from mocode_tui.selection import SelectionGesture

VERSION = "0.4.0"

# Headless replay geometry.  The live screen uses whatever the terminal reports.
HEADLESS_W, HEADLESS_H = 108, 60

# Fake-turn pacing (seconds).  Only this module sleeps.
THINK_DELAY = 0.35
REPLY_DELAY = 0.45
WORK_DELAY = 0.3  # a tool call's beat before its first output row
TOOL_DELAY = 0.16  # one tool-output row per beat
EDIT_DELAY = 0.12  # one diff row per beat
STREAM_DELAY = 0.03
SPINNER_INTERVAL = 0.08  # a running call's title spinner (the pump clock)
# The Markdown reply streams one source line per frame: word-by-word would
# need many more frames for a 24-row document and blow the 6-10s budget.
MD_STREAM_DELAY = 0.08
FIXTURE_STREAM_DELAY = 0.02  # the 347-line /md fixture streams briskly (~7s)

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
    Option("/md", value="md", hint="Stream the Markdown fixture"),
    Option("/preview", value="preview", hint="Split a live preview pane"),
    Option("/quit", value="quit", hint="Leave the demo"),
)

_HELP = (
    "Commands: /help /model /clear /md /preview /quit.  Enter sends, c-j "
    "breaks a line, tab switches pane focus, a folded call's \u25be row "
    "expands it (click it again to fold it back), Ctrl-C quits -- every "
    "guard rail in this footer is the library's Composer."
)

# The Markdown rendering fixture the /md command shows: the engine's
# acceptance surface, loaded from this file's directory (the way the retired
# examples/markdown_demo.py used to open it).
SOURCE = Path(__file__).with_name("Markdown-Rendering-Test.md")

# Assistant answer bodies, as Markdown source.  The rich turn streams in two
# blocks around the live tool calls -- the pi flow: the intro names the plan,
# the tools run below it, and the rest (h2 headings, nested lists, a block
# quote, python and bash fences, an aligned GFM table, a thematic break)
# lands after them.  The short turn answers in a different shape (a
# one-liner, a list, a quote) so no two turns read alike.
_REPLY_INTRO = """\
# mocode-tui, top to bottom

I read the whole toolkit this morning. It is a **full-screen block-document
UI kit**: an alt-screen render loop that diffs one row at a time, a
self-managed scrollback, and a pinned `Composer` + status footer -- see the
[component tables](https://example.invalid/mocode-tui/docs).

Let me look at the chat layer first.
"""
_REPLY_REST = """\
## What this demo scaffolds

- a pi-style transcript
  - user, thinking, and assistant messages
  - tool calls with canned output
- docs that stay honest
  1. component tables in `docs/COMPONENTS.md`
  2. a streaming-safe `Markdown` engine
- *one* commit per wave, English message

> The demo imports nothing beyond the `mocode_tui` package root (and its
> `core` facade) and the standard library -- the library itself stays
> sleep-free by contract.

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
    tui.add(Text("Enter send  \u00b7  c-j newline  \u00b7  / palette  \u00b7  "
                 "tab switches panes  \u00b7  \u25be folds a call open  \u00b7  "
                 "Ctrl-C quit", style=DIM))
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
                 "highlighting, the chat layer, and the frame model "
                 "(panes, chrome, overlays)."))
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
    tui.paint()


async def _stream_markdown(tui: TUI, md: Markdown, text: str,
                           delay: float = MD_STREAM_DELAY) -> None:
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
        await asyncio.sleep(delay)
    tui.paint()


async def _answer(tui: TUI, transcript: Transcript, composer: Composer,
                  question: str, *, rich: bool,
                  folds: dict[Block, _Fold] | None = None) -> None:
    """One fake assistant turn appended under the pinned footer.

    Fully streamed, the pi flow: the user echo, thinking word by word, the
    reply's intro paragraph line by line, then the tool calls run live
    below it -- each opening *running* and flipping *done* -- and the rest
    of the reply streams in a second block underneath them.
    """
    transcript.append(Message("user", question))
    await asyncio.sleep(THINK_DELAY)
    # Thinking streams word by word, same mechanism as the reply below, and
    # the preamble rotates so no two turns think the same sentence.
    thinking = transcript.stream("thinking")
    await _stream(tui, thinking, next(_THINKING_CYCLE))
    await asyncio.sleep(THINK_DELAY)
    # The working spinner rides the footer while the turn works; the
    # ``finally`` keeps it honest on cancellation.
    composer.set_working(True)
    # One fold registry per turn, shared by reference: the tools register
    # into it as they finish, so the loop's clicks see the same object.
    fold_map = folds if folds is not None else {}
    try:
        if rich:
            lead = Markdown("")
            transcript.append(lead)
            await _stream_markdown(tui, lead, _REPLY_INTRO)
            await _run_tools(tui, transcript, fold_map)
            rest = Markdown("")
            transcript.append(rest)
            await _stream_markdown(tui, rest, _REPLY_REST)
        else:
            reply = Markdown("")
            transcript.append(reply)
            await _stream_markdown(tui, reply, _REPLY_SHORT)
            await asyncio.sleep(REPLY_DELAY)
    finally:
        composer.set_working(False)
    tui.paint()


def _spin_tool(tool: ToolBlock, spinner: Spinner, tui: TUI) -> None:
    """One spinner beat: repaint a running call's title from the pump clock."""
    spinner.advance()
    tool.title = f"{spinner.frame} {spinner.text} \u2026"
    tui.invalidate()


class _Fold:
    """Click-to-expand state for one finished tool call.

    A call rests *folded* -- the pi-compact look: its band plus one title
    row.  The demo keeps the full body and footer aside and swaps the
    :class:`ToolBlock`'s plain attributes on toggle; the chevron announces
    the state (``▸`` folded, click to expand; ``▾`` expanded, click to
    fold).  Library-free by design -- folding is demo state over public
    mutable attributes, dispatched by the host from :meth:`TUI.hit_test`.
    """

    __slots__ = ("body", "done", "footer", "open", "tool")

    def __init__(self, tool: ToolBlock, done: str, body: list[str],
                 footer: str) -> None:
        self.tool = tool
        self.done = done
        self.body = body
        self.footer = footer
        self.open = False
        self._apply()  # a call rests folded: the title row is the whole block

    def toggle(self) -> None:
        self.open = not self.open
        self._apply()

    def _apply(self) -> None:
        mark = "\u25be " if self.open else "\u25b8 "
        self.tool.title = mark + self.done
        self.tool.body = self.body if self.open else []
        self.tool.footer = self.footer if self.open else ""


async def _tool_call(tui: TUI, transcript: Transcript, label: str,
                     output: list[str], *, done: str, footer: str,
                     tone: str = "tool",
                     folds: dict[Block, _Fold] | None = None) -> None:
    """One tool call, live: opens *running* -- the title carries a spinner
    driven by :meth:`TUI.every` -- streams its output rows one per beat,
    then flips *done* and folds to the compact title row (a click expands
    the output again).  A foldable block stays ``open``: a sealed block's
    cached rows never repaint, and folding is ongoing interactivity.  The
    ``finally`` stops the spinner even when a turn is cancelled
    mid-flight."""
    spinner = Spinner(label)
    tool = ToolBlock(f"{spinner.frame} {spinner.text} \u2026", tone=tone)
    block = transcript.append(tool)
    handle = tui.every(SPINNER_INTERVAL, lambda: _spin_tool(tool, spinner, tui))
    try:
        await asyncio.sleep(WORK_DELAY)
        for line in output:
            tool.body.append(line)
            tui.invalidate()
            await asyncio.sleep(TOOL_DELAY)
        tool.title = done
        tool.footer = footer
    finally:
        handle.cancel()
    if folds is not None:
        folds[block] = _Fold(tool, done, list(output), footer)
    else:
        block.seal()  # static: frozen rows; foldable blocks stay writable
    tui.invalidate()


async def _apply_edit(tui: TUI, transcript: Transcript, path: str,
                      context: list[str], removed: list[str],
                      added: list[str], *, footer: str,
                      folds: dict[Block, _Fold] | None = None) -> None:
    """The modification, both halves: a tool call carries the state
    (*running* flips *done*) while the EditBlock below it streams its diff
    rows in, one per beat."""
    summary = f"patching {len(context) + len(removed) + len(added)} lines"
    await _tool_call(
        tui, transcript, f"Editing {path}", [summary],
        done=f"\u2713 Edited {path}", footer=footer, folds=folds)
    edit = EditBlock(path)
    block = transcript.append(edit)
    for rows, field in ((context, "context"), (removed, "removed"), (added, "added")):
        for line in rows:
            getattr(edit, field).append(line)
            tui.invalidate()
            await asyncio.sleep(EDIT_DELAY)
    block.seal()
    tui.invalidate()


async def _summary(tui: TUI, transcript: Transcript) -> None:
    """The turn summary streams one row per beat, a check per landed tool."""
    table = Table(["tool", "result"],
                  [["read", ("\u2713 the chat layer, mapped", SUCCESS)]])
    block = transcript.append(table)
    for name, result in (
        ("list", ("\u2713 examples/ walked", SUCCESS)),
        ("edit", ("\u2713 pi_demo.py patched", SUCCESS)),
        ("reply", ("\u2713 this summary", SUCCESS)),
    ):
        await asyncio.sleep(TOOL_DELAY)
        table.rows.append([name, result])
        tui.invalidate()
    block.seal()
    tui.invalidate()


async def _run_tools(tui: TUI, transcript: Transcript,
                     folds: dict[Block, _Fold]) -> None:
    """The rich turn's live middle: two reads, the streamed edit, and the
    row-by-row summary table -- every block stateful or streaming."""
    await _tool_call(
        tui, transcript, "Reading the chat layer",
        ["chat/tools.py -- ToolBlock: title/body/footer are plain attributes",
         "  a running call repaints its title, a done call flips it",
         "chat/transcript.py -- append() returns the Block, a spacer follows",
         "viewport.py -- open blocks re-render per frame, sealed blocks cache"],
        done="\u2713 Read the chat layer", footer="Took 0.4s", folds=folds)
    await _tool_call(
        tui, transcript, "Listing examples/",
        ["$ ls examples",
         "Markdown-Rendering-Test.md  pi_demo.py"],
        done="\u2713 Listed examples/", footer="Took 0.1s", tone="code",
        folds=folds)
    await _apply_edit(
        tui, transcript, "examples/pi_demo.py",
        context=["async def _answer(tui, transcript, question, *, rich):",
                 "    reply = Markdown(\"\")"],
        removed=["    transcript.append(ToolBlock(...))  # canned, all at once"],
        added=["    await _tool_call(tui, transcript, ...)  # streams, states flip"],
        footer="+1 \u22121 \u00b7 Took 0.2s", folds=folds)
    await _summary(tui, transcript)


async def _show_fixture(tui: TUI, transcript: Transcript) -> None:
    """The ``/md`` command: stream the rendering fixture in like a reply,
    then open the finished document at its top for reading.

    The fixture is the engine's acceptance surface, and streaming it is the
    point: every prefix renders safely -- a half-open fence keeps its body,
    a table waits for its delimiter row, an unclosed inline marker stays
    literal -- so the document visibly assembles itself.  The window rides
    the transcript tail while the block grows; when the last line lands, a
    hit test finds the block's topmost painted row and scrolls it to the
    window top -- public scroll API only, no private viewport state.
    """
    notice = transcript.append(Notice(f"Markdown rendering fixture · {SOURCE.name}"))
    notice.seal()
    md = Markdown("")
    block = transcript.append(md)
    await _stream_markdown(tui, md, SOURCE.read_text(encoding="utf-8"),
                           delay=FIXTURE_STREAM_DELAY)
    block.seal()  # complete: render once per width from the sealed cache
    tui.paint()  # lay the final document out before scrolling
    for y in range(tui.screen.height):
        hit = tui.hit_test(0, y)
        if hit is not None and hit.block is block:
            tui.scroll_up(hit.row - y)  # the block's first row to the window top
            tui.invalidate()
            return


async def _stream_preview(tui: TUI, pane: Pane) -> None:
    """The ``/preview`` body: stream the rendering fixture into the preview
    pane, one source line per frame -- the ``/md`` streaming, pointed at the
    pane the split opened.

    The pane's document is the split's fresh one (``pane.document.add(...)``
    is the public way a host fills a pane), and every frame invalidates the
    driver, so both panes repaint while the fixture assembles itself.
    """
    md = Markdown("")
    block = pane.document.add(md)
    await _stream_markdown(tui, md, SOURCE.read_text(encoding="utf-8"),
                           delay=FIXTURE_STREAM_DELAY)
    block.seal()
    tui.paint()


class _Preview:
    """The ``/preview`` state: the pane the fixture streams into, or ``None``
    while the frame holds no preview.

    Demo state over public pane handles, nothing bespoke: opening is
    ``tui.split("vertical")`` plus the fixture streaming into the second
    child, and closing is the kernel's un-split -- ``pane.close()`` leaves
    the leaf, collapses the split back onto the transcript pane and strips
    the divider, so a dismissed preview gives its cells back to the
    transcript instead of sitting empty beside it.
    """

    __slots__ = ("pane",)

    def __init__(self) -> None:
        self.pane: Pane | None = None


def _copy_and_toast(toasts: Toasts):
    """The demo's selection ``on_end``: copy the range, toast the OSC 52
    answer.

    The custom-``on_end`` cookbook pattern, live in the demo: the finished
    range arrives with the pane its addresses live in -- the driver's
    :attr:`TUI.selection_pane`, which is what tells one document's ``b0``
    from a split neighbour's identically numbered one -- and the text is
    read at the width that pane's rows were laid out at (its region, chrome
    subtracted), because a selection's row numbers address that wrapping.
    ``extract`` reads the document straight, so rows scrolled out of view
    copy too.  The write goes through
    :meth:`Screen.copy <mocode_tui.core.screen.Screen.copy>` and the toast
    shows **only when the screen answered ``True``** -- the OSC 52 feedback
    loop, since a non-live screen copies nothing and a live terminal may
    still refuse by policy.
    """

    def on_end(tui: TUI, selection: Selection) -> object:
        pane = tui.selection_pane
        region = None if pane is None else tui.frame.region(pane.id)
        document = tui.document if pane is None else pane.document
        width = tui.screen.width if region is None else region.width
        text = extract(document, selection, width=width)
        if tui.screen.copy(text):
            toasts.show(f"Copied {len(text.splitlines())} lines")

    return on_end


def _fold_press(tui: TUI, event, folds: dict[Block, _Fold]) -> bool:
    """Expand or fold a finished tool call on a press of its chevron row.

    The demo's one cell-level affordance, resolved *before* the selection
    gesture owns the left button: the ``_Fold`` state paints its mark
    (``▸`` folded, ``▾`` open) onto the call's title row, and that row --
    one band pad cell ahead of the mark, ``ToolBlock``'s -- is the call's
    click target.  A press anywhere else on a call's body belongs to the
    gesture, so dragging selects the tool output as visibly as the reply.
    """
    if not isinstance(event, MouseEvent):
        return False
    if event.name != "left" or event.kind != "press":
        return False
    hit = tui.hit_test(event.x, event.y)
    if hit is None:
        return False
    fold = folds.get(hit.block)
    if fold is None:
        return False
    rows = hit.block.render(tui.screen.width)
    if not 0 <= hit.row < len(rows):
        return False
    mark = "\u25be" if fold.open else "\u25b8"
    if not rows[hit.row].text.lstrip().startswith(mark):
        return False  # the body of an expanded call is the gesture's
    fold.toggle()
    return True


def _cycle_focus(tui: TUI) -> None:
    """Tab moves focus to the next pane (the demo's one key binding).

    :attr:`TUI.focus_policy` already focuses a pane on a press; this is the
    keyboard half of D4, over the frame's public pane list.  The cycle runs
    through the panes themselves -- ``pane.focus()`` routes through the
    frame that holds them, a pane it holds no focus request raising -- which
    lands wherever the tiling stands; a single-pane frame cycles to itself.
    """
    panes = tui.frame.panes
    focused = tui.frame.focused_pane
    if focused is None or not panes:
        return
    ids = [pane.id for pane in panes]
    if focused.id in ids:
        panes[(ids.index(focused.id) + 1) % len(panes)].focus()


async def _run_command(tui: TUI, value: str, transcript: Transcript, composer: Composer,
                       folds: dict[Block, _Fold], preview: _Preview) -> bool:
    """Run a palette selection (or a typed command); ``False`` when quitting.

    A palette selection arrives as the option's ``value`` (``"preview"``); a
    typed command arrives with its slash (``"/preview"``).  The leading slash
    is the palette's, so both spellings normalize to the bare command name.
    The streaming commands work as background tasks, the ``/md`` pattern:
    ``/preview`` splits synchronously -- the pane is on screen the instant
    the command runs -- and the fixture streams into it as a task in
    ``_TURNS``, so the loop keeps reading keys while it assembles.  The
    split's whole point stays watching the fixture assemble, now watchable
    while typing.
    """
    global _MODEL
    value = value[1:] if value.startswith("/") else value
    if value == "clear":
        transcript.clear()
        folds.clear()  # the folded blocks went with the scrollback
    elif value == "md":
        # The fixture streams like a reply: a background task the loop's
        # quit path waits on, exactly like an answer turn.
        task = asyncio.create_task(_show_fixture(tui, transcript))
        _TURNS.add(task)
        task.add_done_callback(_TURNS.discard)
    elif value == "preview":
        # Host policy over the public split API: the transcript keeps its
        # document in the first child, the fixture streams live into the
        # second -- and running it again dismisses the preview.  The split
        # is synchronous, so the pane is on screen the instant the command
        # runs; the fixture then streams as a background task, the /md
        # pattern, so the loop keeps reading keys while it assembles.
        if preview.pane is None:
            _, right = tui.split("vertical", ratios=(2, 1))
            preview.pane = right
            task = asyncio.create_task(_stream_preview(tui, right))
            _TURNS.add(task)
            task.add_done_callback(_TURNS.discard)
        else:
            _close_preview(tui, preview)
    elif value == "model":
        _MODEL = (_MODEL + 1) % len(_MODELS)
        composer.statusline.right = (_MODELS[_MODEL],)
    elif value == "quit":
        return False
    else:  # help
        transcript.append(Message("assistant", _HELP))
    return True


def _close_preview(tui: TUI, preview: _Preview) -> None:
    """Dismiss the preview: close its pane and hand the frame back.

    ``Pane.close()`` is the kernel's un-split, the whole dismiss path in
    one public call: the leaf leaves its parent's tiling and the split
    collapses onto the transcript pane -- which keeps its id, its document
    and its chrome, the scrollbar among it -- while the divider of the gap
    that closed goes with it, so the transcript re-wraps at the full width
    rather than sitting beside an empty pane.  Focus is the kernel's to
    fall back: when the preview held it, it lands on the pane that now
    occupies the preview's rectangle, the collapsed transcript.  The demo
    keeps its own ``preview.pane`` guard so a repeat dismiss is a no-op
    before the kernel ever sees it.

    A selection that lived in the preview went with its document: the
    driver's :attr:`TUI.selection_pane` stops resolving, so the highlight
    would paint nothing from here on and the demo retires it rather than
    leaving a dead range for a later copy to read.
    """
    pane = preview.pane
    if pane is None:
        return
    pane.close()
    preview.pane = None
    if tui.selection_pane is None:
        tui.set_selection(None)
    tui.invalidate()


# ---------------------------------------------------------------------------
# The one interactive body, shared by the live and scripted paths
# ---------------------------------------------------------------------------
async def chat(tui: TUI) -> None:
    global _ANSWERED
    _ANSWERED = False
    _TURNS.clear()  # in-flight background turns of this session
    _build_banner(tui)
    composer = _build_footer(tui)
    transcript = Transcript(tui)
    folds: dict[Block, _Fold] = {}  # finished tool calls, click-to-fold
    editor, palette = composer.editor, composer.palette
    preview = _Preview()  # the /preview pane, when the frame is split
    # The frame tier's public face, all host policy: a scrollbar chrome on
    # the transcript pane (named explicitly -- "primary" is the pane the
    # transcript lives in), the toast overlay the copy answers with, and the
    # selection gesture carrying the demo's own on_end.
    toasts = Toasts(tui)
    scrollbar = Scrollbar(tui, pane="primary")
    gesture = SelectionGesture(tui, on_end=_copy_and_toast(toasts))
    composer.anchor_cursor(tui)
    tui.paint()  # the very first frame already carries the IME anchor

    while True:
        event = await tui.read_key()
        if event is None:
            break  # key source exhausted (piped replay) or terminal closed
        # The dispatch order the chrome module documents: chrome first, then
        # the overlays, then the content gesture -- each answering the
        # consume-a-key contract, so a consumed event never reaches the
        # host's own dispatch below.  The demo's single cell-level affordance
        # (a folded call's chevron row) sits between the overlays and the
        # gesture: that row is the tool call's, every other cell is the
        # gesture's.
        if (
            scrollbar.handle(event)
            or toasts.handle(event)
            or _fold_press(tui, event, folds)
            or gesture.handle(event)
        ):
            composer.anchor_cursor(tui)
            tui.invalidate()
            continue
        # The palette owns only navigation and dismissal; every other key
        # falls through to the editor.  The two are decoupled, pi-style: the
        # menu never eats the keyboard.
        if palette.is_open:
            selected = palette.handle_key(event)
            if selected is not False:
                if isinstance(selected, str):
                    editor.clear()
                    if not await _run_command(tui, selected, transcript,
                                              composer, folds, preview):
                        break
                composer.anchor_cursor(tui)
                tui.invalidate()
                continue
        if editor.handle(event):
            pass  # an editing key: the editor consumed it
        elif event.name == "c-c":
            break
        elif event.name == "tab":
            _cycle_focus(tui)  # the keyboard half of focus switching
        elif event.name == "escape":
            if preview.pane is not None:
                _close_preview(tui, preview)
        elif event.name == "enter":
            text = editor.value.strip()
            editor.clear()
            if text.startswith("/"):
                if not await _run_command(tui, text, transcript, composer,
                                          folds, preview):
                    break
            elif text:
                # Answer in the background: the loop keeps read_key()ing, so
                # typing previews live while a turn streams.  Each turn owns
                # its own blocks -- concurrent turns may interleave in the
                # document, but no turn writes into another's blocks.
                task = asyncio.create_task(
                    _answer(tui, transcript, composer, text, rich=not _answered(),
                            folds=folds))
                _TURNS.add(task)
                task.add_done_callback(_TURNS.discard)
        # A leading slash owns the palette: typing one opens it, losing the
        # slash closes it.  Editing keys never re-open a dismissed palette --
        # only a freshly typed slash does -- so dismissing it with enter or
        # escape sticks while the typed command stays put.
        if editor.value.startswith("/") and not palette.is_open:
            palette.open()
        else:
            palette.set_query(editor.value)
        composer.anchor_cursor(tui)  # every keypress re-pins the IME cursor
        tui.invalidate()

    if _TURNS:
        # Let in-flight turns finish so the transcript (and the piped dump)
        # ends complete before the session stops -- a mid-turn quit would
        # leave the last answer's blocks half-written.
        await asyncio.gather(*_TURNS)
    tui.stop()


_ANSWERED = False

#: The session's in-flight background turns (answers, the streamed /md
#: fixture): the quit path gathers them so the dump ends complete.
_TURNS: set[asyncio.Task[None]] = set()


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
    """Three questions, a /preview visit (open, press-to-focus the preview,
    tab back to the transcript, wheel the preview, close), one slash-palette
    visit (open, navigate, dismiss), then Ctrl-C."""
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
    # /preview: type the command, dismiss the palette so the host sees enter,
    # and the frame splits -- the transcript keeps its document in the first
    # child while the fixture streams live into the second.
    for ch in "/preview":
        events.append(Key(ch, ch))
    events.append(Key("escape"))  # dismiss the palette; the typed text stays
    events.append(Key("enter"))  # the host's submit gesture: /preview runs
    # A press over the preview focuses that pane (the default focus policy,
    # D4's mouse half); the gesture behind it anchors nothing but a click.
    events.append(MouseEvent("left", button=0, x=80, y=8, kind="press"))
    events.append(MouseEvent("left", button=0, x=80, y=8, kind="release"))
    events.append(Key("tab"))  # the demo's key binding: focus back to the transcript
    # The wheel is nobody's chrome: read_key() routes it by pointer position
    # (D5), so these notches scroll the pane under (80, 8) -- the preview,
    # unfocused or not -- and one notch back down.
    events.append(MouseEvent("wheel_up", button=0, x=80, y=8, kind="press"))
    events.append(MouseEvent("wheel_up", button=0, x=80, y=8, kind="press"))
    events.append(MouseEvent("wheel_down", button=0, x=80, y=8, kind="press"))
    events.append(Key("escape"))  # dismisses the preview back to the transcript
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
    lines = [row.text for row in tui.rows]
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
