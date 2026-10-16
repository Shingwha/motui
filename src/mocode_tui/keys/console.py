"""The Windows console plumbing: mode bits, record mapping, ctypes structs.

Everything Windows-specific about reading the console lives here: the console
input-mode bits and :func:`windows_input_mode`; the record mappers
(:func:`_key_from_values`, :func:`_console_record_fields`,
:func:`_console_record_events`, :func:`_console_mouse_report`); the pure replay
:func:`keys_from_console_events`; and the ctypes structures plus the
``kernel32`` prototype binding the live reader in
:mod:`mocode_tui.keys.sources` calls.

Mouse records are surfaced with the VT path's own semantics: the mapper
synthesizes the equivalent SGR-1006 report payloads
(:func:`_console_mouse_report`) and feeds them to the one
:class:`~mocode_tui.keys.decoder.KeyDecoder`, so a press, release or motion
resolves to the same :class:`~mocode_tui.core.events.MouseEvent` on both
platforms -- the decoder stays the single authority on what a report means.

The ctypes structures are defined portably (``ctypes`` is stdlib everywhere)
so this module imports identically on every platform and the field offsets
can be asserted in tests; the field widths follow the Windows SDK, so on
Windows these are exactly KEY_EVENT_RECORD (16 bytes), MOUSE_EVENT_RECORD
(16 bytes) and INPUT_RECORD (20 bytes).  Elsewhere the sizes differ and
nothing here is ever touched: the record path only runs when
``os.name == "nt"``.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterable

from ..core.ansi import ESC
from ..core.events import Key, Paste
from .decoder import KeyDecoder

# Windows console input mode bits (wincon.h).
_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
_ENABLE_QUICK_EDIT_MODE = 0x0040
_ENABLE_EXTENDED_FLAGS = 0x0080
_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

#: Ctrl is held (LEFT_CTRL_PRESSED | RIGHT_CTRL_PRESSED).
_CTRL_PRESSED = 0x000C

#: Virtual-key codes the console-record path maps (winuser.h).
_VK_KEYS = {
    0x08: "backspace",  # VK_BACK
    0x09: "tab",  # VK_TAB
    0x0D: "enter",  # VK_RETURN
    0x1B: "escape",  # VK_ESCAPE
    0x21: "page_up",  # VK_PRIOR
    0x22: "page_down",  # VK_NEXT
    0x23: "end",  # VK_END
    0x24: "home",  # VK_HOME
    0x25: "left",  # VK_LEFT
    0x26: "up",  # VK_UP
    0x27: "right",  # VK_RIGHT
    0x28: "down",  # VK_DOWN
    0x2E: "delete",  # VK_DELETE
}

#: INPUT_RECORD.EventType for a keyboard record; every other type is skipped.
_KEY_EVENT = 1

#: INPUT_RECORD.EventType for a mouse record.
_MOUSE_EVENT = 2

#: dwButtonState bits for the three buttons the event model names, each with
#: its SGR-1006 button number (wincon.h):
#: FROM_LEFT_1ST = left, RIGHTMOST (= FROM_LEFT_2ND) = right, FROM_LEFT_3RD =
#: middle.  Bits 4 (0x0008) and 5 (0x0010) are extra buttons the event model
#: does not name, so :data:`_BUTTON_MASK` drops them.
_BUTTON_CODES = ((0x0001, 0), (0x0002, 2), (0x0004, 1))

#: The three named buttons inside dwButtonState's low word.
_BUTTON_MASK = 0x0007

#: MOUSE_EVENT_RECORD dwFlags bits (wincon.h).  A double-click flag is
#: simply not examined: a double-click is two presses.
_MOUSE_MOVED = 0x0001
_MOUSE_WHEELED = 0x0004

#: The SGR-1006 codes the synthesizer emits, matching the decoder's own
#: tables: the motion bit and the two vertical wheel directions (the
#: horizontal wheel stays dropped there, so it stays dropped here).
_SGR_MOTION = 32
_SGR_WHEEL_UP = 64
_SGR_WHEEL_DOWN = 65

#: The wheel delta rides in dwButtonState's high word, as a signed 16-bit
#: value; a positive delta is a forward (up) rotation.
_WHEEL_SHIFT = 16
_WHEEL_SIGN = 0x8000
_WHEEL_WRAP = 0x10000

#: A console record as the pure mappers consume it: the INPUT_RECORD event
#: type tag first, then the record's fields -- a key record
#: ``(_KEY_EVENT, bKeyDown, vk, char, ctrl)`` or a mouse record
#: ``(_MOUSE_EVENT, x, y, button_state, flags, ctrl)``.
ConsoleRecord = tuple[int, ...]


def windows_input_mode(old: int) -> int:
    """The console input mode for raw-ish reading, derived from ``old``.

    Clears ``ENABLE_LINE_INPUT`` and ``ENABLE_ECHO_INPUT`` (the toolkit does
    its own line editing and echoing) and sets
    ``ENABLE_VIRTUAL_TERMINAL_INPUT``.  That bit is an input *delivery*
    switch, and its semantics are exactly what the console path in this
    module depends on: with it set, the console hands input over as a VT
    byte stream -- every key press arrives as one or more KEY_EVENT records
    whose ``UnicodeChar`` carries a single sequence byte (ESC, CR, BS,
    printables, code points), the virtual-key field typically unused.  So
    ``_read_console_records`` feeds those characters to :class:`KeyDecoder`
    (which assembles sequences across records and settles them after a
    silence window) rather than mapping records through the virtual-key
    table; only a NUL character falls back to that table.

    Every other bit passes through untouched -- notably
    ``ENABLE_PROCESSED_INPUT``, which a console normally has set and which
    keeps Ctrl-C raising a real ``KeyboardInterrupt`` as a second line of
    defence.

    The one deliberate exception is ``ENABLE_QUICK_EDIT_MODE``: it lets the
    console host intercept the mouse for its own text selection, competing
    with the application's mouse reporting.  It is cleared, and
    ``ENABLE_EXTENDED_FLAGS`` is set alongside (Windows ignores QuickEdit
    changes without it) -- the same trade raw mode makes on POSIX: the
    application takes the mouse, so it owes the user a selection of its
    own.  ``close()`` restores the saved mode wholesale.
    """
    return (
        (old & ~(_ENABLE_LINE_INPUT | _ENABLE_ECHO_INPUT | _ENABLE_QUICK_EDIT_MODE))
        | _ENABLE_VIRTUAL_TERMINAL_INPUT
        | _ENABLE_EXTENDED_FLAGS
    )


# Windows console input structures.
class _CharUnion(ctypes.Union):
    """The ``uChar`` member of KEY_EVENT_RECORD."""

    _fields_ = [("UnicodeChar", ctypes.c_wchar)]


class _KeyEventRecord(ctypes.Structure):
    """KEY_EVENT_RECORD: 16 bytes on Windows."""

    _fields_ = [
        ("bKeyDown", ctypes.c_int32),  # BOOL
        ("wRepeatCount", ctypes.c_uint16),  # WORD
        ("wVirtualKeyCode", ctypes.c_uint16),
        ("wVirtualScanCode", ctypes.c_uint16),
        ("uChar", _CharUnion),
        ("dwControlKeyState", ctypes.c_uint32),  # DWORD
    ]


class _Coord(ctypes.Structure):
    """COORD: character-cell coordinates, origin 0;0, 16 bits signed."""

    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _MouseEventRecord(ctypes.Structure):
    """MOUSE_EVENT_RECORD: 16 bytes on Windows."""

    _fields_ = [
        ("dwMousePosition", _Coord),
        ("dwButtonState", ctypes.c_uint32),  # DWORD
        ("dwControlKeyState", ctypes.c_uint32),  # DWORD
        ("dwFlags", ctypes.c_uint32),  # DWORD
    ]


class _EventUnion(ctypes.Union):
    """The ``Event`` member of INPUT_RECORD: a key or a mouse record.

    Both members are 16 bytes with identical alignment, so the union is the
    Windows SDK's layout whichever kind the record carries.
    """

    _fields_ = [("Key", _KeyEventRecord), ("Mouse", _MouseEventRecord)]


class _InputRecord(ctypes.Structure):
    """INPUT_RECORD: 20 bytes on Windows."""

    _fields_ = [
        ("EventType", ctypes.c_uint16),
        ("Event", _EventUnion),
    ]


def _kernel32() -> "ctypes.WinDLL":
    """kernel32 with the console-mode and console-input prototypes set."""
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetConsoleMode.restype = ctypes.c_int
    api.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    api.SetConsoleMode.restype = ctypes.c_int
    api.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    api.ReadConsoleInputW.restype = ctypes.c_int
    api.ReadConsoleInputW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_InputRecord),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    api.PeekConsoleInputW.restype = ctypes.c_int
    api.PeekConsoleInputW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_InputRecord),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    return api


def _key_from_values(vk: int, char: str, ctrl: int) -> Key | None:
    """Map a record's virtual key, character and control state to a key.

    The record path's fallback resolution, used when a key record delivers
    no character (``"\\x00"``): the virtual-key table first, then control
    bytes, then Ctrl combinations, then the plain Unicode character.
    """
    name = _VK_KEYS.get(vk)
    if name is not None:
        return Key(name)
    code = ord(char) if char else 0
    if 0x01 <= code <= 0x1A:  # the console delivered the control byte
        return Key(f"c-{chr(ord('a') + code - 1)}")
    if ctrl and ("a" <= char <= "z" or "A" <= char <= "Z"):
        return Key(f"c-{char.lower()}")
    if code >= 0x20 and not 0x7F <= code <= 0x9F:
        return Key(char, char)
    return None


def _console_record_fields(record: _InputRecord) -> ConsoleRecord:
    """The tagged field tuple :func:`_console_record_events` consumes.

    The ctypes record's fields, tagged by :attr:`EventType` so the pure
    mappers (and the replay seam) never touch ctypes.  Key records carry
    their four fields; mouse records carry ``(x, y, button_state, flags,
    control_state)``.
    """
    if record.EventType == _MOUSE_EVENT:
        mouse = record.Event.Mouse
        return (
            _MOUSE_EVENT,
            mouse.dwMousePosition.X,
            mouse.dwMousePosition.Y,
            mouse.dwButtonState,
            mouse.dwFlags,
            mouse.dwControlKeyState,
        )
    key = record.Event.Key
    return (
        _KEY_EVENT,
        key.bKeyDown,
        key.wVirtualKeyCode,
        key.uChar.UnicodeChar,
        key.dwControlKeyState,
    )


def _console_record_events(
    record: ConsoleRecord, decoder: KeyDecoder, bits: int = 0, *, hover: bool = False
) -> tuple[list[Key | Paste], int]:
    """Decode one tagged console record, carrying the held-button state.

    A key record -- ``(_KEY_EVENT, bKeyDown, vk, char, ctrl)`` -- behaves
    exactly as before and leaves ``bits`` untouched: the character wins, and
    with ``ENABLE_VIRTUAL_TERMINAL_INPUT`` set (see
    :func:`windows_input_mode`) the console delivers input as a VT byte
    stream, so every non-NUL character is UTF-8 encoded and fed to
    ``decoder``, which assembles sequences across records; only a NUL
    character falls back to the virtual-key mapping, the delivery another
    console semantics uses for keys that produce no character (arrows, page
    keys) and for Ctrl combinations reported through the control state
    alone.  Exactly one branch runs per record, so the two semantics never
    double-enqueue a key.

    A mouse record -- ``(_MOUSE_EVENT, x, y, button_state, flags, ctrl)`` --
    goes to :func:`_console_mouse_report`; ``hover`` is the record path's
    counterpart of the VT path's DECSET 1003 and gates its button-free
    motion reports.  The return is the events plus the held-button bits
    after this record, since a console press or release is a transition the
    previous record's state disambiguates.
    """
    if record[0] == _MOUSE_EVENT:
        return _console_mouse_report(record[1:], decoder, bits, hover=hover)
    down, vk, char, ctrl = record[1:]
    if not down:
        return [], bits
    if char != "\x00":
        return decoder.feed(char.encode("utf-8")), bits
    key = _key_from_values(vk, char, ctrl)
    if key is not None:
        return [key], bits
    if ctrl & _CTRL_PRESSED and 0x41 <= vk <= 0x5A:  # VK_A..VK_Z, no character
        return [Key(f"c-{chr(vk + (ord('a') - ord('A')))}")], bits
    return [], bits


def _sgr_report(code: int, x: int, y: int, final: str = "M") -> bytes:
    """One SGR-1006 mouse report payload: ESC ``[`` ``<`` code ``;`` x+1 ``;`` y+1 final.

    The console's cell coordinates are 0-based and the report's 1-based, the
    mirror of the decoder's normalization, so a coordinate survives the trip
    through the report unchanged.  UTF-8, like every other byte the console
    path hands the decoder.
    """
    return f"{ESC}[<{code};{x + 1};{y + 1}{final}".encode("utf-8")


def _wheel_delta(state: int) -> int:
    """The signed wheel delta in dwButtonState's high word (0 if none)."""
    delta = state >> _WHEEL_SHIFT
    if delta >= _WHEEL_SIGN:
        delta -= _WHEEL_WRAP
    return delta


def _console_mouse_report(
    record: tuple[int, int, int, int, int],
    decoder: KeyDecoder,
    bits: int,
    *,
    hover: bool = False,
) -> tuple[list[Key | Paste], int]:
    """Synthesize the VT path's SGR-1006 reports for one console mouse record.

    ``record`` is ``(x, y, button_state, flags, control_state)`` -- the
    MOUSE_EVENT_RECORD fields -- and ``bits`` is the held-button state the
    previous record left: the console reports the full current state with
    every record, so a press is a newly-set bit, a release the transition
    to zero, and both need the previous state to name the button.  The
    reports are built as SGR-1006 payloads and fed to the one decoder, so
    the console path resolves press, release, motion and the vertical wheel
    exactly as the VT path does (the horizontal wheel stays dropped, as
    there).

    A ``MOUSE_MOVED`` flag with buttons held is a motion report carrying the
    motion bit; a double-click is ignored, so it surfaces as the two presses
    it physically is (timing policy belongs to the controller).  A record
    that both transitions a button and carries
    ``MOUSE_MOVED`` reports the button only -- the VT path never mixes a
    press and a motion bit in one report.  A wheel tick is discrete: it
    emits its report and leaves ``bits`` alone, since a console may zero the
    low word of a wheel record while a button is still held.

    ``hover`` is the record path's DECSET 1003 counterpart (the record path
    has no 1002/1003 switch of its own): with it set, a ``MOUSE_MOVED``
    record with no button held and no transition synthesizes the wire's
    button-free motion report -- low bits 3, ``_SGR_MOTION | 3`` = 35 --
    which the decoder normalizes to ``MouseEvent("none", button=0)``.
    Off (the default), a bare pointer move stays dropped exactly as the
    default 1002 VT path drops it; a transition record (a press or release
    riding ``MOUSE_MOVED``) never takes the button-free branch.
    """
    x, y, state, flags, _ctrl = record
    events: list[Key | Paste] = []
    if flags & _MOUSE_WHEELED:
        delta = _wheel_delta(state)
        if delta:
            code = _SGR_WHEEL_UP if delta > 0 else _SGR_WHEEL_DOWN
            events.extend(decoder.feed(_sgr_report(code, x, y)))
        return events, bits
    held = state & _BUTTON_MASK
    pressed = held & ~bits
    released = bits & ~held
    for bit, code in _BUTTON_CODES:
        if released & bit:
            events.extend(decoder.feed(_sgr_report(code, x, y, "m")))
    for bit, code in _BUTTON_CODES:
        if pressed & bit:
            events.extend(decoder.feed(_sgr_report(code, x, y)))
    if held and not pressed and not released and flags & _MOUSE_MOVED:
        for bit, code in _BUTTON_CODES:
            if held & bit:
                events.extend(decoder.feed(_sgr_report(code + _SGR_MOTION, x, y)))
    elif hover and not held and not released and flags & _MOUSE_MOVED:
        # No button held before or now: the button-free move (35), the
        # record path's 1003 motion.  A release transition also has
        # ``held == 0`` but ``released != 0`` and is excluded above.
        events.extend(decoder.feed(_sgr_report(_SGR_MOTION | 3, x, y)))
    return events, held


def keys_from_console_events(
    events: Iterable[ConsoleRecord], *, hover: bool = False
) -> list[Key | Paste]:
    """Replay a console-record stream through the one decoder.

    Pure and console-free, so every record kind the console delivers is
    testable without a Windows console: each record is tagged by its
    INPUT_RECORD event type -- a key record ``(_KEY_EVENT, bKeyDown, vk,
    char, ctrl)`` or a mouse record ``(_MOUSE_EVENT, x, y, button_state,
    flags, ctrl)`` -- and the mapping logic is the very same
    ``_console_record_events`` the live reader uses, held-button state
    threaded across the stream exactly as the live reader threads it.  A
    fresh decoder is created per call and no settle/flush is applied -- a
    replay ending mid-sequence leaves that state inside the throwaway
    decoder, exactly where the live reader would settle it after a silence
    period.  A bare pointer move is the record path's counterpart of the VT
    path's 1003 motion: the ``hover`` switch decides whether it surfaces
    (see :func:`_console_mouse_report`), exactly as the switch owns DECSET
    1003 on the VT path.
    """
    decoder = KeyDecoder()
    out: list[Key | Paste] = []
    bits = 0
    for record in events:
        produced, bits = _console_record_events(record, decoder, bits, hover=hover)
        out.extend(produced)
    return out
