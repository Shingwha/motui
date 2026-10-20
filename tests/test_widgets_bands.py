"""Tests for motui.widgets.bands (RowBands / rest).

The shared row-band value: the six tokens, the theme constructor, the
precedence matrix every row view resolves through, and the ``fit`` +
``fill`` rendering half with its ``NONE`` fast path.
"""

from dataclasses import replace

from motui.kernel import DEFAULT_THEME, NONE, Line, Segment, Style, Theme
from motui.widgets import RowBands
from motui.widgets.bands import rest

GROUND = Style(fg="#101010")
ACTIVE = Style(fg="#abcdef")
HOVER = Style(fg="#123456")
DIM = Style(dim=True)
TEXT = Style(italic=True)
DISABLED = Style(fg="#654321")


def _bands(**overrides):
    base = RowBands(
        ground=GROUND,
        active=ACTIVE,
        hover=HOVER,
        dim=DIM,
        text=TEXT,
        disabled=DISABLED,
    )
    return replace(base, **overrides) if overrides else base


def test_the_theme_constructor_maps_the_band_vocabulary():
    bands = RowBands.from_theme(DEFAULT_THEME)
    assert bands.ground == DEFAULT_THEME.ground
    assert bands.active == DEFAULT_THEME.ground_active
    assert bands.hover == DEFAULT_THEME.hover
    assert bands.dim == DEFAULT_THEME.dim
    assert bands.text == NONE
    assert bands.disabled == DEFAULT_THEME.dim
    # The explicit overrides win over the theme token.
    custom = RowBands.from_theme(
        DEFAULT_THEME, ground=GROUND, active=ACTIVE, disabled=DISABLED
    )
    assert (custom.ground, custom.active, custom.disabled) == (GROUND, ACTIVE, DISABLED)
    assert custom.hover == DEFAULT_THEME.hover


def test_the_precedence_matrix_is_disabled_then_hover_then_current():
    bands = _bands()
    assert (
        bands.band(current=True, hovered=True, focused=True, disabled=True)
        == DISABLED
    )
    assert (
        bands.band(current=False, hovered=True, focused=True, disabled=False)
        == HOVER
    )
    assert (
        bands.band(current=True, hovered=False, focused=True, disabled=False)
        == ACTIVE
    )
    assert (
        bands.band(current=False, hovered=False, focused=True, disabled=False)
        == GROUND
    )


def test_an_unfocused_current_row_merges_the_dim_token():
    bands = _bands()
    assert (
        bands.band(current=True, hovered=False, focused=False, disabled=False)
        == ACTIVE.merge(DIM)
    )
    # The dim token is the off switch for a family that never weakens.
    steady = _bands(dim=NONE)
    assert (
        steady.band(current=True, hovered=False, focused=False, disabled=False)
        == ACTIVE
    )
    # A background band is its own position signal: dim never rides it.
    background = Style(bg="#1b3a5b")
    assert (
        _bands(active=background).band(
            current=True, hovered=False, focused=False, disabled=False
        )
        == background
    )


def test_rest_fills_at_the_rows_own_width_with_the_band_underneath():
    row = Line((Segment("abc", Style(fg="red")),))
    painted = rest(row, 6, ACTIVE)
    # The band hugs the row's own cells -- a pill behind the text, never a
    # ribbon across the pane -- so the width is the fitted row's, not ``width``.
    assert painted.width == 3
    assert painted.segments == (Segment("abc", ACTIVE.merge(Style(fg="red"))),)
    # The band reaches the fitted width when the row is wider.
    wide = rest(Line.from_text("abcdef"), 6, ACTIVE)
    assert wide.width == 6
    assert wide.segments == (Segment("abcdef", ACTIVE),)
    # ``fit`` runs first.
    truncated = rest(Line.from_text("abcdef"), 4, ACTIVE)
    assert truncated.width == 4
    assert truncated.text.endswith("\u2026")


def test_rest_has_a_none_fast_path():
    row = Line.from_text("abc")
    assert rest(row, 6, NONE).text == "abc"  # no trailing cells, no restyle
    assert rest(row, 6, NONE).segments[0].style == NONE
    # A row that already fits is handed back as the very same line.
    assert rest(row, 10, NONE) is row


def test_the_value_is_frozen_and_equal_by_field():
    bands = _bands()
    assert bands == _bands()
    assert bands != _bands(hover=ACTIVE)
    try:
        bands.ground = ACTIVE
    except AttributeError:
        pass
    else:  # pragma: no cover - a frozen dataclass must refuse assignment
        raise AssertionError("RowBands must be frozen")
