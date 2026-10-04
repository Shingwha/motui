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


# --- truecolor (W11 palette upgrade) -------------------------------------------------


def test_prefix_fg_hex_string_is_24_bit():
    assert Style(fg="#58a6ff").prefix() == "\x1b[38;2;88;166;255m"


def test_prefix_bg_hex_string_is_24_bit():
    assert Style(bg="#1c2b3a").prefix() == "\x1b[48;2;28;43;58m"


def test_prefix_hex_string_is_case_insensitive():
    assert Style(fg="#58A6FF").prefix() == Style(fg="#58a6ff").prefix()


def test_prefix_hex_matches_the_equivalent_tuple():
    assert Style(bg=(28, 43, 58)).prefix() == Style(bg="#1c2b3a").prefix()


def test_prefix_tuple_is_24_bit():
    assert Style(fg=(88, 166, 255)).prefix() == "\x1b[38;2;88;166;255m"
    assert Style(bg=(22, 40, 28)).prefix() == "\x1b[48;2;22;40;28m"


def test_prefix_truecolor_with_attributes_orders_codes():
    style = Style(fg="#58a6ff", bold=True)
    assert style.prefix() == "\x1b[1;38;2;88;166;255m"


def test_prefix_mixes_named_color_and_truecolor():
    assert Style(fg="cyan", bg="#16281c").prefix() == "\x1b[36;48;2;22;40;28m"


def test_prefix_fg_and_bg_both_truecolor():
    assert Style(fg="#a5d6ff", bg="#12181f").prefix() == "\x1b[38;2;165;214;255;48;2;18;24;31m"


def test_truecolor_style_is_frozen_hashable_and_equal():
    assert Style(fg=(1, 2, 3)) == Style(fg=(1, 2, 3))
    assert Style(fg=(1, 2, 3)) != Style(fg=(1, 2, 4))
    assert Style(fg="#010203") == Style(fg="#010203")
    assert hash(Style(fg=(1, 2, 3))) == hash(Style(fg=(1, 2, 3)))
    with pytest.raises(dataclasses.FrozenInstanceError):
        Style(fg=(1, 2, 3)).fg = (4, 5, 6)  # type: ignore[misc]


def test_truecolor_merge_keeps_channels():
    merged = Style(fg="#58a6ff", bg="#16281c").merge(Style(bold=True))
    assert merged == Style(fg="#58a6ff", bg="#16281c", bold=True)
    assert merged.prefix() == "\x1b[1;38;2;88;166;255;48;2;22;40;28m"


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


def test_truecolor_prefix_is_cached_too(monkeypatch):
    calls = 0
    real = style_module._sgr_codes

    def counting(style):
        nonlocal calls
        calls += 1
        return real(style)

    monkeypatch.setattr(style_module, "_sgr_codes", counting)
    style = Style(fg="#58a6ff", bg="#16281c")
    assert style.prefix() == style.prefix() == "\x1b[38;2;88;166;255;48;2;22;40;28m"
    assert calls == 1


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
    assert MUTED == Style(fg="#8b949e")
    assert ACCENT == Style(fg="#58a6ff", bold=True)
    assert SUCCESS == Style(fg="#4bb563")
    assert ERROR == Style(fg="#e5534b", bold=True)
    assert WARNING == Style(fg="#d29922")
    assert BORDER == Style(fg="#3d444d")
    assert CODE == Style(fg="#a5d6ff")
    assert CURSOR == Style(reverse=True)
    assert SELECTION == Style(reverse=True, dim=True)


def test_semantic_constants_emit_truecolor_prefixes():
    assert BORDER.prefix() == "\x1b[38;2;61;68;77m"
    assert ACCENT.prefix() == "\x1b[1;38;2;88;166;255m"
    assert MUTED.prefix() == "\x1b[38;2;139;148;158m"
    assert SUCCESS.prefix() == "\x1b[38;2;75;181;99m"
    assert ERROR.prefix() == "\x1b[1;38;2;229;83;75m"
    assert WARNING.prefix() == "\x1b[38;2;210;153;34m"
    assert CODE.prefix() == "\x1b[38;2;165;214;255m"
