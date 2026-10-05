"""The event model: keys, pastes, mouse reports, and the source protocol.

* :class:`Key` -- one key press: a routable name plus the printable
  character, if any;
* :class:`Paste` -- a bracketed-paste payload;
* :class:`MouseEvent` -- a :class:`Key` subclass carrying a mouse report's
  button and coordinates;
* :class:`KeySource` -- the protocol anything handing out events implements.

The classes here are frozen dataclasses compared by value; nothing in this
module reads bytes, touches a terminal, or builds an event loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Key:
    """One key press.

    ``name`` is the routing identity: a printable character's own text
    (``"a"``, ``"中"``), a control name (``"enter"``, ``"tab"``,
    ``"backspace"``, ``"escape"``, ``"space"``, ``"up"``, ``"page_up"``,
    ``"c-c"``, ...).  ``char`` is the printable character the key produced,
    empty for keys that produce no character.
    """

    name: str
    char: str = ""


@dataclass(frozen=True)
class MouseEvent(Key):
    """A mouse report: a routable :class:`Key` name plus the report's data.

    The decoder routes the vertical wheel (``"wheel_up"`` /
    ``"wheel_down"``) and button presses (``"left"`` / ``"middle"`` /
    ``"right"``); every other report a terminal can send (button
    releases, horizontal wheel, motion while a button is held) is still
    dropped here -- that branch is the seam future mouse kinds land in.
    ``button`` is the report's low two bits (wheel: 0 = up, 1 = down;
    buttons: 0 = left, 1 = middle, 2 = right); ``x``/``y`` are the
    1-based column/row from the report, the coordinates a component hit
    test consumes (subtract 1 to index ``Painter.rows()``) and that
    scrolling ignores.
    """

    button: int = 0
    x: int = 0
    y: int = 0


@dataclass(frozen=True)
class Paste:
    """A bracketed-paste payload: literal text, never re-interpreted."""

    text: str


@runtime_checkable
class KeySource(Protocol):
    """Anything that can hand out key events: ``async read() -> event | None``.

    ``None`` means end of stream (EOF): a source that is exhausted, a closed
    terminal, or a source that was never started.
    """

    async def read(self) -> "Key | Paste | None":
        ...
