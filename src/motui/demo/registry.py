"""The one registry driving Home, the palette, headless pages and snapshots."""

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
from .scene import Scene, SceneSpec
from .sections.components import ComponentsScene
from .sections.dashboard import DashboardScene
from .sections.gallery import GalleryScene
from .sections.layout import LayoutScene
from .sections.menu import MenuScene
from .sections.motion import MotionScene
from .sections.splash import SplashScene
from .sections.terminal import TerminalScene
from .sections.themes import ThemesScene

__all__ = ["JUMPABLE", "SCENES", "SPECS", "SPEC_BY_NAME", "TILES", "build_scenes"]

SPECS: tuple[SceneSpec, ...] = (
    SceneSpec(
        "splash",
        "Opening",
        "particle assembly and remixed pixel layers",
        lambda theme, seed: SplashScene(theme, seed=seed),
        keys=(("enter / any key", "launch"), ("space", "remix layers")),
        preview_phase=240,
        jumpable=False,
    ),
    SceneSpec(
        "menu",
        "Signal Lab",
        "six experiments, one living preview",
        lambda theme, _seed: MenuScene(theme, TILES),
        keys=(
            ("arrows / tab", "select experiment"),
            ("enter / 1-6", "launch"),
            ("g", "component archive"),
            ("esc", "opening"),
        ),
    ),
    SceneSpec(
        "components",
        "Console Foundry",
        "compose a console with real widgets",
        lambda theme, _seed: ComponentsScene(theme),
        mini=mini_components,
        keys=(
            ("tab / shift-tab", "cycle focus"),
            ("arrows / type", "edit controls"),
            ("enter / space", "activate"),
            ("s", "sort probes"),
            ("esc", "close / lab"),
        ),
    ),
    SceneSpec(
        "layout",
        "Viewport Lab",
        "drive constraints, docks and overflow",
        lambda theme, _seed: LayoutScene(theme),
        mini=mini_layout,
        keys=(("1-4", "select drill"), ("arrows", "adjust geometry"), ("esc", "lab")),
    ),
    SceneSpec(
        "motion",
        "Pulse",
        "a sub-cell rhythm instrument",
        lambda theme, _seed: MotionScene(theme),
        mini=mini_motion,
        preview_phase=96,
        keys=(("space / click", "judge"), ("p", "pause"), ("r", "reset"), ("esc", "lab")),
    ),
    SceneSpec(
        "dashboard",
        "Deep Space",
        "control a living deep-space uplink",
        lambda theme, _seed: DashboardScene(theme),
        mini=mini_dashboard,
        keys=(
            ("space", "pause"),
            ("n / r", "interfere / recover"),
            ("arrows / 1-3", "switch relay"),
            ("esc", "lab"),
        ),
    ),
    SceneSpec(
        "terminal",
        "X-Ray",
        "trace input into terminal cells",
        lambda theme, _seed: TerminalScene(theme),
        mini=mini_terminal,
        keys=(("arrows", "move probe"), ("enter / space", "emit event"), ("esc", "lab")),
    ),
    SceneSpec(
        "themes",
        "Skin Lab",
        "re-skin the entire Signal Lab",
        lambda theme, _seed: ThemesScene(theme),
        mini=mini_themes,
        keys=(
            ("1-5 / arrows", "apply global theme"),
            ("c", "compare palettes"),
            ("ctrl+t", "cycle anywhere"),
            ("esc", "lab"),
        ),
    ),
    SceneSpec(
        "gallery",
        "Component Archive",
        "the widget bench in one page",
        lambda theme, _seed: GalleryScene(theme),
        keys=(("tab", "focus"), ("arrows / type", "operate"), ("esc", "lab")),
    ),
)

TILES: tuple[SceneSpec, ...] = tuple(spec for spec in SPECS if spec.mini is not None)
SCENES: tuple[str, ...] = tuple(spec.name for spec in SPECS)
JUMPABLE: tuple[str, ...] = tuple(spec.name for spec in SPECS if spec.jumpable)
SPEC_BY_NAME: dict[str, SceneSpec] = {spec.name: spec for spec in SPECS}


def build_scenes(theme: Theme, seed: int | None) -> dict[str, Scene]:
    return {spec.name: spec.factory(theme, seed) for spec in SPECS}
