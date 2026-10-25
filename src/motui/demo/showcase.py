"""The showcase's scene machine: one widget, three matching scenes.

``Showcase`` is the widget ``python -m motui`` fills its pane with.  It
owns the current scene's name and one integer **phase** -- the animation
clock -- and delegates rendering and input to the scene object.  The
runner ticks it about thirty times a second; a scene that wants to leave
answers ``Showcase`` with the next scene's name (or ``"quit"``).

The scene protocol is deliberately narrow: ``render``, ``tick``, ``on_key``
and ``on_click``.  Scenes are plain objects, not widgets: the showcase is
the one focus target and hands the scene its own coordinates, which keeps
the App's focus ring out of the demo's business.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..kernel.cell import Line, Surface
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.theme import Theme
from ..widgets.base import Widget

__all__ = ["SCENES", "Scene", "Showcase"]

#: The scenes in tour order: the splash, the menu, the gallery.
SCENES: tuple[str, ...] = ("splash", "menu", "gallery")

#: The phase (animation tick) a scene starts on when it is entered.
START_PHASE = 0


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


class _PlaceholderScene:
    """The skeleton's stand-in until the real scenes land."""

    def __init__(self, name: str, theme: Theme) -> None:
        self.name = name
        self.theme = theme

    def render(self, c: Constraints, phase: int) -> Surface:
        row = Line.from_text(f"/{self.name}")
        return Surface.of([row], c.width)

    def tick(self, phase: int) -> str | None:
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        return None

    def on_click(self, pos: Pos) -> str | None:
        return None


def _scenes(theme: Theme) -> dict[str, Scene]:
    """Build one scene object per :data:`SCENES`, in tour order."""
    return {name: _PlaceholderScene(name, theme) for name in SCENES}


class Showcase(Widget):
    """The whole demo: a scene name, a phase and the scene objects.

    ``render`` delegates to the current scene and pads the answer to the
    pane's height budget, so the fill section owns every row exactly as a
    full-screen widget must.  ``tick`` advances the phase (the scenes read
    it for sweeping, pulsing and progress) and applies a scene's transition;
    ``on_key``/``on_click`` do the same for input.  ``on_quit`` is the host's
    callback for the ``"quit"`` transition -- the showcase never touches the
    runtime itself.
    """

    __slots__ = ("_scenes", "on_quit", "phase", "scene")

    #: The host's quit callback (``App.quit`` under ``python -m motui``).
    on_quit: Callable[[], None] | None

    #: The showcase is the App's one focus target and takes mouse clicks.
    focusable = True
    clickable = True

    def __init__(self, scene: str = "splash", theme: Theme | None = None) -> None:
        if scene not in SCENES:
            raise ValueError(f"unknown scene {scene!r}: expected one of {SCENES}")
        resolved = Theme.dark() if theme is None else theme
        super().__init__(resolved)
        self._scenes = _scenes(resolved)
        self.scene = scene
        self.phase = START_PHASE
        self.on_quit = None

    def switch(self, name: str, *, phase: int = START_PHASE) -> None:
        """Make ``name`` the current scene, resetting the phase by default."""
        if name not in SCENES:
            raise ValueError(f"unknown scene {name!r}: expected one of {SCENES}")
        self.scene = name
        self.phase = phase
        self.touch()

    def tick(self) -> str | None:
        """Advance one animation tick; answer the transition, if any."""
        self.phase += 1
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
        """The current scene's rows, padded to the pane's height budget."""
        surface = self._scenes[self.scene].render(c, self.phase)
        rows = list(surface)
        budget = c.max_height
        if budget is None:
            return Surface.of(rows, c.width)
        rows = rows[:budget]
        if len(rows) < budget:
            rows.extend(Line() for _ in range(budget - len(rows)))
        return Surface.of(rows, c.width)

    def __repr__(self) -> str:
        return f"Showcase(scene={self.scene!r}, phase={self.phase})"
