"""The streaming page: one long Markdown document, growing block by block.

The fixture beside :mod:`motui.demo.content` is the content: 346 lines,
every construct the engine renders.  Instead of mounting it whole, the page
mounts an **empty** :class:`~motui.Markdown` and a
:class:`MarkdownStream` fills it in, one block at a time, off the session's
own beat (the ``tick`` hook).  The document is cut by
:func:`~motui.demo.content.blocks_of`, so every prefix is a byte-exact slice
of the source.

The control bar is one ``Select`` whose pick the host reads once and
reports; the page's ``note`` turns the action's name into a verb on the
stream.  **Dump-safe by construction**: ``interactive=False`` (the piped
replay, ``--pages``) builds the stream finished -- no clock runs on those
paths -- so a dump always shows the whole fixture.
"""

from __future__ import annotations

from typing import Callable

from motui import FocusRing, Markdown, Option, Select, Text

from ..content import blocks_of, fixture_text
from ..page import PageBody, api_note, header, try_line

__all__ = ["CONTROLS", "MarkdownStream", "page"]

#: The control bar, in media-player order: label, action payload, description.
#: The payload is the *action* (``play``, ...) -- what the host's report
#: carries back and :meth:`MarkdownStream.act` resolves.
CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("\u25b6 play", "play", "grow the document from where it stands"),
    ("\u23f8 pause", "pause", "hold the stream where it is"),
    ("\u21e5 step", "step", "append the next block, then hold"),
    ("\u27f2 replay", "replay", "back to the first block, running"),
    ("\u00d7 speed", "speed", "cycle the pace: 1x / 2x / 4x"),
)

#: The control-bar rows the cursor parks on: running (``play``) or holding
#: (``pause`` -- the start state and the auto-stop).
PLAY_ROW = 0
PAUSE_ROW = 1



class MarkdownStream:
    """One document growing into a component, block by block, host-driven."""

    __slots__ = ("_blocks", "_markdown", "_pace", "_text", "cursor", "interactive", "playing")

    #: The ``speed`` control's cycle, in blocks appended per beat.
    PACE_STEPS: tuple[int, ...] = (1, 2, 4)

    def __init__(self, markdown: Markdown, text: str, *, interactive: bool) -> None:
        self._markdown = markdown
        self._text = text
        self._blocks = blocks_of(text)
        self._pace = self.PACE_STEPS[0]
        self.cursor = 0
        self.interactive = interactive
        # A page opens playing: the document grows as the exhibit arrives.
        self.playing = interactive
        if interactive:
            self._render()  # an empty document, about to grow
        else:  # no clock on this path: the document is whole from the start
            self.cursor = self.total
            self._render()

    @property
    def total(self) -> int:
        """How many blocks the source holds."""
        return len(self._blocks)

    @property
    def done(self) -> bool:
        """Whether the whole document is on screen."""
        return self.cursor >= self.total

    def advance(self, count: int = 1) -> None:
        """Append ``count`` blocks, never past the end; landing there stops."""
        self.cursor = min(self.cursor + max(count, 0), self.total)
        self._render()
        if self.done:
            self.playing = False

    def beat(self) -> None:
        """One page beat: append ``pace`` blocks while playing."""
        if self.playing:
            self.advance(self._pace)

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

    def speed(self) -> None:
        """Cycle the pace: 1x -> 2x -> 4x -> 1x, in blocks per beat."""
        index = self.PACE_STEPS.index(self._pace)
        self._pace = self.PACE_STEPS[(index + 1) % len(self.PACE_STEPS)]

    def act(self, action: str) -> bool:
        """Run one control-bar action by name; ``False`` for a name off the bar."""
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
        pace = "" if self._pace == 1 else f" \u00b7 {self._pace}x"
        return f"streaming: {self.cursor}/{self.total} blocks \u00b7 {state}{pace}"

    def _render(self) -> None:
        """Publish the cursor's prefix -- the whole source once it is at the end."""
        self._markdown.text = self._text if self.done else "".join(self._blocks[: self.cursor])


#: The five verbs, by the action name a control-bar pick carries.
_ACTIONS: dict[str, Callable[[MarkdownStream], None]] = {
    "play": MarkdownStream.play,
    "pause": MarkdownStream.pause,
    "step": MarkdownStream.step,
    "replay": MarkdownStream.replay,
    "speed": MarkdownStream.speed,
}


def page(session) -> PageBody:
    """The fixture, a control bar and the readout between them."""
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
        """The page beat: grow the document while playing, then repaint."""
        if stream.playing:
            stream.beat()
        progress.text = stream.status()
        if stream.done and not stream.playing:
            control.index = PAUSE_ROW

    def note(report: str) -> None:
        """One activation was reported: run the pick on the stream."""
        action = report.removeprefix("chosen: ").strip("'\"")
        if stream.act(action):
            progress.text = stream.status()

    return PageBody([
        *header("streaming",
                f"{len(text.splitlines())} lines of Markdown, streamed block by block -- "
                "play it, pause it, step through it, replay it.", theme),
        try_line("activate a row of the control bar below: play, pause, step or replay -- "
                 "or the replay row to start it over", theme),
        progress,
        control,
        markdown,
        api_note("markdown.text = \u2026 + tui.invalidate(); tui.every(PAGE_TICK, \u2026) is the beat",
                 theme),
    ], focus=FocusRing([control]), note=note, tick=tick)
