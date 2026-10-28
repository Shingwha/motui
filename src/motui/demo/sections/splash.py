"""The splash section: the classic 5x7 letterforms as a pixel wordmark.

The word is the showcase's own verified 5x7 font (:data:`FONT_5X7`) --
the letterform set the original text logo used -- scaled onto the
sub-cell grid at an integer multiple (a font cell becomes a 3x4 block,
with one sub-cell shaved off convex corners), so "MOTUI" reads as
letters first and pixels second.  The frame carries three layers of
motion, every one a pure function of the phase:

* an entrance -- the letters rise into place one after another
  (staggered ticks, ease-out-back, fading in along the kernel's
  cool-color curve) and hand over to the loop;
* the loop -- neon keeps its white decay-trail sweep, plasma walks the
  hue wheel along the word, retro flips amber/green phosphor with
  scanline rows, and starfield twinkles a three-layer drift;
* the breathing pulse dots under the word.

The starfield's stars live only in the bands above and below the
wordmark's bounding box, reserved by layout: no star can land on a
stroke in any phase, so the letters never grow holes or freckles.  No
pack carries a palette background either -- inked strokes stay
transparent between sub-rows, so they never grow dark notches on a
mismatched terminal backdrop.

The splash never times out: only a key or a click leaves for the menu.
``seed`` pins the style shuffle for a headless snapshot; ``None`` seeds
from the system, so every live launch starts somewhere new.
"""

from __future__ import annotations

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
from ..art import FONT_5X7, center

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
#: with scanlines, and ``starfield`` twinkles a three-layer star field
#: around the word with occasional red/cyan glitch bands.
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

#: The letters the wordmark spells (all present in :data:`FONT_5X7`).
_WORD_CHARS = "MOTUI"

#: Integer scales for the 5x7 skeleton: sub-cells per font cell, largest
#: first; the biggest one that fits the canvas with margin wins.
_FONT_SCALES = ((3, 4), (2, 3), (1, 2), (1, 1))

#: Font cells between letters (scaled like the glyphs are).
_LETTER_GAP = 2

#: The entrance: letter ``i`` starts ``i * stagger`` ticks in and rises
#: for ``dur`` ticks, from ``drop`` sub-cells below its slot.  Four
#: letters staggered plus one duration is the whole assembly.
_ENTRANCE_STAGGER = 9
_ENTRANCE_DUR = 30
_ENTRANCE_TICKS = 4 * _ENTRANCE_STAGGER + _ENTRANCE_DUR
_ENTRANCE_DROP = 20

#: The neon sweep: a white head flowing left-to-right, its decay trail
#: burning out behind it (one heat step per sub-cell of trail).
_SWEEP_PERIOD = 150
_SWEEP_PAD = 12
_SWEEP_TRAIL = 12
_SWEEP_STEP = 10

#: The starfield's parallax: per-layer drift as (numerator, denominator)
#: sub-cells per tick, far to near.
_STAR_DRIFT = ((1, 12), (1, 6), (1, 3))

#: The virtual space the star seeds were dealt in.
_STAR_SPACE_W = 152
_STAR_SPACE_H = 96

#: Twelve color bands across the word (the packs color by band).
_BANDS = 12


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
    return tuple(round(first + (last - first) * t) for first, last in zip(start, end, strict=False))


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


def _ease_out_back(t: float) -> float:
    """The ease-out-back curve: overshoots ~1.1 mid-way, settles on 1.0."""
    c1 = 1.70158
    c3 = c1 + 1.0
    u = t - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


def _build_letters(sx: int, sy: int) -> tuple[list[list[tuple[int, int]]], int, int]:
    """The word's letters at one integer scale: one point list per letter.

    Points are letter-local sub-cell coordinates.  A font cell becomes a
    solid ``sx x sy`` block, and a convex corner -- both orthogonal font
    neighbours empty -- loses its one corner sub-cell, the rounding that
    keeps the big blocks from reading as squared-off brickwork.
    """
    letters: list[list[tuple[int, int]]] = []
    for char in _WORD_CHARS:
        glyph = FONT_5X7[char]
        inked = {
            (col, row)
            for row, cells in enumerate(glyph)
            for col, bit in enumerate(cells)
            if bit == "1"
        }
        points: list[tuple[int, int]] = []
        for col, row in sorted(inked):
            top = (col, row - 1) in inked
            bottom = (col, row + 1) in inked
            left = (col - 1, row) in inked
            right = (col + 1, row) in inked
            for i in range(sx):
                for j in range(sy):
                    if i == 0 and j == 0 and not left and not top:
                        continue
                    if i == sx - 1 and j == 0 and not right and not top:
                        continue
                    if i == 0 and j == sy - 1 and not left and not bottom:
                        continue
                    if i == sx - 1 and j == sy - 1 and not right and not bottom:
                        continue
                    points.append((col * sx + i, row * sy + j))
        letters.append(points)
    width = (5 * sx + _LETTER_GAP * sx) * len(_WORD_CHARS) - _LETTER_GAP * sx
    return letters, width, 7 * sy


_LETTERS_CACHE: dict[
    tuple[int, int],
    tuple[list[list[tuple[int, int]]], int, int],
] = {}


def _letters(sx: int, sy: int) -> tuple[list[list[tuple[int, int]]], int, int]:
    """The scaled letters for one scale, built once."""
    cached = _LETTERS_CACHE.get((sx, sy))
    if cached is None:
        cached = _build_letters(sx, sy)
        _LETTERS_CACHE[(sx, sy)] = cached
    return cached


def _pick_scale(width: int, height: int) -> tuple[int, int]:
    """The largest integer scale whose word fits the canvas with margin."""
    for sx, sy in _FONT_SCALES:
        if 33 * sx <= width - 4 and 7 * sy <= height - 4:
            return sx, sy
    return (1, 1)


#: The scaled geometry cache: per canvas size and scale, the settled
#: letters as ``(x, y, index)`` triples, the sweep's column lookup, and
#: the star band bounds -- a frame's writes are index lookups, never
#: point math, except for a letter still in flight.
_GEOM_CACHE: dict[
    tuple[int, int, int, int],
    tuple[
        list[list[tuple[int, int, int]]],
        dict[int, list[int]],
        int,
        int,
    ],
] = {}


def _geometry(
    width: int, height: int, sx: int, sy: int
) -> tuple[
    list[list[tuple[int, int, int]]],
    dict[int, list[int]],
    int,
    int,
]:
    """The centred wordmark on one canvas, plus the star bands.

    ``columns`` maps an x to the raster indices the sweep lights;
    ``top``/``bottom`` bound the rows stars may occupy -- everything at
    least two sub-cells clear of the wordmark's box, which is what keeps
    the sky off the letters.
    """
    key = (width, height, sx, sy)
    cached = _GEOM_CACHE.get(key)
    if cached is not None:
        return cached
    letter_points, mark_w, mark_h = _letters(sx, sy)
    ox = max(0, (width - mark_w) // 2)
    oy = max(0, (height - mark_h) // 2)
    pitch = (5 + _LETTER_GAP) * sx  # one letter's slot plus its gap
    letters: list[list[tuple[int, int, int]]] = []
    columns: dict[int, list[int]] = {}
    for order, points in enumerate(letter_points):
        lx = order * pitch  # the letter's slot in the word
        placed: list[tuple[int, int, int]] = []
        for px, py in points:
            x, y = ox + lx + px, oy + py
            if not 0 <= x < width or not 0 <= y < height:
                continue
            index = y * width + x
            placed.append((x, y, index))
            columns.setdefault(x, []).append(index)
        letters.append(placed)
    top = max(0, oy - 2)
    bottom = min(height, oy + mark_h + 2)
    cached = (letters, columns, top, bottom)
    _GEOM_CACHE[key] = cached
    return cached


#: The star seeds: ``(x, y, layer)`` dealt once at import in the virtual
#: star space (far stars outnumber near ones).
def _build_stars() -> tuple[tuple[int, int, int], ...]:
    rng = random.Random(20261027)
    stars: list[tuple[int, int, int]] = []
    for layer, count in enumerate((44, 28, 14)):
        for _ in range(count):
            stars.append((rng.randrange(_STAR_SPACE_W), rng.randrange(_STAR_SPACE_H), layer))
    return tuple(stars)


_STARS: tuple[tuple[int, int, int], ...] = _build_stars()

#: Slot ids the starfield canvas spends on stars and glitch bands.
_STAR_SLOTS = (13, 14, 15)
_GLITCH_RED = 16
_GLITCH_CYAN = 17

#: The per-pack palettes.  Slot 13 is the neon sweep's white; the starfield
#: word is an icy ramp on slots 1-12 with stars and glitch above it.  No
#: pack carries a ``bg``: inked cells stay transparent between sub-rows,
#: so strokes never grow dark notches on a mismatched backdrop.
_PALETTES: dict[str, PixelPalette] = {
    "neon": PixelPalette(
        slots={
            **_ramp(LOGO_START, LOGO_END, _BANDS),
            13: ((255, 255, 255), (170, 174, 192)),
        },
    ),
    "plasma": PixelPalette(
        slots={
            1 + index: (
                _hsl(index * 30, 0.70, 0.60),
                _hsl(index * 30, 0.65, 0.26),
            )
            for index in range(_BANDS)
        },
    ),
    "retro": PixelPalette(
        slots={
            1: ((255, 176, 0), (120, 82, 0)),  # amber phosphor, lit and dim
            2: ((150, 100, 0), (70, 46, 0)),
            3: ((51, 255, 153), (24, 118, 72)),  # green phosphor, lit and dim
            4: ((30, 150, 90), (14, 70, 44)),
        },
    ),
    "starfield": PixelPalette(
        slots={
            # The word rides a bright ice ramp; the star field and glitch
            # bands keep their own (deeper) colors.
            **_ramp("#a9c6ff", "#ffffff", _BANDS),
            _STAR_SLOTS[0]: ((96, 116, 168), (44, 54, 80)),
            _STAR_SLOTS[1]: ((150, 180, 226), (70, 86, 110)),
            _STAR_SLOTS[2]: ((222, 236, 255), (110, 120, 140)),
            _GLITCH_RED: ((255, 92, 108), (120, 44, 52)),
            _GLITCH_CYAN: ((92, 232, 255), (44, 112, 124)),
        },
    ),
}


class SplashScene:
    """The opening: the font-skeleton wordmark in one of four packs.

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

    def _paint(self, canvas: PixelCanvas, pack: str, phase: int, sx: int, sy: int) -> None:
        """Redraw the whole canvas as a pure function of the phase.

        The fill layer carries the word (assembled or in flight); the art
        layer carries the sky and the pack's motion.  The trail heats are
        written explicitly -- the kernel's decay curve, one step per
        sub-cell -- rather than accumulated in the raster, so replaying
        any phase paints the exact same frame.
        """
        canvas.clear()
        width, height = canvas.art.width, canvas.art.height
        if pack == "starfield":
            self._paint_stars(canvas, phase, width, height, sx, sy)
        self._paint_wordmark(canvas, pack, phase, width, height, sx, sy)
        if pack == "neon" and phase >= _ENTRANCE_TICKS:
            self._paint_sweep(canvas, phase, width, sx, sy)

    def _paint_wordmark(
        self,
        canvas: PixelCanvas,
        pack: str,
        phase: int,
        width: int,
        height: int,
        sx: int,
        sy: int,
    ) -> None:
        """The letters on the fill layer, one slot per pack's recipe.

        Each letter rises for :data:`_ENTRANCE_DUR` ticks, staggered one
        :data:`_ENTRANCE_STAGGER`-tick step after the previous one: its
        ink starts ``_ENTRANCE_DROP`` sub-cells low at the cool-color
        threshold and eases up to the slot at full heat, so the assembly
        reads as the letters fading up into place, left to right.
        """
        letters, _columns, _top, _bottom = _geometry(width, height, sx, sy)
        slot_grid, heat_grid = canvas.fill.slot, canvas.fill.heat
        glitch = pack == "starfield" and (phase // 37) % 4 == 0
        shift = phase // 2  # the plasma hue wheel's step
        amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
        for order, letter in enumerate(letters):
            t = (phase - order * _ENTRANCE_STAGGER) / _ENTRANCE_DUR
            if t <= 0:
                continue  # this letter has not been called yet
            drop = 0 if t >= 1 else round((1.0 - _ease_out_back(t)) * _ENTRANCE_DROP)
            heat = 255 if t >= 1 else 128 + int(127.0 * t)
            for x, y, index in letter:
                if drop:
                    y += drop
                    if y >= height:
                        continue
                    index = y * width + x
                if pack == "plasma":
                    band = min(_BANDS - 1, x * _BANDS // width)
                    slot = 1 + (band + shift) % _BANDS
                elif pack == "retro":
                    scanline = (y // 4) % 2
                    slot = (2 if amber else 4) if scanline else (1 if amber else 3)
                else:  # neon and starfield: a fixed band ramp (starfield glitches)
                    slot = 1 + min(_BANDS - 1, x * _BANDS // width)
                    if glitch and (x * 7 + y * 13 + phase) % 19 < 2:
                        slot = _GLITCH_RED if (x + y) % 2 == 0 else _GLITCH_CYAN
                slot_grid[index] = slot
                heat_grid[index] = heat

    def _paint_sweep(self, canvas: PixelCanvas, phase: int, width: int, sx: int, sy: int) -> None:
        """The white sweep: a head column flowing across the assembled
        word, the strokes it passed cooling behind it through the
        palette's cool colors."""
        _letters, columns, _top, _bottom = _geometry(width, canvas.art.height, sx, sy)
        slot_grid, heat_grid = canvas.art.slot, canvas.art.heat
        span = width + 2 * _SWEEP_PAD
        tick = phase - _ENTRANCE_TICKS
        head = tick % _SWEEP_PERIOD * span // _SWEEP_PERIOD - _SWEEP_PAD
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

    def _paint_stars(
        self,
        canvas: PixelCanvas,
        phase: int,
        width: int,
        height: int,
        sx: int,
        sy: int,
    ) -> None:
        """Three parallax depths twinkling in the bands around the word.

        The virtual star space maps onto the two bands (top half of the
        space up, bottom half down), so a star's row never enters the
        wordmark's box whatever the drift does.  Each layer has its own
        speed, brightness slot and twinkle; near stars are two-dot sparks.
        """
        _letters, _columns, top, bottom = _geometry(width, height, sx, sy)
        slot_grid, heat_grid = canvas.art.slot, canvas.art.heat
        stride = canvas.art.width
        half = _STAR_SPACE_H // 2
        lower = height - bottom
        for order, (x, y, layer) in enumerate(_STARS):
            num, den = _STAR_DRIFT[layer]
            px = (x * width // _STAR_SPACE_W - phase * num // den) % width
            if y < half:
                if top <= 0:
                    continue
                py = y * top // half
            else:
                if lower <= 0:
                    continue
                py = bottom + (y - half) * lower // half
            if layer == 1 and (phase // 6 + order) % 7 == 0:
                continue
            if layer == 2 and (phase // 4 + order) % 5 == 0:
                continue
            slot = _STAR_SLOTS[layer]
            index = py * stride + px
            slot_grid[index] = slot
            heat_grid[index] = 255
            if layer == 2 and px + 1 < width:
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

        The canvas runs at 76x23 cells at a 100x30 pane (152x92 virtual
        pixels), shrinking only when the pane does, and the word is drawn
        at the largest integer scale of the 5x7 skeleton that fits it.  A
        whole frame measures 6.4-7.2 ms median across the four loop packs
        at 100x30 on this session's loaded VM, where the unchanged rings
        board reads 6.6 under the same load (~2.8-3 ms on a quiet machine)
        -- inside the 8 ms budget (CPython 3.13.16, Windows; 7-9 rounds of
        200 frames, median of per-round medians).  Wider panes centre the
        canvas.
        """
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        pack = self.style_name(phase)
        canvas_w = max(12, min(76, width - 2))
        canvas_h = max(5, min(23, height - 7))
        sx, sy = _pick_scale(canvas_w * 2, canvas_h * 2)
        canvas = self._canvas(pack)
        canvas.resize(canvas_w, canvas_h)
        self._paint(canvas, pack, phase, sx, sy)
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
