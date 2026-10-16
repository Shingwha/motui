"""The event model: keys, pastes, mouse reports, sources, and scripted replay.

* :class:`Key` -- one key press: a routable name plus the printable
  character, if any;
* :class:`Paste` -- a bracketed-paste payload;
* :class:`MouseEvent` -- a :class:`Key` subclass carrying a mouse report's
  kind, button and coordinates;
* :class:`KeySource` -- the protocol anything handing out events implements;
* :class:`ScriptedKeys` -- the replay source for tests and demos.

The classes here are frozen dataclasses compared by value; nothing in this
module reads bytes, touches a terminal, or builds an event loop.  The pure
``bytes -> events`` decoder that produces these events lives in
:mod:`mocode_tui.keys.decoder`; the terminal-reading source lives in
:mod:`mocode_tui.keys.sources`.

The decoder routes button presses and their releases, the vertical wheel
and motion reports; a host hand-reading events sees motion and release
reports flow by, each carrying :attr:`MouseEvent.kind`.  Wheel and
button-press names are stable, so consumers that match on the name
(viewport scrolling, click dispatch) read what they always read; anything
matching *every* mouse event must tolerate the full flow.
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

    ``kind`` is the report's motion class -- ``"press"`` (a button going
    down), ``"release"`` (a button going up) or ``"motion"`` (the pointer
    moved while the report carried the SGR motion bit: a motion report's
    low bits name the held button -- 0/1/2 -- or are 3 when no button is
    held).  A button-free motion -- the wire's 35, what mode 1003 sends
    while the pointer only moves -- is normalized by the decoder to name
    ``"none"`` with ``button=0``: the event model's own button-free shape.
    Wheel reports are discrete and stay ``kind="press"``.  The decoder
    routes the vertical wheel (``"wheel_up"`` / ``"wheel_down"``), button
    presses (``"left"`` / ``"middle"`` / ``"right"``) with their releases
    and motion reports; the horizontal wheel (low bits 2/3 of a wheel
    report), unknown button codes and a press or release naming no button
    (low 3 is malformed there) stay dropped.  ``button`` is the report's
    low two bits (wheel: 0 = up, 1 = down; buttons: 0 = left, 1 = middle,
    2 = right).

    ``x``/``y`` are the **0-based** column/row of the report: every cell
    index in the toolkit is 0-based, so the decoder subtracts 1 from the
    terminal's 1-based report fields when it builds the event, and a
    component hit test consumes ``x``/``y`` directly.  Scrolling ignores
    the coordinates entirely.
    """

    button: int = 0
    x: int = 0
    y: int = 0
    #: ``"press"`` | ``"release"`` | ``"motion"`` -- see the class docstring.
    kind: str = "press"


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
