"""The splash section: a 5x7 logo cycling through four animated style packs."""

from __future__ import annotations

import math
import random

from ...kernel.cell import Line, Segment, Surface
from ...kernel.events import KeyEvent
from ...kernel.geom import Pos
from ...kernel.layout import Constraints
from ...kernel.style import Style
from ...kernel.theme import Theme
from ..art import big_text, center, gradient_styles

__all__ = [
    "LOGO_END",
    "LOGO_START",
    "SPLASH_GLYPHS",
    "SPLASH_GLYPH_TICKS",
    "SPLASH_ROTATE_TICKS",
    "SPLASH_STYLES",
    "SplashScene",
]

#: How long one splash style holds: four seconds at 30 Hz.
SPLASH_ROTATE_TICKS = 120

#: How often the logo's fill glyph morphs inside a style.
SPLASH_GLYPH_TICKS = 18

#: The style packs the splash rotates through.  Each changes both glyphs and
#: colors; ``starfield`` also draws a field of stars around the word.
SPLASH_STYLES: tuple[str, ...] = ("neon", "plasma", "retro", "starfield")

#: The fill glyphs each pack morphs between (all single-width).
SPLASH_GLYPHS: dict[str, tuple[str, ...]] = {
    "neon": ("\u2588", "\u2593", "\u25a0", "\u2588"),
    "plasma": ("\u2588", "\u2593", "\u2592", "\u25a0"),
    "retro": ("\u2588", "\u2593"),
    "starfield": ("\u25a0", "\u25a3", "\u2726", "\u2588"),
}

#: The logo's ink: the accent fades into the inline-code lavender.
LOGO_START = "#53c8f0"
LOGO_END = "#c4b5fd"


def _hsl(hue: float, saturation: float, lightness: float) -> tuple[int, int, int]:
    """One HSL color as an RGB triple (the plasma/starfield palettes)."""
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


class SplashScene:
    """The opening: a 5x7 logo in one of four animated style packs.

    The splash never times out.  It rotates through :data:`SPLASH_STYLES`
    every :data:`SPLASH_ROTATE_TICKS` animation ticks (about four seconds),
    reshuffling the order whenever it is entered, and only a key or a click
    leaves for the menu.  Each pack changes both the fill glyph and the
    colors: ``neon`` is the cyan-to-lavender ramp with a white sweep,
    ``plasma`` walks the hue wheel across the word, ``retro`` is a green or
    amber CRT with dim scanlines, and ``starfield`` colors cells from a
    drifting star palette with occasional red/cyan glitch bands and a field
    of stars around the logo.

    ``seed`` pins the shuffle for a headless snapshot; ``None`` seeds from
    the system for a live run, so every launch starts on a different pack.
    """

    name = "splash"

    def __init__(self, theme: Theme, *, seed: int | None = 0) -> None:
        self.theme = theme
        self._logo_width = 5 * len("MOTUI") + 4
        self._neon_styles = gradient_styles(LOGO_START, LOGO_END, self._logo_width)
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._order = list(SPLASH_STYLES)
        self.restart()

    def restart(self) -> None:
        """Reshuffle the style order; the next visit starts somewhere new."""
        self._rng.shuffle(self._order)

    def style_name(self, phase: int) -> str:
        """The pack active at ``phase`` (exposed for tests and the hint row)."""
        return self._order[(phase // SPLASH_ROTATE_TICKS) % len(self._order)]

    def _glyph(self, pack: str, phase: int) -> str:
        glyphs = SPLASH_GLYPHS[pack]
        return glyphs[(phase // SPLASH_GLYPH_TICKS) % len(glyphs)]

    def _accent(self, pack: str, phase: int) -> Style:
        """The subtitle/indicator color the active pack uses."""
        if pack == "neon":
            return Style(fg=self._neon_styles[self._logo_width // 2].fg, bold=True)
        if pack == "plasma":
            return Style(fg=_hsl(phase * 4, 0.7, 0.65), bold=True)
        if pack == "retro":
            amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
            return Style(fg=(255, 176, 0) if amber else (51, 255, 153), bold=True)
        return Style(fg=(220, 230, 255), bold=True)

    def _style_at(self, pack: str, phase: int, x: int, y: int) -> Style:
        """One logo cell's style for the active pack."""
        if pack == "neon":
            base = self._neon_styles[x % len(self._neon_styles)]
            sweep = (phase % (self._logo_width + 12)) - 6
            if x == sweep:
                return Style(fg=(255, 255, 255), bold=True)
            return Style(fg=base.fg, bold=(phase // 8 + x // 4) % 2 == 0)
        if pack == "plasma":
            hue = (x * 11 + phase * 6) % 360
            light = 0.55 + 0.12 * math.sin((x + phase / 7) / 3)
            return Style(fg=_hsl(hue, 0.72, light), bold=(x + phase // 9) % 4 == 0)
        if pack == "retro":
            amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
            rgb = (255, 176, 0) if amber else (51, 255, 153)
            if y % 2:
                rgb = tuple(channel // 2 for channel in rgb)
            sweep = (phase % (self._logo_width + 16)) - 8
            if x == sweep:
                return Style(fg=(255, 255, 255), bold=True)
            return Style(fg=rgb, bold=not amber and x % 3 == 0)
        # starfield
        hue = (x * 47 + y * 29 + (phase // 5) * 31) % 360
        glitch = (phase // 37) % 4 == 0 and (x * 7 + y * 13 + phase) % 19 < 2
        if glitch:
            hue = 0 if (x + y) % 2 == 0 else 180
        return Style(
            fg=_hsl(hue, 0.55, 0.6),
            bold=glitch or (x + y + phase // 8) % 7 == 0,
        )

    def _pulse(self, pack: str, phase: int) -> Line:
        """Five dots with one lit: the quiet breathing mark under the logo."""
        lit = (phase // 4) % 5
        accent = self._accent(pack, phase)
        segments: list[Segment] = []
        for index in range(5):
            if index:
                segments.append(Segment("   "))
            segments.append(
                Segment(
                    "\u25cf" if index == lit else "\u00b7",
                    accent if index == lit else self.theme.text.faint,
                )
            )
        return Line(segments)

    def _stars(self, width: int, phase: int) -> list[Line]:
        """Two rows of deterministic stars: the starfield pack's air."""
        rows: list[Line] = []
        for row in range(2):
            segments: list[Segment] = []
            for x in range(max(0, width)):
                seed = x * 37 + row * 91 + (phase // 6) * 17
                if seed % 19 == 0:
                    segments.append(
                        Segment("\u2726", Style(fg=_hsl((seed * 7) % 360, 0.45, 0.62)))
                    )
                elif seed % 11 == 0:
                    segments.append(Segment("\u00b7", self.theme.text.faint))
                else:
                    segments.append(Segment(" "))
            rows.append(Line(segments))
        return rows

    def render(self, c: Constraints, phase: int) -> Surface:
        width = c.width
        height = c.max_height if c.max_height is not None else 24
        pack = self.style_name(phase)
        logo = center(
            width,
            big_text(
                "MOTUI",
                pixel=self._glyph(pack, phase),
                style_at=lambda x, y: self._style_at(pack, phase, x, y),
            ),
        )
        subtitle = center(
            width,
            [Line.from_text("a terminal UI kernel \u00b7 2.0.0", self.theme.text.muted)],
        )
        dots = center(width, [self._pulse(pack, phase)])
        hint = center(
            width,
            [Line.from_text(f"press any key  \u00b7  {pack}", self.theme.text.faint)],
        )
        content = [
            *logo,
            Line(),
            *subtitle,
            Line(),
            *dots,
            Line(),
            *hint,
        ]
        if pack == "starfield":
            content = [
                *self._stars(width, phase),
                Line(),
                *content,
                Line(),
                *self._stars(width, phase + 7),
            ]
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
