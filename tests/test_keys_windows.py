"""Tests for mocode_tui.keys sources: ScriptedKeys and RawTerminalKeys.

The Windows console plumbing is covered here in three tiers, exactly as the
work tickets allow:

* **pure functions and structure shapes** -- ``windows_input_mode``,
  ``_key_from_console_event`` and ``keys_from_console_events`` run
  everywhere (the record mapper is duck-typed and the record replay takes
  plain tuples, so test doubles stand in for the ctypes structure), and the
  ctypes structure sizes/offsets are asserted against the Windows SDK on
  ``os.name == "nt"`` only;
* **kernel32 prototypes** -- the console-input API signatures are asserted
  statically (never called) where kernel32 exists;
* **real ctypes/console interaction** -- a real console is required to
  exercise ``ReadConsoleInputW``/``PeekConsoleInputW``, which this
  environment has no access to (no TTY).  That path is left for real-machine
  acceptance by the lead; the tests below pin everything that can be pinned
  without a console.

``RawTerminalKeys`` itself is exercised through explicit pipe file
descriptors, which works identically on POSIX and Windows: the pipe forces
the cooked-line fallback, and the thread/queue/executor bridge is real.
"""

import asyncio
import ctypes
import os
from dataclasses import dataclass, field

import pytest

from mocode_tui import keys as keys_mod
from mocode_tui.keys import (
    Key,
    KeyDecoder,
    KeySource,
    Paste,
    RawTerminalKeys,
    ScriptedKeys,
)

# Windows console input mode bits (wincon.h).
_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

# A typical console default: PROCESSED | LINE | ECHO | MOUSE | INSERT |
# QUICK_EDIT | EXTENDED | AUTO_POSITION.
_TYPICAL_CONSOLE_MODE = 0x01F7

# Virtual-key codes (winuser.h).
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_LEFT = 0x25
_VK_UP = 0x26
_VK_F1 = 0x70


# --- windows_input_mode (pure) ------------------------------------------------


def test_input_mode_clears_line_and_echo_and_sets_vt_input():
    new = keys_mod.windows_input_mode(_TYPICAL_CONSOLE_MODE)
    assert new & _ENABLE_LINE_INPUT == 0
    assert new & _ENABLE_ECHO_INPUT == 0
    assert new & _ENABLE_VIRTUAL_TERMINAL_INPUT != 0


def test_input_mode_passes_every_other_bit_through():
    new = keys_mod.windows_input_mode(_TYPICAL_CONSOLE_MODE)
    assert new & _ENABLE_PROCESSED_INPUT != 0  # Ctrl-C stays a real signal
    assert new & 0x0010 != 0  # ENABLE_MOUSE_INPUT untouched
    assert new & 0x0020 != 0  # ENABLE_INSERT_MODE untouched
    assert new & 0x0040 != 0  # ENABLE_QUICK_EDIT_MODE untouched
    assert new & 0x0080 != 0  # ENABLE_EXTENDED_FLAGS untouched
    assert new & 0x0100 != 0  # ENABLE_AUTO_POSITION untouched


def test_input_mode_from_zero_only_sets_vt_input():
    assert keys_mod.windows_input_mode(0) == _ENABLE_VIRTUAL_TERMINAL_INPUT


def test_input_mode_is_idempotent():
    once = keys_mod.windows_input_mode(_TYPICAL_CONSOLE_MODE)
    assert keys_mod.windows_input_mode(once) == once


# --- _key_from_console_event (pure, duck-typed records) -----------------------


@dataclass
class FakeChar:
    UnicodeChar: str


@dataclass
class FakeKeyEvent:
    bKeyDown: bool = True
    wRepeatCount: int = 1
    wVirtualKeyCode: int = 0
    uChar: FakeChar = field(default_factory=lambda: FakeChar("\x00"))
    dwControlKeyState: int = 0


def event(vk=0, char="\x00", *, down=True, ctrl=0, repeat=1):
    return FakeKeyEvent(
        bKeyDown=down,
        wRepeatCount=repeat,
        wVirtualKeyCode=vk,
        uChar=FakeChar(char),
        dwControlKeyState=ctrl,
    )


def test_key_up_events_are_ignored():
    assert keys_mod._key_from_console_event(event(_VK_UP, "A", down=False)) is None


@pytest.mark.parametrize(
    ("vk", "name"),
    [
        (0x08, "backspace"),
        (0x09, "tab"),
        (0x0D, "enter"),
        (0x1B, "escape"),
        (_VK_PRIOR, "page_up"),
        (_VK_NEXT, "page_down"),
        (0x23, "end"),
        (0x24, "home"),
        (_VK_LEFT, "left"),
        (_VK_UP, "up"),
        (0x27, "right"),
        (0x28, "down"),
        (0x2E, "delete"),
    ],
)
def test_virtual_key_table(vk, name):
    assert keys_mod._key_from_console_event(event(vk)) == Key(name)


def test_enter_wins_over_its_control_character():
    # VK_RETURN's character (CR) collides with Ctrl-M; the VK table is
    # consulted first, so the key is named "enter".
    assert keys_mod._key_from_console_event(event(0x0D, "\r")) == Key("enter")


def test_unicode_characters_pass_through_wide_included():
    assert keys_mod._key_from_console_event(event(0, "中")) == Key("中", "中")
    assert keys_mod._key_from_console_event(event(0, "a")) == Key("a", "a")


def test_ctrl_combinations_from_control_bytes():
    assert keys_mod._key_from_console_event(event(0, "\x01")) == Key("c-a")
    assert keys_mod._key_from_console_event(event(0, "\x1a")) == Key("c-z")


def test_ctrl_combinations_from_letter_and_state():
    ctrl = 0x0008  # LEFT_CTRL_PRESSED
    assert keys_mod._key_from_console_event(event(0x41, "a", ctrl=ctrl)) == Key("c-a")
    assert keys_mod._key_from_console_event(event(0x5A, "Z", ctrl=0x0004)) == Key("c-z")


def test_unknown_virtual_keys_and_blank_records_are_dropped():
    assert keys_mod._key_from_console_event(event(_VK_F1)) is None
    assert keys_mod._key_from_console_event(event(0)) is None


def test_repeat_count_is_ignored():
    assert keys_mod._key_from_console_event(event(0, "q", repeat=9)) == Key("q", "q")


# --- console records -> byte stream (pure replay) ----------------------------


def key_event(vk=0, char="\x00", *, down=True, ctrl=0):
    """One console record as a ``(bKeyDown, vk, char, ctrl)`` tuple.

    The tuple is the shape ``keys_from_console_events`` (and the live
    reader, through ``_console_record_events``) consumes.
    """
    return (down, vk, char, ctrl)


def _byte_events(text: str):
    """Records delivering ``text`` one character per record.

    That is how ``ENABLE_VIRTUAL_TERMINAL_INPUT`` delivers input: each
    record carries one byte of the VT sequence in ``UnicodeChar``.
    """
    return [key_event(char=ch) for ch in text]


def test_console_bytes_assemble_escape_sequences_across_records():
    # ESC [ A arrives as three records; the decoder must assemble them into
    # up instead of leaking literal "[" and "A" (the W7 bug).
    assert keys_mod.keys_from_console_events(_byte_events("\x1b[A")) == [Key("up")]


def test_console_control_bytes_decode_through_the_decoder():
    assert keys_mod.keys_from_console_events(_byte_events("\r")) == [Key("enter")]
    assert keys_mod.keys_from_console_events(_byte_events("\x7f")) == [Key("backspace")]
    assert keys_mod.keys_from_console_events(_byte_events("\x1b[5~")) == [Key("page_up")]
    assert keys_mod.keys_from_console_events(_byte_events("a\t")) == [
        Key("a", "a"),
        Key("tab"),
    ]


def test_console_code_points_arrive_utf8_encoded():
    # A wide character is one record's character; the decoder sees its
    # UTF-8 bytes and yields a single key per code point.
    assert keys_mod.keys_from_console_events(_byte_events("你好")) == [
        Key("你", "你"),
        Key("好", "好"),
    ]


def test_console_ctrl_bytes_become_c_combinations():
    assert keys_mod.keys_from_console_events(_byte_events("\x01\x03\x1a")) == [
        Key("c-a"),
        Key("c-c"),
        Key("c-z"),
    ]


def test_console_nul_character_falls_back_to_the_virtual_key_table():
    assert keys_mod.keys_from_console_events([key_event(_VK_LEFT)]) == [Key("left")]
    assert keys_mod.keys_from_console_events([key_event(_VK_UP)]) == [Key("up")]
    assert keys_mod.keys_from_console_events([key_event(0x0D)]) == [Key("enter")]
    assert keys_mod.keys_from_console_events([key_event(0x1B)]) == [Key("escape")]
    assert keys_mod.keys_from_console_events([key_event(_VK_PRIOR)]) == [Key("page_up")]


def test_console_ctrl_letter_virtual_key_fallback():
    # Ctrl held with a letter virtual key and no character delivered.
    assert keys_mod.keys_from_console_events([key_event(0x41, "\x00", ctrl=0x0008)]) == [
        Key("c-a")
    ]
    assert keys_mod.keys_from_console_events([key_event(0x5A, "\x00", ctrl=0x0004)]) == [
        Key("c-z")
    ]


def test_console_character_wins_over_the_virtual_key_no_double_enqueue():
    # A record carrying both a character and a virtual key (a VT-input
    # console keeps filling the VK field) feeds the character only: the VK
    # table is not consulted, so nothing is enqueued twice.
    assert keys_mod.keys_from_console_events([key_event(_VK_UP, "A")]) == [Key("A", "A")]
    assert keys_mod.keys_from_console_events([key_event(0x0D, "\r")]) == [Key("enter")]


def test_console_key_up_records_are_ignored():
    assert keys_mod.keys_from_console_events([key_event(_VK_UP, "\x00", down=False)]) == []
    assert keys_mod.keys_from_console_events([key_event(0x41, "a", down=False)]) == []


def test_console_lone_escape_stays_pending_until_settled():
    decoder = KeyDecoder()
    assert keys_mod._console_record_events(key_event(char="\x1b"), decoder) == []
    assert decoder.pending() is True
    assert decoder.settle() == [Key("escape")]


def test_console_screenshot_input_replay():
    # W7 acceptance smoke: the input string from the user's real-machine
    # screenshot -- up up, down down down, "你好", another up, a backspace
    # and page up -- delivered one byte per record.  No literal "[" / "A"
    # may leak through (that was the reported bug).
    raw = "\x1b[A\x1b[A\x1b[B\x1b[B\x1b[B你好\x1b[A\x7f\x1b[5~"
    keys = keys_mod.keys_from_console_events(_byte_events(raw))
    assert keys == [
        Key("up"),
        Key("up"),
        Key("down"),
        Key("down"),
        Key("down"),
        Key("你", "你"),
        Key("好", "好"),
        Key("up"),
        Key("backspace"),
        Key("page_up"),
    ]
    assert Key("[", "[") not in keys
    assert Key("A", "A") not in keys


# --- ctypes structures --------------------------------------------------------


def test_console_structures_are_defined_on_every_platform():
    # Portable definitions exist everywhere; they only match the Windows SDK
    # on Windows (c_wchar is 2 bytes there, 4 bytes elsewhere), which is what
    # the nt-only test below pins.
    assert ctypes.sizeof(keys_mod._InputRecord) >= ctypes.sizeof(keys_mod._KeyEventRecord)
    assert keys_mod._InputRecord.Event.offset >= 2


@pytest.mark.skipif(os.name != "nt", reason="SDK sizes only hold on Windows")
def test_console_structures_match_the_windows_sdk():
    assert ctypes.sizeof(keys_mod._KeyEventRecord) == 16
    assert ctypes.sizeof(keys_mod._InputRecord) == 20
    assert keys_mod._InputRecord.Event.offset == 4
    assert keys_mod._KeyEventRecord.wVirtualKeyCode.offset == 6
    assert keys_mod._KeyEventRecord.uChar.offset == 10
    assert keys_mod._KeyEventRecord.dwControlKeyState.offset == 12


@pytest.mark.skipif(os.name != "nt", reason="real ctypes records only exist on Windows")
def test_real_ctypes_record_maps_keys():
    record = keys_mod._InputRecord()
    record.EventType = keys_mod._KEY_EVENT
    record.Event.bKeyDown = True
    record.Event.wVirtualKeyCode = _VK_UP
    record.Event.uChar.UnicodeChar = "\x00"
    assert keys_mod._key_from_console_event(record.Event) == Key("up")

    record.Event.bKeyDown = False
    assert keys_mod._key_from_console_event(record.Event) is None

    record.Event.bKeyDown = True
    record.Event.wVirtualKeyCode = 0
    record.Event.uChar.UnicodeChar = "中"
    assert keys_mod._key_from_console_event(record.Event) == Key("中", "中")


# --- kernel32 prototypes and reader constants --------------------------------


@pytest.mark.skipif(os.name != "nt", reason="kernel32 only exists on Windows")
def test_console_input_prototypes_are_declared():
    # PeekConsoleInputW must exist with the ReadConsoleInputW signature: the
    # console reader relies on it for non-blocking polling (a blocking read
    # could never settle a lone ESC).  Only the signature is asserted here --
    # calling it would need a real console handle, which this environment
    # does not have.
    api = keys_mod._kernel32()
    assert hasattr(api, "PeekConsoleInputW")
    assert api.PeekConsoleInputW.argtypes == api.ReadConsoleInputW.argtypes
    assert api.PeekConsoleInputW.restype == api.ReadConsoleInputW.restype


def test_settle_threshold_and_batch_size_are_defined():
    # One shared settle threshold (both reader paths) and the console batch
    # size are pinned so neither drifts silently.
    assert keys_mod._SETTLE_SECONDS == 0.050
    assert keys_mod._CONSOLE_BATCH == 32


# --- ScriptedKeys -------------------------------------------------------------


async def test_scripted_keys_replays_then_reports_eof():
    source = ScriptedKeys([Key("a", "a"), Paste("x"), None, Key("z", "z")])
    assert isinstance(source, KeySource)
    assert await source.read() == Key("a", "a")
    assert await source.read() == Paste("x")
    assert await source.read() is None  # a one-shot EOF signal, delivered
    assert await source.read() == Key("z", "z")
    assert await source.read() is None  # sequence exhausted: EOF forever


async def test_scripted_keys_defaults_to_an_empty_sequence():
    assert await ScriptedKeys().read() is None


# --- RawTerminalKeys over a pipe (cooked fallback, real threads) ---------------


def _pipe_pair(payload: bytes) -> tuple[int, int]:
    """A pipe whose write end already holds ``payload`` and is then closed."""
    read_fd, write_fd = os.pipe()
    os.write(write_fd, payload)
    os.close(write_fd)
    return read_fd, write_fd


def _shutdown_pipe(source: RawTerminalKeys, read_fd: int, write_fd: int) -> None:
    """Stop ``source`` and release its pipe without deadlocking its reader.

    Closing a descriptor that another thread is blocked reading on can block
    on Windows (the CRT keeps the fd busy across a blocking read), so the
    write end goes first -- handing the reader its EOF -- and the reader is
    joined before the read end is closed.
    """
    source.close()
    try:
        os.close(write_fd)  # EOF for a reader still blocked in os.read
    except OSError:
        pass
    thread = source._thread
    if thread is not None:
        thread.join(timeout=1.0)
    try:
        if thread is None or not thread.is_alive():
            os.close(read_fd)
    except OSError:
        pass


async def test_pipe_fallback_decodes_bytes_until_eof():
    read_fd, write_fd = _pipe_pair(b"a\x1b[A")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        assert source.cooked_fallback is True
        assert await source.read() == Key("a", "a")
        assert await source.read() == Key("up")
        assert await source.read() is None  # EOF sentinel
    finally:
        _shutdown_pipe(source, read_fd, write_fd)


async def test_cooked_fallback_delivers_a_whole_line_as_characters():
    read_fd, write_fd = _pipe_pair(b"hi\r")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        assert source.cooked_fallback is True
        assert [await source.read() for _ in range(3)] == [
            Key("h", "h"),
            Key("i", "i"),
            Key("enter"),
        ]
    finally:
        _shutdown_pipe(source, read_fd, write_fd)


async def test_read_before_start_returns_none():
    read_fd, write_fd = _pipe_pair(b"")
    source = RawTerminalKeys(read_fd)
    try:
        assert await source.read() is None
    finally:
        _shutdown_pipe(source, read_fd, write_fd)


async def test_close_wakes_a_pending_read_with_the_eof_sentinel():
    read_fd, write_fd = os.pipe()  # never written to: the reader blocks
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        pending = asyncio.create_task(source.read())
        await asyncio.sleep(0)  # let the read reach the executor's queue.get
        source.close()
        assert await asyncio.wait_for(pending, timeout=5) is None
    finally:
        _shutdown_pipe(source, read_fd, write_fd)


def test_close_queues_the_eof_sentinel():
    read_fd, write_fd = _pipe_pair(b"")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        source.close()
        assert source._queue.get(timeout=1) is None
        assert source.cooked_fallback is True
    finally:
        _shutdown_pipe(source, read_fd, write_fd)


def test_close_is_idempotent_and_double_start_spawns_one_thread():
    read_fd, write_fd = _pipe_pair(b"")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        thread = source._thread
        source.start()
        assert source._thread is thread
        source.close()
        source.close()  # idempotent
    finally:
        _shutdown_pipe(source, read_fd, write_fd)
