"""The showcase's shell: one widget owning the current section and phase.

``Showcase`` is the widget ``python -m motui`` fills its pane with.  It
owns the current section's name and one integer **phase** -- the animation
clock -- and delegates rendering and input to the section object.  The
runner ticks it sixty times a second; a section that wants to leave
answers ``Showcase`` with the next section's name (or ``"quit"``).

Two pieces of chrome live in the shell rather than any section: entering
a different section wipes it in column by column (deterministic from the
phase, so headless replays land byte for byte), and an optional status
line pins the section name and a theme/fps note to the bottom row.

Sections are plain objects, not widgets: the shell is the one focus target
and hands the section its own coordinates, which keeps the App's focus ring
out of the demo's business.
"""

from __future__ import annotations

from collections.abc import Callable

from ..kernel.cell import Line, Segment, Surface, cut_line
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.theme import Theme
from ..widgets.base import Widget
from .sections import SCENES, Scene, _scenes

__all__ = ["START_PHASE", "Showcase"]

#: The phase (animation tick) a scene starts on when it is entered.
START_PHASE = 0

#: The wipe's length in ticks: nine ticks at the 60 Hz shell is ~150 ms.
_WIPE_TICKS = 9


class Showcase(Widget):
    """The whole demo: a scene name, a phase and the scene objects.

    ``render`` delegates to the current scene and pads the answer to the
    pane's height budget, so the fill section owns every row exactly as a
    full-screen widget must; while a wipe is running it splices the old
    section's rows to the left of the reveal column.  ``tick`` advances the
    phase (the scenes read it for sweeping, pulsing and progress) and
    applies a scene's transition; ``on_key``/``on_click`` do the same for
    input.  ``on_quit`` is the host's callback for the ``"quit"``
    transition -- the showcase never touches the runtime itself.
    """

    __slots__ = (
        "_scenes",
        "_wipe_from",
        "on_quit",
        "phase",
        "scene",
        "status_line",
        "status_note",
    )

    #: The host's quit callback (``App.quit`` under ``python -m motui``).
    on_quit: Callable[[], None] | None

    #: The showcase is the App's one focus target and takes mouse clicks.
    focusable = True
    clickable = True

    #: Whether the bottom status row is drawn at all (live runs: yes).
    status_line: bool

    #: The status row's right-hand note; the live runner feeds it
    #: ``theme - fps`` from a painter-frames diff, determinate modes
    #: keep the ``--`` default.
    status_note: str

    #: The section a running wipe reveals over, or ``None`` when static.
    _wipe_from: str | None

    def __init__(
        self,
        scene: str = "splash",
        theme: Theme | None = None,
        *,
        seed: int | None = 0,
        status_line: bool = False,
    ) -> None:
        if scene not in SCENES:
            raise ValueError(f"unknown scene {scene!r}: expected one of {SCENES}")
        resolved = Theme.dark() if theme is None else theme
        super().__init__(resolved)
        self._scenes = _scenes(resolved, seed=seed)
        self.scene = scene
        self.phase = START_PHASE
        self._wipe_from = None
        self.status_line = status_line
        self.status_note = "--"
        self.on_quit = None

    def switch(self, name: str, *, phase: int = START_PHASE) -> None:
        """Make ``name`` the current scene, wiping it in over the old one."""
        if name not in SCENES:
            raise ValueError(f"unknown scene {name!r}: expected one of {SCENES}")
        if name != self.scene:
            # A fresh visit gets a fresh style order (and a live seed gives a
            # different order on every return to the splash); leaving one
            # section for another starts a column wipe from the old one.
            self._wipe_from = self.scene
        else:
            self._wipe_from = None
        if name == "splash":
            self._scenes["splash"].restart()
        self.scene = name
        self.phase = phase
        self.touch()

    def tick(self) -> str | None:
        """Advance one animation tick; answer the transition, if any."""
        self.phase += 1
        if self._wipe_from is not None and self.phase >= _WIPE_TICKS:
            self._wipe_from = None
        target = self._scenes[self.scene].tick(self.phase)
        if target is not None:
            self._route(target)
        else:
            self.touch()
        return target

    def on_key(self, event: KeyEvent) -> bool:
        """Route a key to the scene; the showcase consumes every key."""
        target = self._scenes[self.scene].on_key(event)
        self._route(target)
        return True

    def on_click(self, pos: Pos) -> bool:
        """Route a click to the scene; the showcase consumes it."""
        target = self._scenes[self.scene].on_click(pos)
        self._route(target)
        return True

    def _route(self, target: str | None) -> None:
        """Apply one scene transition (``None`` is a no-op)."""
        if target is None:
            return
        if target == "quit":
            if self.on_quit is not None:
                self.on_quit()
            return
        self.switch(target)

    def render(self, c: Constraints) -> Surface:
        """The current scene's rows: wiped in, padded, status bar last."""
        surface = self._scenes[self.scene].render(c, self.phase)
        if self._wipe_from is not None:
            previous = self._scenes[self._wipe_from].render(c, self.phase)
            rows = self._wipe(surface, previous, c.width)
        else:
            rows = list(surface)
        budget = c.max_height
        if budget is None:
            result = rows
        else:
            result = rows[:budget]
            if len(result) < budget:
                result.extend(Line() for _ in range(budget - len(result)))
        if self.status_line and result:
            result[-1] = self._status(c.width)
        return Surface.of(result, c.width)

    def _wipe(self, current: Surface, previous: Surface, width: int) -> list[Line]:
        """Splice ``current`` over ``previous`` at the phase's reveal column.

        The column count is a pure function of the phase, so a wipe replay
        (same switches, same ticks) reproduces every middle frame exactly;
        ``phase + 1`` keeps the first frame after a switch from being empty.
        """
        cols = min(width, width * (self.phase + 1) // _WIPE_TICKS)
        if cols <= 0:
            return list(previous)
        if cols >= width:
            return list(current)
        return [
            cut_line(new, 0, cols) + cut_line(old, cols, width)
            for new, old in zip(current, previous)
        ]

    def _status(self, width: int) -> Line:
        """The bottom bar: the section name on the left, the note on the right."""
        note = self.status_note
        gap = max(1, width - len(self.scene) - len(note))
        return Line(
            (
                Segment(self.scene, self.theme.content.accent),
                Segment(" " * gap, self.theme.text.faint),
                Segment(note, self.theme.text.faint),
            )
        )

    def __repr__(self) -> str:
        return f"Showcase(scene={self.scene!r}, phase={self.phase})"
