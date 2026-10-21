"""The decoder: a pure ``bytes -> events`` state machine.

``KeyDecoder`` turns a raw terminal byte stream into :class:`Event` values:
:class:`KeyEvent` for the keyboard, :class:`MouseEvent` for SGR-1006, X10 and
urxvt-1015 reports, :class:`PasteEvent` for bracketed paste,
:class:`ResizeEvent` for ``CSI 8;rows;cols t`` and :class:`FocusEvent` for
DECSET 1004's ``CSI I`` / ``CSI O``.  It assembles incremental UTF-8 and
escape sequences across feeds, decodes C0 controls, CSI navigation keys, the
SS3 family, the F1-F24 names, modifier parameters, the kitty keyboard
protocol (`CSI codepoint;mods u`) and xterm's modifyOtherKeys, and it is
synchronous and total: nothing raises, unknown input is dropped or degraded,
never fatal -- and platform-free: no terminal, no screen, no clock.

Names follow the frozen 1.2 event contract: printable keys are named after
themselves, space is ``space`` with ``char=" "``, ``\\r`` is ``enter`` while
``\\n`` is ``c-j``, and chords use ``c-``, ``a-``, ``s-`` in that order
(``c-s-left``).
"""

from __future__ import annotations

import codecs

from .events import (
    Event,
    FocusEvent,
    KeyEvent,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)

# ---------------------------------------------------------------------------
# KeyDecoder
# ---------------------------------------------------------------------------

#: Bracketed paste start/end markers (CSI 200~ / 201~).
_PASTE_START = "\x1b[200~"
_PASTE_END = "\x1b[201~"

#: The modifier prefix order: Ctrl, Alt, Shift, then Super.
_MODIFIER_PREFIXES = (
    ("ctrl", "c-"),
    ("alt", "a-"),
    ("shift", "s-"),
    ("super", "super-"),
)

#: CSI/SS3 letter finals and the key each names.
_FINAL_KEYS = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
    "H": "home",
    "F": "end",
    "P": "f1",
    "Q": "f2",
    "R": "f3",
    "S": "f4",
}

#: SS3 finals (``ESC O X``).  The same letters as :data:`_FINAL_KEYS`.
_SS3_KEYS = dict(_FINAL_KEYS)

#: CSI ``~`` family, keyed by the first parameter.  The F-key parameter
#: numbers follow xterm's modifyFunctionKeys table (16 and 22 are reserved).
_TILDE_KEYS = {
    1: "home",
    2: "insert",
    3: "delete",
    4: "end",
    5: "page_up",
    6: "page_down",
    7: "home",
    8: "end",
    11: "f1",
    12: "f2",
    13: "f3",
    14: "f4",
    15: "f5",
    17: "f6",
    18: "f7",
    19: "f8",
    20: "f9",
    21: "f10",
    23: "f11",
    24: "f12",
}

#: First parameter that opens/closes a bracketed paste.
_PASTE_START_CODE = 200
_PASTE_END_CODE = 201

#: The first parameter of xterm's modifyOtherKeys form.
_MODIFY_OTHER_KEYS_CODE = 27

#: Mouse button names by the report's low two bits.
_BUTTON_NAMES = {0: "left", 1: "middle", 2: "right", 3: "none"}

#: Wheel names by the report's low two bits.
_WHEEL_NAMES = {0: "wheel_up", 1: "wheel_down", 2: "wheel_left", 3: "wheel_right"}

#: The motion and wheel bits inside a mouse report's first field.
_MOTION_BIT = 0x20
_WHEEL_BIT = 0x40


def _modifiers(bits: int) -> frozenset[str]:
    """The modifier set for an SGR report field or a 1-based modifier param."""
    modifiers: set[str] = set()
    if bits & 1:
        modifiers.add("shift")
    if bits & 2:
        modifiers.add("alt")
    if bits & 4:
        modifiers.add("ctrl")
    if bits & 8:
        modifiers.add("super")
    return frozenset(modifiers)


def _mouse_modifiers(code: int) -> frozenset[str]:
    """The modifier set of an SGR/X10/urxvt button code (bits 4, 8, 16)."""
    modifiers: set[str] = set()
    if code & 4:
        modifiers.add("shift")
    if code & 8:
        modifiers.add("alt")
    if code & 16:
        modifiers.add("ctrl")
    return frozenset(modifiers)


def _modifier_bits(value: int) -> int:
    """The bit mask of a 1-based xterm/kitty modifier parameter."""
    return max(0, value - 1)


def _chord(base: str, modifiers: frozenset[str]) -> str:
    """Spell ``base`` with the chord prefixes, ``c-`` then ``a-`` then ``s-``.

    ``base`` may already carry a ``c-`` prefix when it was derived from a C0
    codepoint; an explicit ``ctrl`` modifier then stands for that same fact
    and is not written twice.
    """
    if "ctrl" in modifiers and base.startswith("c-"):
        base = base[2:]
    prefix = "".join(
        prefix for modifier, prefix in _MODIFIER_PREFIXES if modifier in modifiers
    )
    return prefix + base


def _base_from_codepoint(code: int) -> tuple[str, str] | None:
    """The ``(key, char)`` a Unicode codepoint names, or ``None`` to drop.

    C0 controls keep the historical names (``enter`` for CR, ``c-j`` for LF,
    ``tab``, ``escape``, ``backspace``); space has ``key="space"`` with
    ``char=" "``; everything printable above the C0 range is named after
    itself.  C1 controls and NUL carry no meaning and are dropped.
    """
    if code == 0x0D:
        return "enter", ""
    if code == 0x0A:
        return "c-j", ""
    if code == 0x09:
        return "tab", ""
    if code == 0x1B:
        return "escape", ""
    if code == 0x7F:
        return "backspace", ""
    if code == 0x20:
        return "space", " "
    if 0x01 <= code <= 0x1A:
        return f"c-{chr(ord('a') + code - 1)}", ""
    if code < 0 or code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
        return None  # not a Unicode scalar value
    if code < 0x20 or 0x7F <= code <= 0x9F:
        return None
    ch = chr(code)
    return ch, ch


def _char_key(ch: str) -> KeyEvent | None:
    """Map a single ground character to a key, or ``None`` to drop it."""
    base = _base_from_codepoint(ord(ch))
    if base is None:
        return None
    key, char = base
    return KeyEvent(key, char)


def _parse_int(field: str) -> int | None:
    """``field`` as an int, or ``None`` when it is not one."""
    try:
        return int(field)
    except ValueError:
        return None


def _param_modifiers(parts: list[str]) -> frozenset[str]:
    """The modifier set carried by the second CSI parameter, if any."""
    if len(parts) < 2 or not parts[1]:
        return frozenset()
    value = _parse_int(parts[1].split(":", 1)[0])
    if value is None:
        return frozenset()
    return _modifiers(_modifier_bits(value))


class KeyDecoder:
    """Turns a raw byte stream into :class:`Event` values.

    The decoder is incremental over ``feed`` calls: the stream may be split
    anywhere -- one byte per call is fine -- and escape state is carried
    across feeds rather than resolved at every boundary:

    * a ``feed`` ending inside ``ESC``, ``ESC [ ...`` or ``ESC O`` leaves the
      partial sequence pending (see :meth:`pending`); the next feed's bytes
      continue assembling it (``feed(b"\\x1b")`` then ``feed(b"[A")`` yields
      ``up``);
    * an ``ESC`` followed by another ``ESC`` resolves immediately to one
      escape key and restarts;
    * an ``ESC`` followed by any non-``[``/non-``O`` byte, and a ``CSI``
      aborted by a byte outside the parameter/final ranges, resolve as soon
      as the disambiguating byte arrives: *escape* followed by the collected
      characters re-read literally (the introducer is consumed);
    * a complete but unrecognized sequence (unknown final byte, unknown
      ``~`` parameter) is dropped;
    * a *pending* sequence is adjudicated by :meth:`settle` after a silence
      period: a bare ``ESC`` becomes the *escape* key, a pending ``CSI``
      degrades to *escape* plus its parameters re-read literally, a pending
      ``SS3`` to *escape* plus a literal ``O``;
    * paste aggregation is different: it spans any number of feeds until
      the end marker arrives, and a marker **split across feeds** is still
      recognized -- the scan holds back a trailing partial marker (at most
      ``len(_PASTE_END) - 1`` characters) instead of folding those bytes
      into the payload;
    * X10 mouse reports (``ESC [ M`` plus three bytes) are assembled across
      feeds exactly like the other sequences.

    Nothing raises: unknown input is dropped or degraded, never fatal.
    """

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._paste: list[str] | None = None  # accumulator while pasting
        self._paste_hold = ""  # a trailing partial end marker, held back
        self._esc: str | None = None  # "escape" / "csi" / "ss3" / "x10"
        self._csi_params: list[str] = []  # collected while in "csi"
        self._x10: list[str] = []  # collected bytes while in "x10"

    # -- public API ----------------------------------------------------------

    def feed(self, data: bytes) -> list[Event]:
        """Decode ``data`` (possibly a partial UTF-8 sequence) into events.

        Bytes continue any pending escape/CSI sequence; state left pending
        at the end of this feed stays pending for the next one.  The input
        must be ``bytes`` -- text, bytearray and memoryview are programming
        errors and raise ``TypeError``.
        """
        if not isinstance(data, bytes):
            raise TypeError(f"feed() takes bytes, got {type(data).__name__}")
        text = self._utf8.decode(data)
        return self._emit(text)

    def pending(self) -> bool:
        """Whether an escape/CSI/SS3/X10 sequence is still being assembled.

        A paste in progress is never pending -- its payload is simply
        text until the end marker arrives.
        """
        return self._esc is not None

    def settle(self) -> list[Event]:
        """Adjudicate a pending escape/CSI sequence after a silence period.

        A pending bare ``ESC`` becomes the *escape* key; a pending ``CSI``
        degrades to *escape* followed by its collected parameter characters
        re-read literally; a pending ``SS3`` and an incomplete X10 report
        release their introducer bytes as literal keys.  Pastes are
        untouched.
        """
        events: list[Event] = []
        if self._esc == "escape":
            events.append(KeyEvent("escape"))
            self._esc = None
        elif self._esc == "csi":
            events.extend(self._degrade_csi())
        elif self._esc == "ss3":
            events.extend((KeyEvent("escape"), KeyEvent("O", "O")))
            self._esc = None
        elif self._esc == "x10":
            events.extend(self._degrade_x10())
        return events

    def finish(self) -> list[Event]:
        """Finish the stream: settle, flush pending UTF-8, close any paste.

        A truncated UTF-8 sequence surfaces as U+FFFD; an unclosed bracketed
        paste is delivered verbatim as one final :class:`PasteEvent`, the
        held-back partial-marker tail included (it was never a marker: the
        stream ended first).
        """
        events = self.settle()
        events.extend(self._emit(self._utf8.decode(b"", final=True)))
        if self._paste is not None:
            if self._paste_hold:
                self._paste.append(self._paste_hold)
                self._paste_hold = ""
            events.append(PasteEvent("".join(self._paste)))
            self._paste = None
        return events

    # -- internals -----------------------------------------------------------

    def _emit(self, text: str) -> list[Event]:
        """Scan decoded ``text`` left to right, emitting events."""
        events: list[Event] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if self._paste is not None:
                i = self._advance_paste(text, i, n, events)
                continue
            if self._esc is not None:
                i = self._advance_escape(text, i, events)
                continue
            if ch == "\x1b":
                self._esc = "escape"  # wait for the next byte to disambiguate
                i += 1
                continue
            key = _char_key(ch)
            if key is not None:
                events.append(key)
            i += 1
        return events

    def _advance_paste(self, text: str, i: int, n: int, events: list[Event]) -> int:
        """Continue an open paste with ``text[i:]``; the index to resume at.

        The scan joins the held-back tail (``_paste_hold``, empty between
        feeds unless the previous one ended on a partial end marker) with
        this feed's bytes and searches the marker there, so a marker split
        across **any** feed boundary still closes the paste.  When no marker
        is present, everything that cannot begin one is appended to the
        payload and at most ``len(_PASTE_END) - 1`` trailing characters are
        held back -- a tail that could still complete into the marker -- and
        the whole feed counts as consumed.
        """
        hold = self._paste_hold
        buffer = hold + text[i:]
        self._paste_hold = ""
        end = buffer.find(_PASTE_END)
        if end < 0:
            keep = 0
            for size in range(1, min(len(_PASTE_END) - 1, len(buffer)) + 1):
                if buffer.endswith(_PASTE_END[:size]):
                    keep = size  # the longest tail that is a marker prefix
            self._paste_hold = buffer[len(buffer) - keep :] if keep else ""
            self._paste.append(buffer[: len(buffer) - keep])
            return n
        self._paste.append(buffer[:end])
        events.append(PasteEvent("".join(self._paste)))
        self._paste = None
        # Map the resume point back into ``text``: the marker's end sits
        # ``len(hold)`` characters into ``buffer`` earlier than it does in
        # the feed.  The hold is a proper prefix, so this always advances.
        return i + (end + len(_PASTE_END)) - len(hold)

    def _advance_escape(self, text: str, i: int, events: list[Event]) -> int:
        """Continue the pending escape/CSI/SS3/X10 sequence with ``text[i]``.

        Returns the index to continue scanning from.  Every path either
        completes the sequence, resolves it outright, or leaves it pending
        for a later feed -- resolution never happens merely because a feed
        ended.
        """
        ch = text[i]
        if self._esc == "x10":
            self._x10.append(ch)
            if len(self._x10) == 3:
                self._esc = None
                self._emit_x10(events)
            return i + 1
        if self._esc == "ss3":
            self._esc = None
            name = _SS3_KEYS.get(ch)
            if name is not None:
                events.append(KeyEvent(name))
                return i + 1
            # An unknown SS3: the escape resolves and the byte re-reads as
            # ground, with the "O" surfaced literally.
            events.extend((KeyEvent("escape"), KeyEvent("O", "O")))
            return i
        if self._esc == "escape":
            if ch == "[":
                self._esc = "csi"
                self._csi_params = []
                return i + 1
            if ch == "O":
                self._esc = "ss3"
                return i + 1
            # ESC ESC, or ESC followed by a byte that cannot extend the
            # sequence: the escape resolves now.  A restarting ESC keeps
            # the pending state; any other byte is re-read as ground.
            events.append(KeyEvent("escape"))
            if ch == "\x1b":
                return i + 1
            self._esc = None
            return i
        # CSI: parameter/intermediate bytes, then one final byte.
        code = ord(ch)
        if 0x20 <= code <= 0x3F:
            self._csi_params.append(ch)
            return i + 1
        if 0x40 <= code <= 0x7E:
            params = "".join(self._csi_params)
            self._esc = None
            self._csi_params = []
            self._emit_csi(params, ch, events)
            return i + 1
        # Aborted by an invalid byte: the sequence degrades and the byte is
        # re-read as ground (a CR becomes enter, and so on).
        events.extend(self._degrade_csi())
        return i

    def _degrade_csi(self) -> list[Event]:
        """Emit the escape part of a degraded CSI and clear the csi state.

        The collected parameter characters are re-read literally as ground
        keys, preserving the historical degrade semantics; the ``[``
        introducer stays consumed.
        """
        events: list[Event] = [KeyEvent("escape")]
        for param in self._csi_params:
            key = _char_key(param)
            if key is not None:
                events.append(key)
        self._esc = None
        self._csi_params = []
        return events

    def _degrade_x10(self) -> list[Event]:
        """Release an incomplete X10 report as literal keys."""
        events: list[Event] = [KeyEvent("escape"), KeyEvent("[", "["), KeyEvent("M", "M")]
        for ch in self._x10:
            key = _char_key(ch)
            if key is not None:
                events.append(key)
        self._x10 = []
        self._esc = None
        return events

    def _emit_csi(self, params: str, final: str, events: list[Event]) -> None:
        """Dispatch a complete CSI sequence; unknown sequences are dropped."""
        if params.startswith("<"):  # SGR mouse report (CSI < b ; x ; y M/m)
            self._emit_sgr(params, final, events)
            return
        if final == "~":
            self._emit_tilde(params, events)
            return
        if final == "u":
            self._emit_kitty(params, events)
            return
        if final == "t":
            self._emit_resize(params, events)
            return
        if final == "I":
            events.append(FocusEvent(True))
            return
        if final == "O":
            events.append(FocusEvent(False))
            return
        if final in ("M", "m"):
            if params == "":
                if final == "M":  # the X10 introducer: three raw bytes follow
                    self._esc = "x10"
                    self._x10 = []
                return
            self._emit_urxvt(params, final, events)
            return
        if final == "Z":
            parts = params.split(";") if params else []
            modifiers = _param_modifiers(parts) | {"shift"}
            events.append(KeyEvent(_chord("tab", modifiers), "", modifiers))
            return
        name = _FINAL_KEYS.get(final)
        if name is None:
            return
        parts = params.split(";") if params else []
        modifiers = _param_modifiers(parts)
        events.append(KeyEvent(_chord(name, modifiers), "", modifiers))

    def _emit_tilde(self, params: str, events: list[Event]) -> None:
        """Decode the ``CSI n ~`` family, modifyOtherKeys included."""
        parts = params.split(";")
        code = _parse_int(parts[0]) if parts and parts[0] else None
        if code is None:
            return  # e.g. "ESC [ 3;5-~": unknown, dropped
        if code == _MODIFY_OTHER_KEYS_CODE:
            self._emit_modify_other_keys(parts, events)
            return
        if code == _PASTE_START_CODE:
            self._paste = []
            return
        if code == _PASTE_END_CODE:
            self._close_paste(events)
            return
        name = _TILDE_KEYS.get(code)
        if name is None:
            return
        modifiers = _param_modifiers(parts)
        events.append(KeyEvent(_chord(name, modifiers), "", modifiers))

    def _emit_modify_other_keys(self, parts: list[str], events: list[Event]) -> None:
        """Decode xterm's ``CSI 27;modifier;codepoint ~`` form."""
        if len(parts) != 3:
            return
        value = _parse_int(parts[1])
        code = _parse_int(parts[2])
        if value is None or code is None:
            return
        modifiers = _modifiers(_modifier_bits(value))
        self._emit_codepoint(code, modifiers, "press", events)

    def _emit_kitty(self, params: str, events: list[Event]) -> None:
        """Decode kitty's ``CSI codepoint;mods[:event] u`` form."""
        parts = params.split(";")
        code = _parse_int(parts[0]) if parts and parts[0] else None
        if code is None:
            return
        modifiers = frozenset()
        kind = "press"
        if len(parts) > 1 and parts[1]:
            bits_field, _, event_field = parts[1].partition(":")
            value = _parse_int(bits_field)
            if value is None:
                return
            modifiers = _modifiers(_modifier_bits(value))
            if event_field:
                kind = {"1": "press", "2": "repeat", "3": "release"}.get(
                    event_field, "press"
                )
        self._emit_codepoint(code, modifiers, kind, events)

    def _emit_codepoint(
        self, code: int, modifiers: frozenset[str], kind: str, events: list[Event]
    ) -> None:
        """Emit the key a codepoint + modifier set names (kitty and xterm).

        A printable codepoint with no Ctrl/Alt/Super keeps its character
        identity; with a control modifier it becomes a chord and carries no
        ``char`` (the key is not text).
        """
        base = _base_from_codepoint(code)
        if base is None:
            return
        key, char = base
        if char and not (modifiers & {"ctrl", "alt", "super"}):
            events.append(KeyEvent(key, char, modifiers, kind))
            return
        events.append(KeyEvent(_chord(key, modifiers), "", modifiers, kind))

    def _emit_resize(self, params: str, events: list[Event]) -> None:
        """Decode ``CSI 8;rows;cols t`` into a :class:`ResizeEvent`."""
        parts = params.split(";")
        if len(parts) != 3 or parts[0] != "8":
            return
        rows = _parse_int(parts[1])
        cols = _parse_int(parts[2])
        if rows is None or cols is None:
            return
        events.append(ResizeEvent(cols, rows))

    def _emit_sgr(self, params: str, final: str, events: list[Event]) -> None:
        """Decode one SGR-1006 report (``CSI < b ; x ; y M/m``)."""
        if final not in ("M", "m"):
            return
        fields = params[1:].split(";")
        if len(fields) != 3:
            return
        b = _parse_int(fields[0])
        x = _parse_int(fields[1])
        y = _parse_int(fields[2])
        if b is None or x is None or y is None:
            return
        # The report's coordinates are 1-based; every cell index in the
        # toolkit is 0-based, so the decoder normalizes here once and for all.
        modifiers = _mouse_modifiers(b)
        low = b & 0x03
        if b & _WHEEL_BIT:
            events.append(
                MouseEvent(_WHEEL_NAMES[low], x - 1, y - 1, "wheel", modifiers)
            )
            return
        if b & _MOTION_BIT:
            events.append(
                MouseEvent(_BUTTON_NAMES[low], x - 1, y - 1, "motion", modifiers)
            )
            return
        kind = "release" if final == "m" else "press"
        events.append(MouseEvent(_BUTTON_NAMES[low], x - 1, y - 1, kind, modifiers))

    def _emit_x10(self, events: list[Event]) -> None:
        """Decode the three bytes of an X10 report collected in ``_x10``."""
        chars, self._x10 = self._x10, []
        values: list[int] = []
        for ch in chars:
            code = ord(ch)
            values.append(code if code <= 0xFF else 0)
        b = max(0, values[0] - 32)
        x = max(0, values[1] - 33)
        y = max(0, values[2] - 33)
        self._emit_mouse_code(b, x, y, None, events)

    def _emit_urxvt(self, params: str, final: str, events: list[Event]) -> None:
        """Decode one urxvt-1015 report (``CSI b ; x ; y M/m``)."""
        if final == "M" and params == "":
            return
        fields = params.split(";")
        if len(fields) != 3:
            return
        b = _parse_int(fields[0])
        x = _parse_int(fields[1])
        y = _parse_int(fields[2])
        if b is None or x is None or y is None:
            return
        kind = "release" if final == "m" else None
        self._emit_mouse_code(b, x - 1, y - 1, kind, events)

    def _emit_mouse_code(
        self,
        code: int,
        x: int,
        y: int,
        kind: str | None,
        events: list[Event],
    ) -> None:
        """Decode a shared X10/urxvt button code into a :class:`MouseEvent`.

        ``kind`` forces the report class for a lowercase ``m`` urxvt report
        and is ``None`` for an X10 report, whose class comes from the code
        (low bits 3 is a button-free release).
        """
        modifiers = _mouse_modifiers(code)
        low = code & 0x03
        if code & _WHEEL_BIT:
            events.append(MouseEvent(_WHEEL_NAMES[low], x, y, "wheel", modifiers))
            return
        if code & _MOTION_BIT:
            events.append(MouseEvent(_BUTTON_NAMES[low], x, y, "motion", modifiers))
            return
        if kind is None:
            kind = "release" if low == 3 else "press"
        events.append(MouseEvent(_BUTTON_NAMES[low], x, y, kind, modifiers))

    def _close_paste(self, events: list[Event]) -> None:
        """Deliver the accumulated paste, or drop a stray end marker."""
        if self._paste is None:
            return  # end marker without a start: dropped
        events.append(PasteEvent("".join(self._paste)))
        self._paste = None
