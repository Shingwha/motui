"""Style values and SGR bytes: attributes, named and truecolor colors,
merge, quantization and capability detection.

A style is a frozen value; its prefix orders attributes, then foreground,
then background.  The capability path quantizes hex and tuple colors for
256- and 16-color terminals while named colors keep their base codes.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from motui.core.style import (
    Color,
    Style,
    quantize,
    sgr_prefix,
)
from motui.terminal.capability import detect_color_mode


def test_empty_style_has_no_prefix():
    assert Style().prefix() == ""
    assert Style(bold=False).prefix() == ""


def test_named_colors_and_attribute_codes():
    assert Style(fg="red").prefix() == "\x1b[31m"
    assert Style(bg="blue").prefix() == "\x1b[44m"
    assert Style(dim=True).prefix() == "\x1b[2m"
    assert Style(reverse=True).prefix() == "\x1b[7m"
    assert Style(strike=True).prefix() == "\x1b[9m"


def test_code_order_is_attributes_then_fg_then_bg():
    style = Style(fg="cyan", bg="magenta", bold=True, italic=True, underline=True)
    assert style.prefix() == "\x1b[1;3;4;36;45m"


def test_truecolor_hex_and_tuple_forms_are_equivalent():
    assert Style(fg="#58a6ff").prefix() == "\x1b[38;2;88;166;255m"
    assert Style(fg=(88, 166, 255)).prefix() == Style(fg="#58a6ff").prefix()
    assert Style(bg=(22, 40, 28)).prefix() == "\x1b[48;2;22;40;28m"
    assert Style(fg="#58a6ff", bold=True).prefix() == "\x1b[1;38;2;88;166;255m"
    assert Style(fg="cyan", bg="#16281c").prefix() == "\x1b[36;48;2;22;40;28m"


def test_unknown_color_name_raises_key_error():
    with pytest.raises(KeyError):
        Style(fg="chartreuse").prefix()
    with pytest.raises(KeyError):
        Style(bg="not-a-color").prefix()


def test_style_is_frozen_hashable_and_compared_by_fields():
    style = Style(fg="red", bold=True)
    assert style == Style(fg="red", bold=True)
    assert hash(style) == hash(Style(fg="red", bold=True))
    assert style != Style(fg="red")
    with pytest.raises(Exception):
        style.fg = "blue"  # type: ignore[misc]


def test_merge_overrides_colors_and_ors_attributes():
    base = Style(fg="red", bg="blue", bold=True)
    assert base.merge(Style()) == base
    merged = Style(fg="red", bg="blue").merge(Style(fg="green"))
    assert (merged.fg, merged.bg) == ("green", "blue")
    both = Style(bold=True).merge(Style(dim=True))
    assert both.bold is True and both.dim is True
    assert base == Style(fg="red", bg="blue", bold=True)


def test_quantize_to_256_uses_the_xterm_palette():
    assert quantize((0, 0, 0), "256") == 16
    assert quantize((255, 255, 255), "256") == 231
    assert quantize((255, 0, 0), "256") == 196
    assert quantize((128, 128, 128), "256") == 244
    assert quantize((88, 166, 255), "256") == 75
    assert quantize((22, 40, 28), "256") == 234
    assert quantize((139, 148, 158), "256") == 246
    assert quantize((88, 166, 255), "none") == -1


def test_quantize_to_16_snaps_to_the_base_color_table():
    assert quantize((0, 0, 0), "16") == 0
    assert quantize((255, 0, 0), "16") == 9
    assert quantize((205, 0, 0), "16") == 1
    assert quantize((128, 128, 128), "16") == 8
    assert quantize((88, 166, 255), "16") == 12
    assert quantize((255, 255, 255), "16") == 15


def test_sgr_prefix_downgrades_one_style_through_all_modes():
    blue = Style(fg="#58a6ff")
    assert sgr_prefix(blue, "truecolor") == "\x1b[38;2;88;166;255m"
    assert sgr_prefix(blue, "256") == "\x1b[38;5;75m"
    assert sgr_prefix(blue, "16") == "\x1b[94m"
    assert sgr_prefix(blue, "none") == ""
    assert sgr_prefix(Style(fg=(22, 40, 28), bg="#58a6ff"), "256") == (
        "\x1b[38;5;234;48;5;75m"
    )


def test_sgr_prefix_keeps_attributes_and_named_colors():
    for mode in ("truecolor", "256", "16"):
        assert sgr_prefix(Style(fg="cyan", bg="blue"), mode) == "\x1b[36;44m"
    styled = Style(fg="#58a6ff", bg=(22, 40, 28), bold=True, dim=True, underline=True)
    assert sgr_prefix(styled, "256") == "\x1b[1;2;4;38;5;75;48;5;234m"
    assert sgr_prefix(styled, "16") == "\x1b[1;2;4;94;40m"
    assert sgr_prefix(styled, "none") == "\x1b[1;2;4m"
    assert sgr_prefix(Style(reverse=True), "none") == "\x1b[7m"


def test_detect_color_mode_env_matrix():
    cases = [
        ({"NO_COLOR": "1"}, "none"),
        ({"NO_COLOR": ""}, "truecolor"),
        ({"NO_COLOR": "", "TERM": "xterm-256color"}, "256"),
        ({"NO_COLOR": "", "COLORTERM": "truecolor"}, "truecolor"),
        ({"TERM": "dumb"}, "none"),
        ({"TERM": "dumb", "COLORTERM": "truecolor"}, "none"),
        ({"COLORTERM": "truecolor", "TERM": "xterm-256color"}, "truecolor"),
        ({"COLORTERM": "24bit"}, "truecolor"),
        ({"COLORTERM": "unknown"}, "truecolor"),
        ({"TERM": "xterm-256color"}, "256"),
        ({"TERM": "screen-256color"}, "256"),
        ({"TERM": "xterm"}, "truecolor"),
        ({}, "truecolor"),
    ]
    for env, expected in cases:
        assert detect_color_mode(env) == expected


def test_detect_color_mode_defaults_to_the_process_environment(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert detect_color_mode() == "none"
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("COLORTERM", raising=False)
    assert detect_color_mode() == "256"


def test_color_is_a_frozen_value_with_a_validated_ansi_fallback():
    color = Color("#53c8f0", ansi="bright_cyan")
    assert color.value == "#53c8f0" and color.ansi == "bright_cyan"
    assert color == Color("#53c8f0", ansi="bright_cyan")
    assert hash(color) == hash(Color("#53c8f0", ansi="bright_cyan"))
    assert color.ansi is not None and color.ansi in {
        "black", "bright_cyan", "bright_white",
    }
    with pytest.raises(FrozenInstanceError):
        color.ansi = "cyan"  # type: ignore[misc]
    with pytest.raises(ValueError):
        Color("#53c8f0", ansi="chartreuse")
    assert Color("#53c8f0").ansi is None


def test_color_renders_truecolor_from_its_value():
    assert Style(fg=Color("#53c8f0")).prefix() == "\x1b[38;2;83;200;240m"
    assert Style(fg=Color((83, 200, 240))).prefix() == "\x1b[38;2;83;200;240m"
    assert Style(bg=Color("#53c8f0", ansi="bright_cyan")).prefix() == (
        "\x1b[48;2;83;200;240m"
    )
    assert Style(fg=Color("red")).prefix() == "\x1b[31m"


def test_color_prefers_its_ansi_name_under_16_colors():
    color = Color("#53c8f0", ansi="bright_cyan")
    assert sgr_prefix(Style(fg=color), "16") == "\x1b[96m"
    assert sgr_prefix(Style(bg=color), "16") == "\x1b[106m"
    assert sgr_prefix(Style(fg=Color("#53c8f0")), "16") == "\x1b[36m"


def test_color_quantizes_under_256_colors():
    color = Color("#53c8f0", ansi="bright_cyan")
    assert sgr_prefix(Style(fg=color), "256") == "\x1b[38;5;81m"
    assert sgr_prefix(Style(bg=color), "256") == "\x1b[48;5;81m"


def test_color_drops_under_none_but_keeps_attributes():
    color = Color("#53c8f0", ansi="bright_cyan")
    assert sgr_prefix(Style(fg=color), "none") == ""
    assert sgr_prefix(Style(fg=color, bg=color, bold=True, underline=True), "none") == (
        "\x1b[1;4m"
    )


def test_color_merge_and_style_equality_treat_it_as_a_value():
    color = Color("#53c8f0", ansi="bright_cyan")
    base = Style(fg=color)
    assert base.merge(Style(bold=True)).fg == color
    other = Color("#ff0000", ansi="red")
    assert base.merge(Style(fg=other)).fg == other
    assert Style(fg=color) == Style(fg=Color("#53c8f0", ansi="bright_cyan"))
    assert Style(fg=color) != Style(fg=Color("#53c8f0", ansi="cyan"))
