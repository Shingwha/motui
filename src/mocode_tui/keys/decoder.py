"""The decoder: a pure ``bytes -> events`` state machine.

``KeyDecoder`` turns a raw terminal byte stream into :class:`Key` /
:class:`Paste` events: incremental UTF-8 and escape sequences assembled
across feeds, control names, CSI navigation keys, bracketed paste and SGR
mouse reports.  It is synchronous and total -- nothing raises, unknown input
is dropped or degraded, never fatal -- and platform-free: no terminal, no
screen, no clock.
"""

from __future__ import annotations

import codecs

from ..core.events import Key, MouseEvent, Paste

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

#: SGR mouse buttons: the report's low two bits for the three buttons a
#: report can name.  The wheel uses the same low bits (0 = up, 1 = down).
_BUTTON_NAMES = {0: "left", 1: "middle", 2: "right"}

#: SGR-1006 report classes keyed by the report's final byte.  Each entry is
#: a ``(kind, motion)`` pair: the event kind the report decodes to, and
#: whether the motion bit (``b & 0x20``) re-routes it to a motion report.
#: Uppercase ``M`` is a button press -- or motion when the motion bit rides
#: along, which is what mode 1002 sends while the pointer moves (the low
#: bits name the held button, 0 with none held); lowercase ``m`` is a
#: button release.  Wheel reports are routed before this table and stay
#: discrete presses, so they never consult the class kind.
_REPORT_CLASSES = {"M": ("press", True), "m": ("release", False)}

#: The motion and wheel bits inside an SGR report's first parameter.
_MOTION_BIT = 0x20
_WHEEL_BIT = 0x40


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

    The decoder is incremental over ``feed`` calls: the stream may be split
    anywhere -- one byte per call is fine -- and escape state is carried
    across feeds rather than resolved at every boundary:

    * a ``feed`` ending inside ``ESC`` or ``ESC [ ...`` leaves the partial
      sequence pending (see :meth:`pending`); the next feed's bytes continue
      assembling it (``feed(b"\\x1b")`` then ``feed(b"[A")`` yields ``up``);
    * an ``ESC`` followed by another ``ESC`` resolves immediately to one
      escape key and restarts;
    * an ``ESC`` followed by any non-``[`` byte, and a ``CSI`` aborted by a
      byte outside the parameter/final ranges, resolve as soon as the
      disambiguating byte arrives: *escape* followed by the collected
      characters re-read literally (the ``[`` introducer is consumed);
    * a complete but unrecognized sequence (unknown final byte, unknown
      ``~`` parameter) is dropped;
    * a *pending* sequence is adjudicated by :meth:`settle` after a silence
      period: a bare ``ESC`` becomes the *escape* key, a pending ``CSI``
      degrades to *escape* plus its parameters re-read literally.  The
      caller owns that deadline (see ``RawTerminalKeys``);
    * paste aggregation is different: it spans any number of feeds until
      the end marker arrives.

    Nothing raises: unknown input is dropped or degraded, never fatal.
    """

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._paste: list[str] | None = None  # accumulator while pasting
        self._esc: str | None = None  # pending "escape" / "csi" state
        self._csi_params: list[str] = []  # collected while in "csi"

    # -- public API ----------------------------------------------------------

    def feed(self, data: bytes) -> list[Key | Paste]:
        """Decode ``data`` (possibly a partial UTF-8 sequence) into events.

        Bytes continue any pending escape/CSI sequence; state left pending
        at the end of this feed stays pending for the next one.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(f"feed() takes bytes, got {type(data).__name__}")
        text = self._utf8.decode(bytes(data))
        return self._emit(text)

    def pending(self) -> bool:
        """Whether an escape/CSI sequence is still being assembled.

        A paste in progress is never pending -- its payload is simply
        text until the end marker arrives.
        """
        return self._esc is not None

    def settle(self) -> list[Key | Paste]:
        """Adjudicate a pending escape/CSI sequence after a silence period.

        A pending bare ``ESC`` becomes the *escape* key; a pending ``CSI``
        degrades to *escape* followed by its collected parameter
        characters re-read literally.  Pastes are untouched.
        """
        events: list[Key | Paste] = []
        if self._esc == "escape":
            events.append(Key("escape"))
            self._esc = None
        elif self._esc == "csi":
            events.extend(self._degrade_csi())
        return events

    def finish(self) -> list[Key | Paste]:
        """Finish the stream: settle, flush pending UTF-8, close any paste.

        A truncated UTF-8 sequence surfaces as U+FFFD; an unclosed bracketed
        paste is delivered verbatim as one final :class:`Paste`.
        """
        events = self.settle()
        events.extend(self._emit(self._utf8.decode(b"", final=True)))
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

    def _advance_escape(self, text: str, i: int, events: list[Key | Paste]) -> int:
        """Continue the pending escape/CSI sequence with ``text[i]``.

        Returns the index to continue scanning from.  Every path either
        completes the sequence, resolves it outright, or leaves it pending
        for a later feed -- resolution never happens merely because a feed
        ended.
        """
        ch = text[i]
        if self._esc == "escape":
            if ch == "[":
                self._esc = "csi"
                self._csi_params = []
                return i + 1
            # ESC ESC, or ESC followed by a byte that cannot extend the
            # sequence: the escape resolves now.  A restarting ESC keeps
            # the pending state; any other byte is re-read as ground.
            events.append(Key("escape"))
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

    def _degrade_csi(self) -> list[Key | Paste]:
        """Emit the escape part of a degraded CSI and clear the csi state.

        The collected parameter characters are re-read literally as ground
        keys, preserving the historical degrade semantics; the ``[``
        introducer stays consumed.
        """
        events: list[Key | Paste] = [Key("escape")]
        for param in self._csi_params:
            key = _char_key(param)
            if key is not None:
                events.append(key)
        self._esc = None
        self._csi_params = []
        return events

    def _emit_csi(self, params: str, final: str, events: list[Key | Paste]) -> None:
        """Dispatch a complete CSI sequence; unknown sequences are dropped."""
        if params.startswith("<"):  # SGR mouse report (CSI < b ; x ; y M/m)
            self._emit_mouse_report(params, final, events)
            return
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

    def _emit_mouse_report(self, params: str, final: str, events: list[Key | Paste]) -> None:
        """Decode one SGR-1006 mouse report into press/release/motion events.

        Only the ``M``/``m`` finals are reports at all: the final byte
        selects the report class from :data:`_REPORT_CLASSES`, and the three
        fields (``b ; x ; y``) must all be integers, or the report is
        malformed and dropped like any other unrecognized sequence.

        ``b & 0x40`` marks a wheel report and its low two bits select the
        direction (0 = up, 1 = down); the horizontal wheel (2/3) stays
        dropped today.  A wheel report is discrete, so it decodes
        ``kind="press"`` regardless of the final byte's class.  A button
        report decodes when its low two bits name a known button (0 = left,
        1 = middle, 2 = right) -- the same resolution for press, release and
        motion; unknown button codes stay dropped.  Modifier bits (shift 4,
        alt/meta 8, ctrl 16) are covered by the low-two-bits tests, so a
        modified report keeps its name.
        """
        report = _REPORT_CLASSES.get(final)
        if report is None:
            return
        fields = params[1:].split(";")
        if len(fields) != 3:
            return
        try:
            b, x, y = int(fields[0]), int(fields[1]), int(fields[2])
        except ValueError:
            return
        # The report's coordinates are 1-based; every cell index in the
        # toolkit is 0-based, so the decoder normalizes here once and for all
        # (a hit test then consumes an event's x/y directly).
        x, y = x - 1, y - 1
        kind, motion = report
        if b & _WHEEL_BIT:
            low = b & 0x03
            if low > 1:
                return  # horizontal wheel: not routed today
            # A wheel report is discrete: always a press, final byte aside.
            events.append(
                MouseEvent(
                    "wheel_up" if low == 0 else "wheel_down",
                    button=low,
                    x=x,
                    y=y,
                    kind="press",
                )
            )
            return
        if motion and b & _MOTION_BIT:
            kind = "motion"  # mode 1002 motion report (drag, or hover at 0)
        low = b & 0x03
        name = _BUTTON_NAMES.get(low)
        if name is not None:
            events.append(MouseEvent(name, button=low, x=x, y=y, kind=kind))

    def _close_paste(self, events: list[Key | Paste]) -> None:
        """Deliver the accumulated paste, or drop a stray end marker."""
        if self._paste is None:
            return  # end marker without a start: dropped
        events.append(Paste("".join(self._paste)))
        self._paste = None
