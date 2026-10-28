"""Compatibility re-exports for the showcase's historical import path.

The scene classes live in :mod:`motui.demo.sections`, the shell widget in
:mod:`motui.demo.shell`; this module exists so ``motui.demo.showcase``
keeps answering every name it always did (``tests/test_demo_scenes.py``
imports the scene classes from here).  It holds no logic of its own.
"""

from __future__ import annotations

from .sections import (
    SCENES,
    DashboardScene,
    GalleryScene,
    MenuScene,
    Scene,
    SnakeScene,
    SplashScene,
)
from .sections.splash import (
    LOGO_END,
    LOGO_START,
    SPLASH_GLYPHS,
    SPLASH_GLYPH_TICKS,
    SPLASH_ROTATE_TICKS,
    SPLASH_STYLES,
)
from .shell import START_PHASE, Showcase

__all__ = [
    "LOGO_END",
    "LOGO_START",
    "SCENES",
    "SPLASH_GLYPHS",
    "SPLASH_GLYPH_TICKS",
    "SPLASH_ROTATE_TICKS",
    "SPLASH_STYLES",
    "START_PHASE",
    "DashboardScene",
    "GalleryScene",
    "MenuScene",
    "Scene",
    "Showcase",
    "SnakeScene",
    "SplashScene",
]
