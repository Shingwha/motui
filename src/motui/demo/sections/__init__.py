"""The showcase's scene classes; the registry lives in ``demo.registry``."""

from __future__ import annotations

from .components import ComponentsScene
from .dashboard import DashboardScene
from .gallery import GalleryScene
from .layout import LayoutScene
from .menu import MenuScene
from .motion import MotionScene
from .splash import SplashScene
from .terminal import TerminalScene
from .themes import ThemesScene

__all__ = [
    "ComponentsScene",
    "DashboardScene",
    "GalleryScene",
    "LayoutScene",
    "MenuScene",
    "MotionScene",
    "SplashScene",
    "TerminalScene",
    "ThemesScene",
]
