"""The terminal layer: screens, bytes, input decoding and capability probes.

Everything the toolkit writes to or reads from a terminal lives here.  The
kernel above it holds pure values only; this package is the one place that
touches a stream, the process environment, the console or the clock.

``ansi`` is deliberately **not** re-exported: escape construction is private
to this layer and to tests that assert on exact bytes.  A host paints through
:class:`Painter` and reads events through :class:`KeyDecoder` or a source.
"""

from __future__ import annotations

from .capability import auto_theme, detect_color_mode, terminal_size
from .clipboard import Clipboard, MemoryClipboard, ScreenClipboard
from .decoder import KeyDecoder
from .keys import RawTerminalKeys
from .paint import Painter
from .screen import HeadlessScreen, Screen, TerminalScreen

__all__ = [
    "Clipboard",
    "HeadlessScreen",
    "KeyDecoder",
    "MemoryClipboard",
    "Painter",
    "RawTerminalKeys",
    "Screen",
    "ScreenClipboard",
    "TerminalScreen",
    "auto_theme",
    "detect_color_mode",
    "terminal_size",
]
