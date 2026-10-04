"""Screen surfaces: the alternate-screen terminal and the in-memory recorder.

Everything the toolkit paints reaches a sink through the :class:`Screen`
protocol.  :class:`TerminalScreen` owns the alternate-screen enter/leave byte
pair for a real stream; :class:`HeadlessScreen` records every written byte in
memory so tests and piped runs can inspect the exact output.  Neither screen
interprets escape sequences: all escape bytes are constructed in
:mod:`mocode_tui.ansi`, and the headless screen in particular is a recorder,
not a terminal emulator.
"""

from __future__ import annotations

import io
import sys
from typing import Protocol, runtime_checkable

from .ansi import enable_vt, enter_alt_screen, hide_cursor, leave_alt_screen, show_cursor
from .text import terminal_size

__all__ = ["HeadlessScreen", "Screen", "TerminalScreen"]


@runtime_checkable
class Screen(Protocol):
    """A writable screen surface with a known size.

    ``width``/``height`` are the current column/row counts, kept fresh by
    :meth:`refresh_size` (the painter calls it before every frame).  ``live``
    says whether written bytes reach a real terminal: on a pipe or a file the
    painter stays silent instead of scattering escapes.  ``enter``/``leave``
    bracket a full-screen session, ``write`` appends sink bytes, and ``flush``
    pushes them out.
    """

    @property
    def width(self) -> int:
        ...

    @property
    def height(self) -> int:
        ...

    @property
    def live(self) -> bool:
        ...

    def enter(self) -> None:
        ...

    def leave(self) -> None:
        ...

    def write(self, s: str) -> None:
        ...

    def flush(self) -> None:
        ...

    def refresh_size(self) -> None:
        ...


class TerminalScreen:
    """A screen backed by a real stream (``sys.stdout`` by default).

    Liveness is decided once, at construction: ``stream.isatty()`` *and* a
    successful Windows VT probe (VT failure means the stream cannot render
    escapes, so it counts as non-live).  A non-live screen never receives
    escape bytes: :meth:`enter` and :meth:`leave` degrade to empty writes, so
    piped runs stay pure text.  The size is cached and only re-sampled by
    :meth:`refresh_size`.
    """

    def __init__(self, stream: io.TextIOBase | None = None) -> None:
        self._stream = sys.stdout if stream is None else stream
        self._live = bool(self._stream.isatty()) and enable_vt()
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

    def enter(self) -> None:
        """Enter the alternate screen and hide the cursor (no-op when non-live)."""
        self.write(enter_alt_screen() + hide_cursor() if self._live else "")

    def leave(self) -> None:
        """Show the cursor and leave the alternate screen (no-op when non-live)."""
        self.write(show_cursor() + leave_alt_screen() if self._live else "")

    def write(self, s: str) -> None:
        self._stream.write(s)

    def flush(self) -> None:
        self._stream.flush()

    def refresh_size(self) -> None:
        self._width, self._height = terminal_size()

    def __repr__(self) -> str:
        return f"TerminalScreen(live={self._live}, {self._width}x{self._height})"


class HeadlessScreen:
    """An in-memory screen that records every byte written to it.

    ``live`` is always ``True``: the headless screen is what tests and piped
    runs paint into, and its whole job is faithful byte recording (see
    :attr:`output`).  It performs no escape interpretation.  ``width`` and
    ``height`` are adjustable so tests can simulate a resize; the fixed size
    otherwise never changes on its own.
    """

    def __init__(self, width: int = 80, height: int = 24) -> None:
        self._width = width
        self._height = height
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
    def output(self) -> str:
        """Every byte written so far, in order (escapes included, unparsed)."""
        return self._buffer.getvalue()

    def enter(self) -> None:
        """Record the real alternate-screen enter bytes (live by construction)."""
        self.write(enter_alt_screen() + hide_cursor())

    def leave(self) -> None:
        """Record the real alternate-screen leave bytes."""
        self.write(show_cursor() + leave_alt_screen())

    def write(self, s: str) -> None:
        self._buffer.write(s)

    def flush(self) -> None:
        """Nothing to push: the recording buffer is the output."""

    def clear(self) -> None:
        """Reset the recording buffer (``output`` becomes ``""``)."""
        self._buffer.seek(0)
        self._buffer.truncate(0)

    def refresh_size(self) -> None:
        """No-op: headless dimensions are fixed unless a test adjusts them."""

    def __repr__(self) -> str:
        return f"HeadlessScreen({self._width}x{self._height}, {len(self.output)} bytes)"
