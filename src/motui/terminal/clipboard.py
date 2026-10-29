"""Clipboard: the one ``copy(text)`` capability every layer shares.

The toolkit never writes a real clipboard itself; the host's backend
decides. Both implementations answer ``True`` as best-effort."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .screen import Screen

__all__ = ["Clipboard", "MemoryClipboard", "ScreenClipboard"]


@runtime_checkable
class Clipboard(Protocol):
    """Anything that can take text: ``copy(text) -> bool``; ``True`` means
    accepted, never guaranteed."""

    def copy(self, text: str) -> bool:
        ...


class ScreenClipboard:
    """The screen-backed clipboard: OSC 52 through the attached screen, which
    owns the write and its flush."""

    __slots__ = ("_screen",)

    def __init__(self, screen: Screen) -> None:
        self._screen = screen

    def copy(self, text: str) -> bool:
        """Put ``text`` on the screen's clipboard; report whether it wrote."""
        return self._screen.copy_to_clipboard(text)

    def __repr__(self) -> str:
        return f"ScreenClipboard({self._screen!r})"


class MemoryClipboard:
    """The in-memory clipboard: records the last text, never touches a screen."""

    __slots__ = ("text",)

    def __init__(self) -> None:
        self.text: str | None = None

    def copy(self, text: str) -> bool:
        """Record ``text`` as the clipboard's content; always ``True``."""
        self.text = text
        return True

    def __repr__(self) -> str:
        return f"MemoryClipboard({self.text!r})"
