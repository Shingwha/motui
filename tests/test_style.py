"""Tests for mocode_tui.style."""

import dataclasses

import pytest

from mocode_tui import style as style_module
from mocode_tui.style import (
    ACCENT,
    BORDER,
    CODE,
    CURSOR,
    DIM,
    ERROR,
    FG_CODES,
    MUTED,
    NONE,
    RESET,
    SELECTION,
    SUCCESS,
    WARNING,
    Style,
)


def test_empty_style_prefix_is_empty():
    assert Style().prefix() == ""
    assert NONE.prefix() == ""


def test_prefix_fg_only():
    assert Style(fg="red").prefix() == "\x1b[31m"


def test_prefix_bg_uses_fg_code_plus_ten():
    assert Style(bg="blue").prefix() == "\x1b[44m"


def test_prefix_individual_attributes():
    assert Style(bold=True).prefix() == "\x1b[1m"
    assert Style(dim=True).prefix() == "\x1b[2m"
    assert Style(italic=True).prefix() == "\x1b[3m"
    assert Style(underline=True).prefix() == "\x1b[4m"
    assert Style(reverse=True).prefix() == "\x1b[7m"


def test_prefix_attribute_order():
    style = Style(
        fg="cyan",
        bg="magenta",
        bold=True,
        dim=True,
        italic=True,
        underline=True,
        reverse=True,
    )
    assert style.prefix() == "\x1b[1;2;3;4;7;36;45m"


def test_unknown_color_raises_key_error():
    with pytest.raises(KeyError):
        Style(fg="chartreuse").prefix()
    with pytest.raises(KeyError):
        Style(bg="not-a-color").prefix()


def test_prefix_computed_at_most_once_per_instance(monkeypatch):
    calls = 0
    real = style_module._sgr_codes

    def counting(style):
        nonlocal calls
        calls += 1
        return real(style)

    monkeypatch.setattr(style_module, "_sgr_codes", counting)
    style = Style(fg="green", bold=True)
    first = style.prefix()
    second = style.prefix()
    assert first == second == "\x1b[1;32m"
    assert calls == 1
    # A different instance gets its own (single) computation.
    other = Style(fg="red")
    assert other.prefix() == "\x1b[31m"
    assert calls == 2


def test_palette_has_sixteen_named_colors_with_exact_codes():
    assert FG_CODES == {
        "black": 30,
        "red": 31,
        "green": 32,
        "yellow": 33,
        "blue": 34,
        "magenta": 35,
        "cyan": 36,
        "white": 37,
        "bright_black": 90,
        "bright_red": 91,
        "bright_green": 92,
        "bright_yellow": 93,
        "bright_blue": 94,
        "bright_magenta": 95,
        "bright_cyan": 96,
        "bright_white": 97,
    }


def test_reset_constant():
    assert RESET == "\x1b[0m"


def test_style_is_frozen_and_hashable():
    style = Style(fg="red")
    with pytest.raises(dataclasses.FrozenInstanceError):
        style.fg = "blue"  # type: ignore[misc]
    assert hash(Style(fg="red")) == hash(Style(fg="red"))
    assert Style(fg="red") == Style(fg="red")
    assert Style(fg="red") != Style(fg="blue")
    assert len({Style(fg="red"), Style(fg="red"), Style()}) == 2


def test_merge_none_fields_pass_through():
    base = Style(fg="red", bg="blue", bold=True)
    merged = base.merge(Style())
    assert merged == base
    assert (merged.fg, merged.bg, merged.bold) == ("red", "blue", True)


def test_merge_overrides_non_none_fields():
    merged = Style(fg="red", bg="blue").merge(Style(fg="green"))
    assert merged.fg == "green"
    assert merged.bg == "blue"


def test_merge_booleans_are_ored():
    merged = Style(bold=True).merge(Style(dim=True))
    assert merged.bold is True
    assert merged.dim is True
    assert Style().merge(Style(underline=True)).underline is True


def test_merge_does_not_mutate_inputs():
    base = Style(fg="red")
    other = Style(fg="green", underline=True)
    merged = base.merge(other)
    assert merged.fg == "green" and merged.underline is True
    assert base == Style(fg="red")
    assert other == Style(fg="green", underline=True)


def test_semantic_constants():
    assert NONE == Style()
    assert DIM == Style(dim=True)
    assert MUTED == Style(fg="bright_black")
    assert ACCENT == Style(fg="cyan", bold=True)
    assert SUCCESS == Style(fg="green")
    assert ERROR == Style(fg="red", bold=True)
    assert WARNING == Style(fg="yellow")
    assert BORDER == Style(fg="bright_black")
    assert CODE == Style(fg="yellow")
    assert CURSOR == Style(reverse=True)
    assert SELECTION == Style(reverse=True, dim=True)
