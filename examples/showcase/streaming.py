"""The streaming exhibit: one long Markdown document, growing block by block.

The fixture beside this package is the content: 346 lines, every construct
the engine renders -- and instead of mounting it whole, the page mounts an
**empty** :class:`~mocode_tui.Markdown` and a :class:`MarkdownStream` fills it
in, one block at a time, off the shell's own beat (``tui.every(PAGE_TICK,
...)``, handed to the page as :attr:`~showcase.page.PageBody.tick`).  The
document is cut by the same splitter the chat page's replies use
(:func:`~showcase.content.blocks_of`), so the exhibit and the chat layer grow
their text the same way; the difference is only who drives the cursor.

**The control bar** is one :class:`~mocode_tui.Select` with five rows --
``play / pause / step / replay / speed`` -- which is the demo of the D6
recipe: this library ships no ``Button``, so a menu whose activation the host
reads once *is* the button.  Nothing on the bar carries a callback.  The pick
travels the documented road: ``activate()`` writes it into ``chosen``, the
host reads that once and reports it (the toast), and the report comes back to
the page through :attr:`~showcase.page.PageBody.note` -- the page hook, not a
component callback -- where :meth:`MarkdownStream.act` turns the action's name
into a verb on the stream.  One activation is one report and one step of the
document.

**Dump-safe by construction.**  The piped replay and ``--pages`` run no pump
clock, so no beat would ever grow a partial document there:
``interactive=False`` builds the stream **finished** (the page's very first
frame is the whole fixture) and :meth:`MarkdownStream.act` answers every pick
without moving the cursor -- a pause or a replay on a path that cannot resume
could only shrink the document, and a dump is a document, not a promise.  On
a real terminal the same page opens *playing*: the document grows as you
arrive, and opening the exhibit again starts it over, because the page is
rebuilt from scratch on every :meth:`~showcase.session.Showcase.show`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

from mocode_tui import FocusRing, Markdown, Option, Select, Text

from .content import blocks_of, fixture_text
from .page import PageBody, api_note, header, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["MarkdownStream", "kind_of", "page"]

#: The control bar, in media-player order: the row's label, the action its
#: payload names, and the description beside it.  The payload is the *action*
#: (``play``, ``pause``, ...), because the action is what the host's report
#: carries back and what :meth:`MarkdownStream.act` resolves -- the label is
#: for the eye, the value for the wire.
CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("\u25b6 play", "play", "grow the document from where it stands"),
    ("\u23f8 pause", "pause", "hold the stream where it is"),
    ("\u21e5 step", "step", "append the next block, then hold"),
    ("\u27f2 replay", "replay", "back to the first block, running"),
    ("\u00d7 speed", "speed", "cycle the pace: 1x / 2x / 4x"),
)

#: The control-bar rows the cursor parks on for a stream that is running
#: (``play``) or holding (``pause`` -- the start state and the auto-stop).
PLAY_ROW = 0
PAUSE_ROW = 1

#: The pace the speed row cycles through: blocks per page beat.  A beat is
#: :data:`~showcase.session.PAGE_TICK` (0.1s), so 1x is ten blocks a second --
#: the whole fixture in about ten seconds -- and the faster settings shorten
#: the wait to see the end of the document.
SPEEDS: tuple[int, ...] = (1, 2, 4)

#: What a list item's first line looks like: a bullet or an ordered marker.
#: Task lists (``- [ ] ``) start like any other bullet, which is what the
#: readout calls them.
_LIST_ITEM = re.compile(r"(?:[-*+]|\d{1,9}[.)])\s")


def kind_of(block: str) -> str:
    """The construct one block is, for the progress line's readout.

    The order of the tests is the order of the markers' specificity: a fence
    first (its info string could hold anything), then the quote, table,
    heading and rule markers, then a list item -- and everything else is a
    paragraph, the setext heading included, which no leading marker
    announces.
    """
    first = next((line.strip() for line in block.splitlines() if line.strip()), "")
    if first.startswith(("```", "~~~")):
        return "code"
    if first.startswith(">"):
        return "quote"
    if first.startswith("|"):
        return "table"
    if first.startswith("#"):
        return "heading"
    if first.startswith(("---", "***", "___")):
        return "rule"
    if _LIST_ITEM.match(first):
        return "list"
    return "paragraph"


class MarkdownStream:
    """One document growing into a component, block by block, host-driven.

    The page-side controller: it holds the target :class:`~mocode_tui.Markdown`,
    the source text, its blocks (:func:`~showcase.content.blocks_of`), the
    cursor (how many blocks are on screen), the state (``playing``, paused, or
    ``done`` -- the cursor at the end) and the current speed.  It never sleeps
    and never repaints: the page's beat calls :meth:`beat` on the pump's
    clock, and the host's next invalidate paints the growth.  The controller
    is therefore a state a dump can read, not a task a dump must wait for.

    **The verbs** are the control bar's five rows, each one cursor move:
    :meth:`play` (a document already at the end starts over, the way a
    player's play does), :meth:`pause`, :meth:`step` (one block, then hold),
    :meth:`replay` (back before the first block, running) and
    :meth:`cycle_speed`.  :meth:`act` is their one entry -- the page's
    ``note`` hook resolves the pick the host read off the bar into an action
    name and hands it here -- while :meth:`advance` and :meth:`finish` are the
    raw moves beneath them.  Reaching the end **stops the stream** (the beat
    that completes the document leaves ``playing`` ``False``); the page parks
    the control bar and its progress line reads ``done``.

    **A non-interactive stream is a finished one.**  ``interactive=False``
    (the piped replay, ``--pages``) constructs the document whole, and
    :meth:`act` leaves the cursor alone there, whatever was picked: no clock
    runs on those paths, so a pause or a replay could only shrink the
    document, and a dump that shows a partial fixture is a dump that lies.

    **Every prefix is the source's own bytes.**  The blocks carry the blank
    lines that followed them, so a prefix never re-spaces the Markdown around
    a cut, and the document's last state is the source text itself, character
    for character -- which is what lets the chat page's final block be
    compared with the reply it streamed.
    """

    __slots__ = ("_blocks", "_markdown", "_speed", "_text", "cursor", "interactive", "playing")

    def __init__(self, markdown: Markdown, text: str, *, interactive: bool) -> None:
        self._markdown = markdown
        self._text = text
        self._blocks = blocks_of(text)
        self.cursor = 0
        self._speed = 0
        self.interactive = interactive
        # A page opens playing: the document grows as the exhibit arrives.
        self.playing = interactive
        if interactive:
            self._render()  # an empty document, about to grow
        else:
            self.finish()  # no clock on this path: the stream is the document

    @property
    def total(self) -> int:
        """How many blocks the source holds."""
        return len(self._blocks)

    @property
    def done(self) -> bool:
        """Whether the whole document is on screen."""
        return self.cursor >= self.total

    @property
    def speed(self) -> int:
        """The current multiplier: :data:`SPEEDS`'s entry under the cursor."""
        return SPEEDS[self._speed]

    @property
    def blocks_per_beat(self) -> int:
        """How many blocks one page beat appends at the current speed."""
        return self.speed

    def advance(self, count: int = 1) -> None:
        """Append ``count`` blocks, never past the end; landing there stops.

        The auto-stop is the completing beat's: the document is whole, so the
        stream is no longer playing -- and a later :meth:`play` starts it
        over.
        """
        self.cursor = min(self.cursor + max(count, 0), self.total)
        self._render()
        if self.done:
            self.playing = False

    def finish(self) -> None:
        """Put the whole document on screen in one step, and hold."""
        self.cursor = self.total
        self.playing = False
        self._render()

    def beat(self) -> None:
        """One page beat: append the speed's blocks while playing."""
        if self.playing:
            self.advance(self.blocks_per_beat)

    def play(self) -> None:
        """Start (or resume) the stream; a finished document starts over."""
        if self.done:
            self.cursor = 0
            self._render()
        self.playing = True

    def pause(self) -> None:
        """Hold the stream where it is."""
        self.playing = False

    def step(self) -> None:
        """Append exactly one block and hold -- the frame-by-frame walk."""
        self.playing = False
        self.advance(1)

    def replay(self) -> None:
        """Back before the first block, running again."""
        self.cursor = 0
        self._render()
        self.playing = True

    def cycle_speed(self) -> None:
        """Step to the next multiplier in :data:`SPEEDS`, wrapping around."""
        self._speed = (self._speed + 1) % len(SPEEDS)

    def act(self, action: str) -> bool:
        """Run one control-bar action by name; ``False`` for a name off the bar.

        The one entry a pick takes.  A non-interactive stream answers the pick
        and leaves the cursor alone -- the document stays whole there,
        whatever was picked.
        """
        handler = _ACTIONS.get(action)
        if handler is None:
            return False
        if self.interactive:
            handler(self)
        return True

    def status(self) -> str:
        """The progress line: how far the stream is, what arrived, its state."""
        if self.playing:
            state = "playing"
        else:
            state = "done" if self.done else "paused"
        where = kind_of(self._blocks[self.cursor - 1]) if self.cursor else "ready"
        return (f"streaming: {self.cursor}/{self.total} blocks \u00b7 {where} \u00b7 "
                f"{state} \u00b7 {self.speed}x")

    def _render(self) -> None:
        """Publish the cursor's prefix -- the whole source once it is at the end."""
        self._markdown.text = self._text if self.done else "".join(self._blocks[: self.cursor])


#: The five verbs, by the action name a control-bar pick carries.
_ACTIONS: dict[str, Callable[[MarkdownStream], None]] = {
    "play": MarkdownStream.play,
    "pause": MarkdownStream.pause,
    "step": MarkdownStream.step,
    "replay": MarkdownStream.replay,
    "speed": MarkdownStream.cycle_speed,
}


def page(session: Showcase) -> PageBody:
    """The fixture, a control bar, and the readouts between them.

    The page is built fresh on every :meth:`~showcase.session.Showcase.show`,
    so opening the exhibit -- or coming back to it -- always replays the
    document from its first block; on a non-interactive path the same
    constructor builds it finished instead (the stream's own rule), which is
    what keeps ``--pages`` and the piped dump complete.

    The three hooks are the page's whole wiring: ``note`` turns the host's
    report of one control-bar pick into a stream verb, ``tick`` advances the
    stream on the shell's beat while it is playing, and both repaint the
    progress line -- while the bar's cursor stays where the user left it,
    except for the one move the stream makes by itself: the beat that
    completes the document parks the cursor on the pause row.
    """
    theme = session.theme
    text = fixture_text()
    markdown = Markdown("", theme=theme)
    stream = MarkdownStream(markdown, text, interactive=session.tui.interactive)
    control = Select(
        [Option(label, value=action, description=note) for label, action, note in CONTROLS],
        max_rows=None,  # all five rows are the bar: a control that scrolls is not one
        wrap=False,  # the bar's ends are ends: stepping off play holds, it does not jump
        theme=theme,
    )
    control.index = PLAY_ROW if stream.playing else PAUSE_ROW
    progress = Text(stream.status(), style=theme.dim)

    def tick() -> None:
        """The page beat: grow the document while playing, then repaint.

        The host invalidates the frame after this returns, so the growth is
        painted with the beat that made it.  The one cursor move the page
        makes on its own lives here: a stream the beat just completed parks
        the bar on the pause row -- the stop is visible there as well as in
        the progress line's ``done``.
        """
        if stream.playing:
            stream.beat()
        progress.text = stream.status()
        if stream.done and not stream.playing:
            control.index = PAUSE_ROW

    def note(report: str) -> None:
        """One activation was reported: run the pick on the stream.

        The host has read the control bar's ``chosen`` once and reported the
        action's name (``chosen: 'pause'``); the name is the whole message,
        and :meth:`MarkdownStream.act` is the only thing it reaches.  The bar
        keeps no callback -- component -> ``chosen`` -> host report -> this
        hook -> the controller is the whole road.

        The pick moves the document, never the bar: the row under the user's
        hand stays there (a transport does not jump under the finger), and
        only a stream that stopped *itself* -- the beat in ``tick`` -- parks
        the cursor on the pause row.
        """
        action = report.removeprefix("chosen: ").strip("'\"")
        if stream.act(action):
            progress.text = stream.status()

    return PageBody([
        *header("streaming",
                f"{len(text.splitlines())} lines of Markdown, streamed block by block -- "
                "play it, pause it, step through it, replay it.", theme),
        try_line("activate a row of the control bar below: play, pause, step or replay -- "
                 "or the speed row to change the pace", theme),
        control,
        api_note("Select.activate() -> chosen -- the host reads the pick once and the page "
                 "drives the stream", theme),
        progress,
        markdown,
        api_note("markdown.text = \u2026 + tui.invalidate(); tui.every(PAGE_TICK, \u2026) is the beat",
                 theme),
    ], focus=FocusRing([control]), hint="the control bar", note=note, tick=tick)
