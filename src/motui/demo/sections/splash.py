"""The splash section: a hand-drawn pixel wordmark in four style packs.

The wordmark is not a font anymore: "MOTUI" is drawn as sub-cell strokes
(3-4 sub-cells thick) on a 152x96 design grid, scaled onto whatever
:class:`~motui.widgets.PixelCanvas` hosts it (the canvas caps at 60x18
cells to hold the 8 ms frame budget -- see :meth:`SplashScene.render`).  The fill layer
carries the word itself; the art layer carries the pack's motion -- the
neon sweep's decay trail, the starfield's three-layer parallax drift.
Every frame is a pure function of the phase: both layers are cleared and
redrawn with explicit heats, so a headless replay never depends on how
many decay steps a live run took between frames.

The four packs keep their identities.  ``neon`` is the cyan-to-lavender
ramp (:data:`LOGO_START` -> :data:`LOGO_END`) with a white sweep flowing
through the strokes; ``plasma`` walks the hue wheel along the word;
``retro`` alternates amber and green CRT phosphor with scanline rows; and
``starfield`` drifts stars at three depths behind an icy word, with
occasional red/cyan glitch bands.  The splash never times out: only a key
or a click leaves for the menu.  ``seed`` pins the style shuffle for a
headless snapshot; ``None`` seeds from the system, so every live launch
starts somewhere new.
"""

from __future__ import annotations

import math
import random

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.pixel import PixelPalette
from ...kernel.style import Style
from ...kernel.text import WrapMode
from ...kernel.theme import Theme
from ...widgets import PixelCanvas
from ..art import center

__all__ = [
    "LOGO_END",
    "LOGO_START",
    "SPLASH_GLYPHS",
    "SPLASH_GLYPH_TICKS",
    "SPLASH_ROTATE_TICKS",
    "SPLASH_STYLES",
    "SplashScene",
]

#: How long one splash style holds: two seconds at the shell's 60 Hz.
SPLASH_ROTATE_TICKS = 120

#: How often the pulse dot's glyph morphs inside a style.
SPLASH_GLYPH_TICKS = 18

#: The style packs the splash rotates through.  Each is a full identity:
#: ``neon`` is the cyan-to-lavender ramp with a white sweep, ``plasma``
#: walks the hue wheel across the word, ``retro`` is an amber or green CRT
#: with scanlines, and ``starfield`` drifts a three-layer star field
#: behind the word with occasional red/cyan glitch bands.
SPLASH_STYLES: tuple[str, ...] = ("neon", "plasma", "retro", "starfield")

#: The fill glyphs each pack's pulse dot morphs between (all single-width).
SPLASH_GLYPHS: dict[str, tuple[str, ...]] = {
    "neon": ("\u2588", "\u2593", "\u25a0", "\u2588"),
    "plasma": ("\u2588", "\u2593", "\u2592", "\u25a0"),
    "retro": ("\u2588", "\u2593"),
    "starfield": ("\u25a0", "\u25a3", "\u2726", "\u2588"),
}

#: The wordmark's neon ramp: the accent fades into the inline-code lavender.
LOGO_START = "#53c8f0"
LOGO_END = "#c4b5fd"

_CLIP = WrapMode.CLIP

#: The wordmark's virtual canvas: 152x96 sub-cells, five 24-wide letters
#: joined by 8-wide gaps, drawn in 3-wide brush strokes.
_MARK_W = 152
_MARK_H = 96
_BRUSH = 3
_BANDS = 12

#: The neon sweep: a white head flowing left-to-right, its decay trail
#: burning out behind it (one heat step per sub-cell of trail).
_SWEEP_PERIOD = 150
_SWEEP_PAD = 12
_SWEEP_TRAIL = 12
_SWEEP_STEP = 10

#: The starfield's parallax: per-layer drift as (numerator, denominator)
#: sub-cells per tick, far to near.
_STAR_DRIFT = ((1, 12), (1, 6), (1, 3))


def _hsl(hue: float, saturation: float, lightness: float) -> tuple[int, int, int]:
    """One HSL color as an RGB triple (the plasma pack's hue wheel)."""
    h = (hue % 360.0) / 60.0
    chroma = (1 - abs(2 * lightness - 1)) * saturation
    second = chroma * (1 - abs(h % 2 - 1))
    base = lightness - chroma / 2
    if h < 1:
        rgb = (chroma, second, 0.0)
    elif h < 2:
        rgb = (second, chroma, 0.0)
    elif h < 3:
        rgb = (0.0, chroma, second)
    elif h < 4:
        rgb = (0.0, second, chroma)
    elif h < 5:
        rgb = (second, 0.0, chroma)
    else:
        rgb = (chroma, 0.0, second)
    return tuple(round((value + base) * 255) for value in rgb)


def _rgb(value: str) -> tuple[int, int, int]:
    """The RGB triple a ``#rrggbb`` string names."""
    text = value.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _mix(start: tuple[int, int, int], end: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """One interpolated step between two RGB triples."""
    return tuple(round(first + (last - first) * t) for first, last in zip(start, end))


def _ramp(
    start: str, end: str, count: int, *, dim: float = 0.42
) -> dict[int, tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """``count`` (main, cool) palette pairs stepping ``start`` -> ``end``."""
    first, last = _rgb(start), _rgb(end)
    return {
        1 + index: (
            _mix(first, last, index / (count - 1)),
            _mix(first, last, index / (count - 1) * dim),
        )
        for index in range(count)
    }


def _brush(cells: set[tuple[int, int]], x: int, y: int) -> None:
    """Stamp the square brush at ``(x, y)``, clipped to the virtual canvas."""
    for dx in range(_BRUSH):
        for dy in range(_BRUSH):
            px, py = x + dx, y + dy
            if 0 <= px < _MARK_W and 0 <= py < _MARK_H:
                cells.add((px, py))


def _thick(cells: set[tuple[int, int]], x0: int, y0: int, x1: int, y1: int) -> None:
    """A brush-width Bresenham line between two virtual points."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _brush(cells, x0, y0)
        if x0 == x1 and y0 == y1:
            return
        step = 2 * err
        if step >= dy:
            err += dy
            x0 += sx
        if step <= dx:
            err += dx
            y0 += sy


def _arc(
    cells: set[tuple[int, int]],
    cx: int,
    cy: int,
    rx: int,
    ry: int,
    start: float,
    stop: float,
) -> None:
    """A parametric elliptical arc, brushed (the O bowl, the U bottom)."""
    steps = 256
    for index in range(steps + 1):
        angle = start + (stop - start) * index / steps
        _brush(cells, round(cx + rx * math.cos(angle)), round(cy + ry * math.sin(angle)))


def _build_wordmark() -> frozenset[tuple[int, int]]:
    """The "MOTUI" strokes as one set of virtual sub-cells."""
    cells: set[tuple[int, int]] = set()
    _thick(cells, 0, 0, 0, 93)  # M: the two stems...
    _thick(cells, 21, 0, 21, 93)
    _thick(cells, 1, 1, 11, 45)  # ...and the V of diagonals
    _thick(cells, 22, 1, 12, 45)
    _arc(cells, 44, 48, 11, 45, 0.0, 2 * math.pi)  # O
    _thick(cells, 64, 1, 85, 1)  # T: the bar...
    _thick(cells, 75, 1, 75, 93)  # ...and the stem
    _thick(cells, 96, 0, 96, 70)  # U: the two stems...
    _thick(cells, 117, 0, 117, 70)
    _arc(cells, 108, 70, 11, 24, 0.0, math.pi)  # ...and the bottom bowl
    _thick(cells, 128, 1, 149, 1)  # I: top serif...
    _thick(cells, 128, 93, 149, 93)  # ...bottom serif...
    _thick(cells, 139, 0, 139, 93)  # ...and the stem
    return frozenset(cells)


#: The wordmark, built once at import: pure data, deterministic.
_WORDMARK: frozenset[tuple[int, int]] = _build_wordmark()


#: The star field: ``(x, y, layer)`` over the virtual canvas, one seeded
#: deal at import (far stars outnumber near ones).
def _build_stars() -> tuple[tuple[int, int, int], ...]:
    rng = random.Random(20261027)
    stars: list[tuple[int, int, int]] = []
    for layer, count in enumerate((44, 28, 14)):
        for _ in range(count):
            stars.append((rng.randrange(_MARK_W), rng.randrange(_MARK_H), layer))
    return tuple(stars)


_STARS: tuple[tuple[int, int, int], ...] = _build_stars()

#: Slot ids the starfield canvas spends on stars and glitch bands.
_STAR_SLOTS = (13, 14, 15)
_GLITCH_RED = 16
_GLITCH_CYAN = 17

#: The per-pack palettes.  Slot 13 is the neon sweep's white; the starfield
#: word is an icy ramp on slots 1-12 with stars and glitch above it.
_PALETTES: dict[str, PixelPalette] = {
    "neon": PixelPalette(
        slots={
            **_ramp(LOGO_START, LOGO_END, _BANDS),
            13: ((255, 255, 255), (170, 174, 192)),
        },
        bg=(10, 10, 18),
    ),
    "plasma": PixelPalette(
        slots={
            1 + index: (
                _hsl(index * 30, 0.70, 0.60),
                _hsl(index * 30, 0.65, 0.26),
            )
            for index in range(_BANDS)
        },
        bg=(16, 8, 20),
    ),
    "retro": PixelPalette(
        slots={
            1: ((255, 176, 0), (120, 82, 0)),  # amber phosphor, lit and dim
            2: ((150, 100, 0), (70, 46, 0)),
            3: ((51, 255, 153), (24, 118, 72)),  # green phosphor, lit and dim
            4: ((30, 150, 90), (14, 70, 44)),
        },
        bg=(10, 8, 6),
    ),
    "starfield": PixelPalette(
        slots={
            **_ramp("#7896e6", "#ebf2ff", _BANDS),
            _STAR_SLOTS[0]: ((96, 116, 168), (44, 54, 80)),
            _STAR_SLOTS[1]: ((150, 180, 226), (70, 86, 110)),
            _STAR_SLOTS[2]: ((222, 236, 255), (110, 120, 140)),
            _GLITCH_RED: ((255, 92, 108), (120, 44, 52)),
            _GLITCH_CYAN: ((92, 232, 255), (44, 112, 124)),
        },
        bg=(5, 6, 12),
    ),
}

#: The scaled geometry cache: ``(band indices, column indices, points)``
#: for one canvas size, computed on first use (a frame's slot assignment
#: and the sweep's columns are index lookups, never point math).
_GEOM_CACHE: dict[
    tuple[int, int],
    tuple[list[list[int]], dict[int, list[int]], set[tuple[int, int]]],
] = {}


def _geometry(
    width: int, height: int
) -> tuple[list[list[int]], dict[int, list[int]], set[tuple[int, int]]]:
    """The wordmark scaled onto a ``width x height`` sub-cell canvas.

    Bands split the canvas into :data:`_BANDS` column strips (the packs
    color by band); columns map an x to the raster indices the sweep
    lights; the point set is the membership test the stars use to keep
    from punching holes in the strokes.
    """
    cached = _GEOM_CACHE.get((width, height))
    if cached is not None:
        return cached
    sx, sy = width / _MARK_W, height / _MARK_H
    bands: list[list[int]] = [[] for _ in range(_BANDS)]
    columns: dict[int, list[int]] = {}
    points: set[tuple[int, int]] = set()
    for x, y in _WORDMARK:
        px, py = int(x * sx), int(y * sy)
        if not 0 <= px < width or not 0 <= py < height:
            continue
        index = py * width + px
        bands[min(_BANDS - 1, px * _BANDS // width)].append(index)
        columns.setdefault(px, []).append(index)
        points.add((px, py))
    cached = (bands, columns, points)
    _GEOM_CACHE[(width, height)] = cached
    return cached


class SplashScene:
    """The opening: the pixel wordmark in one of four animated packs.

    The splash never times out.  It rotates through :data:`SPLASH_STYLES`
    every :data:`SPLASH_ROTATE_TICKS` animation ticks, reshuffling the
    order whenever it is entered, and only a key or a click leaves for the
    menu.  ``style_name`` answers the active pack for a phase (tests and
    the hint row read it); every frame is a pure function of the phase, so
    a headless replay is byte-identical to the live showcase.
    """

    name = "splash"

    def __init__(self, theme: Theme, *, seed: int | None = 0) -> None:
        self.theme = theme
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._order = list(SPLASH_STYLES)
        self.restart()
        self._canvases: dict[str, PixelCanvas] = {}

    def restart(self) -> None:
        """Reshuffle the style order; the next visit starts somewhere new."""
        self._rng.shuffle(self._order)

    def style_name(self, phase: int) -> str:
        """The pack active at ``phase`` (exposed for tests and the hint row)."""
        return self._order[(phase // SPLASH_ROTATE_TICKS) % len(self._order)]

    def _canvas(self, pack: str) -> PixelCanvas:
        """The pack's own canvas: each palette is built once, lazily."""
        canvas = self._canvases.get(pack)
        if canvas is None:
            canvas = PixelCanvas(palette=_PALETTES[pack])
            self._canvases[pack] = canvas
        return canvas

    # -- painting ----------------------------------------------------------

    def _paint(self, canvas: PixelCanvas, pack: str, phase: int) -> None:
        """Redraw the whole canvas as a pure function of the phase.

        The fill layer carries the word; the art layer carries the pack's
        motion.  The trail heats are written explicitly -- the kernel's
        decay curve, one step per sub-cell -- rather than accumulated in
        the raster, so replaying any phase paints the exact same frame.
        """
        canvas.clear()
        width, height = canvas.art.width, canvas.art.height
        if pack == "starfield":
            self._paint_stars(canvas, phase, width, height)
        self._paint_wordmark(canvas, pack, phase, width, height)
        if pack == "neon":
            self._paint_sweep(canvas, phase, width)

    def _paint_wordmark(
        self, canvas: PixelCanvas, pack: str, phase: int, width: int, height: int
    ) -> None:
        """The strokes on the fill layer, one slot per pack's recipe."""
        bands, _columns, _points = _geometry(width, height)
        slot_grid, heat_grid = canvas.fill.slot, canvas.fill.heat
        if pack == "plasma":
            shift = phase // 2  # the hue wheel walks along the word
            for band, indices in enumerate(bands):
                slot = 1 + (band + shift) % _BANDS
                for index in indices:
                    slot_grid[index] = slot
                    heat_grid[index] = 255
        elif pack == "retro":
            # Amber or green phosphor by hold period, dimmed on every
            # other cell row: the scanlines.
            amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
            lit, dim = (1, 2) if amber else (3, 4)
            for indices in bands:
                for index in indices:
                    scanline = (index // width // 4) % 2
                    slot_grid[index] = dim if scanline else lit
                    heat_grid[index] = 255
        else:  # neon and starfield: a fixed band ramp (starfield glitches)
            glitch = pack == "starfield" and (phase // 37) % 4 == 0
            for band, indices in enumerate(bands):
                slot = 1 + band
                for index in indices:
                    if glitch and (index % width * 7 + index // width * 13 + phase) % 19 < 2:
                        color = (
                            _GLITCH_RED
                            if (index // width + index % width) % 2 == 0
                            else _GLITCH_CYAN
                        )
                        slot_grid[index] = color
                    else:
                        slot_grid[index] = slot
                    heat_grid[index] = 255

    def _paint_sweep(self, canvas: PixelCanvas, phase: int, width: int) -> None:
        """The white sweep: a head column flowing across, the strokes it
        passed cooling behind it through the palette's cool colors."""
        _bands, columns, _points = _geometry(width, canvas.art.height)
        slot_grid, heat_grid = canvas.art.slot, canvas.art.heat
        span = width + 2 * _SWEEP_PAD
        head = (phase % _SWEEP_PERIOD) * span // _SWEEP_PERIOD - _SWEEP_PAD
        for step in range(_SWEEP_TRAIL):
            heat = 255 - step * _SWEEP_STEP
            if heat <= 0:
                break
            indices = columns.get(head - step)
            if not indices:
                continue
            for index in indices:
                slot_grid[index] = 13
                heat_grid[index] = heat

    def _paint_stars(self, canvas: PixelCanvas, phase: int, width: int, height: int) -> None:
        """Three parallax depths drifting left behind the word.

        Each layer has its own speed (far stars crawl, near ones glide),
        brightness slot and twinkle; near stars never land on a stroke.
        """
        _bands, _columns, points = _geometry(width, height)
        slot_grid, heat_grid = canvas.art.slot, canvas.art.heat
        stride = canvas.art.width
        for order, (x, y, layer) in enumerate(_STARS):
            num, den = _STAR_DRIFT[layer]
            px = (x * width // _MARK_W - phase * num // den) % width
            py = y * height // _MARK_H
            if (px, py) in points:
                continue
            if layer == 1 and (phase // 6 + order) % 7 == 0:
                continue
            if layer == 2 and (phase // 4 + order) % 5 == 0:
                continue
            slot = _STAR_SLOTS[layer]
            index = py * stride + px
            slot_grid[index] = slot
            heat_grid[index] = 255
            if layer == 2 and (px + 1, py) not in points and px + 1 < width:
                spark = index + 1
                slot_grid[spark] = slot
                heat_grid[spark] = 200

    # -- chrome ------------------------------------------------------------

    def _accent(self, pack: str, phase: int) -> Style:
        """The subtitle/indicator color the active pack uses."""
        if pack == "neon":
            return Style(fg=_mix(_rgb(LOGO_START), _rgb(LOGO_END), 0.5), bold=True)
        if pack == "plasma":
            return Style(fg=_hsl(phase * 4, 0.7, 0.65), bold=True)
        if pack == "retro":
            amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
            return Style(fg=(255, 176, 0) if amber else (51, 255, 153), bold=True)
        return Style(fg=(220, 230, 255), bold=True)

    def _pulse(self, pack: str, phase: int) -> Line:
        """Five dots with one lit: the quiet breathing mark under the word.

        The lit dot takes the pack's morphing fill glyph -- the one piece
        of the classic glyph cycle that survived the pixel wordmark.
        """
        glyphs = SPLASH_GLYPHS[pack]
        lit = glyphs[(phase // SPLASH_GLYPH_TICKS) % len(glyphs)]
        accent = self._accent(pack, phase)
        segments: list[Segment] = []
        for index in range(5):
            if index:
                segments.append(Segment("   "))
            segments.append(
                Segment(
                    lit if index == (phase // 4) % 5 else "\u00b7",
                    accent if index == (phase // 4) % 5 else self.theme.text.faint,
                )
            )
        return Line(segments)

    # -- the scene ---------------------------------------------------------

    def render(self, c: Constraints, phase: int) -> Surface:
        """The centred wordmark canvas over the subtitle, pulse and hint.

        The canvas caps at 60x17 cells -- a 120x68-sub-cell wordmark, about
        four fifths of the nominal 152x96 -- because the frame budget is
        8 ms and quantize scales with cell area: at the nominal 76x23 the
        dense wordmark measured ~9 ms median, at the cap the four packs
        answer 5.9-6.3 ms (CPython 3.13.16, Windows; 7 rounds of 200
        frames, median of per-round medians, 100x30 pane).  Wider panes
        centre the canvas.
        """
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        pack = self.style_name(phase)
        canvas_w = max(12, min(60, width - 2))
        canvas_h = max(5, min(17, height - 7))
        canvas = self._canvas(pack)
        canvas.resize(canvas_w, canvas_h)
        self._paint(canvas, pack, phase)
        pad = max(0, (width - canvas_w) // 2)
        prefix = Line((Segment(" " * pad),)) if pad else None
        # The pad is chosen so every row already fits the pane: clip only
        # the degenerate pane (narrower than the canvas), never per frame.
        mark = canvas.render(Constraints(width=canvas_w))
        mark = [prefix + row for row in mark] if prefix else list(mark)
        subtitle = center(
            width,
            [Line.from_text("a terminal UI kernel \u00b7 2.0.0", self.theme.text.muted)],
        )
        dots = center(width, [self._pulse(pack, phase)])
        hint = center(
            width,
            [Line.from_text(f"press any key  \u00b7  {pack}", self.theme.text.faint)],
        )
        content = [*mark, Line(), *subtitle, Line(), *dots, Line(), *hint]
        top = max(0, (height - len(content)) // 2)
        rows = [Line() for _ in range(top)] + content
        return Surface.of(rows, width)

    def tick(self, phase: int) -> str | None:
        """The splash never times out; only a key or a click leaves it."""
        return None

    def on_key(self, event: KeyEvent) -> str | None:
        return "menu"

    def on_click(self, pos: Pos) -> str | None:
        return "menu"
