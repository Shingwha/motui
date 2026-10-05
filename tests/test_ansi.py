"""Tests for mocode_tui.core.ansi.

Every escape byte the toolkit emits is constructed here; ``cursor_position``
is 1-based, invalid coordinates emit nothing; the mouse pair reverses.
"""

from mocode_tui.core.ansi import (
    clear_line,
    clear_screen,
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
