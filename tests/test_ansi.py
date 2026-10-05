"""Tests for mocode_tui.core.ansi.

Every escape byte the toolkit emits is constructed here; ``cursor_position``
is 1-based, invalid coordinates emit nothing; the mouse pair reverses, and
the OSC 52 clipboard sequence carries base64 of UTF-8.
"""

import base64

import pytest

from mocode_tui.core.ansi import (
    clear_line,
    clear_screen,
    copy_clipboard,
    cursor_position,
    disable_mouse_tracking,
    enable_mouse_tracking,
    enable_vt,
    enter_alt_screen,
    hide_cursor,
    leave_alt_screen,
    show_cursor,
)


def test_clear_line_and_clear_screen():
    assert clear_line() == "\x1b[K"
    assert clear_screen() == "\x1b[2J"


def test_cursor_position_is_one_based():
    assert cursor_position(1, 1) == "\x1b[1;1H"
    assert cursor_position(24, 80) == "\x1b[24;80H"
    assert cursor_position(0, 1) == ""  # invalid coordinate: nothing
    assert cursor_position(1, 0) == ""


def test_cursor_hide_show_and_alt_screen_pair():
    assert hide_cursor() == "\x1b[?25l"
    assert show_cursor() == "\x1b[?25h"
    assert enter_alt_screen() == "\x1b[?1049h"
    assert leave_alt_screen() == "\x1b[?1049l"


def test_mouse_tracking_pair():
    # 1000 + 1002 + SGR 1006 on, disable the exact reverse order (DESIGN.md):
    # 1002 motion reports are new since selection W1, an intentional
    # contract change -- a drag gesture cannot exist without them.
    assert enable_mouse_tracking() == "\x1b[?1000h\x1b[?1002h\x1b[?1006h"
    assert disable_mouse_tracking() == "\x1b[?1006l\x1b[?1002l\x1b[?1000l"


def test_enable_vt_returns_bool():
    # The probe decides liveness on Windows; any failure means non-live.
    assert isinstance(enable_vt(), bool)


def test_copy_clipboard_is_the_osc52_sequence_with_base64_of_utf8():
    assert copy_clipboard("hi") == "\x1b]52;c;aGk=\x07"


@pytest.mark.parametrize(
    "text",
    ["", "plain", "two\nlines", "日本語のテキスト", "emoji 🙂 and quotes \"'`"],
)
def test_copy_clipboard_payload_round_trips_as_utf8_base64(text: str):
    sequence = copy_clipboard(text)
    assert sequence.startswith("\x1b]52;c;") and sequence.endswith("\x07")
    payload = sequence[len("\x1b]52;c;") : -1]
    assert base64.b64decode(payload).decode("utf-8") == text
