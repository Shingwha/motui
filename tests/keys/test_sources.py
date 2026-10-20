"""The key sources: Windows console records, the VT byte path, pipe fallback
and the source lifecycle.

The console record mappers are pure and platform-free: records replay
through the one decoder, so the same logical gesture yields the same event
through console records and raw VT bytes.  ``RawTerminalKeys`` is exercised
over real pipes through its cooked fallback, EOF and close lifecycle.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from motui.kernel.events import (
    FocusEvent,
    KeyEvent,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)
from motui.keys import KeyDecoder, RawTerminalKeys
from motui.keys.console import keys_from_console_events, windows_input_mode

_ENABLE_PROCESSED_INPUT = 0x0001
_ENABLE_LINE_INPUT = 0x0002
_ENABLE_ECHO_INPUT = 0x0004
_ENABLE_QUICK_EDIT_MODE = 0x0040
_ENABLE_EXTENDED_FLAGS = 0x0080
_ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

_TYPICAL_CONSOLE_MODE = 0x01F7

_VK_PRIOR = 0x21
_VK_NEXT = 0x22
_VK_LEFT = 0x25
_VK_UP = 0x26

_KEY_EVENT = 1
_MOUSE_EVENT = 2
_FOCUS_EVENT = 16
_WINDOW_BUFFER_SIZE_EVENT = 4

_LEFT_BUTTON = 0x0001
_RIGHT_BUTTON = 0x0002
_MIDDLE_BUTTON = 0x0004

_MOUSE_MOVED = 0x0001
_DOUBLE_CLICK = 0x0002
_MOUSE_WHEELED = 0x0004
_WHEEL_NOTCH = 120


def key_record(vk=0, char="\x00", *, down=True, repeat=1, ctrl=0):
    return (_KEY_EVENT, down, repeat, vk, char, ctrl)


def mouse_record(x=0, y=0, *, buttons=0, flags=0, ctrl=0):
    return (_MOUSE_EVENT, x, y, buttons, flags, ctrl)


def wheel_record(x, y, notches):
    return mouse_record(
        x, y, buttons=(notches << 16) & 0xFFFFFFFF, flags=_MOUSE_WHEELED
    )


def byte_events(text: str):
    return [key_record(char=ch) for ch in text]


def test_input_mode_clears_line_echo_and_quick_edit_and_sets_vt_input():
    new = windows_input_mode(_TYPICAL_CONSOLE_MODE)
    assert new & _ENABLE_LINE_INPUT == 0
    assert new & _ENABLE_ECHO_INPUT == 0
    assert new & _ENABLE_VIRTUAL_TERMINAL_INPUT != 0
    assert new & _ENABLE_PROCESSED_INPUT != 0
    assert new & _ENABLE_QUICK_EDIT_MODE == 0
    assert new & _ENABLE_EXTENDED_FLAGS != 0
    assert windows_input_mode(0) == (
        _ENABLE_VIRTUAL_TERMINAL_INPUT | _ENABLE_EXTENDED_FLAGS
    )
    assert windows_input_mode(new) == new


def test_console_bytes_assemble_escape_sequences_across_records():
    assert keys_from_console_events(byte_events("\x1b[A")) == [KeyEvent("up")]
    assert keys_from_console_events(byte_events("\r")) == [KeyEvent("enter")]
    assert keys_from_console_events(byte_events("\x7f")) == [KeyEvent("backspace")]
    assert keys_from_console_events(byte_events("\x1b[5~")) == [KeyEvent("page_up")]
    assert keys_from_console_events(byte_events("a\t")) == [
        KeyEvent("a", "a"),
        KeyEvent("tab"),
    ]
    assert keys_from_console_events(byte_events("\x01\x03\x1a")) == [
        KeyEvent("c-a"),
        KeyEvent("c-c"),
        KeyEvent("c-z"),
    ]


def test_console_code_points_arrive_utf8_and_nul_falls_back_to_virtual_keys():
    assert keys_from_console_events(byte_events("\u4f60\u597d")) == [
        KeyEvent("\u4f60", "\u4f60"),
        KeyEvent("\u597d", "\u597d"),
    ]
    cases = [
        (_VK_LEFT, "left"),
        (_VK_UP, "up"),
        (_VK_PRIOR, "page_up"),
        (_VK_NEXT, "page_down"),
        (0x0D, "enter"),
        (0x1B, "escape"),
    ]
    for vk, name in cases:
        assert keys_from_console_events([key_record(vk)]) == [KeyEvent(name)]
    assert keys_from_console_events([key_record(0x41, "\x00", ctrl=0x0008)]) == [
        KeyEvent("c-a")
    ]


def test_console_character_wins_over_the_virtual_key_and_key_up_is_ignored():
    assert keys_from_console_events([key_record(_VK_UP, "A")]) == [KeyEvent("A", "A")]
    assert keys_from_console_events([key_record(_VK_UP, "\x00", down=False)]) == []


def test_console_press_drag_and_release_surface_all_three_kinds():
    assert keys_from_console_events(
        [
            mouse_record(5, 3, buttons=_LEFT_BUTTON),
            mouse_record(5, 4, buttons=_LEFT_BUTTON, flags=_MOUSE_MOVED),
            mouse_record(5, 4),
        ]
    ) == [
        MouseEvent("left", x=5, y=3, kind="press"),
        MouseEvent("left", x=5, y=4, kind="motion"),
        MouseEvent("left", x=5, y=4, kind="release"),
    ]


def test_console_buttons_map_to_the_event_model_names():
    for buttons, name in (
        (_LEFT_BUTTON, "left"),
        (_RIGHT_BUTTON, "right"),
        (_MIDDLE_BUTTON, "middle"),
    ):
        assert keys_from_console_events([mouse_record(2, 5, buttons=buttons)]) == [
            MouseEvent(name, x=2, y=5, kind="press")
        ]


def test_a_console_double_click_is_two_presses():
    assert keys_from_console_events(
        [
            mouse_record(4, 6, buttons=_LEFT_BUTTON),
            mouse_record(4, 6),
            mouse_record(4, 6, buttons=_LEFT_BUTTON, flags=_DOUBLE_CLICK),
        ]
    ) == [
        MouseEvent("left", x=4, y=6, kind="press"),
        MouseEvent("left", x=4, y=6, kind="release"),
        MouseEvent("left", x=4, y=6, kind="press"),
    ]


def test_console_wheel_reports_up_and_down():
    for notches, name in ((_WHEEL_NOTCH, "wheel_up"), (-_WHEEL_NOTCH, "wheel_down")):
        assert keys_from_console_events([wheel_record(7, 2, notches)]) == [
            MouseEvent(name, x=7, y=2, kind="wheel")
        ]


def test_console_bare_motion_follows_the_hover_switch():
    move = [mouse_record(3, 3, flags=_MOUSE_MOVED)]
    assert keys_from_console_events(move) == []
    assert keys_from_console_events(move, hover=True) == [
        MouseEvent("none", x=3, y=3, kind="motion")
    ]


def test_a_console_move_with_a_button_transition_is_not_a_bare_motion():
    assert keys_from_console_events(
        [mouse_record(1, 1, buttons=_RIGHT_BUTTON, flags=_MOUSE_MOVED)]
    ) == [MouseEvent("right", x=1, y=1, kind="press")]
    assert keys_from_console_events(
        [
            mouse_record(1, 1, buttons=_LEFT_BUTTON),
            mouse_record(1, 1, flags=_MOUSE_MOVED),
        ],
        hover=True,
    ) == [
        MouseEvent("left", x=1, y=1, kind="press"),
        MouseEvent("left", x=1, y=1, kind="release"),
    ]
    assert keys_from_console_events([mouse_record(0, 0)]) == []


def test_console_mouse_reports_match_the_vt_path():
    console = keys_from_console_events(
        [
            mouse_record(2, 5, buttons=_LEFT_BUTTON),
            mouse_record(2, 6, buttons=_LEFT_BUTTON, flags=_MOUSE_MOVED),
            mouse_record(2, 6),
            mouse_record(4, 5, buttons=_RIGHT_BUTTON),
            wheel_record(4, 5, _WHEEL_NOTCH),
        ]
    )
    vt = KeyDecoder().feed(
        b"\x1b[<0;3;6M\x1b[<32;3;7M\x1b[<0;3;7m\x1b[<2;5;6M\x1b[<64;5;6M"
    )
    assert console == vt


def test_console_repeat_count_surfaces_repeated_presses():
    assert keys_from_console_events([key_record(_VK_UP, repeat=3)]) == [
        KeyEvent("up"),
        KeyEvent("up", kind="repeat"),
        KeyEvent("up", kind="repeat"),
    ]
    assert keys_from_console_events([key_record(0, "a", repeat=2)]) == [
        KeyEvent("a", "a"),
        KeyEvent("a", "a", kind="repeat"),
    ]
    assert keys_from_console_events([key_record(0, "a", down=False, repeat=3)]) == []


def test_console_focus_and_resize_records_surface_as_events():
    assert keys_from_console_events([(_FOCUS_EVENT, 1)]) == [FocusEvent(True)]
    assert keys_from_console_events([(_FOCUS_EVENT, 0)]) == [FocusEvent(False)]
    assert keys_from_console_events([(_WINDOW_BUFFER_SIZE_EVENT, 120, 40)]) == [
        ResizeEvent(120, 40)
    ]


def pipe_with(payload: bytes) -> int:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, payload)
    os.close(write_fd)
    return read_fd


async def test_the_cooked_pipe_fallback_delivers_the_decoded_keys():
    cases = [
        (b"a\x1b[A", [KeyEvent("a", "a"), KeyEvent("up")]),
        (b"hi\r", [KeyEvent("h", "h"), KeyEvent("i", "i"), KeyEvent("enter")]),
        (b"a\x1b", [KeyEvent("a", "a"), KeyEvent("escape")]),
    ]
    for payload, expected in cases:
        read_fd = pipe_with(payload)
        source = RawTerminalKeys(read_fd)
        try:
            source.start()
            assert source.cooked_fallback is True
            for want in [*expected, None]:
                assert await asyncio.wait_for(source.read(), timeout=5) == want
        finally:
            source.close()
            os.close(read_fd)


async def test_read_before_start_returns_none():
    read_fd = pipe_with(b"")
    source = RawTerminalKeys(read_fd)
    try:
        assert await source.read() is None
    finally:
        source.close()
        os.close(read_fd)


async def test_close_is_idempotent_and_a_second_start_spawns_one_reader():
    read_fd = pipe_with(b"ab")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        source.start()
        assert await asyncio.wait_for(source.read(), timeout=5) == KeyEvent("a", "a")
        assert await asyncio.wait_for(source.read(), timeout=5) == KeyEvent("b", "b")
        assert await asyncio.wait_for(source.read(), timeout=5) is None
        source.close()
        source.close()
        assert await source.read() is None
    finally:
        source.close()
        os.close(read_fd)


async def test_eof_is_sticky_and_never_hangs_a_second_read():
    read_fd = pipe_with(b"ab")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        assert await asyncio.wait_for(source.read(), timeout=5) == KeyEvent("a", "a")
        assert await asyncio.wait_for(source.read(), timeout=5) == KeyEvent("b", "b")
        assert await asyncio.wait_for(source.read(), timeout=5) is None
        assert await asyncio.wait_for(source.read(), timeout=5) is None
    finally:
        source.close()
        os.close(read_fd)


async def test_eof_flushes_the_decoders_unfinished_state():
    read_fd = pipe_with(b"\x1b[200~raw")
    source = RawTerminalKeys(read_fd)
    try:
        source.start()
        assert await asyncio.wait_for(source.read(), timeout=5) == PasteEvent("raw")
        assert await asyncio.wait_for(source.read(), timeout=5) is None
    finally:
        source.close()
        os.close(read_fd)
