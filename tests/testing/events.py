"""Event shorthands: the one spelling of every input a test injects.

Each helper builds the real event dataclass -- no test-local event classes,
no monkeypatched constructors.
"""

from __future__ import annotations

from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent, ResizeEvent

_MODIFIERS = frozenset()


def key(name: str, char: str = "") -> KeyEvent:
    """One key press: its routable ``name`` plus the printable ``char``."""
    return KeyEvent(name, char)


def press(
    x: int, y: int, button: str = "left", modifiers: frozenset[str] = _MODIFIERS
) -> MouseEvent:
    """A button press report at the 0-based cell."""
    return MouseEvent(button, x=x, y=y, kind="press", modifiers=modifiers)


def release(
    x: int, y: int, button: str = "left", modifiers: frozenset[str] = _MODIFIERS
) -> MouseEvent:
    """A button release report at the 0-based cell."""
    return MouseEvent(button, x=x, y=y, kind="release", modifiers=modifiers)


def motion(
    x: int, y: int, button: str = "none", modifiers: frozenset[str] = _MODIFIERS
) -> MouseEvent:
    """A motion report at the 0-based cell; ``none`` is a bare hover."""
    return MouseEvent(button, x=x, y=y, kind="motion", modifiers=modifiers)


def wheel(
    x: int, y: int, direction: str = "down", modifiers: frozenset[str] = _MODIFIERS
) -> MouseEvent:
    """A wheel notch: ``direction`` is ``up``, ``down``, ``left`` or ``right``."""
    return MouseEvent(
        f"wheel_{direction}", x=x, y=y, kind="wheel", modifiers=modifiers
    )


def paste(text: str) -> PasteEvent:
    """A bracketed-paste payload."""
    return PasteEvent(text)


def resize(width: int, height: int) -> ResizeEvent:
    """A terminal resize report."""
    return ResizeEvent(width, height)
