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
from .components import ComponentsScene
from .dashboard import DashboardScene
from .gallery import GalleryScene
from .layout import LayoutScene
from .menu import MenuScene
from .motion import MotionScene
from .placeholder import PlaceholderScene
from .splash import SplashScene

__all__ = [
    "SCENES",
    "ComponentsScene",
    "DashboardScene",
    "GalleryScene",
    "LayoutScene",
    "MenuScene",
    "MotionScene",
    "PlaceholderScene",
    "Scene",
    "SnakeScene",
    "SplashScene",
]

#: The scenes in tour order: the splash, the Home tiles, the six sections,
#: then the two standalone tours the contract pins (the snake game stays
#: renderable under its own name beside the motion section).
SCENES: tuple[str, ...] = (
    "splash",
    "menu",
    "components",
    "layout",
    "motion",
    "dashboard",
    "terminal",
    "themes",
    "snake",
    "gallery",
)

#: The sections later waves build; each ships as an under-construction
#: panel so the registry, tiles, golden set and ``--pages`` stay complete.
_PLACEHOLDERS: tuple[tuple[str, str], ...] = (
    ("terminal", "keys, mouse and paint, dissected"),
    ("themes", "the shipped themes, side by side"),
)


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
    """Build one scene object per :data:`SCENES`, in tour order.

    ``motion`` is the pixel rings board (with the snake board one ``tab``
    away); ``snake`` stays its own standalone scene object so the contract
    name keeps rendering the classic game.
    """
    scenes: dict[str, Scene] = {
        "splash": SplashScene(theme, seed=seed),
        "menu": MenuScene(theme),
        "components": ComponentsScene(theme),
        "layout": LayoutScene(theme),
        "dashboard": DashboardScene(theme),
        "gallery": GalleryScene(theme),
        "motion": MotionScene(theme),
        "snake": SnakeScene(theme),
    }
    for name, blurb in _PLACEHOLDERS:
        scenes[name] = PlaceholderScene(theme, name=name, blurb=blurb)
    return {key: scenes[key] for key in SCENES}
