"""Screen surfaces: the alternate-screen terminal and the in-memory recorder.

Everything the toolkit paints reaches a sink through the :class:`Screen`
abstract base.  :class:`TerminalScreen` owns the alternate-screen enter/leave
byte pair for a real stream; :class:`HeadlessScreen` records every written
byte in memory so tests and piped runs can inspect the exact output.  Neither
screen interprets escape sequences: all escape bytes are constructed in
:mod:`motui.terminal.ansi`, and the headless screen in particular is a
recorder, not a terminal emulator.
"""

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
    """The mouse reporting a host asks the terminal for.

    ``OFF`` leaves tracking disabled; ``BUTTON`` reports presses and the
    wheel (DECSET 1000 only, no motion); ``DRAG`` adds button-held motion
    (1002), which is what a drag gesture consumes; ``MOVE`` reports every
    motion event (1003), which is what a hover tier needs.  Buttons are
    reported for all three enabled modes -- the distinction is solely which
    motion the terminal also sends.
    """

    OFF = "off"
    BUTTON = "button"
    DRAG = "drag"
    MOVE = "move"


def mouse_switches(mode: MouseMode) -> tuple[bool, bool]:
    """Map a :class:`MouseMode` to a screen's ``(mouse, hover)`` switches.

    ``BUTTON`` and ``DRAG`` share the screen's default 1002 motion: the
    screen reports motion only while a button is held, so its button-event
    tracking is enough for both.  ``MOVE`` is the only mode that needs the
    screen's 1003 any-event tracking.
    """
    if mode is MouseMode.OFF:
        return (False, False)
    if mode is MouseMode.MOVE:
        return (True, True)
    return (True, False)


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalOptions:
    """One terminal configuration: the switches a host used to spread around.

    ``stream`` is the output sink (``sys.stdout`` when ``None``); ``input``
    is the event source a :class:`~motui.terminal.terminal.Terminal` reads
    (``None`` means no source and therefore EOF).  ``mouse`` folds the old
    ``mouse``/``hover`` pair into one mode (see :class:`MouseMode`);
    ``paste`` and ``focus_events`` are the independent reporting switches,
    and ``color_mode`` is forwarded to a constructed screen (``"auto"`` runs
    the environment probe once).  ``sync`` asks the painter for the
    synchronized-update bracket.  ``screen`` is the testing/headless escape
    hatch: a screen given here is used as-is, overriding every screen-shaped
    option above.
    """

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

    ``width``/``height`` are the current column/row counts, kept fresh by
    :meth:`refresh_size` (the painter calls it before every frame).  ``live``
    says whether written bytes reach a real terminal: on a pipe or a file the
    painter stays silent instead of scattering escapes.  ``enter``/``leave``
    bracket a full-screen session, ``write`` appends sink bytes, and ``flush``
    pushes them out.  :meth:`copy_to_clipboard` puts ``text`` on the terminal's
    clipboard (OSC 52) and reports whether it wrote; its default declines, so
    a custom screen only implements it when it owns the write.  ``color_mode``
    is the capability the painter renders rows for: a screen that declares
    none is painted truecolor.

    The class is an ABC, not a protocol: a host subclasses it and the
    inherited members answer for it (third-party subclasses that implemented
    the 1.x protocol members keep working unchanged).  The library never
    tests a screen with ``isinstance``; the type is an annotation and the
    painter calls the members directly.
    """

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
        """Put ``text`` on the terminal's clipboard; report whether it wrote.

        The default declines: a screen that cannot write OSC 52 says so, and
        a caller treats the clipboard as best-effort either way.
        """
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

    Liveness is decided once, at construction: ``stream.isatty()`` *and* a
    successful Windows VT probe (VT failure means the stream cannot render
    escapes, so it counts as non-live).  A non-live screen never receives
    escape bytes: :meth:`enter` and :meth:`leave` degrade to empty writes and
    :meth:`copy` writes nothing, so piped runs stay pure text.  The size is
    cached and only re-sampled by :meth:`refresh_size`.  ``mouse=False`` and
    ``paste=False`` drop their reporting pair from the enter/leave bytes --
    the switches are independent, for hosts that turn either mode on
    themselves.  ``hover=True`` swaps the mouse pair's motion mode: the
    1003 any-event tracking a :class:`~motui.app.pointer.Pointer` needs
    instead of the 1002 button-event tracking a drag consumes; the leave
    bytes disable every mode either way.  ``focus_events=True`` adds DECSET
    1004 to the bracket (last in, first out), so the terminal reports
    :class:`~motui.kernel.events.FocusEvent` gains and losses; off by default,
    because the reports are the host's to interpret -- the pointer tier still
    watches mouse reports only, and a host scrubs its hover and animation on
    a lost focus itself.
    ``color_mode`` is the capability the painter renders rows for:
    ``"auto"`` (the default) resolves :func:`~motui.kernel.style.detect_color_mode`
    once, at construction, and the answer stands -- ``NO_COLOR``/``TERM=dumb``
    mean no color, ``COLORTERM`` truecolor and a ``256color`` ``TERM`` pick
    their modes, anything else stays truecolor.  A concrete mode is taken as
    given; either way the mode lands in :attr:`color_mode`, which the painter
    reads.
    """

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
        """The stream's text encoding -- what a plain-text write may carry.

        A frame holds box characters a legacy codepage cannot represent, so
        the one writer that sends frames as *text* (the non-live dump) asks
        the screen what its stream can hold; ``None`` for a stream that does
        not say.
        """
        return getattr(self._stream, "encoding", None)

    def enter(self) -> None:
        """Enter the alternate screen, hide the cursor, enable tracking + paste.

        Alt screen, hidden cursor, mouse tracking, bracketed paste and --
        when the switch is on -- focus reporting, in that order, all only
        when live; a reporting pair whose switch is off is dropped.
        :meth:`leave` is the exact reverse (no-op when non-live).
        """
        tracking = enable_mouse_tracking(hover=self._hover) if self._mouse else ""
        paste = enable_bracketed_paste() if self._paste else ""
        focus = enable_focus_events() if self._focus_events else ""
        self.write(
            (enter_alt_screen() + hide_cursor() + tracking + paste + focus)
            if self._live
            else ""
        )

    def leave(self) -> None:
        """Disable paste and tracking, show the cursor, leave the alternate screen.

        The exact reverse of :meth:`enter` -- focus reporting off first, then
        paste and tracking -- and a no-op when non-live.
        """
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
        """Put ``text`` on the terminal's clipboard (OSC 52); live only, and flushed.

        Returns whether it wrote.  A non-live screen writes nothing and
        returns ``False`` (D6): a pipe or a file has no clipboard, and the
        toolkit never scatters escapes at a surface that cannot render
        them.  A live write is flushed here -- the clipboard primitive owns
        its push, so a host never follows it with ``flush()``.  Terminal
        support for application clipboard writes varies, so even a ``True``
        is best-effort -- the caller's hook is the real contract.
        """
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
    """An in-memory screen that records every byte written to it.

    ``live`` is always ``True``: the headless screen is what tests and piped
    runs paint into, and its whole job is faithful byte recording (see
    :attr:`output`).  It performs no escape interpretation.  ``width`` and
    ``height`` are adjustable so tests can simulate a resize; the fixed size
    otherwise never changes on its own.  ``mouse=False`` / ``paste=False``
    drop the matching reporting pair from the recorded bracket, exactly as
    ``TerminalScreen``'s switches do; ``hover=True`` records the 1003
    motion mode in place of the default 1002 -- the bytes are recorded
    like every other byte, so a test can assert the mode a hover host
    would send; ``focus_events=True`` records the DECSET 1004 pair the same
    way, off by default like every other screen's.  ``color_mode`` defaults
    to a definite ``"truecolor"`` -- not the environment probe a live
    terminal runs -- so a test's bytes never depend on the machine it runs
    on.
    """

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
        """Record the real alternate-screen enter bytes (live by construction).

        Alt screen, hidden cursor, mouse tracking and bracketed paste -- the
        exact bytes a live session sends, each reporting pair dropped when
        its switch is off; a ``focus_events`` screen records the DECSET 1004
        enable byte after the paste pair.
        """
        tracking = enable_mouse_tracking(hover=self._hover) if self._mouse else ""
        paste = enable_bracketed_paste() if self._paste else ""
        focus = enable_focus_events() if self._focus_events else ""
        self.write(enter_alt_screen() + hide_cursor() + tracking + paste + focus)

    def leave(self) -> None:
        """Record the real alternate-screen leave bytes.

        Focus reporting and paste off first (the reverse of the enable
        order), then mouse tracking, the cursor and the primary buffer.
        """
        focus = disable_focus_events() if self._focus_events else ""
        paste = disable_bracketed_paste() if self._paste else ""
        tracking = disable_mouse_tracking(hover=self._hover) if self._mouse else ""
        self.write(focus + paste + tracking + show_cursor() + leave_alt_screen())

    def write(self, s: str) -> None:
        self._buffer.write(s)

    def copy_to_clipboard(self, text: str) -> bool:
        """Record the OSC 52 clipboard bytes and report ``True``.

        The headless screen is live by construction, and its job is faithful
        byte recording: recording the copy is what lets a test prove it
        happened (on a live terminal nothing observable comes back).  Flush
        is a no-op -- the recording buffer is the output.
        """
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
