"""The demo command palette: every jumpable scene plus its chrome."""

from __future__ import annotations

from collections.abc import Callable

from ..app import App, Command, CommandRegistry
from .registry import SPECS
from .shell import Showcase

__all__ = ["build_commands"]


def build_commands(app: App, showcase: Showcase) -> CommandRegistry:
    """One jump per jumpable scene, then help, status and quit."""

    def jump(name: str) -> Callable[[], None]:
        return lambda: showcase.switch(name)

    def toggle_status() -> None:
        showcase.status_line = not showcase.status_line
        showcase.touch()

    commands = [
        Command(
            name=f"jump to {spec.name}",
            description=spec.blurb,
            group="demo",
            handler=jump(spec.name),
        )
        for spec in SPECS
        if spec.jumpable
    ]
    commands.extend(
        (
            Command(
                name="next global theme",
                description="re-skin the entire Signal Lab",
                group="appearance",
                handler=showcase.cycle_theme,
            ),
            Command(
                name="previous global theme",
                description="re-skin the entire Signal Lab",
                group="appearance",
                handler=lambda: showcase.cycle_theme(-1),
            ),
            Command(
                name="toggle calm mode",
                description="pause or resume ambient motion",
                group="appearance",
                handler=showcase.toggle_motion,
            ),
            Command(
                name="show help",
                description="open the keys panel",
                group="demo",
                handler=showcase.toggle_help,
            ),
            Command(
                name="toggle status line",
                description="show or hide the bottom bar",
                group="demo",
                handler=toggle_status,
            ),
            Command(
                name="quit the demo",
                description="leave the showcase",
                group="demo",
                handler=app.quit,
            ),
        )
    )
    return CommandRegistry(commands)
