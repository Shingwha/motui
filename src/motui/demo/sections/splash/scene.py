"""The splash scene: the wordmark, its packs and the pulse strip."""

from __future__ import annotations

import random

from ....kernel.cell import Line, Segment, Surface
from ....kernel.events import KeyEvent
from ....kernel.geom import Pos
from ....kernel.layout import Constraints
from ....kernel.style import Style
from ....kernel.theme import Theme
from ....widgets import PixelCanvas
from ...common import center
from ...scene import Scene
from ...version import DEMO_VERSION
from .packs import (
    LOGO_END,
    LOGO_START,
    PALETTES,
    SPLASH_GLYPH_TICKS,
    SPLASH_GLYPHS,
    SPLASH_ROTATE_TICKS,
    SPLASH_STYLES,
    hsl,
    mix,
    rgb,
)
from .stars import paint_stars
from .wordmark import ENTRANCE_TICKS, paint_sweep, paint_wordmark, pick_scale

__all__ = ["SplashScene"]


class SplashScene(Scene):
    """The opening: the font-skeleton wordmark in one of four packs.

    The splash never times out.  It rotates through :data:`SPLASH_STYLES`
    every :data:`SPLASH_ROTATE_TICKS` animation ticks, reshuffling the order
    whenever it is entered, and only a key or a click leaves for the menu.
    Every frame is a pure function of the phase, so a headless replay is
    byte-identical to the live showcase.
    """

    name = "splash"

    def __init__(self, theme: Theme, *, seed: int | None = 0) -> None:
        super().__init__(theme)
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._order = list(SPLASH_STYLES)
        self._canvases: dict[str, PixelCanvas] = {}

    def enter(self) -> None:
        """Reshuffle the style order; the next visit starts somewhere new."""
        super().enter()
        self._rng.shuffle(self._order)

    def style_name(self, phase: int) -> str:
        """The pack active at ``phase`` (exposed for tests and the hint row)."""
        return self._order[(phase // SPLASH_ROTATE_TICKS) % len(self._order)]

    def _canvas(self, pack: str) -> PixelCanvas:
        """The pack's own canvas: each palette is built once, lazily."""
        canvas = self._canvases.get(pack)
        if canvas is None:
            canvas = PixelCanvas(palette=PALETTES[pack])
            self._canvases[pack] = canvas
        return canvas

    # -- painting ----------------------------------------------------------

    def _paint(self, canvas: PixelCanvas, pack: str, phase: int, sx: int, sy: int) -> None:
        """Redraw the whole canvas as a pure function of the phase."""
        canvas.clear()
        width, height = canvas.pixel_width, canvas.pixel_height
        if pack == "starfield":
            paint_stars(canvas, phase, width, height, sx, sy)
        paint_wordmark(canvas, pack, phase, width, height, sx, sy)
        if pack == "neon" and phase >= ENTRANCE_TICKS:
            paint_sweep(canvas, phase, width, sx, sy)

    # -- chrome ------------------------------------------------------------

    def _accent(self, pack: str, phase: int) -> Style:
        """The subtitle/indicator color the active pack uses."""
        if pack == "neon":
            return Style(fg=mix(rgb(LOGO_START), rgb(LOGO_END), 0.5), bold=True)
        if pack == "plasma":
            return Style(fg=hsl(phase * 4, 0.7, 0.65), bold=True)
        if pack == "retro":
            amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
            return Style(fg=(255, 176, 0) if amber else (51, 255, 153), bold=True)
        return Style(fg=(220, 230, 255), bold=True)

    def _pulse(self, pack: str, phase: int) -> Line:
        """Five dots with one lit: the quiet breathing mark under the word."""
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
        """The centred wordmark canvas over the subtitle, pulse and hint."""
        self._phase = phase
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        pack = self.style_name(phase)
        canvas_w = max(12, min(76, width - 2))
        canvas_h = max(5, min(23, height - 7))
        sx, sy = pick_scale(canvas_w * 2, canvas_h * 2)
        canvas = self._canvas(pack)
        canvas.resize(canvas_w, canvas_h)
        self._paint(canvas, pack, phase, sx, sy)
        pad = max(0, (width - canvas_w) // 2)
        prefix = Line((Segment(" " * pad),)) if pad else None
        mark = canvas.render(Constraints(width=canvas_w))
        mark = [prefix + row for row in mark] if prefix else list(mark)
        subtitle = center(
            width,
            [
                Line.from_text(
                    f"a terminal UI kernel \u00b7 {DEMO_VERSION}",
                    self.theme.text.muted,
                )
            ],
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
