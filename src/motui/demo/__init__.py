"""The showcase: ``python -m motui`` is one interactive page, not a tour.

The shell opens on a splash, then lands on the Home tiles: six sections
(components, layout, motion, dashboard, terminal, themes) reachable from
one grid, plus the standalone snake game and the widget gallery the
contract keeps renderable.  The package owns the three entry modes:

* a real terminal runs the showcase live (alt screen, mouse, timed ticks);
* a piped run -- or ``--headless`` -- prints the menu's frame and exits 0;
* ``--pages`` prints every scene as plain text at a fixed phase.

``render_scene`` and ``scene_output`` are the two rendering paths the tools
share: the first is the plain-text dump ``--pages`` writes, the second the
real painter bytes the semantic golden records.  Both take the scene name,
the geometry and an explicit phase, so a snapshot is a value, never a
clock reading.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from ..app import App, Runtime
from ..kernel.layout import Constraints
from ..terminal import HeadlessScreen, MouseMode, Terminal, TerminalOptions
from .showcase import SCENES, Showcase

__all__ = ["SCENES", "main", "render_scene", "scene_output"]

#: The fixed phase ``--pages`` and the semantic snapshots share.  Twenty
#: ticks show motion in every scene: the splash's sweep is mid-word, the
#: snake has taken its first steps, and the dashboard window has streamed.
PAGE_PHASE = 20

#: The live showcase's tick rate (the splash auto-advances after 60 ticks).
TICK_HZ = 30

_USAGE = (
    "usage: python -m motui [--pages] [--headless] [--scene NAME] "
    "[--frames N] [--width N] [--height N]"
)


def _utf8_stdout() -> None:
    """Write the dump paths in UTF-8 whatever the console's codepage is."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    with contextlib.suppress(ValueError, OSError):
        reconfigure(encoding="utf-8")


def _scene_text(showcase: Showcase, width: int, height: int) -> str:
    """One showcase frame as plain text, trailing blank rows dropped."""
    surface = showcase.render(Constraints(width=width, max_height=height))
    lines = [row.text.rstrip() for row in surface]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def render_scene(
    name: str,
    *,
    width: int = 100,
    height: int = 30,
    phase: int = PAGE_PHASE,
    seed: int = 0,
) -> str:
    """One scene as its plain-text frame at ``width`` x ``height``, phase fixed."""
    showcase = Showcase(scene=name, seed=seed)
    showcase.phase = phase
    return _scene_text(showcase, width, height)


def scene_output(
    name: str,
    *,
    width: int = 100,
    height: int = 30,
    phase: int = PAGE_PHASE,
    seed: int = 0,
) -> str:
    """One scene's painted bytes, recorded from a fresh headless runtime.

    The path the semantic golden feeds to the emulator: a headless screen,
    a non-interactive runtime, ``fill(Showcase)`` and one ``paint`` -- no
    event pump, no clock, no terminal.  ``seed`` pins the splash's style
    order for a reproducible snapshot.
    """
    screen = HeadlessScreen(width, height)
    runtime = Runtime(
        Terminal(TerminalOptions(screen=screen)),
        interactive=False,
    )
    showcase = Showcase(scene=name, seed=seed)
    showcase.phase = phase
    runtime.workspace.fill(showcase)
    runtime.paint()
    return screen.output


def _pages() -> None:
    """Print every scene as plain text, one full-width rule per scene."""
    for name in SCENES:
        header = f"\u2500\u2500 /{name} "
        print(f"\n{header}{'\u2500' * max(0, 100 - len(header))}")
        print(render_scene(name, width=100, height=30, phase=PAGE_PHASE))


def _tick(app: App, showcase: Showcase) -> None:
    """One animation tick: advance the phase and repaint."""
    showcase.tick()
    app.invalidate()


def _interactive(scene: str) -> None:
    """Run the showcase on a real terminal until the scene asks to quit."""
    app = App(terminal=TerminalOptions(mouse=MouseMode.MOVE), title="motui showcase")
    # A live launch starts on a random splash pack; headless snapshots pin 0.
    showcase = Showcase(scene=scene, seed=None)
    showcase.on_quit = app.quit
    app.fill(showcase)
    app.focus(showcase)
    app.every(1 / TICK_HZ, lambda: _tick(app, showcase))
    app.run()


@dataclass(frozen=True, slots=True)
class _Options:
    """The parsed command line: every value typed, no ``object`` soup."""

    pages: bool = False
    headless: bool = False
    scene: str = "menu"
    frames: int = 0
    width: int = 100
    height: int = 30
    scene_set: bool = False


def _parse(args: Sequence[str]) -> _Options | None:
    """Parse the small flag set; ``None`` means the usage line was printed."""
    pages = False
    headless = False
    scene = "menu"
    scene_set = False
    frames = 0
    width = 100
    height = 30
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--pages":
            pages = True
            index += 1
        elif arg == "--headless":
            headless = True
            index += 1
        elif arg in ("-h", "--help"):
            print(_USAGE)
            return None
        elif arg in ("--scene", "--frames", "--width", "--height"):
            if index + 1 >= len(args):
                print(_USAGE)
                return None
            value = args[index + 1]
            if arg == "--scene":
                scene = value
                scene_set = True
            elif not value.isdigit():
                print(_USAGE)
                return None
            elif arg == "--frames":
                frames = int(value)
            elif arg == "--width":
                width = int(value)
            else:
                height = int(value)
            index += 2
        else:
            print(_USAGE)
            return None
    if scene not in SCENES:
        print(_USAGE)
        return None
    return _Options(pages, headless, scene, frames, width, height, scene_set)


def main(argv: Sequence[str] | None = None) -> int:
    """The demo's one entry point: pages, headless, or the live showcase."""
    _utf8_stdout()
    options = _parse(sys.argv[1:] if argv is None else list(argv))
    if options is None:
        return 2
    if options.pages:
        _pages()
        return 0
    headless = options.headless or not (
        sys.stdin.isatty() and sys.stdout.isatty()
    )
    if headless:
        # A piped run has no screen to wait on: keep the menu frame unless the
        # caller asked for a specific scene.  The live launch opens on splash.
        scene = options.scene if options.scene_set else "menu"
        showcase = Showcase(scene=scene)
        for _ in range(options.frames):
            showcase.tick()
        sys.stdout.write(
            _scene_text(showcase, options.width, options.height) + "\n"
        )
        return 0
    _interactive(options.scene if options.scene_set else "splash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
