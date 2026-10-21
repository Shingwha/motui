"""The event model: keys, mouse reports, pastes, resizes, focus, sources.

Every input is an :class:`Event`:

* :class:`KeyEvent` -- one key press: a routable ``key`` name, the printable
  ``char`` if any, the structured ``modifiers`` and the press kind;
* :class:`MouseEvent` -- a mouse report: the ``button`` name, the 0-based
  coordinates, the report ``kind`` and the modifier set;
* :class:`PasteEvent` -- a bracketed-paste payload, literal text;
* :class:`ResizeEvent` -- the terminal's new ``width`` and ``height``;
* :class:`FocusEvent` -- the window gained or lost focus.

A mouse report is never a key: :class:`MouseEvent`, :class:`PasteEvent`,
:class:`ResizeEvent` and :class:`FocusEvent` are siblings of
:class:`KeyEvent`, not subclasses, so ``isinstance(event, KeyEvent)`` matches
the keyboard only.

The classes here are frozen dataclasses compared by value; nothing in this
module reads bytes, touches a terminal, or builds an event loop.  The pure
``bytes -> events`` decoder that produces these events lives in
:mod:`motui.core.decoder`; the terminal-reading source lives in
:mod:`motui.core.sources`.  Events carry no timestamp: time enters through
the driver's ``clock()`` seam.
"""

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
    """One key press.

    ``key`` is the routing identity: a printable character's own text
    (``"a"``, ``"中"``), ``"space"`` for the space bar, a control name
    (``"enter"``, ``"tab"``, ``"backspace"``, ``"escape"``, ``"up"``,
    ``"page_up"``, ...), or a chord (``"c-c"``, ``"c-s-left"``).  ``char``
    is the printable character the key produced, empty for keys that produce
    no character.  ``modifiers`` is the structured form of the same fact --
    ``"ctrl"``, ``"alt"``, ``"shift"``, ``"super"`` -- filled only when an
    escape sequence carries the modifier explicitly.  ``kind`` is
    ``"press"``, ``"repeat"`` or ``"release"``.
    """

    key: str
    char: str = ""
    modifiers: frozenset[str] = frozenset()
    kind: str = "press"


@dataclass(frozen=True, slots=True)
class MouseEvent(Event):
    """A mouse report.

    ``button`` names the report's button -- ``"left"``, ``"middle"``,
    ``"right"``, ``"none"``, or one of the four wheel directions
    (``"wheel_up"``, ``"wheel_down"``, ``"wheel_left"``, ``"wheel_right"``).
    ``x``/``y`` are the **0-based** column/row of the report: every cell
    index in the toolkit is 0-based, so the decoder subtracts 1 from the
    terminal's 1-based report fields when it builds the event, and a
    component hit test consumes ``x``/``y`` directly.  Scrolling ignores
    the coordinates entirely.

    ``kind`` is ``"press"``, ``"release"``, ``"motion"`` (the pointer moved;
    the button names the held one, or ``"none"``) or ``"wheel"`` (a discrete
    wheel notch).  ``modifiers`` carries the report's ``"shift"``,
    ``"alt"`` and ``"ctrl"`` bits.
    """

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
    """Anything that can hand out events: ``async read() -> Event | None``.

    ``None`` means end of stream (EOF): a source that is exhausted, a closed
    terminal, or a source that was never started.
    """

    async def read(self) -> Event | None:
        ...
