"""Keyboard events: the event model, the byte decoder, and the key sources.

Three layers live here:

* the **event model** -- :class:`Key` (a routable name plus the printable
  character, if any) and :class:`Paste` (a bracketed-paste payload);
* the **decoder** -- :class:`KeyDecoder`, a pure ``bytes -> events`` state
  machine that turns a raw terminal byte stream into events (incremental
  UTF-8, control names, CSI navigation keys, bracketed paste);
* the **sources** -- :class:`ScriptedKeys` for tests and :class:`RawTerminalKeys`
  for a real terminal (POSIX ``termios`` raw mode or the Windows console
  record API, with a cooked-line fallback).

Nothing in this module builds an event loop, touches a screen, or writes to a
sink: decoding is synchronous and total, and sources only ever hand events to
their caller.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["Key", "KeyDecoder", "KeySource", "Paste"]


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


# ---------------------------------------------------------------------------
# KeyDecoder
# ---------------------------------------------------------------------------

#: Bracketed paste start/end markers (CSI 200~ / 201~).
_PASTE_START = "\x1b[200~"
_PASTE_END = "\x1b[201~"

#: CSI final bytes that map to navigation keys (parameters, e.g. the modifier
#: fields of ``ESC [ 1;5 A``, are accepted and ignored -- the event model has
#: no modifiers, and the base key is the useful information).
_FINAL_KEYS = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
}

#: CSI ``~`` family, keyed by the first parameter.
_TILDE_KEYS = {
    1: "home",
    7: "home",
    3: "delete",
    4: "end",
    8: "end",
    5: "page_up",
    6: "page_down",
}

#: First parameter that opens/closes a bracketed paste.
_PASTE_START_CODE = 200
_PASTE_END_CODE = 201


def _char_key(ch: str) -> Key | None:
    """Map a single decoded character to a key, or ``None`` to drop it.

    C0/C1 controls that carry no meaning in the event model (NUL, the four
    C1 separators, ...) are dropped: a lost key beats a crash.  Everything
    else -- ASCII printables and any non-ASCII code point, wide characters
    included -- is a key named after itself.
    """
    code = ord(ch)
    if ch in ("\r", "\n"):
        return Key("enter")
    if ch == "\t":
        return Key("tab")
    if code == 0x7F:
        return Key("backspace")
    if 0x01 <= code <= 0x1A:  # Ctrl-A .. Ctrl-Z
        return Key(f"c-{chr(ord('a') + code - 1)}")
    if code == 0x20:
        return Key("space", " ")
    if code < 0x20 or 0x7F <= code <= 0x9F:
        return None
    return Key(ch, ch)


class KeyDecoder:
    """Turns a raw byte stream into :class:`Key` / :class:`Paste` events.

    The decoder is incremental over ``feed`` calls for UTF-8 only: a complete
    escape sequence is expected to arrive within a single ``feed`` (the
    documented pipe-byte assumption), and escape state is resolved at every
    feed boundary:

    * a bare ``ESC`` left at the end of a feed is an isolated *escape* key;
    * a leftover incomplete ``CSI`` degrades to *escape* followed by its
      parameter characters re-read literally;
    * an ``ESC`` followed by an unknown byte degrades to *escape* followed by
      that byte re-read literally;
    * a complete but unrecognized sequence (unknown final byte, unknown
      ``~`` parameter) is dropped.

    Nothing raises: unknown input is dropped or degraded, never fatal.
    """

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._paste: list[str] | None = None  # accumulator while pasting

    # -- public API ----------------------------------------------------------

    def feed(self, data: bytes) -> list[Key | Paste]:
        """Decode ``data`` (possibly a partial UTF-8 sequence) into events."""
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"feed() takes bytes, got {type(data).__name__}")
        text = self._utf8.decode(bytes(data))
        return self._emit(text)

    def flush(self) -> list[Key | Paste]:
        """Finish the stream: flush pending UTF-8 and any open paste.

        A truncated UTF-8 sequence surfaces as U+FFFD; an unclosed bracketed
        paste is delivered verbatim as one final :class:`Paste`.
        """
        events = self._emit(self._utf8.decode(b"", final=True))
        if self._paste is not None:
            events.append(Paste("".join(self._paste)))
            self._paste = None
        return events

    # -- internals -----------------------------------------------------------

    def _emit(self, text: str) -> list[Key | Paste]:
        """Scan decoded ``text`` left to right, emitting events."""
        events: list[Key | Paste] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if self._paste is not None:
                end = text.find(_PASTE_END, i)
                if end < 0:
                    self._paste.append(text[i:])
                    break  # wait for the end marker in a later feed
                self._paste.append(text[i:end])
                events.append(Paste("".join(self._paste)))
                self._paste = None
                i = end + len(_PASTE_END)
                continue
            if ch == "\x1b":
                i = self._emit_escape(text, i, events)
                continue
            key = _char_key(ch)
            if key is not None:
                events.append(key)
            i += 1
        return events

    def _emit_escape(self, text: str, i: int, events: list[Key | Paste]) -> int:
        """Handle the escape sequence starting at ``text[i] == ESC``.

        Returns the index to continue scanning from.  Escape resolution is
        total: every path emits at least the isolated-escape fallback and
        never leaves partial state behind.
        """
        n = len(text)
        if i + 1 >= n:
            events.append(Key("escape"))  # lone ESC at the end of the feed
            return i + 1
        nxt = text[i + 1]
        if nxt == "\x1b":
            events.append(Key("escape"))  # ESC ESC: one escape, restart
            return i + 1
        if nxt != "[":
            events.append(Key("escape"))  # unknown 2-byte escape: literal
            return i + 1
        # CSI: parameter/intermediate bytes, then one final byte.
        j = i + 2
        while j < n and 0x20 <= ord(text[j]) <= 0x3F:
            j += 1
        if j < n and 0x40 <= ord(text[j]) <= 0x7E:
            self._emit_csi(text[i + 2 : j], text[j], events)
            return j + 1
        # Incomplete or malformed CSI: escape, then the parameter characters
        # re-read literally (the "[" introducer is consumed).
        events.append(Key("escape"))
        return i + 2

    def _emit_csi(self, params: str, final: str, events: list[Key | Paste]) -> None:
        """Dispatch a complete CSI sequence; unknown sequences are dropped."""
        if final == "~":
            first = params.split(";", 1)[0]
            try:
                code = int(first) if first else 0
            except ValueError:
                return  # e.g. "ESC [ 3;5-~": unknown, dropped
            if code == _PASTE_START_CODE:
                self._paste = []
                return
            if code == _PASTE_END_CODE:
                self._close_paste(events)
                return
            name = _TILDE_KEYS.get(code)
            if name is not None:
                events.append(Key(name))
            return
        name = _FINAL_KEYS.get(final)
        if name is not None:
            events.append(Key(name))

    def _close_paste(self, events: list[Key | Paste]) -> None:
        """Deliver the accumulated paste, or drop a stray end marker."""
        if self._paste is None:
            return  # end marker without a start: dropped
        events.append(Paste("".join(self._paste)))
        self._paste = None
