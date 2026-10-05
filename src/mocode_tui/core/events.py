"""The event model: keys, pastes, mouse reports, sources, and scripted replay.

* :class:`Key` -- one key press: a routable name plus the printable
  character, if any;
* :class:`Paste` -- a bracketed-paste payload;
* :class:`MouseEvent` -- a :class:`Key` subclass carrying a mouse report's
  button and coordinates;
* :class:`KeySource` -- the protocol anything handing out events implements;
* :class:`ScriptedKeys` -- the replay source for tests and demos.

The classes here are frozen dataclasses compared by value; nothing in this
module reads bytes, touches a terminal, or builds an event loop.  The pure
``bytes -> events`` decoder that produces these events lives in
:mod:`mocode_tui.keys.decoder`; the terminal-reading source lives in
:mod:`mocode_tui.keys.sources`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["Key", "KeySource", "MouseEvent", "Paste", "ScriptedKeys"]


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
    dropped there -- that branch is the seam future mouse kinds land in.
    ``button`` is the report's low two bits (wheel: 0 = up, 1 = down;
    buttons: 0 = left, 1 = middle, 2 = right).

    ``x``/``y`` are the **0-based** column/row of the report: every cell
    index in the toolkit is 0-based, so the decoder subtracts 1 from the
    terminal's 1-based report fields when it builds the event, and a
    component hit test consumes ``x``/``y`` directly.  Scrolling ignores
    the coordinates entirely.
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


class ScriptedKeys:
    """A key source that replays a fixed sequence of events, then EOFs.

    Handy for tests and demos: hand it ``Key``/``Paste`` events and every
    ``read()`` returns the next item in order, until the sequence is
    exhausted -- after which ``read()`` returns ``None`` forever.  A ``None``
    item inside the sequence is delivered as a one-shot end-of-stream signal,
    exactly like a real source reporting EOF before more input arrives.
    """

    def __init__(self, events: Iterable[Key | Paste | None] = ()) -> None:
        self._events = list(events)
        self._index = 0

    async def read(self) -> Key | Paste | None:
        if self._index >= len(self._events):
            return None
        event = self._events[self._index]
        self._index += 1
        return event
