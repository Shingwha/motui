"""The menu section: the Home tile grid that routes to every other section."""

from __future__ import annotations

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.style import Style
from ...kernel.text import WrapMode
from ...kernel.theme import Theme

__all__ = ["MenuScene"]

#: Single-row clip for the composed menu rows (no ellipsis on chrome).
_CLIP = WrapMode.CLIP

#: Tile grid geometry: three columns of fixed-height tiles.
_COLUMNS = 3
_TILE_H = 10  # 2 border rows + name + blurb + 6 animation rows
_GAP = 1

#: The six destinations, in tile order (row-major across the grid).
_TILES: tuple[tuple[str, str], ...] = (
    ("components", "widgets, one page each"),
    ("layout", "rows, columns, constraints"),
    ("motion", "the snake, live"),
    ("dashboard", "streaming sparklines"),
    ("terminal", "keys, mouse, paint"),
    ("themes", "ink & signal variants"),
)


def _bar(width: int, fraction: float, style: Style) -> Line:
    """One progress-style bar of ``width`` cells, ``fraction`` filled."""
    filled = max(0, min(width, round(width * fraction)))
    if filled <= 0:
        return Line()
    if filled >= width:
        return Line((Segment("\u2588" * width, style),))
    return Line(
        (
            Segment("\u2588" * filled, style),
            Segment("\u25b7" * (width - filled), style),
        )
    )


def _mini_components(phase: int, width: int, theme: Theme) -> list[Line]:
    """Widget preview: three stacked bars pulsing one after another."""
    styles = (theme.content.accent, theme.status.success, theme.status.warning)
    rows: list[Line] = []
    for index, style in enumerate(styles):
        fraction = 0.5 + 0.5 * _sweep(phase + index * 7, 16)
        rows.append(_bar(width - 1, fraction, style))
    return rows


def _mini_layout(phase: int, width: int, theme: Theme) -> list[Line]:
    """Layout preview: a 2x2 grid whose active quadrant rotates."""
    active = (phase // 8) % 4
    hot = theme.content.accent
    cold = theme.borders.base
    half = max(1, (width - 1) // 2)
    rows: list[Line] = []
    for row in range(2):
        cells: list[Segment] = []
        for col in range(2):
            style = hot if row * 2 + col == active else cold
            cells.append(Segment("\u2500" * half, style))
            if col == 0:
                cells.append(Segment(" ", Style()))
        rows.append(Line(tuple(cells)))
    return rows


def _mini_motion(phase: int, width: int, theme: Theme) -> list[Line]:
    """Motion preview: a four-dot snake crawling along a small track."""
    track = max(4, width - 1)
    head = theme.status.success
    trail = theme.text.faint
    rows: list[Line] = [Line(), Line()]
    for row in range(2):
        cells: list[str | None] = [None] * track
        for dot in range(4):
            cells[(phase // 2 - dot) % track] = dot
        segments: list[Segment] = []
        for col, dot in enumerate(cells):
            if dot is None:
                continue
            style = head if dot == 0 else trail
            prefix = "\u00b7" * (col - sum(1 for c in cells[:col] if c is not None))
            segments.append(Segment(prefix + "\u25cf", style))
        rows.append(Line(tuple(segments)) if segments else Line())
    return rows


def _mini_dashboard(phase: int, width: int, theme: Theme) -> list[Line]:
    """Dashboard preview: a wave of sparkline bars, 6 rows tall."""
    accent = theme.content.accent
    rows: list[Line] = []
    for row in range(6):
        segments: list[Segment] = []
        for col in range(width - 1):
            level = (phase // 2 + col * 5 + row * 3) % 11
            segments.append(Segment("\u258f" if level > row * 2 else " ", accent))
        rows.append(Line(tuple(segments)))
    return rows


def _mini_terminal(phase: int, width: int, theme: Theme) -> list[Line]:
    """Terminal preview: a prompt whose typed text grows and resets."""
    faint = theme.text.faint
    caret = theme.content.accent
    typed = phase % max(1, width - 4)
    prompt = Segment("> ", faint)
    text = Segment("motui " * (typed // 6), faint)
    cursor_char = "\u2588" if (phase // 4) % 2 == 0 else " "
    rows = [
        Line((prompt, text, Segment(cursor_char, caret))),
        Line(),
        Line((Segment("60 Hz \u00b7 1/60 throttle", faint),)),
    ]
    return rows


def _mini_themes(phase: int, width: int, theme: Theme) -> list[Line]:
    """Themes preview: four swatches whose highlight cycles."""
    swatches = (
        theme.content.accent,
        theme.status.success,
        theme.status.warning,
        theme.status.danger,
    )
    active = (phase // 6) % len(swatches)
    block = max(2, (width - 1) // len(swatches))
    rows: list[Line] = [Line()]
    for row in range(2):
        segments: list[Segment] = []
        for index, style in enumerate(swatches):
            glyph = "\u2588" * block if index == active else "\u2591" * block
            segments.append(Segment(glyph, style))
        rows.append(Line(tuple(segments)))
    return rows


#: One mini animation painter per tile, in :data:`_TILES` order.
_MINIS = (
    _mini_components,
    _mini_layout,
    _mini_motion,
    _mini_dashboard,
    _mini_terminal,
    _mini_themes,
)


def _sweep(phase: int, period: int) -> float:
    """A deterministic 0..1..0 triangle wave over ``period`` ticks."""
    step = phase % period
    span = period / 2
    return abs(step - span) / span


class MenuScene:
    """The hub: a centred masthead over six destination tiles.

    Each tile names a section, teases it in one line and runs a small
    deterministic animation derived from the phase.  Arrows move the
    selection (left/right step one tile, up/down jump a row), enter opens
    it, a click opens the clicked tile, ``esc`` returns to the splash and
    ``q`` quits.
    """

    name = "menu"

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self._phase = 0
        self._top = 0
        self._left = 0
        self._tile_w = 30
        self.index = 0
        #: Tile rectangles recorded by the last ``render``: hit targets
        #: ``(row, col, height, width)`` in pane coordinates.
        self.rects: list[tuple[int, int, int, int]] = []

    # -- rendering ---------------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        self._phase = phase
        width = c.width
        self._tile_w = min(30, max(20, (width - 2 * _GAP - 4) // _COLUMNS))
        grid_w = _COLUMNS * self._tile_w + (_COLUMNS - 1) * _GAP
        grid = self._grid(grid_w)

        masthead = self._masthead(grid_w)
        footer = self._footer()
        rows = [*masthead, *grid[0], Line(), *grid[1], Line(), footer]

        height = c.max_height if c.max_height is not None else len(rows)
        top = max(0, (height - len(rows)) // 2)
        left = max(0, (width - grid_w) // 2)
        self._top = top
        self._left = left
        self.rects = [
            (
                top + len(masthead) + row * (_TILE_H + _GAP),
                left + col * (self._tile_w + _GAP),
                _TILE_H,
                self._tile_w,
            )
            for row in range(2)
            for col in range(_COLUMNS)
        ]

        pad = Line((Segment(" " * left),)) if left else Line()
        out = [Line() for _ in range(top)]
        out.extend((pad + row).clip(_CLIP, width) for row in rows)
        return Surface.of(out, width)

    def _masthead(self, grid_w: int) -> list[Line]:
        """The centred one-row title block."""
        text = "motui showcase"
        version = "2.0.0 \u00b7 Ink & Signal"
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

    def _footer(self) -> Line:
        """The one-row hint bar: navigation plus the standalone pages."""
        faint = self.theme.text.faint
        accent = self.theme.content.accent
        return Line(
            (
                Segment("\u2190\u2191\u2193\u2192 choose \u00b7 enter open", faint),
                Segment(" \u00b7 esc back \u00b7 q quit \u00b7 also: ", faint),
                Segment("Snake", accent),
                Segment(", ", faint),
                Segment("Gallery", accent),
            )
        )

    def _grid(self, grid_w: int) -> list[list[Line]]:
        """The tile rows: two rows of three framed, centred tiles."""
        rows: list[list[Line]] = [[Line() for _ in range(_TILE_H)] for _ in range(2)]
        for index, (_, blurb) in enumerate(_TILES):
            row, col = divmod(index, _COLUMNS)
            tile = self._tile(index, blurb)
            for h, tile_row in enumerate(tile):
                merged = rows[row][h] + tile_row
                rows[row][h] = merged
        return rows

    def _tile(self, index: int, blurb: str) -> list[Line]:
        """One tile's ten rows: border, name, blurb, six animation rows."""
        selected = index == self.index
        border = self.theme.content.accent if selected else self.theme.borders.base
        width = self._tile_w - 2
        name_style = (
            self.theme.content.accent if selected else self.theme.text.muted
        )
        corner = "\u2554\u2557\u255a\u255d"
        edge_l, edge_r = Segment("\u2551", border), Segment("\u2551", border)
        rows: list[tuple[Segment, ...]] = [
            (Segment(corner[0] + "\u2550" * width + corner[1], border),),
            (edge_l,)
            + self._centred(_TILES[index][0].capitalize(), width, name_style)
            + (edge_r,),
            (edge_l,) + self._centred(blurb, width, self.theme.text.faint) + (edge_r,),
        ]
        for mini_row in _MINIS[index](self._phase, width, self.theme):
            rows.append((edge_l,) + self._inset(mini_row, width) + (edge_r,))
        rows.append((Segment(corner[2] + "\u2550" * width + corner[3], border),))
        return [Line(segments) for segments in rows]

    @staticmethod
    def _centred(text: str, width: int, style: Style) -> tuple[Segment, ...]:
        """One text row between the tile's side borders, centred."""
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

    # -- behaviour ---------------------------------------------------------------

    def tick(self, phase: int) -> str | None:
        self._phase = phase
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        key = event.key
        if key == "up":
            self.index = (self.index - _COLUMNS) % len(_TILES)
        elif key == "down":
            self.index = (self.index + _COLUMNS) % len(_TILES)
        elif key == "left":
            self.index = (self.index - 1) % len(_TILES)
        elif key == "right":
            self.index = (self.index + 1) % len(_TILES)
        elif key in ("enter", "space"):
            return self._activate()
        elif key == "escape":
            return "splash"
        elif key == "q":
            return "quit"
        return None

    def on_click(self, pos: Pos) -> str | None:
        for index, (row, col, height, width) in enumerate(self.rects):
            if row <= pos.y < row + height and col <= pos.x < col + width:
                self.index = index
                return self._activate()
        return None

    def _activate(self) -> str:
        """Open the selected tile's section."""
        return _TILES[self.index][0]
