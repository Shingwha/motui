"""RowBands: the one band vocabulary and the shared rest helper."""

from dataclasses import replace

import pytest

from motui.kernel.style import NONE, Style
from motui.kernel.theme import DEFAULT_THEME
from motui.kernel.lines import Line
from motui.widgets import RowBands
from motui.widgets.bands import rest

GROUND = Style(fg="#101010")
ACTIVE = Style(fg="#abcdef")
HOVER = Style(fg="#123456")
DIM = Style(dim=True)
DISABLED = Style(fg="#654321")


def bands() -> RowBands:
    return RowBands(ground=GROUND, active=ACTIVE, hover=HOVER, dim=DIM, disabled=DISABLED)


def test_the_theme_constructor_maps_the_band_vocabulary():
    themed = RowBands.from_theme(DEFAULT_THEME)
    assert themed.ground == DEFAULT_THEME.ground
    assert themed.active == DEFAULT_THEME.ground_active
    assert themed.hover == DEFAULT_THEME.hover
    assert themed.dim == DEFAULT_THEME.dim
    assert themed.disabled == DEFAULT_THEME.dim
    custom = RowBands.from_theme(DEFAULT_THEME, ground=GROUND, hover=HOVER)
    assert (custom.ground, custom.hover) == (GROUND, HOVER)


@pytest.mark.parametrize(
    "current, hovered, focused, disabled, expected",
    [
        (True, True, True, True, DISABLED),
        (False, True, True, False, HOVER),
        (True, False, True, False, ACTIVE),
        (False, False, True, False, GROUND),
    ],
)
def test_the_precedence_is_disabled_then_hover_then_current(
    current, hovered, focused, disabled, expected
):
    assert (
        bands().band(current=current, hovered=hovered, focused=focused, disabled=disabled)
        == expected
    )


def test_an_unfocused_current_row_merges_the_dim_token():
    assert bands().band(current=True, hovered=False, focused=False, disabled=False) == ACTIVE.merge(DIM)
    steady = replace(bands(), dim=NONE)
    assert steady.band(current=True, hovered=False, focused=False, disabled=False) == ACTIVE
    background = Style(bg="#1b3a5b")
    assert (
        replace(bands(), active=background).band(
            current=True, hovered=False, focused=False, disabled=False
        )
        == background
    )


def test_rest_fills_at_the_rows_own_width_with_the_band_underneath():
    painted = rest(Line.from_text("abcdef"), 6, ACTIVE)
    assert painted.width == 6 and painted.text == "abcdef"
    assert all(seg.style == ACTIVE for seg in painted.segments)
    short = rest(Line.from_text("abc"), 10, ACTIVE)
    assert short.width == 3
    truncated = rest(Line.from_text("abcdef"), 4, ACTIVE)
    assert truncated.width == 4 and truncated.text.endswith("\u2026")


def test_rest_has_a_none_fast_path():
    row = Line.from_text("abc")
    assert rest(row, 10, NONE) is row
    assert rest(row, 6, NONE).text == "abc"


def test_the_band_value_is_frozen_and_compares_by_field():
    assert bands() == bands()
    assert bands() != replace(bands(), hover=ACTIVE)
