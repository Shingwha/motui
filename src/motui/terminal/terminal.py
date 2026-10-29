"""The terminal adapter: one screen, one input source, one capability answer.

It owns no policy: it never dispatches an event, moves focus, scrolls or
paints."""

from __future__ import annotations

from dataclasses import dataclass

from ..kernel.events import Event, EventSource
from ..kernel.style import ColorMode
from .clipboard import ScreenClipboard
from .screen import (
    Screen,
    TerminalOptions,
    TerminalScreen,
    mouse_switches,
)

__all__ = ["Capability", "Terminal"]

#: The defaults are frozen values; one shared instance is the argument default.
_DEFAULT_OPTIONS = TerminalOptions()


@dataclass(frozen=True, slots=True, kw_only=True)
class Capability:
    """What the attached screen can render, sampled on demand; a value, not a
    handle, so ask again after a resize."""

    color_mode: ColorMode
    size: tuple[int, int]
    live: bool
    encoding: str | None = None


class Terminal:
    """A configured screen plus the event source and clipboard over it.

    ``screen=`` wins over ``options.screen``, which wins over building a
    TerminalScreen; :meth:`attach` replaces the input source."""

    def __init__(
        self,
        options: TerminalOptions = _DEFAULT_OPTIONS,
        *,
        screen: Screen | None = None,
    ) -> None:
        self.options = options
        if screen is not None:
            self._screen = screen
        elif options.screen is not None:
            self._screen = options.screen
        else:
            mouse, hover = mouse_switches(options.mouse)
            self._screen = TerminalScreen(
                options.stream,
                mouse=mouse,
                paste=options.paste,
                hover=hover,
                focus_events=options.focus_events,
                color_mode=options.color_mode,
            )
        self._input = options.input
        self._clipboard = ScreenClipboard(self._screen)

    @property
    def screen(self) -> Screen:
        """The attached screen; a terminal never replaces it mid-run."""
        return self._screen

    @property
    def input(self) -> EventSource | None:
        """The event source :meth:`read_event` reads, ``None`` for no source."""
        return self._input

    @property
    def live(self) -> bool:
        """Whether written bytes reach a real terminal."""
        return self._screen.live

    @property
    def size(self) -> tuple[int, int]:
        """The screen's current ``(columns, rows)``."""
        return self._screen.size

    @property
    def capability(self) -> Capability:
        """The screen's color, size, liveness and encoding, sampled now."""
        return Capability(
            color_mode=self._screen.color_mode,
            size=self._screen.size,
            live=self._screen.live,
            encoding=self._screen.encoding,
        )

    @property
    def clipboard(self) -> ScreenClipboard:
        """The clipboard that writes OSC 52 through the attached screen."""
        return self._clipboard

    def attach(self, source: EventSource | None) -> None:
        """Point :meth:`read_event` at ``source`` (``None`` reports EOF)."""
        self._input = source

    def enter(self) -> None:
        """Enter the full-screen session through the screen."""
        self._screen.enter()

    def leave(self) -> None:
        """Leave the full-screen session through the screen."""
        self._screen.leave()

    async def read_event(self) -> Event | None:
        """Read the next event from the attached source; ``None`` is EOF."""
        source = self._input
        if source is None:
            return None
        return await source.read()

    def refresh_size(self) -> None:
        """Re-sample the screen's size."""
        self._screen.refresh_size()

    def close(self) -> None:
        """Release the input source (best effort) and the screen; a caller that
        keeps the source never calls this."""
        source, self._input = self._input, None
        close = getattr(source, "close", None)
        if close is not None:
            close()
        self._screen.close()

    def __repr__(self) -> str:
        return (
            f"Terminal(mouse={self.options.mouse.value!r}, live={self.live}, "
            f"{self.size[0]}x{self.size[1]}, input={self._input!r})"
        )
