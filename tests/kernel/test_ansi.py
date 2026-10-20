"""The ANSI byte vocabulary: cursor, erase, mouse, paste, synchronization,
OSC 52, title, hyperlinks and cursor shapes.

This is the layer where the bytes are the product: every sequence is pinned
exactly.  Coordinates are 1-based, invalid coordinates emit nothing, and
control bytes are scrubbed from every OSC payload.
"""

from __future__ import annotations

import base64

import pytest

from motui.kernel.ansi import (
    CLEAR_LINE,
    begin_sync_update,
    clear_screen,
    copy_clipboard,
    cursor_position,
    cursor_shape,
    disable_bracketed_paste,
    disable_focus_events,
    disable_mouse_tracking,
    enable_bracketed_paste,
    enable_focus_events,
    enable_mouse_tracking,
    end_sync_update,
    enter_alt_screen,
    hide_cursor,
    hyperlink_close,
    hyperlink_open,
    leave_alt_screen,
    set_window_title,
    show_cursor,
)


def test_clear_line_and_clear_screen():
    assert CLEAR_LINE == "\x1b[K"
    assert clear_screen() == "\x1b[2J"


def test_cursor_position_is_one_based_and_rejects_invalid_coordinates():
    assert cursor_position(1, 1) == "\x1b[1;1H"
    assert cursor_position(24, 80) == "\x1b[24;80H"
    assert cursor_position(0, 1) == ""
    assert cursor_position(1, 0) == ""


def test_cursor_hide_show_and_alt_screen_pair():
    assert hide_cursor() == "\x1b[?25l"
    assert show_cursor() == "\x1b[?25h"
    assert enter_alt_screen() == "\x1b[?1049h"
    assert leave_alt_screen() == "\x1b[?1049l"


def test_mouse_tracking_pair_and_the_hover_mode():
    assert enable_mouse_tracking() == "\x1b[?1000h\x1b[?1002h\x1b[?1006h"
    assert disable_mouse_tracking() == (
        "\x1b[?1006l\x1b[?1003l\x1b[?1002l\x1b[?1000l"
    )
    assert enable_mouse_tracking(hover=True) == "\x1b[?1000h\x1b[?1003h\x1b[?1006h"
    assert disable_mouse_tracking(hover=True) == disable_mouse_tracking()


def test_synchronized_update_pair():
    assert begin_sync_update() == "\x1b[?2026h"
    assert end_sync_update() == "\x1b[?2026l"


def test_bracketed_paste_and_focus_pairs():
    assert enable_bracketed_paste() == "\x1b[?2004h"
    assert disable_bracketed_paste() == "\x1b[?2004l"
    assert enable_focus_events() == "\x1b[?1004h"
    assert disable_focus_events() == "\x1b[?1004l"


def test_copy_clipboard_is_osc52_with_base64_of_utf8():
    assert copy_clipboard("hi") == "\x1b]52;c;aGk=\x07"
    for text in ("", "plain", "two\nlines", "\u65e5\u672c\u8a9e", "emoji \U0001F642"):
        sequence = copy_clipboard(text)
        payload = sequence[len("\x1b]52;c;") : -1]
        assert base64.b64decode(payload).decode("utf-8") == text


def test_window_title_is_osc2_with_control_bytes_scrubbed():
    assert set_window_title("hi") == "\x1b]2;hi\x07"
    assert set_window_title("a\x1b]2;evil\x07b\nc") == "\x1b]2;a]2;evilbc\x07"
    assert set_window_title("") == "\x1b]2;\x07"


def test_hyperlink_pair_is_st_terminated_and_scrubbed():
    assert hyperlink_open("https://example.invalid") == (
        "\x1b]8;;https://example.invalid\x1b\\"
    )
    assert hyperlink_close() == "\x1b]8;;\x1b\\"
    assert hyperlink_open("a\x1b]8;;evil\x07b\nc") == "\x1b]8;;a]8;;evilbc\x1b\\"
    assert hyperlink_open("") == "\x1b]8;;\x1b\\"


def test_cursor_shape_is_decscusr():
    assert cursor_shape("block") == "\x1b[2 q"
    assert cursor_shape("beam") == "\x1b[6 q"
    assert cursor_shape("underline") == "\x1b[4 q"
    assert cursor_shape("default") == "\x1b[0 q"
    with pytest.raises(KeyError):
        cursor_shape("bar")
