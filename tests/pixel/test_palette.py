"""PixelPalette.from_theme: the eight derived slots and their fallbacks."""

from __future__ import annotations

from dataclasses import replace

from motui.kernel.style import Color, Style
from motui.kernel.theme import DEFAULT_THEME
from motui.pixel import PixelPalette


def test_from_theme_fills_eight_slots_in_role_order():
    palette = PixelPalette.from_theme(DEFAULT_THEME)
    assert sorted(palette.slots) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert palette.bg is None
    assert palette.slots[1] == ((83, 200, 240), (32, 76, 91))  # content.accent
    assert palette.slots[2] == ((196, 181, 253), (74, 69, 96))  # inline_code
    assert palette.slots[3] == ((91, 209, 139), (35, 79, 53))  # status.success
    assert palette.slots[4] == ((242, 193, 78), (92, 73, 30))  # status.warning
    assert palette.slots[5] == ((242, 112, 138), (92, 43, 52))  # status.danger
    assert palette.slots[6] == palette.slots[1]  # headings[0] shares the accent
    assert palette.slots[7] == ((139, 149, 167), (53, 57, 63))  # text.muted
    assert palette.slots[8] == ((93, 102, 119), (35, 39, 45))  # text.faint


def test_cool_is_38_percent_of_main_per_channel():
    palette = PixelPalette.from_theme(DEFAULT_THEME)
    for main, cool in palette.slots.values():
        assert cool == tuple(round(channel * 0.38) for channel in main)


def test_named_or_missing_tokens_use_the_fixed_fallback():
    named = replace(
        DEFAULT_THEME,
        content=replace(
            DEFAULT_THEME.content,
            accent=Style(fg=Color("red", ansi="red")),
        ),
        text=replace(DEFAULT_THEME.text, muted=Style(fg="red")),
    )
    palette = PixelPalette.from_theme(named)
    assert palette.slots[1] == ((77, 232, 210), (29, 88, 80))
    assert palette.slots[7] == ((138, 168, 181), (52, 64, 69))


def test_hex_and_tuple_tokens_both_convert_to_rgb():
    themed = replace(
        DEFAULT_THEME,
        content=replace(
            DEFAULT_THEME.content,
            accent=Style(fg="#010203"),
            inline_code=Style(fg=(4, 5, 6)),
        ),
    )
    palette = PixelPalette.from_theme(themed)
    assert palette.slots[1] == ((1, 2, 3), (0, 1, 1))
    assert palette.slots[2] == ((4, 5, 6), (2, 2, 2))
