"""The showcase's sections: one scene class per file plus the registry.

Each :class:`Scene` is a plain object -- not a widget -- that renders whole
frames and answers transitions; :func:`_scenes` builds one object per
:data:`SCENES` entry for a given theme, and the shell widget
(:mod:`motui.demo.shell`) owns whichever section is current.
"""

from __future__ import annotations

from typing import Protocol

from ...kernel.cell import Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.theme import Theme
from ..snake import SnakeScene
from .dashboard import DashboardScene
from .gallery import GalleryScene
from .menu import MenuScene
from .splash import SplashScene

__all__ = [
    "SCENES",
    "DashboardScene",
    "GalleryScene",
    "MenuScene",
    "Scene",
    "SnakeScene",
    "SplashScene",
]

#: The scenes in tour order: splash, menu, snake, dashboard, gallery.
SCENES: tuple[str, ...] = ("splash", "menu", "snake", "dashboard", "gallery")


class Scene(Protocol):
    """One showcase scene: render a frame, advance, route input.

    ``render`` answers the rows for the whole pane, filled by the
    :class:`Showcase`; ``tick`` runs once per animation tick and may name
    the next scene; ``on_key``/``on_click`` may do the same or answer
    ``None``.  A transition is one of :data:`SCENES` or ``"quit"``.
    """

    name: str

    def render(self, c: Constraints, phase: int) -> Surface: ...

    def tick(self, phase: int) -> str | None: ...

    def on_key(self, event: KeyEvent) -> str | None: ...

    def on_click(self, pos: Pos) -> str | None: ...


def _scenes(theme: Theme, *, seed: int | None = 0) -> dict[str, Scene]:
    """Build one scene object per :data:`SCENES`, in tour order."""
    return {
        "splash": SplashScene(theme, seed=seed),
        "menu": MenuScene(theme),
        "snake": SnakeScene(theme),
        "dashboard": DashboardScene(theme),
        "gallery": GalleryScene(theme),
    }
