"""Clipboard: the one ``copy(text)`` capability every layer shares.

The toolkit never writes to a real clipboard by itself: a component with a
copy gesture (a text selection, a table's row action) asks a
:class:`Clipboard` and lets the host decide where the text lands.  The
protocol is deliberately one method -- ``copy(text) -> bool`` -- so a
custom backend (a desktop clipboard, an editor integration, a test double)
needs nothing from the kernel.

Two implementations ship:

* :class:`ScreenClipboard` forwards to the screen's OSC 52 door
  (:meth:`~motui.kernel.screen.Screen.copy_to_clipboard`), which owns the
  write and its flush;
* :class:`MemoryClipboard` records the last text in memory -- the headless
  backend, and the one a test reads back.

Both answer ``True`` when the backend took the text and ``False`` when it
could not (a non-live terminal screen); the caller's hook is the real
contract, so a ``True`` is best-effort, never a guarantee.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .screen import Screen

__all__ = ["Clipboard", "MemoryClipboard", "ScreenClipboard"]


@runtime_checkable
class Clipboard(Protocol):
    """Anything that can take text: ``copy(text) -> bool``.

    The single capability a copy gesture needs.  ``True`` means the
    backend accepted the text (best-effort -- a terminal clipboard write
    cannot be confirmed); ``False`` means it declined, and the caller may
    fall back to its own mechanism.
    """

    def copy(self, text: str) -> bool:
        ...


class ScreenClipboard:
    """The screen-backed clipboard: OSC 52 through the attached screen.

    The screen owns the terminal write and its flush
    (:meth:`~motui.kernel.screen.Screen.copy_to_clipboard`), so this
    adapter adds no buffering and no second flush.
    """

    __slots__ = ("_screen",)

    def __init__(self, screen: Screen) -> None:
        self._screen = screen

    def copy(self, text: str) -> bool:
        """Put ``text`` on the screen's clipboard; report whether it wrote."""
        return self._screen.copy_to_clipboard(text)

    def __repr__(self) -> str:
        return f"ScreenClipboard({self._screen!r})"


class MemoryClipboard:
    """The in-memory clipboard: records the last text, never touches a screen.

    The headless backend and the test double: :attr:`text` is the last
    copied value (``None`` before the first copy), readable back exactly
    as it was handed in.
    """

    __slots__ = ("text",)

    def __init__(self) -> None:
        self.text: str | None = None

    def copy(self, text: str) -> bool:
        """Record ``text`` as the clipboard's content; always ``True``."""
        self.text = text
        return True

    def __repr__(self) -> str:
        return f"MemoryClipboard({self.text!r})"
