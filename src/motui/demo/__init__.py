"""The showcase: ``python -m motui`` is one interactive page, not a tour.

It opens on a layered splash, then lands on the Signal Lab index; the
package splits into cli, preview, registry, shell and sections."""

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
