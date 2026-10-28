"""The splash scene package: font, packs, wordmark, stars and chrome."""

from __future__ import annotations

from .packs import (
    LOGO_END,
    LOGO_START,
    SPLASH_GLYPH_TICKS,
    SPLASH_GLYPHS,
    SPLASH_ROTATE_TICKS,
    SPLASH_STYLES,
)
from .scene import SplashScene

__all__ = [
    "LOGO_END",
    "LOGO_START",
    "SPLASH_GLYPHS",
    "SPLASH_GLYPH_TICKS",
    "SPLASH_ROTATE_TICKS",
    "SPLASH_STYLES",
    "SplashScene",
]
