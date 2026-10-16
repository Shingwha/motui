"""Tests for mocode_tui.core.ansi.

Every escape byte the toolkit emits is constructed here; ``cursor_position``
is 1-based, invalid coordinates emit nothing; the mouse and paste pairs
reverse, and the OSC 52 clipboard sequence carries base64 of UTF-8.
"""

import base64

import pytest

from mocode_tui.core.ansi import (
    CLEAR_LINE,
    begin_sync_update,
    clear_screen,
    copy_clipboard,
    cursor_position,
    cursor_shape,
    disable_bracketed_paste,
    disable_mouse_tracking,
    enable_bracketed_paste,
    enable_mouse_tracking,
    enable_vt,
    end_sync_update,
    enter_alt_screen,
    hide_cursor,
    leave_alt_screen,
    set_window_title,
    show_cursor,
)


def test_clear_line_and_clear_screen():
    assert CLEAR_LINE == "\x1b[K"
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
    # 1000 + 1002 + SGR 1006 on; 1002 motion reports are new since selection
    # W1, an intentional contract change -- a drag gesture cannot exist
    # without them.
    assert enable_mouse_tracking() == "\x1b[?1000h\x1b[?1002h\x1b[?1006h"
    # Off disables 1006 + 1003 + 1002 + 1000 in reverse order.  1003 joined
    # the all-off pair in pointer W2 -- the disable side cannot know which
    # motion mode the enable side chose, and disabling an unset mode is a
    # no-op, so every mode goes off.
    assert disable_mouse_tracking() == "\x1b[?1006l\x1b[?1003l\x1b[?1002l\x1b[?1000l"


def test_hover_mouse_tracking_swaps_1002_for_1003():
    # Hover needs any-event tracking: 1003 reports all motion, where 1002
    # only reports motion with a button held.
    assert enable_mouse_tracking(hover=True) == "\x1b[?1000h\x1b[?1003h\x1b[?1006h"
    assert "?1002h" not in enable_mouse_tracking(hover=True)
    # The reverse-order contract is the same all-off pair on either path.
    assert disable_mouse_tracking(hover=True) == disable_mouse_tracking()


def test_sync_update_pair():
    # DECSET 2026: the terminal holds everything between the pair and swaps
    # the frame in with one repaint; a terminal that does not know the mode
    # ignores both sequences, so the painter may bracket unconditionally.
    assert begin_sync_update() == "\x1b[?2026h"
    assert end_sync_update() == "\x1b[?2026l"


def test_bracketed_paste_pair():
    # DECSET 2004: the terminal wraps a paste in CSI 200~ / CSI 201~, so a
    # multi-line paste decodes to one Paste event -- never a run of enter
    # keys, one per line break.
    assert enable_bracketed_paste() == "\x1b[?2004h"
    assert disable_bracketed_paste() == "\x1b[?2004l"


def test_enable_vt_returns_bool():
    # The probe decides liveness on Windows; any failure means non-live.
    assert isinstance(enable_vt(), bool)


def test_copy_clipboard_is_the_osc52_sequence_with_base64_of_utf8():
    assert copy_clipboard("hi") == "\x1b]52;c;aGk=\x07"


def test_window_title_is_osc2_with_control_bytes_scrubbed():
    assert set_window_title("hi") == "\x1b]2;hi\x07"
    # ESC and BEL inside a title would inject escape bytes or cut the string
    # short at the bell, so every C0 control is dropped before the payload
    # is built (the newline too: a title is one line).
    assert set_window_title("a\x1b]2;evil\x07b\nc") == "\x1b]2;a]2;evilbc\x07"
    assert set_window_title("") == "\x1b]2;\x07"


def test_cursor_shape_is_decscusr_with_steady_parameters():
    # STEADY variants: 2 = block, 6 = beam, 4 = underline; 0 restores the
    # terminal's own default.
    assert cursor_shape("block") == "\x1b[2 q"
    assert cursor_shape("beam") == "\x1b[6 q"
    assert cursor_shape("underline") == "\x1b[4 q"
    assert cursor_shape("default") == "\x1b[0 q"
    with pytest.raises(KeyError):
        cursor_shape("bar")  # outside the contract, never silently swallowed


@pytest.mark.parametrize(
    "text",
    ["", "plain", "two\nlines", "日本語のテキスト", "emoji 🙂 and quotes \"'`"],
)
def test_copy_clipboard_payload_round_trips_as_utf8_base64(text: str):
    sequence = copy_clipboard(text)
    assert sequence.startswith("\x1b]52;c;") and sequence.endswith("\x07")
    payload = sequence[len("\x1b]52;c;") : -1]
    assert base64.b64decode(payload).decode("utf-8") == text
