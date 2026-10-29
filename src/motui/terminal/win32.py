"""The Windows console plumbing: mode bits, record mapping and ctypes structs.

Mouse records are synthesized as SGR-1006 payloads and fed to the one
decoder, so both platforms resolve the same events. The structs are
defined portably so tests can assert their offsets."""

from __future__ import annotations

import ctypes
from collections.abc import Iterable
from dataclasses import replace

from ..kernel.events import (
    Event,
    FocusEvent,
    KeyEvent,
    ResizeEvent,
)
from .ansi import ESC
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

#: INPUT_RECORD.EventType values the record mappers know.
_KEY_EVENT = 1
_MOUSE_EVENT = 2
_WINDOW_BUFFER_SIZE_EVENT = 4
_FOCUS_EVENT = 16

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
#: ``(_KEY_EVENT, bKeyDown, repeat, vk, char, ctrl)``, a mouse record
#: ``(_MOUSE_EVENT, x, y, button_state, flags, ctrl)``, a focus record
#: ``(_FOCUS_EVENT, focused)`` or a buffer-size record
#: ``(_WINDOW_BUFFER_SIZE_EVENT, width, height)``.
ConsoleRecord = tuple[int, ...]


def windows_input_mode(old: int) -> int:
    """The raw-ish console input mode: clears line, echo and QuickEdit, sets VT
    input; every other bit (notably processed input for Ctrl-C) passes
    through."""
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


class _FocusEventRecord(ctypes.Structure):
    """FOCUS_EVENT_RECORD: ``BOOL bSetFocus``."""

    _fields_ = [("bSetFocus", ctypes.c_int32)]


class _WindowBufferSizeRecord(ctypes.Structure):
    """WINDOW_BUFFER_SIZE_RECORD: ``COORD dwSize``."""

    _fields_ = [("dwSize", _Coord)]


class _EventUnion(ctypes.Union):
    """The ``Event`` member of INPUT_RECORD; every member fits the SDK's
    16-byte payload."""

    _fields_ = [
        ("Key", _KeyEventRecord),
        ("Mouse", _MouseEventRecord),
        ("Focus", _FocusEventRecord),
        ("WindowBufferSize", _WindowBufferSizeRecord),
    ]


class _InputRecord(ctypes.Structure):
    """INPUT_RECORD: 20 bytes on Windows."""

    _fields_ = [
        ("EventType", ctypes.c_uint16),
        ("Event", _EventUnion),
    ]


def _kernel32() -> ctypes.WinDLL:
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


def _key_from_values(vk: int, char: str, ctrl: int) -> KeyEvent | None:
    """Map a record's virtual key, character and control state to a key when
    the record delivered no character."""
    name = _VK_KEYS.get(vk)
    if name is not None:
        return KeyEvent(name)
    code = ord(char) if char else 0
    if 0x01 <= code <= 0x1A:  # the console delivered the control byte
        return KeyEvent(f"c-{chr(ord('a') + code - 1)}")
    if ctrl and ("a" <= char <= "z" or "A" <= char <= "Z"):
        return KeyEvent(f"c-{char.lower()}")
    if code >= 0x20 and not 0x7F <= code <= 0x9F:
        return KeyEvent(char, char)
    return None


def _console_record_fields(record: _InputRecord) -> ConsoleRecord:
    """The tagged field tuple :func:`_console_record_events` consumes; the
    pure mappers never touch ctypes."""
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
    if record.EventType == _FOCUS_EVENT:
        return (_FOCUS_EVENT, int(bool(record.Event.Focus.bSetFocus)))
    if record.EventType == _WINDOW_BUFFER_SIZE_EVENT:
        size = record.Event.WindowBufferSize.dwSize
        return (_WINDOW_BUFFER_SIZE_EVENT, size.X, size.Y)
    key = record.Event.Key
    return (
        _KEY_EVENT,
        key.bKeyDown,
        key.wRepeatCount,
        key.wVirtualKeyCode,
        key.uChar.UnicodeChar,
        key.dwControlKeyState,
    )


def _repeated(events: list[Event], repeat: int) -> list[Event]:
    """Apply a key record's ``wRepeatCount``: a press then ``repeat`` events."""
    if repeat <= 1:
        return events
    out: list[Event] = []
    for event in events:
        out.append(event)
        if isinstance(event, KeyEvent) and event.kind == "press":
            out.extend(replace(event, kind="repeat") for _ in range(repeat - 1))
    return out


def _console_record_events(
    record: ConsoleRecord, decoder: KeyDecoder, bits: int = 0, *, hover: bool = False
) -> tuple[list[Event], int]:
    """Decode one tagged console record, threading the held-button state across
    records."""
    if record[0] == _MOUSE_EVENT:
        return _console_mouse_report(record[1:], decoder, bits, hover=hover)
    if record[0] == _FOCUS_EVENT:
        return [FocusEvent(bool(record[1]))], bits
    if record[0] == _WINDOW_BUFFER_SIZE_EVENT:
        return [ResizeEvent(record[1], record[2])], bits
    down, repeat, vk, char, ctrl = record[1:]
    if not down:
        return [], bits
    events: list[Event]
    if char != "\x00":
        events = decoder.feed(char.encode("utf-8"))
    else:
        key = _key_from_values(vk, char, ctrl)
        events = [] if key is None else [key]
        if not events and ctrl & _CTRL_PRESSED and 0x41 <= vk <= 0x5A:  # VK_A..VK_Z
            events = [KeyEvent(f"c-{chr(vk + (ord('a') - ord('A')))}")]
    return _repeated(events, repeat), bits


def _sgr_report(code: int, x: int, y: int, final: str = "M") -> bytes:
    """One SGR-1006 report payload, translating 0-based cells to the report's
    1-based coordinates."""
    return f"{ESC}[<{code};{x + 1};{y + 1}{final}".encode()


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
) -> tuple[list[Event], int]:
    """Synthesize the VT path's SGR reports for one console mouse record; a
    press is a newly set bit, so the previous state names the button."""
    x, y, state, flags, _ctrl = record
    events: list[Event] = []
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
        # No button held before or now: the button-free move, the record
        # path's 1003 motion.  A release transition also has ``held == 0``
        # but ``released != 0`` and is excluded above.
        events.extend(decoder.feed(_sgr_report(_SGR_MOTION | 3, x, y)))
    return events, held


def keys_from_console_events(
    events: Iterable[ConsoleRecord], *, hover: bool = False
) -> list[Event]:
    """Replay a console-record stream through the one decoder; pure and
    console-free, with held-button state threaded across the stream."""
    decoder = KeyDecoder()
    out: list[Event] = []
    bits = 0
    for record in events:
        produced, bits = _console_record_events(record, decoder, bits, hover=hover)
        out.extend(produced)
    return out
