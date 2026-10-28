"""The splash's style packs: palettes, glyph cycles and color helpers."""

from __future__ import annotations

from ....pixel import PixelPalette

__all__ = [
    "LOGO_END",
    "LOGO_START",
    "SPLASH_GLYPHS",
    "SPLASH_GLYPH_TICKS",
    "SPLASH_ROTATE_TICKS",
    "SPLASH_STYLES",
]

#: How long one splash style holds: two seconds at the shell's 60 Hz.
SPLASH_ROTATE_TICKS = 120

#: How often the pulse dot's glyph morphs inside a style.
SPLASH_GLYPH_TICKS = 18

#: The style packs the splash rotates through.
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

#: Twelve color bands across the word (the packs color by band).
BANDS = 12

#: Slot ids the starfield canvas spends on stars and glitch bands.
STAR_SLOTS = (13, 14, 15)
GLITCH_RED = 16
GLITCH_CYAN = 17


def hsl(hue: float, saturation: float, lightness: float) -> tuple[int, int, int]:
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


def rgb(value: str) -> tuple[int, int, int]:
    """The RGB triple a ``#rrggbb`` string names."""
    text = value.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def mix(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """One interpolated step between two RGB triples."""
    return tuple(
        round(first + (last - first) * t)
        for first, last in zip(start, end, strict=False)
    )


def ramp(
    start: str,
    end: str,
    count: int,
    *,
    dim: float = 0.42,
) -> dict[int, tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """``count`` (main, cool) palette pairs stepping ``start`` -> ``end``."""
    first, last = rgb(start), rgb(end)
    return {
        1 + index: (
            mix(first, last, index / (count - 1)),
            mix(first, last, index / (count - 1) * dim),
        )
        for index in range(count)
    }


#: The per-pack palettes.  No pack carries a ``bg``: inked cells stay
#: transparent between sub-rows, so strokes never grow dark notches.
PALETTES: dict[str, PixelPalette] = {
    "neon": PixelPalette(
        slots={
            **ramp(LOGO_START, LOGO_END, BANDS),
            13: ((255, 255, 255), (170, 174, 192)),
        },
    ),
    "plasma": PixelPalette(
        slots={
            1 + index: (hsl(index * 30, 0.70, 0.60), hsl(index * 30, 0.65, 0.26))
            for index in range(BANDS)
        },
    ),
    "retro": PixelPalette(
        slots={
            1: ((255, 176, 0), (120, 82, 0)),
            2: ((150, 100, 0), (70, 46, 0)),
            3: ((51, 255, 153), (24, 118, 72)),
            4: ((30, 150, 90), (14, 70, 44)),
        },
    ),
    "starfield": PixelPalette(
        slots={
            **ramp("#a9c6ff", "#ffffff", BANDS),
            STAR_SLOTS[0]: ((96, 116, 168), (44, 54, 80)),
            STAR_SLOTS[1]: ((150, 180, 226), (70, 86, 110)),
            STAR_SLOTS[2]: ((222, 236, 255), (110, 120, 140)),
            GLITCH_RED: ((255, 92, 108), (120, 44, 52)),
            GLITCH_CYAN: ((92, 232, 255), (44, 112, 124)),
        },
    ),
}
