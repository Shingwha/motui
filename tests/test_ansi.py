"""Tests for mocode_tui.ansi."""

import io
import os

import pytest

from mocode_tui import ansi
from mocode_tui.ansi import (
    CLEAR_LINE,
    ESC,
    RESET,
    clear_line,
    delete_lines,
    enable_vt,
    enter_alt_screen,
    erase_down,
    hide_cursor,
    leave_alt_screen,
    move_to_column,
    move_up,
    show_cursor,
    stdout_isatty,
    strip_ansi,
)


# --- constants and escape shapes -------------------------------------------


def test_constants():
    assert ESC == "\x1b"
    assert RESET == "\x1b[0m"
    assert CLEAR_LINE == "\x1b[K"


def test_move_up():
    assert move_up(3) == "\x1b[3A"
    assert move_up(1) == "\x1b[1A"
    assert move_up(0) == ""
    assert move_up(-2) == ""


def test_move_to_column_is_zero_based():
    assert move_to_column() == "\x1b[1G"
    assert move_to_column(0) == "\x1b[1G"
    assert move_to_column(4) == "\x1b[5G"
    assert move_to_column(79) == "\x1b[80G"
    assert move_to_column(-1) == ""


def test_clear_line():
    assert clear_line() == "\x1b[K"
    assert clear_line() == CLEAR_LINE


def test_delete_lines():
    assert delete_lines(2) == "\x1b[2M"
    assert delete_lines(1) == "\x1b[1M"
    assert delete_lines(0) == ""
    assert delete_lines(-4) == ""


def test_screen_and_cursor_escapes():
    assert erase_down() == "\x1b[J"
    assert hide_cursor() == "\x1b[?25l"
    assert show_cursor() == "\x1b[?25h"
    assert enter_alt_screen() == "\x1b[?1049h"
    assert leave_alt_screen() == "\x1b[?1049l"


def test_alt_screen_round_trip_is_well_formed():
    assert strip_ansi(enter_alt_screen()) == ""
    assert strip_ansi(leave_alt_screen()) == ""


# --- strip_ansi --------------------------------------------------------------


def test_strip_ansi_removes_csi_sequences():
    assert strip_ansi("\x1b[31mred\x1b[0m") == "red"
    assert strip_ansi("\x1b[1;36;44mx") == "x"
    assert strip_ansi("a\x1b[2Kb") == "ab"


def test_strip_ansi_removes_private_sequences():
    assert strip_ansi("\x1b[?1049h") == ""
    assert strip_ansi("\x1b[?25l") == ""


def test_strip_ansi_removes_lone_escape_pairs():
    assert strip_ansi("a\x1bXb") == "ab"


def test_strip_ansi_leaves_plain_text():
    assert strip_ansi("plain text 日本") == "plain text 日本"


def test_strip_ansi_empty():
    assert strip_ansi("") == ""


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


# --- stdout_isatty --------------------------------------------------------------


def test_stdout_isatty_is_bool():
    assert isinstance(stdout_isatty(), bool)


def test_stdout_isatty_reflects_stream(monkeypatch):
    class FakeTTY(io.StringIO):
        def isatty(self) -> bool:
            return True

    class FakePipe(io.StringIO):
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(ansi.sys, "stdout", FakeTTY())
    assert stdout_isatty() is True
    monkeypatch.setattr(ansi.sys, "stdout", FakePipe())
    assert stdout_isatty() is False


def test_stdout_isatty_survives_broken_stream(monkeypatch):
    class Broken:
        def isatty(self):
            raise OSError("no stream")

    monkeypatch.setattr(ansi.sys, "stdout", Broken())
    assert stdout_isatty() is False
