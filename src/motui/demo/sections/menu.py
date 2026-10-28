"""The menu section: the hub that routes to every other section."""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import Column, Panel, Text
from ...widgets.choice import Option, Select

__all__ = ["MenuScene"]

#: Single-row clip for the composed menu rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP


class MenuScene:
    """The hub: a centred panel of four destinations.

    ``Snake`` and ``Dashboard`` are playable/live in this build alongside
    ``Gallery``; ``Quit`` leaves.  Up/down (or j/k) move the cursor, enter
    opens the choice, a click selects a row, ``esc`` returns to the splash
    and ``q`` quits.
    """

    name = "menu"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self._top = 0
        self._left = 0
        self.options = [
            Option("Snake", "snake", "a snake, a bite, a tail"),
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
        content = list(self.panel.render(Constraints(width=panel_width)))
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
        """Open the chosen destination (``None`` only for an empty menu)."""
        option = self.list.options[self.list.index]
        return str(option.value)
