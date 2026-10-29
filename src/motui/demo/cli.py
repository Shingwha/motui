"""The showcase's command line: pages, headless replay or the live shell."""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Sequence

from .. import __version__
from ..app import App
from ..terminal import MouseMode, TerminalOptions
from .commands import build_commands
from .preview import render_scene, scene_text
from .registry import SCENES, SPEC_BY_NAME, SPECS
from .scene import TICK_HZ
from .shell import Showcase

__all__ = ["main"]


def _nonneg(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m motui",
        description="The motui showcase: one interactive page over the toolkit.",
    )
    parser.add_argument("--pages", action="store_true", help="print every scene")
    parser.add_argument("--headless", action="store_true", help="print one frame")
    parser.add_argument("--scene", choices=SCENES, help="the scene to open")
    parser.add_argument("--frames", type=_nonneg, default=0, help="ticks to advance")
    parser.add_argument("--width", type=_nonneg, default=100, help="pane width in cells")
    parser.add_argument("--height", type=_nonneg, default=30, help="pane height in cells")
    parser.add_argument("--list", action="store_true", help="list the scenes")
    parser.add_argument("--version", action="version", version=f"motui {__version__}")
    return parser


def _utf8_stdout() -> None:
    """Write the dump paths in UTF-8 whatever the console's codepage is."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):
        reconfigure(encoding="utf-8")


def _pages(width: int, height: int) -> None:
    for name in SCENES:
        spec = SPEC_BY_NAME[name]
        header = f"\u2500\u2500 /{name} \u2014 {spec.title} "
        print(f"\n{header}{'\u2500' * max(0, 100 - len(header))}")
        print(render_scene(name, width=width, height=height))


def _list() -> None:
    for spec in SPECS:
        print(f"{spec.name:<12} {spec.title:<14} {spec.blurb}")


def _interactive(scene: str) -> None:
    app = App(
        terminal=TerminalOptions(mouse=MouseMode.MOVE),
        throttle=1 / TICK_HZ,
        title="MOTUI / SIGNAL LAB",
    )
    showcase = Showcase(scene=scene, seed=None, status_line=True)
    showcase.on_quit = app.quit
    app.bind("ctrl+p", lambda: app.open_palette(build_commands(app, showcase)))
    clock, painter = app.workspace.clock, app.workspace.painter
    since, frames = clock(), painter.frames

    def tick() -> None:
        showcase.tick()
        app.invalidate()
        nonlocal since, frames
        now, count = clock(), painter.frames
        elapsed = now - since
        if elapsed >= 1.0:
            fps = round((count - frames) / elapsed)
            showcase.status_note = f"{fps} fps"
            since, frames = now, count

    app.fill(showcase)
    app.focus(showcase)
    app.every(1 / TICK_HZ, tick)
    app.run()


def main(argv: Sequence[str] | None = None) -> int:
    """The demo's one entry point: pages, headless, or the live showcase."""
    _utf8_stdout()
    parser = _parser()
    try:
        options = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    except SystemExit as exc:
        return int(exc.code)

    if options.list:
        _list()
        return 0
    if options.pages:
        _pages(options.width, options.height)
        return 0

    headless = options.headless or not (
        sys.stdin.isatty() and sys.stdout.isatty()
    )
    if headless:
        scene = options.scene or "menu"
        spec = SPEC_BY_NAME[scene]
        showcase = Showcase(scene=scene, phase=spec.preview_phase)
        for _ in range(options.frames):
            showcase.tick()
        sys.stdout.write(scene_text(showcase, options.width, options.height) + "\n")
        return 0

    _interactive(options.scene or "splash")
    return 0
