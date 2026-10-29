"""The Signal Lab home: one live experiment and a keyboard-first index."""

from __future__ import annotations

from collections.abc import Sequence

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import Panel, Row
from ..common import FixedHeight, LinesView, hit_target, pad_rows
from ..scene import Scene, SceneSpec
from ..version import DEMO_VERSION

__all__ = ["MenuScene"]

_CLIP = WrapMode.CLIP


class MenuScene(Scene):
    name = "menu"

    def __init__(self, theme: Theme, tiles: Sequence[SceneSpec]) -> None:
        super().__init__(theme)
        self.tiles = tuple(tiles)
        self.index = 0
        self.rects: list[tuple[int, int, int, int]] = []
        self._left = 0
        self._top = 0
        self._nav_w = 28
        self._preview_w = 60

    def enter(self) -> None:
        super().enter()
        self.rects.clear()

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width, height = c.width, c.max_height or 24
        margin = 2 if width >= 70 else 0
        self._nav_w = min(30, max(23, width * 29 // 100))
        gap = 2
        self._preview_w = max(20, width - margin * 2 - self._nav_w - gap)
        body_h = max(10, height - 7)
        self._left = margin
        self._top = 3
        spec = self.tiles[self.index]
        preview = self._preview(spec, phase, self._preview_w, body_h)
        index = self._index_panel(body_h)
        body = Row(
            [preview, index],
            widths=[self._preview_w, self._nav_w],
            gap=gap,
        ).render(Constraints(width=self._preview_w + self._nav_w + gap))
        pad = Line((Segment(" " * margin),)) if margin else Line()
        rows = [
            pad + self._masthead(width - margin * 2),
            pad + Line.from_text(
                "A living atlas of terminal interfaces", self.theme.text.faint
            ),
            Line(),
            *(pad + row for row in body),
            Line(),
            pad + Line.from_text(
                "↑↓/←→/tab select · enter launch · 1-6 direct · g gallery",
                self.theme.text.muted,
            ),
            pad + Line.from_text(
                "F1 manual · F2 calm · ctrl+t global theme · ctrl+p commands · esc splash",
                self.theme.text.faint,
            ),
        ]
        self.rects = [
            (
                self._top + 1 + item * 2,
                margin + self._preview_w + gap + 1,
                2,
                self._nav_w - 2,
            )
            for item in range(len(self.tiles))
        ]
        return Surface.of(pad_rows(rows, height), width)

    def _masthead(self, width: int) -> Line:
        left = "MOTUI / SIGNAL LAB"
        right = f"06 EXPERIMENTS · {DEMO_VERSION}"
        gap = max(1, width - len(left) - len(right))
        return Line(
            (
                Segment(left, self.theme.content.accent),
                Segment(" " * gap),
                Segment(right, self.theme.text.faint),
            )
        ).clip(_CLIP, width)

    def _preview(self, spec: SceneSpec, phase: int, width: int, height: int):
        mini = spec.mini(phase, max(8, width - 4), self.theme) if spec.mini else []
        lines = [
            Line.from_text(spec.blurb, self.theme.text.muted),
            Line(),
            *mini,
        ]
        view = LinesView(self.theme, lines)
        panel = Panel(
            FixedHeight(view, max(1, height - 2)),
            title=f"{self.index + 1:02d} / {spec.title.upper()}",
            theme=self.theme,
        )
        return FixedHeight(panel, height)

    def _index_panel(self, height: int):
        rows: list[Line] = []
        for position, spec in enumerate(self.tiles):
            selected = position == self.index
            marker = ">" if selected else " "
            style = self.theme.content.accent if selected else self.theme.text.muted
            rows.append(
                Line(
                    (
                        Segment(f"{marker} {position + 1:02d} ", style),
                        Segment(spec.title, style),
                    )
                )
            )
            detail = "LIVE PREVIEW" if selected else spec.name.upper()
            rows.append(Line.from_text(f"     {detail}", self.theme.text.faint))
        rows.extend(
            [
                Line(),
                Line.from_text("  ARCHIVE", self.theme.text.faint),
                Line.from_text("  g  Component gallery", self.theme.text.muted),
            ]
        )
        return FixedHeight(
            Panel(LinesView(self.theme, rows), title="EXPERIMENT INDEX", theme=self.theme),
            height,
        )

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key in ("up", "left", "s-tab", "backtab"):
            self.index = (self.index - 1) % len(self.tiles)
        elif key in ("down", "right", "tab"):
            self.index = (self.index + 1) % len(self.tiles)
        elif key in tuple("123456") and int(key) <= len(self.tiles):
            self.index = int(key) - 1
            return self._activate()
        elif key in ("enter", "space"):
            return self._activate()
        elif key == "g":
            return "gallery"
        elif key == "escape":
            return "splash"
        elif key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        index = hit_target(self.rects, pos)
        if index is None:
            return None
        self.index = index
        return self._activate()

    def _activate(self) -> str:
        return self.tiles[self.index].name
