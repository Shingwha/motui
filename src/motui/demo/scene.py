"""The showcase's scene contract and its one registry descriptor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from ..kernel.cell import Line, Surface
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.theme import Theme

__all__ = [
    "PAGE_PHASE",
    "START_PHASE",
    "TICK_HZ",
    "Miniature",
    "Scene",
    "SceneFactory",
    "SceneSpec",
]

#: The shell's animation tick rate.
TICK_HZ = 60

#: The phase a scene starts on when it is entered.
START_PHASE = 0

#: The default preview phase shared by ``--pages`` and semantic snapshots.
#: Motion overrides it with a phase where its first rings are alive.
PAGE_PHASE = 20

#: One phase-driven miniature for a Home tile: ``(phase, width, theme)``.
Miniature = Callable[[int, int, Theme], list[Line]]

#: A scene factory receives the theme and the splash seed.
SceneFactory = Callable[[Theme, "int | None"], "Scene"]


class Scene:
    """One showcase scene: render a frame, advance, route input.

    ``enter`` is the only reset door: the shell calls it for the initial
    scene and on every switch, and a scene must leave the same state it
    would have on a first visit.  Within one entry the phase passed to
    ``tick``/``render`` is non-decreasing; a seek that rewinds enters the
    scene again.
    """

    name: ClassVar[str] = ""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = START_PHASE

    def enter(self) -> None:
        self._phase = START_PHASE

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def render(self, c: Constraints, phase: int) -> Surface:
        raise NotImplementedError

    def on_key(self, event: KeyEvent) -> str | None:
        return None

    def on_click(self, pos: Pos) -> str | None:
        return None


@dataclass(frozen=True, slots=True)
class SceneSpec:
    """Everything the shell, Home tiles and command palette need about a scene."""

    name: str
    title: str
    blurb: str
    factory: SceneFactory
    keys: tuple[tuple[str, str], ...] = ()
    mini: Miniature | None = None
    preview_phase: int = PAGE_PHASE
    jumpable: bool = True
