"""The terminal layer: screens, bytes, input decoding and capability probes.

The one place that touches a stream, the process environment, the
console or the clock."""

from __future__ import annotations

from .capability import auto_theme, detect_color_mode, terminal_size
from .clipboard import Clipboard, MemoryClipboard, ScreenClipboard
from .decoder import KeyDecoder
from .keys import RawTerminalKeys
from .paint import Painter
from .render import styled_line
from .screen import HeadlessScreen, MouseMode, Screen, TerminalOptions, TerminalScreen
from .terminal import Capability, Terminal

__all__ = [
    "Capability",
    "Clipboard",
    "HeadlessScreen",
    "KeyDecoder",
    "MemoryClipboard",
    "MouseMode",
    "Painter",
    "RawTerminalKeys",
    "Screen",
    "ScreenClipboard",
    "Terminal",
    "TerminalOptions",
    "TerminalScreen",
    "auto_theme",
    "detect_color_mode",
    "styled_line",
    "terminal_size",
]
