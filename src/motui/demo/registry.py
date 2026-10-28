"""The one scene registry: shell, Home tiles, palette and snapshots."""

from __future__ import annotations

from ..kernel.theme import Theme
from .minis import (
    mini_components,
    mini_dashboard,
    mini_layout,
    mini_motion,
    mini_terminal,
    mini_themes,
)
from .scene import PAGE_PHASE, Scene, SceneSpec
from .sections.components import ComponentsScene
from .sections.dashboard import DashboardScene
from .sections.gallery import GalleryScene
from .sections.layout import LayoutScene
from .sections.menu import MenuScene
from .sections.motion import MotionScene
from .sections.splash import SplashScene
from .sections.terminal import TerminalScene
from .sections.themes import ThemesScene
from .snake import SnakeScene

__all__ = ["JUMPABLE", "SCENES", "SPECS", "SPEC_BY_NAME", "TILES", "build_scenes"]

#: The scenes in tour order.  Motion's preview phase sits after its first
#: rings are alive, so ``--pages`` and the semantic snapshot are not empty.
SPECS: tuple[SceneSpec, ...] = (
    SceneSpec(
        "splash",
        "Splash",
        "the opening wordmark",
        lambda theme, seed: SplashScene(theme, seed=seed),
        keys=(("any key", "enter the showcase"),),
        preview_phase=PAGE_PHASE,
        jumpable=False,
    ),
    SceneSpec(
        "menu",
        "Home",
        "choose a section",
        lambda theme, _seed: MenuScene(theme, TILES),
        keys=(
            ("arrows", "choose"),
            ("enter", "open"),
            ("esc", "back to splash"),
            ("q", "quit"),
        ),
    ),
    SceneSpec(
        "components",
        "Components",
        "widgets, one page each",
        lambda theme, _seed: ComponentsScene(theme),
        mini=mini_components,
        keys=(
            ("tab", "cycle focus"),
            ("enter/space", "activate"),
            ("s", "sort the table"),
            ("esc", "close / back"),
            ("q", "quit unless typing"),
        ),
    ),
    SceneSpec(
        "layout",
        "Layout",
        "rows, columns, spans",
        lambda theme, _seed: LayoutScene(theme),
        mini=mini_layout,
        keys=(("1-4", "drill"), ("arrows", "adjust"), ("esc", "menu"), ("q", "quit")),
    ),
    SceneSpec(
        "motion",
        "Motion",
        "pixel rings, live",
        lambda theme, _seed: MotionScene(theme),
        mini=mini_motion,
        preview_phase=96,
        keys=(("space/click", "judge"), ("esc", "menu"), ("q", "quit")),
    ),
    SceneSpec(
        "dashboard",
        "Dashboard",
        "streaming sparklines",
        lambda theme, _seed: DashboardScene(theme),
        mini=mini_dashboard,
        keys=(("esc", "menu"), ("q", "quit")),
    ),
    SceneSpec(
        "terminal",
        "Terminal",
        "keys, mouse, paint",
        lambda theme, _seed: TerminalScene(theme),
        mini=mini_terminal,
        keys=(("click", "land a report"), ("esc", "menu"), ("q", "quit")),
    ),
    SceneSpec(
        "themes",
        "Themes",
        "ink & signal variants",
        lambda theme, _seed: ThemesScene(theme),
        mini=mini_themes,
        keys=(
            ("1-4 / left-right", "pick"),
            ("c", "compare"),
            ("esc", "menu"),
            ("q", "quit"),
        ),
    ),
    SceneSpec(
        "snake",
        "Snake",
        "the classic game",
        lambda theme, _seed: SnakeScene(theme),
        keys=(
            ("arrows/wasd", "steer"),
            ("space", "pause"),
            ("esc", "menu"),
            ("q", "quit"),
        ),
    ),
    SceneSpec(
        "gallery",
        "Gallery",
        "real widgets on one page",
        lambda theme, _seed: GalleryScene(theme),
        keys=(
            ("tab", "focus"),
            ("arrows", "move"),
            ("esc", "menu"),
            ("q", "quit unless typing"),
        ),
    ),
)

#: The Home tiles: every spec with a miniature.
TILES: tuple[SceneSpec, ...] = tuple(spec for spec in SPECS if spec.mini is not None)

#: All scene names, in tour order.
SCENES: tuple[str, ...] = tuple(spec.name for spec in SPECS)

#: The scenes the command palette may jump to.
JUMPABLE: tuple[str, ...] = tuple(spec.name for spec in SPECS if spec.jumpable)

SPEC_BY_NAME: dict[str, SceneSpec] = {spec.name: spec for spec in SPECS}


def build_scenes(theme: Theme, seed: int | None) -> dict[str, Scene]:
    """Build one scene object per spec, in tour order."""
    return {spec.name: spec.factory(theme, seed) for spec in SPECS}
