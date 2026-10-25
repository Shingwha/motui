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

from ..kernel.cell import Line, Segment, Surface
from ..kernel.events import KeyEvent
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from ..widgets.base import Widget
from ..widgets.choice import Option, Select
from ..widgets.decor import Panel
from ..widgets.layout import Column
from ..widgets.text import Text
from .art import big_text, center, gradient_styles

__all__ = ["SCENES", "MenuScene", "Scene", "Showcase", "SplashScene"]

#: Single-row clip for the composed menu rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP

#: The scenes in tour order: the splash, the menu, the gallery.
SCENES: tuple[str, ...] = ("splash", "menu", "gallery")

#: The phase (animation tick) a scene starts on when it is entered.
START_PHASE = 0

#: How long the splash holds before the menu: 60 ticks at 30 Hz is two seconds.
SPLASH_TICKS = 60

#: The logo's ink: the accent fades into the inline-code lavender.
LOGO_START = "#53c8f0"
LOGO_END = "#c4b5fd"


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


class SplashScene:
    """The opening: a pixel logo, a subtitle, a sweep and a pulse.

    The logo is the 5x7 word ``motui`` painted cell by cell through
    :func:`~motui.demo.art.big_text`: a two-color ramp runs across it and a
    bright column sweeps one cell every other tick.  The subtitle and the
    hint sit under it, and five dots pulse in the bottom band.  Any key or
    click skips to the menu, and so does :data:`SPLASH_TICKS` of idle time.
    """

    name = "splash"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._logo_width = 5 * len("motui") + 4
        self._logo_styles = gradient_styles(LOGO_START, LOGO_END, self._logo_width)
        self._sweep_style = Style(fg=(255, 255, 255), bold=True)

    def render(self, c: Constraints, phase: int) -> Surface:
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        sweep = (phase % (self._logo_width + 12)) - 6
        logo = center(
            width,
            big_text(
                "motui",
                styles=self._logo_styles,
                highlight=sweep,
                highlight_style=self._sweep_style,
            ),
        )
        subtitle = center(
            width,
            [Line.from_text("a terminal UI kernel \u00b7 2.0.0", self.theme.text.muted)],
        )
        dots = center(width, [self._pulse(phase)])
        hint = center(width, [Line.from_text("press any key", self.theme.text.faint)])
        content = [
            *logo,
            Line(),
            *subtitle,
            Line(),
            *dots,
            Line(),
            *hint,
        ]
        top = max(0, (height - len(content)) // 2)
        rows = [Line() for _ in range(top)] + content
        return Surface.of(rows, width)

    def _pulse(self, phase: int) -> Line:
        """Five dots with one lit: the quiet breathing mark under the logo."""
        lit = (phase // 4) % 5
        segments: list[Segment] = []
        for index in range(5):
            if index:
                segments.append(Segment("   "))
            segments.append(
                Segment(
                    "\u25cf" if index == lit else "\u00b7",
                    self.theme.content.accent if index == lit else self.theme.text.faint,
                )
            )
        return Line(segments)

    def tick(self, phase: int) -> str | None:
        return "menu" if phase >= SPLASH_TICKS else None

    def on_key(self, event: KeyEvent) -> str | None:
        return "menu"

    def on_click(self, pos: Pos) -> str | None:
        return "menu"


class MenuScene:
    """The hub: a centred panel of four destinations.

    ``Breakout`` and ``Dashboard`` are named already but have no scene in
    this build, so choosing one shows a toast line and stays put; ``Gallery``
    is live.  Up/down (or j/k) move the cursor, enter opens the choice, a
    click selects a row, ``esc`` returns to the splash and ``q`` quits.
    """

    name = "menu"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self._notice = ""
        self._notice_until = 0
        self._top = 0
        self._left = 0
        self.options = [
            Option("Breakout", "breakout", "a paddle, a wall, a spark"),
            Option("Dashboard", "dashboard", "live sparklines"),
            Option("Gallery", "gallery", "real components, one page"),
            Option("Quit", "quit", "leave the showcase"),
        ]
        self.list = Select(self.options, max_rows=None, theme=theme)
        self.list.focused = True
        self._title = Text("motui", style=theme.content.accent, theme=theme)
        self._version = Text(
            "2.0.0 \u00b7 Ink & Signal", style=theme.text.faint, theme=theme
        )
        self._hint = Text(
            "\u2191/\u2193 choose \u00b7 enter open \u00b7 esc back \u00b7 q quit",
            style=theme.text.faint,
            theme=theme,
        )
        heading = Column([self._title, self._version], gap=0)
        body = Column([heading, self.list, self._hint], gap=1)
        self.panel = Panel(body, title="showcase", theme=theme)

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        panel_width = min(48, max(24, width - 4))
        panel_rows = list(self.panel.render(Constraints(width=panel_width)))
        content = list(panel_rows)
        if self._notice:
            content.append(Line())
            content.append(
                Line.from_text(self._notice, self.theme.status.warning)
            )
        height = c.max_height if c.max_height is not None else len(content) + 4
        top = max(0, (height - len(content)) // 2)
        left = max(0, (width - panel_width) // 2)
        self._top = top
        self._left = left
        rows = [Line() for _ in range(top)]
        pad = Line((Segment(" " * left),)) if left else Line()
        for row in content:
            rows.append((pad + row).clip(_CLIP, width))
        return Surface.of(rows, width)

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        if self._notice and phase >= self._notice_until:
            self._notice = ""
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key in ("up", "k"):
            self.list.move(-1)
        elif key in ("down", "j"):
            self.list.move(1)
        elif key in ("enter", "space"):
            return self._activate()
        elif key == "escape":
            return "splash"
        elif key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        if pos.y < self._top or pos.x < self._left:
            return None
        content = getattr(self.panel, "child_at", lambda row, col: None)(
            pos.y - self._top, pos.x - self._left
        )
        if content is None:
            return None
        body, row, col = content
        target = getattr(body, "child_at", lambda r, c: None)(row, col)
        if target is None:
            return None
        widget, inner_row, inner_col = target
        if widget is self.list:
            self.list.on_click(Pos(x=inner_col, y=inner_row))
        return None

    def _activate(self) -> str | None:
        option = self.list.options[self.list.index]
        value = option.value
        if value == "gallery":
            return "gallery"
        if value == "quit":
            return "quit"
        self._notice = f"{option.label} \u2014 coming in this build"
        self._notice_until = self._phase + 90
        return None


class _PlaceholderScene:
    """The gallery's stand-in until the real components land."""

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
    return {
        "splash": SplashScene(theme),
        "menu": MenuScene(theme),
        "gallery": _PlaceholderScene("gallery", theme),
    }


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
