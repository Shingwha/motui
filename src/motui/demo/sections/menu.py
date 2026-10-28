"""The menu section: the Home tile grid that routes to every other section."""

from __future__ import annotations

from collections.abc import Sequence

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.style import Style
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ..common import hit_target
from ..scene import Scene, SceneSpec
from ..version import DEMO_VERSION

__all__ = ["MenuScene"]

#: Single-row clip for the composed menu rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP

#: Tile grid geometry: three columns of fixed-height tiles.
_COLUMNS = 3
_TILE_H = 10  # 2 border rows + name + blurb + 6 animation rows
_GAP = 1

#: Every mini animation paints exactly this many rows, so all tiles close
#: their bottom border on the same line.
_MINI_H = 6


class MenuScene(Scene):
    """The hub: a centred masthead over the Home destination tiles.

    Each tile names a section, teases it in one line and runs a small
    deterministic animation derived from the phase.  Arrows move the
    selection (left/right step one tile, up/down jump a row), enter opens
    it, a click opens the clicked tile, ``s``/``g`` open the standalone
    Snake/Gallery pages, ``esc`` returns to the splash and ``q`` quits.
    """

    name = "menu"

    def __init__(self, theme: Theme, tiles: Sequence[SceneSpec]) -> None:
        super().__init__(theme)
        self.tiles = tuple(tiles)
        self._top = 0
        self._left = 0
        self._tile_w = 30
        self.index = 0
        #: Tile rectangles recorded by the last ``render``: hit targets
        #: ``(row, col, height, width)`` in pane coordinates.
        self.rects: list[tuple[int, int, int, int]] = []

    def enter(self) -> None:
        super().enter()
        self.index = 0
        self.rects.clear()

    # -- rendering ---------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        # Twelve columns is the floor where a tile still reads (a ten-char
        # name between the borders); below that the pane is too narrow for
        # three tiles and the clip is the graceful degradation.
        self._tile_w = min(30, max(12, (width - 2 * _GAP - 4) // _COLUMNS))
        grid_w = _COLUMNS * self._tile_w + (_COLUMNS - 1) * _GAP
        grid = self._grid()

        masthead = self._masthead(grid_w)
        footer = self._footer()
        rows = [*masthead]
        for index, grid_row in enumerate(grid):
            if index:
                rows.append(Line())
            rows.extend(grid_row)
        rows.extend(footer)

        height = c.max_height if c.max_height is not None else len(rows)
        top = max(0, (height - len(rows)) // 2)
        left = max(0, (width - grid_w) // 2)
        self._top = top
        self._left = left
        row_count = (len(self.tiles) + _COLUMNS - 1) // _COLUMNS
        self.rects = [
            (
                top + len(masthead) + row * (_TILE_H + _GAP),
                left + col * (self._tile_w + _GAP),
                _TILE_H,
                self._tile_w,
            )
            for row in range(row_count)
            for col in range(_COLUMNS)
            if row * _COLUMNS + col < len(self.tiles)
        ]

        pad = Line((Segment(" " * left),)) if left else Line()
        out = [Line() for _ in range(top)]
        out.extend((pad + row).clip(_CLIP, width) for row in rows)
        return Surface.of(out, width)

    def _masthead(self, grid_w: int) -> list[Line]:
        """The centred one-row title block."""
        text = "motui showcase"
        version = f"{DEMO_VERSION} \u00b7 Ink & Signal"
        span = len(text) + 3 + len(version)
        pad = max(0, (grid_w - span) // 2)
        return [
            Line(
                (
                    Segment(" " * pad),
                    Segment(text, self.theme.content.accent),
                    Segment(" \u00b7 ", self.theme.text.faint),
                    Segment(version, self.theme.text.faint),
                )
            )
        ]

    def _footer(self) -> list[Line]:
        """The two-row hint bar: navigation, then global doors and help."""
        faint = self.theme.text.faint
        accent = self.theme.content.accent
        return [
            Line(
                (
                    Segment("\u2190\u2191\u2193\u2192 choose \u00b7 enter open", faint),
                    Segment(" \u00b7 esc back \u00b7 q quit", faint),
                )
            ),
            Line(
                (
                    Segment("F1 help \u00b7 ctrl+p commands \u00b7 s ", faint),
                    Segment("Snake", accent),
                    Segment(" \u00b7 g ", faint),
                    Segment("Gallery", accent),
                )
            ),
        ]

    def _grid(self) -> list[list[Line]]:
        """The tile rows, two rows of three framed, gap-separated tiles."""
        row_count = (len(self.tiles) + _COLUMNS - 1) // _COLUMNS
        rows: list[list[Line]] = [
            [Line() for _ in range(_TILE_H)] for _ in range(row_count)
        ]
        for index, spec in enumerate(self.tiles):
            row, col = divmod(index, _COLUMNS)
            tile = self._tile(spec)
            for h, tile_row in enumerate(tile):
                merged = rows[row][h]
                if col:
                    merged = merged + Line((Segment(" " * _GAP),))
                rows[row][h] = merged + tile_row
        return rows

    def _tile(self, spec: SceneSpec) -> list[Line]:
        """One tile's ten rows: border, name, blurb, six animation rows."""
        selected = spec.name == self.tiles[self.index].name
        border = self.theme.content.accent if selected else self.theme.borders.base
        width = self._tile_w - 2
        name_style = (
            self.theme.content.accent if selected else self.theme.text.muted
        )
        corner = "\u2554\u2557\u255a\u255d"
        edge_l, edge_r = Segment("\u2551", border), Segment("\u2551", border)
        rows: list[tuple[Segment, ...]] = [
            (Segment(corner[0] + "\u2550" * width + corner[1], border),),
            (edge_l, *self._centred(spec.title, width, name_style), edge_r),
            (edge_l, *self._centred(spec.blurb, width, self.theme.text.faint), edge_r),
        ]
        mini = spec.mini
        mini_rows = mini(self._phase, width, self.theme) if mini is not None else []
        # Pad every preview to the same height so all tiles stay equal-height.
        mini_rows = [*mini_rows, *([Line()] * (_MINI_H - len(mini_rows)))]
        for mini_row in mini_rows:
            rows.append((edge_l, *self._inset(mini_row, width), edge_r))
        rows.append((Segment(corner[2] + "\u2550" * width + corner[3], border),))
        return [Line(segments) for segments in rows]

    @staticmethod
    def _centred(text: str, width: int, style: Style) -> tuple[Segment, ...]:
        """One text row between the tile's side borders, centred."""
        text = text[:width]
        pad = max(0, (width - len(text)) // 2)
        rest = width - len(text) - pad
        return (Segment(" " * pad), Segment(text, style), Segment(" " * rest))

    @staticmethod
    def _inset(row: Line, width: int) -> tuple[Segment, ...]:
        """One animation row between the side borders, left-aligned."""
        return (
            Segment(" "),
            *row.segments,
            Segment(" " * max(0, width - row.width - 1)),
        )

    # -- behaviour ---------------------------------------------------------

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "up":
            self.index = (self.index - _COLUMNS) % len(self.tiles)
        elif key == "down":
            self.index = (self.index + _COLUMNS) % len(self.tiles)
        elif key == "left":
            self.index = (self.index - 1) % len(self.tiles)
        elif key == "right":
            self.index = (self.index + 1) % len(self.tiles)
        elif key in ("enter", "space"):
            return self._activate()
        elif key == "s":
            return "snake"
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
        """Open the selected tile's section."""
        return self.tiles[self.index].name
