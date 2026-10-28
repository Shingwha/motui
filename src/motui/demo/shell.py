"""The showcase shell: one widget owning the current scene and phase."""

from __future__ import annotations

from collections.abc import Callable

from ..kernel.cell import Line, Segment, Surface, cut_line
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from ..widgets import Panel, Text
from ..widgets.base import Widget
from .registry import SCENES, SPEC_BY_NAME, build_scenes
from .scene import START_PHASE

__all__ = ["START_PHASE", "Showcase"]

#: The wipe's length in ticks: nine ticks at the 60 Hz shell is ~150 ms.
_WIPE_TICKS = 9

_CLIP = WrapMode.CLIP


class Showcase(Widget):
    """The whole demo: a scene, a phase, the transition chrome and help.

    ``render`` delegates to the current scene and pads the answer to the
    pane's height budget.  While a wipe runs it holds the old scene at the
    phase it was left on, so the reveal never shows a reset scene.  ``tick``
    advances the phase; ``enter`` is the one reset door the shell calls on
    the initial scene and on every switch.
    """

    __slots__ = (
        "_help",
        "_scenes",
        "_wipe_from",
        "_wipe_phase",
        "on_quit",
        "phase",
        "scene",
        "status_line",
        "status_note",
    )

    focusable = True
    clickable = True

    on_quit: Callable[[], None] | None
    status_line: bool
    status_note: str
    _wipe_from: str | None
    _wipe_phase: int | None

    def __init__(
        self,
        scene: str = "splash",
        theme: Theme | None = None,
        *,
        seed: int | None = 0,
        status_line: bool = False,
        phase: int = START_PHASE,
    ) -> None:
        if scene not in SPEC_BY_NAME:
            raise ValueError(f"unknown scene {scene!r}: expected one of {SCENES}")
        resolved = Theme.dark() if theme is None else theme
        super().__init__(resolved)
        self._scenes = build_scenes(resolved, seed)
        self.scene = scene
        self.phase = phase
        self._wipe_from = None
        self._wipe_phase = None
        self._help = False
        self.status_line = status_line
        self.status_note = "--"
        self.on_quit = None
        self._scenes[scene].enter()

    @property
    def spec(self):
        """The current scene's registry descriptor."""
        return SPEC_BY_NAME[self.scene]

    @property
    def help_open(self) -> bool:
        return self._help

    def toggle_help(self) -> None:
        """Open or close the global help overlay; opening pauses ticks."""
        self._help = not self._help
        self.touch()

    def switch(self, name: str, *, phase: int = START_PHASE) -> None:
        """Make ``name`` the current scene, wiping it in over the old one."""
        if name not in SPEC_BY_NAME:
            raise ValueError(f"unknown scene {name!r}: expected one of {SCENES}")
        if name != self.scene:
            self._wipe_from = self.scene
            self._wipe_phase = self.phase
        else:
            self._wipe_from = None
            self._wipe_phase = None
        self._scenes[name].enter()
        self.scene = name
        self.phase = phase
        self._help = False
        self.touch()

    def seek(self, phase: int) -> None:
        """Move the phase; a rewind enters the current scene afresh."""
        if phase < self.phase:
            self._scenes[self.scene].enter()
            self.phase = START_PHASE
            self._wipe_from = None
            self._wipe_phase = None
        self.phase = phase
        self._help = False
        self.touch()

    def tick(self) -> str | None:
        """Advance one animation tick; a help overlay pauses the clock."""
        if self._help:
            return None
        self.phase += 1
        if self._wipe_from is not None and self.phase >= _WIPE_TICKS:
            self._wipe_from = None
            self._wipe_phase = None
        target = self._scenes[self.scene].tick(self.phase)
        if target is not None:
            self._route(target)
        else:
            self.touch()
        return target

    def on_key(self, event: KeyEvent) -> bool:
        """Route a key; F1 toggles help before the scene sees the event."""
        if event.key == "f1":
            self.toggle_help()
            return True
        if self._help:
            if event.key == "escape":
                self.toggle_help()
            return True
        target = self._scenes[self.scene].on_key(event)
        self._route(target)
        return True

    def on_click(self, pos: Pos) -> bool:
        """A click closes help or routes to the scene."""
        if self._help:
            self.toggle_help()
            return True
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
        """The current scene's rows: wiped in, padded, help and status last."""
        surface = self._scenes[self.scene].render(c, self.phase)
        if self._wipe_from is not None and self._wipe_phase is not None:
            previous = self._scenes[self._wipe_from].render(c, self._wipe_phase)
            rows = self._wipe(surface, previous, c.width)
        else:
            rows = list(surface)
        budget = c.max_height
        if budget is not None:
            rows = rows[:budget]
            rows.extend(Line() for _ in range(budget - len(rows)))
        if self.status_line and rows:
            rows[-1] = self._status(c.width)
        if self._help:
            rows = self._help_overlay(rows, c.width)
        return Surface.of(rows, c.width)

    def _wipe(self, current: Surface, previous: Surface, width: int) -> list[Line]:
        """Splice ``current`` over ``previous`` at the phase's reveal column.

        The column count is a pure function of the phase, so a wipe replay
        reproduces every middle frame exactly; ``phase + 1`` keeps the first
        frame after a switch from being empty.
        """
        cols = min(width, width * (self.phase + 1) // _WIPE_TICKS)
        if cols <= 0:
            return list(previous)
        if cols >= width:
            return list(current)
        return [
            cut_line(new, 0, cols) + cut_line(old, cols, width)
            for new, old in zip(current, previous, strict=False)
        ]

    def _status(self, width: int) -> Line:
        """The bottom bar: the scene title, then the theme/fps note."""
        title = self.spec.title
        note = self.status_note
        gap = max(1, width - len(title) - len(note))
        line = Line(
            (
                Segment(title, self.theme.content.accent),
                Segment(" " * gap, self.theme.text.faint),
                Segment(note, self.theme.text.faint),
            )
        )
        return line.clip(_CLIP, width)

    def _help_overlay(self, rows: list[Line], width: int) -> list[Line]:
        """A centred help panel over the current scene; covers its rows."""
        spec = self.spec
        lines = [
            f"{spec.title} \u2014 {spec.blurb}",
            "",
            "global: F1 close \u00b7 ctrl+p commands \u00b7 esc back \u00b7 q quit",
            "",
        ]
        lines.extend(f"{key:<16} {action}" for key, action in spec.keys)
        panel_w = min(68, max(24, width - 6))
        panel = Panel(
            Text("\n".join(lines), theme=self.theme),
            title="help",
            theme=self.theme,
        )
        panel_rows = list(
            panel.render(Constraints(width=panel_w, max_height=max(1, len(rows) - 2)))
        )
        left = max(0, (width - panel_w) // 2)
        top = max(0, (len(rows) - len(panel_rows)) // 2)
        prefix = Line((Segment(" " * left),))
        for offset, row in enumerate(panel_rows):
            y = top + offset
            if 0 <= y < len(rows):
                rows[y] = (prefix + row).fill(width)
        return rows

    def __repr__(self) -> str:
        return f"Showcase(scene={self.scene!r}, phase={self.phase})"
