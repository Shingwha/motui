"""Tests for mocode_tui.core.style: the SGR prefix forms, colors, merge.

Attributes first, then fg, then bg; a color is a named 16-color (unknown
names raise), a ``#rrggbb`` string or an ``(r, g, b)`` tuple; frozen.  The
capability story -- ``quantize`` / ``sgr_prefix`` / ``detect_color_mode`` --
downgrades without ever touching the instance cache.
"""

import dataclasses

import pytest

import mocode_tui.core.style as style_module
from mocode_tui.core.style import (
    RESET,
    Style,
    detect_color_mode,
    quantize,
    sgr_prefix,
)


def test_empty_style_prefix_is_empty():
    assert Style().prefix() == ""
    assert Style(bold=False).prefix() == ""


def test_the_prefix_is_computed_once_even_when_it_is_empty(monkeypatch):
    """The empty answer is a computed value, not the "not computed" sentinel:
    the commonest path of all -- an unstyled segment -- never re-walks its
    SGR parameters on the second call."""
    calls: list[Style] = []
    real = style_module._sgr_codes

    def counting(style: Style) -> list[str]:
        calls.append(style)
        return real(style)

    monkeypatch.setattr(style_module, "_sgr_codes", counting)
    plain = Style()
    assert plain.prefix() == "" and plain.prefix() == ""
    assert len(calls) == 1
    painted = Style(fg="red")
    assert painted.prefix() == "\x1b[31m" and painted.prefix() == "\x1b[31m"
    assert len(calls) == 2


def test_named_colors_and_attribute_codes():
    assert Style(fg="red").prefix() == "\x1b[31m"
    assert Style(bg="blue").prefix() == "\x1b[44m"  # fg code + 10
    assert Style(dim=True).prefix() == "\x1b[2m"
    assert Style(reverse=True).prefix() == "\x1b[7m"
    assert Style(strike=True).prefix() == "\x1b[9m"


def test_code_order_is_attributes_then_fg_then_bg():
    style = Style(fg="cyan", bg="magenta", bold=True, italic=True, underline=True)
    assert style.prefix() == "\x1b[1;3;4;36;45m"


def test_truecolor_forms_and_equivalence():
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


def test_style_is_frozen_and_hashable():
    assert hash(Style(fg="red")) == hash(Style(fg="red"))
    assert Style(fg=(1, 2, 3)) == Style(fg=(1, 2, 3))
    assert Style(fg=(1, 2, 3)) != Style(fg=(1, 2, 4))
    assert len({Style(fg="red"), Style(fg="red"), Style()}) == 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        Style(fg="red").fg = "blue"  # type: ignore[misc]


def test_merge_none_passthrough_and_ored_attributes():
    base = Style(fg="red", bg="blue", bold=True)
    assert base.merge(Style()) == base  # None fields pass through
    merged = Style(fg="red", bg="blue").merge(Style(fg="green"))
    assert (merged.fg, merged.bg) == ("green", "blue")  # colors override
    both = Style(bold=True).merge(Style(dim=True))
    assert both.bold is True and both.dim is True  # attributes OR
    # Neither operand is mutated.
    other = Style(fg="green")
    assert base.merge(other) is not base and base.merge(other) is not other
    assert base == Style(fg="red", bg="blue", bold=True)
    assert other == Style(fg="green")


def test_reset_constant():
    assert RESET == "\x1b[0m"


# --- capability and downgrade -------------------------------------------------


def test_quantize_to_256_matches_the_xterm_palette():
    # The cube's 6x6x6 grid and the grayscale ramp are both searched; the
    # table is the palette terminals actually define.
    assert quantize((0, 0, 0), "256") == 16  # the cube's origin
    assert quantize((255, 255, 255), "256") == 231  # the cube's far corner
    assert quantize((255, 0, 0), "256") == 196  # a pure primary
    assert quantize((0, 205, 0), "256") == 40  # nearest cube entry, not xterm's 16-color green
    assert quantize((128, 128, 128), "256") == 244  # exactly on the gray ramp
    assert quantize((88, 166, 255), "256") == 75  # #58a6ff: (95, 175, 255)
    assert quantize((22, 40, 28), "256") == 234  # a near-black green: the ramp wins
    assert quantize((139, 148, 158), "256") == 246  # #8b949e: gray again


def test_quantize_to_16_snaps_to_the_base_color_table():
    assert quantize((0, 0, 0), "16") == 0  # black
    assert quantize((255, 0, 0), "16") == 9  # bright_red, not red (205,0,0)
    assert quantize((205, 0, 0), "16") == 1  # exact xterm red
    assert quantize((128, 128, 128), "16") == 8  # bright_black
    assert quantize((88, 166, 255), "16") == 12  # bright_blue (92, 92, 255)
    assert quantize((255, 255, 255), "16") == 15  # bright_white
    # A tie keeps the lower index: (10, 10, 10) sits nearer black than gray.
    assert quantize((10, 10, 10), "16") == 0


def test_sgr_prefix_downgrades_one_style_through_all_four_modes():
    blue = Style(fg="#58a6ff")
    assert sgr_prefix(blue, "truecolor") == "\x1b[38;2;88;166;255m"
    assert sgr_prefix(blue, "256") == "\x1b[38;5;75m"
    assert sgr_prefix(blue, "16") == "\x1b[94m"  # bright_blue's base code
    assert sgr_prefix(blue, "none") == ""  # no color at all
    assert sgr_prefix(Style(fg=(22, 40, 28), bg="#58a6ff"), "256") == (
        "\x1b[38;5;234;48;5;75m"
    )


def test_sgr_prefix_keeps_attributes_and_named_colors_in_every_mode():
    # Named colors are already the terminal's vocabulary: base code in the
    # color-bearing modes, dropped like every other color by "none".
    for mode in ("truecolor", "256", "16"):
        assert sgr_prefix(Style(fg="cyan", bg="blue"), mode) == "\x1b[36;44m"
    assert sgr_prefix(Style(fg="cyan", bg="blue"), "none") == ""
    styled = Style(fg="#58a6ff", bg=(22, 40, 28), bold=True, dim=True, underline=True)
    assert sgr_prefix(styled, "256") == "\x1b[1;2;4;38;5;75;48;5;234m"
    assert sgr_prefix(styled, "16") == "\x1b[1;2;4;94;40m"
    assert sgr_prefix(styled, "none") == "\x1b[1;2;4m"  # colors gone, attributes kept
    assert sgr_prefix(Style(reverse=True), "none") == "\x1b[7m"


def test_sgr_prefix_truecolor_delegates_to_the_instance_cache(monkeypatch):
    calls: list[Style] = []
    real = style_module._sgr_codes

    def counting(style: Style) -> list[str]:
        calls.append(style)
        return real(style)

    monkeypatch.setattr(style_module, "_sgr_codes", counting)
    style = Style(fg="#58a6ff")
    assert sgr_prefix(style) == style.prefix() == sgr_prefix(style, "truecolor")
    assert len(calls) == 1  # the cached path, computed once
    # A downgrade never touches the cache: a second call recomputes cheaply
    # and the truecolor bytes are unchanged.
    assert sgr_prefix(style, "256") == "\x1b[38;5;75m"
    assert style.prefix() == "\x1b[38;2;88;166;255m" and len(calls) == 1


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"NO_COLOR": "1"}, "none"),
        ({"NO_COLOR": ""}, "truecolor"),  # empty is no preference: the default stands
        ({"NO_COLOR": "", "TERM": "xterm-256color"}, "256"),  # ...and the next rules apply
        ({"NO_COLOR": "", "COLORTERM": "truecolor"}, "truecolor"),
        ({"TERM": "dumb"}, "none"),
        ({"TERM": "dumb", "COLORTERM": "truecolor"}, "none"),
        ({"COLORTERM": "truecolor", "TERM": "xterm-256color"}, "truecolor"),
        ({"COLORTERM": "24bit"}, "truecolor"),
        ({"COLORTERM": "unknown"}, "truecolor"),  # the historical answer stands
        ({"TERM": "xterm-256color"}, "256"),
        ({"TERM": "screen-256color"}, "256"),
        ({"TERM": "xterm"}, "truecolor"),
        ({"TERM": "vt100"}, "truecolor"),
        ({}, "truecolor"),
    ],
)
def test_detect_color_mode_env_matrix(env, expected):
    assert detect_color_mode(env) == expected


def test_detect_color_mode_defaults_to_the_process_environment(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert detect_color_mode() == "none"
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("COLORTERM", raising=False)
    assert detect_color_mode() == "256"
