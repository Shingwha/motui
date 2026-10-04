"""The Windows console plumbing: mode bits, record mapping, ctypes structs.

Everything Windows-specific about reading the console lives here: the console
input-mode bits and :func:`windows_input_mode`; the record mappers
(:func:`_key_from_console_event`, :func:`_key_from_values`,
:func:`_console_record_events`); the pure replay :func:`keys_from_console_events`;
and the ctypes structures plus the ``kernel32`` prototype binding the live
reader in :mod:`mocode_tui.keys.sources` calls.

The ctypes structures are defined portably (``ctypes`` is stdlib everywhere)
so this module imports identically on every platform and the field offsets
can be asserted in tests; the field widths follow the Windows SDK, so on
Windows these are exactly KEY_EVENT_RECORD (16 bytes) and INPUT_RECORD (20
bytes).  Elsewhere the sizes differ and nothing here is ever touched: the
record path only runs when ``os.name == "nt"``.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterable

from mocode_tui.keys.decoder import KeyDecoder
from mocode_tui.keys.events import Key, Paste

# Windows console input mode bits (wincon.h).
_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
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
    """
    return (old & ~(_ENABLE_LINE_INPUT | _ENABLE_ECHO_INPUT)) | _ENABLE_VIRTUAL_TERMINAL_INPUT


# Windows console input structures.  They are defined portably (``ctypes`` is
# stdlib everywhere) so this module imports identically on every platform and
# the field offsets can be asserted in tests; the field widths follow the
# Windows SDK, so on Windows these are exactly KEY_EVENT_RECORD (16 bytes)
# and INPUT_RECORD (20 bytes).  Elsewhere the sizes differ and nothing here is
# ever touched: the record path only runs when ``os.name == "nt"``.
class _CharUnion(ctypes.Union):
    """The ``uChar`` member of KEY_EVENT_RECORD."""

    _fields_ = [("UnicodeChar", ctypes.c_wchar), ("AsciiChar", ctypes.c_char)]


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


class _InputRecord(ctypes.Structure):
    """INPUT_RECORD: 20 bytes on Windows."""

    _fields_ = [
        ("EventType", ctypes.c_uint16),
        ("Event", _KeyEventRecord),
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


def _key_from_console_event(record: object) -> Key | None:
    """Map one Windows KEY_EVENT_RECORD to a key event, or ``None``.

    ``record`` is anything exposing the KEY_EVENT_RECORD fields --
    ``bKeyDown``, ``wVirtualKeyCode``, ``uChar.UnicodeChar``,
    ``dwControlKeyState`` -- which the real ctypes structure satisfies and a
    test double can imitate.  Key-up events and unrecognizable records
    return ``None``; the repeat count is ignored.

    Resolution order: the virtual-key table first (so Enter/Tab/Escape keep
    their names even though their characters collide with Ctrl codes), then
    Ctrl combinations, then the plain Unicode character -- wide characters
    pass through untouched, bypassing any code page.
    """
    if not record.bKeyDown:
        return None
    return _key_from_values(
        record.wVirtualKeyCode, record.uChar.UnicodeChar, record.dwControlKeyState
    )


def _key_from_values(vk: int, char: str, ctrl: int) -> Key | None:
    """Map a record's virtual key, character and control state to a key.

    The virtual-key resolution of :func:`_key_from_console_event`, shared
    with the record-to-byte-stream path so both agree on names.
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


def _console_record_events(
    record: tuple[bool, int, str, int], decoder: KeyDecoder
) -> list[Key | Paste]:
    """Decode one console key record -- ``(bKeyDown, vk, char, ctrl)``.

    The character wins.  With ``ENABLE_VIRTUAL_TERMINAL_INPUT`` set (see
    :func:`windows_input_mode`) the console delivers input as a VT byte
    stream: each record carries one byte of the sequence -- ESC, CR, BS,
    printables, code points -- in ``UnicodeChar``, so every non-NUL
    character is UTF-8 encoded and fed to ``decoder``, which assembles
    sequences across records.  Only a NUL character falls back to the
    virtual-key mapping, the delivery another console semantics uses for
    keys that produce no character (arrows, page keys) and for Ctrl
    combinations reported through the control state alone.

    Exactly one branch runs per record, so the two semantics never
    double-enqueue a key.
    """
    down, vk, char, ctrl = record
    if not down:
        return []
    if char != "\x00":
        return decoder.feed(char.encode("utf-8"))
    key = _key_from_values(vk, char, ctrl)
    if key is not None:
        return [key]
    if ctrl & _CTRL_PRESSED and 0x41 <= vk <= 0x5A:  # VK_A..VK_Z, no character
        return [Key(f"c-{chr(vk + (ord('a') - ord('A')))}")]
    return []


def keys_from_console_events(
    events: Iterable[tuple[bool, int, str, int]],
) -> list[Key | Paste]:
    """Replay a console-record stream through the byte-stream decoder.

    Pure and console-free, so both console delivery semantics are testable
    without a Windows console: each event is a ``(bKeyDown, virtual_key,
    char, control_state)`` tuple and the mapping logic is the very same
    ``_console_record_events`` the live reader uses.  A fresh decoder is
    created per call and no settle/flush is applied -- a replay ending
    mid-sequence leaves that state inside the throwaway decoder, exactly
    where the live reader would settle it after a silence period.
    """
    decoder = KeyDecoder()
    out: list[Key | Paste] = []
    for record in events:
        out.extend(_console_record_events(record, decoder))
    return out
