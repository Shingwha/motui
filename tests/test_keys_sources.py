"""Tests for motui.keys.sources (console seams and RawTerminalKeys).

The pure console seams are pinned here, the live-console path left for
real-machine acceptance; ``RawTerminalKeys`` runs over real pipes.
"""

import asyncio
import os

import pytest

from motui.kernel.events import (
    Key,
    KeySource,
    MouseEvent,
    Paste,
    ScriptedKeys,
)
from motui.keys import KeyDecoder, RawTerminalKeys
from motui.keys.console import keys_from_console_events, windows_input_mode

# Windows console input mode bits (wincon.h).
_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
_ENABLE_QUICK_EDIT_MODE = 0x0040
_ENABLE_EXTENDED_FLAGS = 0x0080
_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

# A typical console default: PROCESSED | LINE | ECHO | MOUSE | INSERT |
# QUICK_EDIT | EXTENDED | AUTO_POSITION.
_TYPICAL_CONSOLE_MODE = 0x01F7

# Virtual-key codes (winuser.h).
_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_LEFT = 0x25
_VK_UP = 0x26


# --- windows_input_mode (pure) ------------------------------------------------


def test_input_mode_clears_line_and_echo_and_sets_vt_input():
    new = windows_input_mode(_TYPICAL_CONSOLE_MODE)
    assert new & _ENABLE_LINE_INPUT == 0
    assert new & _ENABLE_ECHO_INPUT == 0
    assert new & _ENABLE_VIRTUAL_TERMINAL_INPUT != 0
    # Every other bit passes through untouched -- notably PROCESSED_INPUT,
    # which keeps Ctrl-C raising a real KeyboardInterrupt.
    assert new & _ENABLE_PROCESSED_INPUT != 0
    assert new & 0x0130 == _TYPICAL_CONSOLE_MODE & 0x0130  # MOUSE|INSERT|AUTO_POSITION
    # QuickEdit is cleared (the console host must not steal the mouse from
    # the application's own selection) and EXTENDED_FLAGS is set alongside
    # it, or Windows ignores the QuickEdit change.
    assert new & _ENABLE_QUICK_EDIT_MODE == 0
    assert new & _ENABLE_EXTENDED_FLAGS != 0
    assert windows_input_mode(0) == _ENABLE_VIRTUAL_TERMINAL_INPUT | _ENABLE_EXTENDED_FLAGS
    assert windows_input_mode(new) == new  # idempotent


# --- console records -> byte stream (pure replay) ------------------------------


# INPUT_RECORD event types the record mappers know.
_KEY_EVENT = 1
_MOUSE_EVENT = 2

# dwButtonState bits for the three named buttons (wincon.h).
_LEFT_BUTTON = 0x0001
_RIGHT_BUTTON = 0x0002
_MIDDLE_BUTTON = 0x0004

# MOUSE_EVENT_RECORD dwFlags bits (wincon.h).
_MOUSE_MOVED = 0x0001
_DOUBLE_CLICK = 0x0002
_MOUSE_WHEELED = 0x0004

# The wheel delta rides in dwButtonState's high word, signed.
_WHEEL_NOTCH = 120


def key_event(vk=0, char="\x00", *, down=True, ctrl=0):
    """One console record as a ``(_KEY_EVENT, bKeyDown, vk, char, ctrl)`` tuple."""
    return (_KEY_EVENT, down, vk, char, ctrl)


def mouse_event(x=0, y=0, *, buttons=0, flags=0, ctrl=0):
    """One console record as ``(_MOUSE_EVENT, x, y, buttons, flags, ctrl)``."""
    return (_MOUSE_EVENT, x, y, buttons, flags, ctrl)


def wheel(x, y, notches):
    """A vertical-wheel record: the signed delta sits in the high word."""
    return mouse_event(x, y, buttons=(notches << 16) & 0xFFFFFFFF, flags=_MOUSE_WHEELED)


def _byte_events(text: str):
    """Records delivering ``text`` one character per record.

    That is how ``ENABLE_VIRTUAL_TERMINAL_INPUT`` delivers input: each record
    carries one byte of the VT sequence in ``UnicodeChar``.
    """
    return [key_event(char=ch) for ch in text]


def test_console_bytes_assemble_escape_sequences_across_records():
    # ESC [ A arrives as three records; the decoder assembles them into up
    # instead of leaking literal "[" and "A" (the W7 bug).
    assert keys_from_console_events(_byte_events("\x1b[A")) == [Key("up")]
    assert keys_from_console_events(_byte_events("\r")) == [Key("enter")]
    assert keys_from_console_events(_byte_events("\x7f")) == [Key("backspace")]
    assert keys_from_console_events(_byte_events("\x1b[5~")) == [Key("page_up")]
    assert keys_from_console_events(_byte_events("a\t")) == [Key("a", "a"), Key("tab")]
    assert keys_from_console_events(_byte_events("\x01\x03\x1a")) == [
        Key("c-a"),
        Key("c-c"),
        Key("c-z"),
    ]


def test_console_code_points_arrive_utf8_encoded():
    # A wide character is one record's character; the decoder sees its UTF-8
    # bytes and yields a single key per code point.
    assert keys_from_console_events(_byte_events("你好")) == [Key("你", "你"), Key("好", "好")]


def test_console_nul_character_falls_back_to_the_virtual_key_table():
    assert keys_from_console_events([key_event(_VK_LEFT)]) == [Key("left")]
    assert keys_from_console_events([key_event(_VK_UP)]) == [Key("up")]
    assert keys_from_console_events([key_event(_VK_PRIOR)]) == [Key("page_up")]
    assert keys_from_console_events([key_event(_VK_NEXT)]) == [Key("page_down")]
    assert keys_from_console_events([key_event(0x0D)]) == [Key("enter")]
    assert keys_from_console_events([key_event(0x1B)]) == [Key("escape")]
    # Ctrl held with a letter virtual key and no character delivered.
    assert keys_from_console_events([key_event(0x41, "\x00", ctrl=0x0008)]) == [Key("c-a")]
    assert keys_from_console_events([key_event(0x5A, "\x00", ctrl=0x0004)]) == [Key("c-z")]


def test_console_character_wins_over_the_virtual_key_no_double_enqueue():
    # A record carrying both a character and a virtual key (a VT-input
    # console keeps filling the VK field) feeds the character only.
    assert keys_from_console_events([key_event(_VK_UP, "A")]) == [Key("A", "A")]
    assert keys_from_console_events([key_event(0x0D, "\r")]) == [Key("enter")]
    # Key-up records carry nothing.
    assert keys_from_console_events([key_event(_VK_UP, "\x00", down=False)]) == []
    assert keys_from_console_events([key_event(0x41, "a", down=False)]) == []


# --- mouse records -> SGR-1006 reports (pure replay) --------------------------


def test_console_press_drag_and_release_surface_all_three_kinds():
    # One logical gesture: the left button down, a drag one row, release.
    # The console reports the full button state per record, so the mapper
    # reads the transitions and feeds the one decoder SGR-1006 payloads --
    # the events are the VT path's own, same names and kinds.
    assert keys_from_console_events(
        [
            mouse_event(5, 3, buttons=_LEFT_BUTTON),
            mouse_event(5, 4, buttons=_LEFT_BUTTON, flags=_MOUSE_MOVED),
            mouse_event(5, 4),
        ]
    ) == [
        MouseEvent("left", button=0, x=5, y=3, kind="press"),
        MouseEvent("left", button=0, x=5, y=4, kind="motion"),
        MouseEvent("left", button=0, x=5, y=4, kind="release"),
    ]


@pytest.mark.parametrize(
    "buttons, name, button",
    [
        (_LEFT_BUTTON, "left", 0),
        (_RIGHT_BUTTON, "right", 2),
        (_MIDDLE_BUTTON, "middle", 1),
    ],
)
def test_console_buttons_map_to_the_event_model_names(buttons, name, button):
    assert keys_from_console_events([mouse_event(2, 5, buttons=buttons)]) == [
        MouseEvent(name, button=button, x=2, y=5, kind="press")
    ]


def test_console_double_click_is_two_presses():
    # The console flags the second click DOUBLE_CLICK; the mapper ignores
    # the flag -- the timing policy belongs to the controller -- and reports
    # the two presses the gesture physically is.
    assert keys_from_console_events(
        [
            mouse_event(4, 6, buttons=_LEFT_BUTTON),
            mouse_event(4, 6),
            mouse_event(4, 6, buttons=_LEFT_BUTTON, flags=_DOUBLE_CLICK),
        ]
    ) == [
        MouseEvent("left", button=0, x=4, y=6, kind="press"),
        MouseEvent("left", button=0, x=4, y=6, kind="release"),
        MouseEvent("left", button=0, x=4, y=6, kind="press"),
    ]


@pytest.mark.parametrize(
    "notches, name, button",
    [(_WHEEL_NOTCH, "wheel_up", 0), (-_WHEEL_NOTCH, "wheel_down", 1)],
)
def test_console_wheel_reports_up_and_down(notches, name, button):
    # The wheel is discrete, like the VT path: a press-kind report whose
    # name TUI.read_key's scroll interception consumes unchanged.
    assert keys_from_console_events([wheel(7, 2, notches)]) == [
        MouseEvent(name, button=button, x=7, y=2, kind="press")
    ]


def test_console_bare_motion_follows_the_hover_switch():
    # The record path has no 1002/1003 switch of its own: the hover switch
    # is its 1003 counterpart.  Off (the default) a bare pointer move stays
    # unreported, exactly as the default VT path never sends 35; on, it
    # decodes to the button-free motion through the one decoder.
    move = [mouse_event(3, 3, flags=_MOUSE_MOVED)]
    assert keys_from_console_events(move) == []
    assert keys_from_console_events(move, hover=True) == [
        MouseEvent("none", button=0, x=3, y=3, kind="motion")
    ]


def test_console_release_that_also_moved_is_no_bare_motion():
    # A release transition rides MOUSE_MOVED without being a pointer move:
    # even with hover on it reports the release only, never a motion.
    assert keys_from_console_events(
        [
            mouse_event(1, 1, buttons=_LEFT_BUTTON),
            mouse_event(1, 1, flags=_MOUSE_MOVED),
        ],
        hover=True,
    ) == [
        MouseEvent("left", button=0, x=1, y=1, kind="press"),
        MouseEvent("left", button=0, x=1, y=1, kind="release"),
    ]


def test_console_press_that_also_moved_is_a_press_not_a_motion():
    # A click landing right after a pointer move carries MOUSE_MOVED; the
    # VT path never mixes a press and a motion bit into one report.
    assert keys_from_console_events(
        [mouse_event(1, 1, buttons=_RIGHT_BUTTON, flags=_MOUSE_MOVED)]
    ) == [MouseEvent("right", button=2, x=1, y=1, kind="press")]


def test_console_release_with_no_prior_press_reports_nothing():
    # A stream cannot open on a release: the held-button state starts empty,
    # and no phantom button is ever named.
    assert keys_from_console_events([mouse_event(0, 0)]) == []
    assert keys_from_console_events([mouse_event(0, 0, buttons=0x0008)]) == []  # extra


def test_console_mouse_reports_match_the_vt_path():
    # The parity contract: the mapper synthesizes SGR-1006 payloads, so one
    # logical gesture decodes to the very same events through the console
    # records and through raw VT bytes.
    console = keys_from_console_events(
        [
            mouse_event(2, 5, buttons=_LEFT_BUTTON),
            mouse_event(2, 6, buttons=_LEFT_BUTTON, flags=_MOUSE_MOVED),
            mouse_event(2, 6),
            mouse_event(4, 5, buttons=_RIGHT_BUTTON),
            wheel(4, 5, _WHEEL_NOTCH),
        ]
    )
    decoder = KeyDecoder()
    vt = decoder.feed(b"\x1b[<0;3;6M\x1b[<32;3;7M\x1b[<0;3;7m\x1b[<2;5;6M\x1b[<64;5;6M")
    assert console == vt


def test_console_stream_mixes_key_and_mouse_records():
    assert keys_from_console_events(
        [
            *_byte_events("a"),
            mouse_event(1, 1, buttons=_LEFT_BUTTON),
            key_event(_VK_LEFT),
            mouse_event(1, 1),
        ]
    ) == [
        Key("a", "a"),
        MouseEvent("left", button=0, x=1, y=1, kind="press"),
        Key("left"),
        MouseEvent("left", button=0, x=1, y=1, kind="release"),
    ]


# --- ScriptedKeys -------------------------------------------------------------


async def test_scripted_keys_replays_then_reports_eof():
    source = ScriptedKeys([Key("a", "a"), Paste("x"), None, Key("z", "z")])
    assert isinstance(source, KeySource)
    assert await source.read() == Key("a", "a")
    assert await source.read() == Paste("x")
    assert await source.read() is None  # a one-shot EOF signal, delivered
    assert await source.read() == Key("z", "z")
    assert await source.read() is None  # sequence exhausted: EOF forever


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
    joined before the read end is closed.  Teardown mechanics only: no
    contract is asserted through the private thread handle.
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


@pytest.mark.parametrize(
    "payload, expected",
    [
        (b"a\x1b[A", [Key("a", "a"), Key("up")]),  # an escape sequence assembles
        (b"hi\r", [Key("h", "h"), Key("i", "i"), Key("enter")]),  # a line, as characters
        (b"a\x1b", [Key("a", "a"), Key("escape")]),  # EOF backstops a pending ESC
    ],
)
async def test_the_cooked_pipe_fallback_delivers_the_decoded_keys(payload, expected):
    read_fd, write_fd = _pipe_pair(payload)
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        assert source.cooked_fallback is True  # a pipe is not a terminal
        for want in [*expected, None]:  # every stream ends on the EOF sentinel
            assert await asyncio.wait_for(source.read(), timeout=5) == want
    finally:
        _shutdown_pipe(source, read_fd, write_fd)


# select() probes sockets only on Windows, and os.read() refuses socket fds
# there, so the deadline-waiting branch of _read_bytes cannot be exercised
# end-to-end on Windows: the byte path on Windows is the console path plus
# the cooked fallback, which blocks in os.read with EOF/close backstopping a
# pending tail.
_posix_only = pytest.mark.skipif(
    os.name == "nt",
    reason="select() cannot probe a pipe fd on Windows (sockets only)",
)


@_posix_only
async def test_pending_escape_settles_after_the_silence_window():
    # A lone ESC with no continuation must settle into the escape key after
    # the settle window instead of hanging forever.  Real time drives the
    # default 50 ms window: the pipe is written once and never again, the
    # reader thread's select deadline expires, and the escape key arrives.
    read_fd, write_fd = os.pipe()  # stays open: no EOF rescues the ESC
    os.write(write_fd, b"a\x1b")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        assert source.cooked_fallback is True
        assert await asyncio.wait_for(source.read(), timeout=5) == Key("a", "a")
        assert await asyncio.wait_for(source.read(), timeout=5) == Key("escape")
    finally:
        _shutdown_pipe(source, read_fd, write_fd)


async def test_read_before_start_returns_none():
    read_fd, write_fd = _pipe_pair(b"")
    source = RawTerminalKeys(read_fd)
    try:
        assert await source.read() is None  # never started: nothing will arrive
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


async def test_close_is_idempotent_and_double_start_spawns_one_reader():
    read_fd, write_fd = _pipe_pair(b"ab")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        source.start()  # a second start must not spawn a second reader
        assert await source.read() == Key("a", "a")
        assert await source.read() == Key("b", "b")
        assert await source.read() is None  # each byte exactly once, then EOF
        source.close()
        source.close()  # idempotent
        assert await source.read() is None  # a closed source never yields again
    finally:
        _shutdown_pipe(source, read_fd, write_fd)
