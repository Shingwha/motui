"""The two deterministic rendering paths the tools share."""

from __future__ import annotations

from ..app import Runtime
from ..kernel.layout import Constraints
from ..terminal import HeadlessScreen, Terminal, TerminalOptions
from .registry import SPEC_BY_NAME
from .shell import Showcase

__all__ = ["render_scene", "scene_output", "scene_text"]


def scene_text(showcase: Showcase, width: int, height: int) -> str:
    """One showcase frame as plain text, trailing blank rows dropped."""
    surface = showcase.render(Constraints(width=width, max_height=height))
    lines = [row.text.rstrip() for row in surface]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _spec(name: str):
    spec = SPEC_BY_NAME.get(name)
    if spec is None:
        raise ValueError(f"unknown scene {name!r}: expected one of {tuple(SPEC_BY_NAME)}")
    return spec


def render_scene(
    name: str,
    *,
    width: int = 100,
    height: int = 30,
    phase: int | None = None,
    seed: int = 0,
) -> str:
    """One scene as its plain-text frame at ``width`` x ``height``.

    ``phase=None`` uses the scene's registry preview phase, so motion's
    ``--pages`` frame is not an empty board.
    """
    spec = _spec(name)
    showcase = Showcase(
        scene=name,
        seed=seed,
        phase=spec.preview_phase if phase is None else phase,
    )
    return scene_text(showcase, width, height)


def scene_output(
    name: str,
    *,
    width: int = 100,
    height: int = 30,
    phase: int | None = None,
    seed: int = 0,
) -> str:
    """One scene's painted bytes, recorded from a fresh headless runtime."""
    spec = _spec(name)
    screen = HeadlessScreen(width, height)
    runtime = Runtime(
        Terminal(TerminalOptions(screen=screen)),
        interactive=False,
    )
    showcase = Showcase(
        scene=name,
        seed=seed,
        phase=spec.preview_phase if phase is None else phase,
    )
    runtime.workspace.fill(showcase)
    runtime.paint()
    return screen.output
