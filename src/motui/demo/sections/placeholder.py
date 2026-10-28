"""The placeholder sections: under-construction panels for waves to come."""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import Column, Panel, Text

__all__ = ["PlaceholderScene"]

_CLIP = WrapMode.CLIP


class PlaceholderScene:
    """One "under construction" section: a centred panel and a way home.

    Every section that a later wave will build (components, layout,
    terminal, themes) ships as one of these so the shell's registry, the
    tiles, the golden set and the ``--pages`` tour stay complete.  The
    panel carries the section's name, the notice and the return hint; a
    small dot strip under the notice advances with the phase so the frame
    proves it is alive.  ``esc`` returns to the menu, ``q`` quits.
    """

    def __init__(self, theme: Theme, *, name: str, blurb: str) -> None:
        self.theme = theme
        self.name = name
        self.blurb = blurb
        self._phase = 0
        self._title = Text(
            name.upper(), style=theme.content.accent, theme=theme
        )
        self._notice = Text(
            "under construction", style=theme.text.muted, theme=theme
        )
        self._blurb = Text(blurb, style=theme.text.faint, theme=theme)
        self._hint = Text(
            "esc home \u00b7 q quit", style=theme.text.faint, theme=theme
        )

    def _dots(self, phase: int) -> Text:
        """The animated strip: a dot orbiting a fixed-width track."""
        track = 12
        position = phase % track
        strip = " " * position + "\u25cf" + " " * (track - position - 1)
        return Text(strip, style=self.theme.status.info, theme=self.theme)

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        panel_width = min(52, max(28, width - 4))
        body = Column(
            [self._title, self._notice, self._blurb, self._dots(phase), self._hint],
            gap=1,
        )
        panel = Panel(body, title=f"/{self.name}", theme=self.theme)
        content = list(panel.render(Constraints(width=panel_width)))
        height = c.max_height if c.max_height is not None else len(content) + 4
        top = max(0, (height - len(content)) // 2)
        left = max(0, (width - panel_width) // 2)
        rows = [Line() for _ in range(top)]
        pad = Line((Segment(" " * left),)) if left else Line()
        for row in content:
            rows.append((pad + row).clip(_CLIP, width))
        return Surface.of(rows, width)

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        if event.key == "escape":
            return "menu"
        if event.key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        return None
