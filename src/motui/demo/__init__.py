"""The showcase: ``python -m motui`` is one interactive page, not a tour.

The shell opens on a splash, then lands on the Home tiles.  The package is
split by responsibility: :mod:`motui.demo.cli` owns the entry modes,
:mod:`motui.demo.preview` the deterministic text/painter snapshots,
:mod:`motui.demo.registry` the one scene registry, :mod:`motui.demo.shell`
the phase/transition chrome and :mod:`motui.demo.sections` the scenes.
"""

from __future__ import annotations

from .cli import main
from .preview import render_scene, scene_output
from .registry import SCENES
from .scene import PAGE_PHASE, START_PHASE, TICK_HZ, Scene, SceneSpec
from .version import DEMO_BAND, DEMO_VERSION

__all__ = [
    "DEMO_BAND",
    "DEMO_VERSION",
    "PAGE_PHASE",
    "SCENES",
    "START_PHASE",
    "TICK_HZ",
    "Scene",
    "SceneSpec",
    "main",
    "render_scene",
    "scene_output",
]
