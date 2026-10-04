"""Tests for mocode_tui.ansi."""

import os

import pytest

from mocode_tui import ansi
from mocode_tui.ansi import (
    CLEAR_LINE,
    ESC,
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


# --- constants and escape shapes -------------------------------------------


def test_constants():
    assert ESC == "\x1b"
    assert CLEAR_LINE == "\x1b[K"


def test_clear_line():
    assert clear_line() == "\x1b[K"
    assert clear_line() == CLEAR_LINE


def test_clear_screen():
    assert clear_screen() == "\x1b[2J"


def test_cursor_position_is_one_based():
    assert cursor_position(1, 1) == "\x1b[1;1H"
    assert cursor_position(3, 7) == "\x1b[3;7H"
    assert cursor_position(24, 80) == "\x1b[24;80H"
    assert cursor_position(0, 1) == ""
    assert cursor_position(1, 0) == ""


def test_screen_and_cursor_escapes():
    assert hide_cursor() == "\x1b[?25l"
    assert show_cursor() == "\x1b[?25h"
    assert enter_alt_screen() == "\x1b[?1049h"
    assert leave_alt_screen() == "\x1b[?1049l"


def test_mouse_tracking_pair_is_well_formed():
    assert enable_mouse_tracking() == "\x1b[?1000h\x1b[?1006h"
    assert disable_mouse_tracking() == "\x1b[?1006l\x1b[?1000l"


# --- enable_vt ----------------------------------------------------------------


def test_enable_vt_returns_bool():
    result = enable_vt()
    assert isinstance(result, bool)


def test_enable_vt_non_windows_is_true(monkeypatch):
    # Contract: os.name != "nt" -> True (native VT everywhere else).
    monkeypatch.setattr(os, "name", "posix")
    assert enable_vt() is True


def test_enable_vt_windows_failure_returns_false(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(ansi, "_windows_vt_enabled", lambda: False)
    # A failed probe must surface as False (screen -> non-live), never raise.
    assert enable_vt() is False


def test_enable_vt_windows_success_passes_through(monkeypatch):
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(ansi, "_windows_vt_enabled", lambda: True)
    assert enable_vt() is True


def test_enable_vt_windows_probe_exception_returns_false(monkeypatch):
    def boom() -> bool:
        raise OSError("ctypes unavailable")

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(ansi, "_windows_vt_enabled", boom)
    assert enable_vt() is False
