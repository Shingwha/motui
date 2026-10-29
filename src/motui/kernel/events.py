"""The event model: keys, mouse reports, pastes, resizes, focus and sources.

All events are frozen value dataclasses. A mouse report is never a
:class:`KeyEvent`, so ``isinstance(event, KeyEvent)`` matches the keyboard
only. Nothing here reads bytes, touches a terminal, or carries a timestamp."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "Event",
    "EventSource",
    "FocusEvent",
    "KeyEvent",
    "MouseEvent",
    "PasteEvent",
    "ResizeEvent",
]


class Event:
    """Base class for every input event."""


@dataclass(frozen=True, slots=True)
class KeyEvent(Event):
    """One key press: the routing ``key``, the printable ``char``, structured
    ``modifiers``, and ``press``/``repeat``/``release`` kind."""

    key: str
    char: str = ""
    modifiers: frozenset[str] = frozenset()
    kind: str = "press"


@dataclass(frozen=True, slots=True)
class MouseEvent(Event):
    """A mouse report; ``x``/``y`` are 0-based columns/rows -- the decoder
    subtracts one from the terminal's report."""

    button: str = "none"
    x: int = 0
    y: int = 0
    kind: str = "press"
    modifiers: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class PasteEvent(Event):
    """A bracketed-paste payload: literal text, never re-interpreted."""

    text: str


@dataclass(frozen=True, slots=True)
class ResizeEvent(Event):
    """The terminal reported a new size: ``width`` columns, ``height`` rows."""

    width: int
    height: int


@dataclass(frozen=True, slots=True)
class FocusEvent(Event):
    """The terminal window gained (``True``) or lost (``False``) focus."""

    focused: bool


@runtime_checkable
class EventSource(Protocol):
    """Anything that hands out events; ``None`` means end of stream."""

    async def read(self) -> Event | None:
        ...
