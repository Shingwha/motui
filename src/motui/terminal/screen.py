"""Screen surfaces: the alternate-screen terminal and the in-memory recorder.

Neither interprets escape sequences; all escape bytes come from
:mod:`motui.terminal.ansi`."""

from __future__ import annotations

import io
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Literal, TextIO

from ..kernel.events import EventSource
from ..kernel.style import ColorMode
from .ansi import (
    copy_clipboard,
    disable_bracketed_paste,
    disable_focus_events,
    disable_mouse_tracking,
    enable_bracketed_paste,
    enable_focus_events,
    enable_mouse_tracking,
    enable_vt,
    enter_alt_screen,
    hide_cursor,
    leave_alt_screen,
    show_cursor,
)
from .capability import detect_color_mode, terminal_size

__all__ = [
    "HeadlessScreen",
    "MouseMode",
    "Screen",
    "TerminalOptions",
    "TerminalScreen",
    "mouse_switches",
]


class MouseMode(Enum):
    """The mouse reporting a host asks for: OFF, BUTTON, DRAG (1002) or MOVE
    (1003)."""

    OFF = "off"
    BUTTON = "button"
    DRAG = "drag"
    MOVE = "move"


def mouse_switches(mode: MouseMode) -> tuple[bool, bool]:
    """Map a :class:`MouseMode` to a screen's ``(mouse, hover)`` switches; only
    MOVE needs 1003."""
    if mode is MouseMode.OFF:
        return (False, False)
    if mode is MouseMode.MOVE:
        return (True, True)
    return (True, False)


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalOptions:
    """One terminal configuration: stream, input, mouse mode, paste/focus
    switches, color mode and sync; ``screen`` overrides the rest."""

    stream: TextIO | None = None
    input: EventSource | None = None
    mouse: MouseMode = MouseMode.MOVE
    paste: bool = True
    focus_events: bool = False
    color_mode: ColorMode | Literal["auto"] = "auto"
    sync: bool = True
    screen: Screen | None = None


class Screen(ABC):
    """A writable screen surface with a known size.

    ``live`` says whether bytes reach a real terminal; the painter stays
    silent on a non-live screen. An ABC, not a protocol."""

    #: The color capability the painter renders this screen's rows for.
    color_mode: ColorMode

    @property
    @abstractmethod
    def width(self) -> int:
        """The current column count."""

    @property
    @abstractmethod
    def height(self) -> int:
        """The current row count."""

    @property
    @abstractmethod
    def live(self) -> bool:
        """Whether written bytes reach a real terminal."""

    @property
    @abstractmethod
    def size(self) -> tuple[int, int]:
        """The current ``(width, height)`` in cells."""

    @property
    @abstractmethod
    def encoding(self) -> str | None:
        """The stream's text encoding, or ``None`` when it does not say."""

    @abstractmethod
    def enter(self) -> None:
        """Enter the full-screen session."""

    @abstractmethod
    def leave(self) -> None:
        """Leave the full-screen session."""

    @abstractmethod
    def write(self, s: str) -> None:
        """Append ``s`` to the sink."""

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the terminal's clipboard; the default declines, so a
        custom screen implements it only when it owns the write."""
        return False

    @abstractmethod
    def flush(self) -> None:
        """Push accumulated bytes out."""

    @abstractmethod
    def refresh_size(self) -> None:
        """Re-sample the terminal size."""

    @abstractmethod
    def close(self) -> None:
        """Release whatever the screen owns (never the caller's stream)."""


class TerminalScreen(Screen):
    """A screen backed by a real stream (``sys.stdout`` by default).

    Liveness is decided once (isatty and the Windows VT probe), and a
    non-live screen never receives escape bytes. The size is cached until
    :meth:`refresh_size`."""

    def __init__(
        self,
        stream: io.TextIOBase | None = None,
        *,
        mouse: bool = True,
        paste: bool = True,
        hover: bool = False,
        focus_events: bool = False,
        color_mode: ColorMode | Literal['auto'] = "auto",
    ) -> None:
        self._stream = sys.stdout if stream is None else stream
        self._live = bool(self._stream.isatty()) and enable_vt()
        self._mouse = mouse
        self._paste = paste
        self._hover = hover
        self._focus_events = focus_events
        #: The color capability the painter renders this screen's rows for.
        self.color_mode: ColorMode = (
            detect_color_mode() if color_mode == "auto" else color_mode
        )
        self._width, self._height = terminal_size()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def live(self) -> bool:
        return self._live

    @property
    def size(self) -> tuple[int, int]:
        """The current ``(width, height)`` in cells."""
        return self._width, self._height

    @property
    def encoding(self) -> str | None:
        """The stream's text encoding, or ``None``; the non-live dump asks before
        sending frames as text."""
        return getattr(self._stream, "encoding", None)

    def enter(self) -> None:
        """Enter the alternate screen, hide the cursor, enable tracking, paste and
        focus reporting (live only, in that order)."""
        tracking = enable_mouse_tracking(hover=self._hover) if self._mouse else ""
        paste = enable_bracketed_paste() if self._paste else ""
        focus = enable_focus_events() if self._focus_events else ""
        self.write(
            (enter_alt_screen() + hide_cursor() + tracking + paste + focus)
            if self._live
            else ""
        )

    def leave(self) -> None:
        """The exact reverse of :meth:`enter`; a no-op when non-live."""
        focus = disable_focus_events() if self._focus_events else ""
        paste = disable_bracketed_paste() if self._paste else ""
        tracking = disable_mouse_tracking(hover=self._hover) if self._mouse else ""
        self.write(
            (focus + paste + tracking + show_cursor() + leave_alt_screen())
            if self._live
            else ""
        )

    def write(self, s: str) -> None:
        self._stream.write(s)

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the clipboard (OSC 52) and flush; live only, and a
        ``True`` is best-effort."""
        if not self._live:
            return False
        self._stream.write(copy_clipboard(text))
        self._stream.flush()
        return True

    def flush(self) -> None:
        self._stream.flush()

    def refresh_size(self) -> None:
        self._width, self._height = terminal_size()

    def close(self) -> None:
        """Flush pending bytes; the stream itself belongs to its owner."""
        self._stream.flush()

    def __repr__(self) -> str:
        return f"TerminalScreen(live={self._live}, {self._width}x{self._height})"


class HeadlessScreen(Screen):
    """An in-memory screen recording every byte written; ``live`` is always
    true and no escape is interpreted. Dimensions are adjustable for resize
    tests."""

    def __init__(
        self,
        width: int = 80,
        height: int = 24,
        *,
        mouse: bool = True,
        paste: bool = True,
        hover: bool = False,
        focus_events: bool = False,
        color_mode: ColorMode = "truecolor",
    ) -> None:
        self._width = width
        self._height = height
        self._mouse = mouse
        self._paste = paste
        self._hover = hover
        self._focus_events = focus_events
        #: The color capability the painter renders this screen's rows for.
        self.color_mode: ColorMode = color_mode
        self._buffer = io.StringIO()

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        self._width = value

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        self._height = value

    @property
    def live(self) -> bool:
        return True

    @property
    def size(self) -> tuple[int, int]:
        """The current ``(width, height)`` in cells."""
        return self._width, self._height

    @property
    def encoding(self) -> str:
        """The recorder's bytes are text: UTF-8 is the honest declaration."""
        return "utf-8"

    @property
    def output(self) -> str:
        """Every byte written so far, in order (escapes included, unparsed)."""
        return self._buffer.getvalue()

    def enter(self) -> None:
        """Record the real alternate-screen enter bytes, the exact ones a live
        session sends."""
        tracking = enable_mouse_tracking(hover=self._hover) if self._mouse else ""
        paste = enable_bracketed_paste() if self._paste else ""
        focus = enable_focus_events() if self._focus_events else ""
        self.write(enter_alt_screen() + hide_cursor() + tracking + paste + focus)

    def leave(self) -> None:
        """Record the real alternate-screen leave bytes, the reverse of the enable
        order."""
        focus = disable_focus_events() if self._focus_events else ""
        paste = disable_bracketed_paste() if self._paste else ""
        tracking = disable_mouse_tracking(hover=self._hover) if self._mouse else ""
        self.write(focus + paste + tracking + show_cursor() + leave_alt_screen())

    def write(self, s: str) -> None:
        self._buffer.write(s)

    def copy_to_clipboard(self, text: str) -> bool:
        """Record the OSC 52 bytes and report ``True``, so a test can prove the
        copy happened."""
        self._buffer.write(copy_clipboard(text))
        return True

    def flush(self) -> None:
        """Nothing to push: the recording buffer is the output."""

    def refresh_size(self) -> None:
        """No-op: headless dimensions are fixed unless a test adjusts them."""

    def close(self) -> None:
        """Nothing to release: the recording buffer needs no closing."""

    def __repr__(self) -> str:
        return f"HeadlessScreen({self._width}x{self._height}, {len(self.output)} bytes)"
