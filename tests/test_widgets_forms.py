"""The form widgets: ``Slider``, ``Collapsible``, ``ShortcutBar``.

The components the widgets-basic wave adds, each asserted as its own
contract: the state it holds, the controller methods a host routes (and the
``chosen`` value each writes for a single read), the row-level ``hover_at``
marking that must render zero extra bytes when it cleared, and the focus
band that must be told apart from the plain render.  The choice presets --
``Radio`` and ``CheckGroup`` -- are exercised beside their base in
``test_widgets_choice.py``.
"""

from __future__ import annotations

import pytest

from _doubles import texts

from motui.kernel import Component
from motui.kernel.block import Activable, Clickable
from motui.kernel.lines import Line, Segment
from motui.kernel.lines import Text
from motui.kernel.style import NONE, Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.widgets import Collapsible, ShortcutBar, Slider

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
PLAIN = Style(fg="#123456")
HOVER = Style(italic=True)
FOCUS = Style(underline=True)


# --- Slider ---------------------------------------------------------------------


def test_slider_renders_the_track_and_the_value():
    slider = Slider(5)
    row = slider.render(14)[0]
    assert row.text == "[=====-----] 5"  # key + label + 2 brackets leave a 10-cell track
    assert row.segments[1] == Segment("=====", DEFAULT_THEME.accent)
    assert row.segments[2] == Segment("-----", DEFAULT_THEME.dim)
    assert isinstance(slider, Component)
    assert slider.render(30)[0].text == "[=============-------------] 5"  # the track follows width


def test_slider_clamps_and_snaps_to_the_step_grid():
    assert Slider(99, maximum=10).value == 10
    assert Slider(-5).value == 0
    slider = Slider(7, minimum=0, maximum=10, step=3)  # grid: 0, 3, 6, 9
    assert slider.value == 6  # 7 snaps down to the nearest grid point
    slider.value = 10
    assert slider.value == 9  # the largest grid point not past maximum
    slider.value = 100
    assert slider.value == 9
    slider.value = -100
    assert slider.value == 0
    assert Slider(5, minimum=7, maximum=7).value == 7  # an empty range pins the value


def test_slider_move_steps_clamps_and_clears_a_stale_choice():
    slider = Slider(4)
    assert slider.move(1) is True and slider.value == 5
    slider.chosen = 5  # the host read once and reset
    assert slider.move(1) is True and slider.value == 6 and slider.chosen is None
    assert slider.move(9) is True and slider.value == 10  # clamped at the top
    assert slider.move(1) is False  # already there: nothing moved
    assert slider.move(-99) is True and slider.value == 0
    assert slider.move(-1) is False
    stepped = Slider(0, minimum=0, maximum=9, step=3)
    assert stepped.move(1) is True and stepped.value == 3  # whole steps of the grid


def test_slider_click_maps_the_column_onto_the_value():
    slider = Slider(5)
    assert isinstance(slider, Clickable)
    slider.render(14)  # the track spans cells 1..10
    assert slider.click(0, 1) is True and slider.value == 0  # the track's first cell
    slider.render(14)
    assert slider.click(0, 6) is True and slider.value == 5  # the track's middle
    slider.render(14)
    assert slider.click(0, 11) is True and slider.value == 10  # the closing bracket
    slider.render(14)
    assert slider.click(0, 0) is True and slider.value == 0  # the opening bracket
    slider.render(14)
    assert slider.click(0, 99) is True and slider.value == 10  # past the row
    slider.render(14)
    assert slider.click(0, 6) is True  # a hit even when the value already sat there
    slider.chosen = 5
    assert slider.click(0, 6) is True and slider.chosen is None  # a click clears the pick
    for row in (-1, 1, 9):
        before = slider.value
        assert slider.click(row, 3) is False and slider.value == before


def test_slider_click_before_the_first_render_uses_the_default_width():
    slider = Slider(0)
    assert slider.click(0, 1) is True  # the 80-column default geometry
    assert slider.value == 0
    assert slider.click(0, 79) is True and slider.value == 10  # deep into the track's tail


def test_slider_activate_confirms_the_value_and_reads_once():
    slider = Slider(4, minimum=0, maximum=20)
    slider.move(2)
    assert isinstance(slider, Activable)
    assert slider.activate() is True and slider.chosen == 6
    slider.chosen = None
    assert slider.value == 6  # confirming changes nothing


def test_slider_marks_the_row_and_clears_back():
    slider = Slider(5, filled_style=SELECTED, empty_style=PLAIN, hover_style=HOVER)
    plain = slider.render(14)
    assert slider.hover_at(0, 3) is True
    marked = slider.render(14)
    assert marked[0].segments[1].style == SELECTED.merge(HOVER)
    assert marked[0].segments[2].style == PLAIN.merge(HOVER)
    assert marked[0].text == plain[0].text  # the band never changes the text
    assert slider.hover_at(0, 99) is False  # the same row: nothing to repaint
    assert slider.hover_at(-1, -1) is True  # the pointer left
    assert slider.render(14) == plain  # byte-for-byte the un-hovered row
    assert slider.hover_at(1, 0) is False  # no second row: nothing to mark
    assert slider.render(14) == plain


def test_slider_focus_band_is_told_apart_from_the_plain_render():
    styles = dict(filled_style=SELECTED, empty_style=PLAIN, focus_style=FOCUS)
    plain = Slider(5, **styles).render(14)[0]
    focused = Slider(5, focused=True, **styles).render(14)[0]
    assert focused.segments[1].style == SELECTED.merge(FOCUS)
    assert focused.segments[3].style == FOCUS  # brackets too: the row is one band
    assert plain.segments[1].style == SELECTED


# --- Collapsible -----------------------------------------------------------------


def test_collapsible_folds_its_body_away_and_back():
    section = Collapsible("options", Text("body one\nbody two"))
    rows = section.render(20)
    assert [row.text for row in rows] == ["\u25be options", "  body one", "  body two"]
    assert rows[0].segments == (
        Segment("\u25be ", DEFAULT_THEME.accent),
        Segment("options", DEFAULT_THEME.accent),
    )
    assert section.open is True
    section.open = False  # a host may set the state directly
    assert [row.text for row in section.render(20)] == ["\u25b8 options"]
    assert isinstance(section, Component)


def test_collapsible_click_and_activate_are_the_same_flip():
    section = Collapsible("options", Text("body"))
    assert isinstance(section, Clickable) and isinstance(section, Activable)
    assert section.chosen is None
    assert section.activate() is True
    assert (section.open, section.chosen) == (False, False)
    section.chosen = None  # the host reads once and resets
    expected = True
    for col in (0, 3, 40):  # the title row owns the whole width; each hit flips it
        assert section.click(0, col) is True
        assert section.open is expected and section.chosen is expected
        section.chosen = None
        expected = not expected
    for row in (-1, 1, 9):  # a body row or a cell past the render is not the control
        assert section.click(row, 0) is False and section.chosen is None
    assert section.open is True  # the misses never flipped it


def test_collapsible_marks_the_title_row_and_clears_back():
    section = Collapsible(
        "options", Text("body"), title_style=SELECTED, hover_style=HOVER
    )
    plain = section.render(20)
    assert section.hover_at(0, 2) is True
    marked = section.render(20)
    assert marked[0].segments[0].style == SELECTED.merge(HOVER)
    assert marked[0].segments[1].style == SELECTED.merge(HOVER)
    assert marked[1] == plain[1]  # the body row is untouched
    assert section.hover_at(0, 0) is False  # the same row: nothing to repaint
    assert section.hover_at(1, 0) is True  # a body row carries no marking
    assert section.render(20) == plain  # byte-for-byte the un-hovered rows
    assert section.hover_at(-1, -1) is False  # nothing was marked: no change


def test_collapsible_focus_band_is_told_apart_from_the_plain_render():
    styles = dict(title_style=SELECTED, focus_style=FOCUS)
    plain = Collapsible("options", Text("body"), **styles).render(20)
    focused = Collapsible("options", Text("body"), focused=True, **styles).render(20)
    assert focused[0].segments[0].style == SELECTED.merge(FOCUS)
    assert focused[1] == plain[1]  # the body keeps its own styles
    assert plain[0].segments[0].style == SELECTED


def test_collapsible_nested_content_stays_inside_the_width():
    nested = Collapsible(
        "outer",
        Collapsible("inner", Text("a long body line that has to wrap inside the section")),
    )
    for row in nested.render(24):
        assert row.width <= 24
    assert [row.text for row in nested.render(24)][:2] == [
        "\u25be outer",
        "  \u25be inner",
    ]
    # a body wider than the painting width truncates through fit, marker and all
    narrow = Collapsible("a-title-that-is-far-too-long", Text("body")).render(4)
    assert narrow[0].width == 4 and narrow[0].text.endswith("\u2026")


# --- ShortcutBar -----------------------------------------------------------------


def test_shortcut_bar_renders_one_row_of_key_label_pairs():
    bar = ShortcutBar([("c-n", "next"), ("c-p", "prev"), ("/", "palette")])
    rows = bar.render(40)
    assert len(rows) == 1
    assert rows[0].text == "c-n next \u00b7 c-p prev \u00b7 / palette"
    assert rows[0].segments == (
        Segment("c-n", DEFAULT_THEME.accent),
        Segment(" next", DEFAULT_THEME.dim),
        Segment(" \u00b7 ", NONE),
        Segment("c-p", DEFAULT_THEME.accent),
        Segment(" prev", DEFAULT_THEME.dim),
        Segment(" \u00b7 ", NONE),
        Segment("/", DEFAULT_THEME.accent),
        Segment(" palette", DEFAULT_THEME.dim),
    )
    assert isinstance(bar, Component)
    assert not isinstance(bar, Clickable)  # chrome only: no interaction


def test_shortcut_bar_custom_separator_and_styles_round_trip():
    bar = ShortcutBar(
        [("a", "one"), ("b", "two")],
        separator=" | ",
        key_style=SELECTED,
        label_style=PLAIN,
    )
    assert bar.render(40)[0].text == "a one | b two"
    assert bar.render(40)[0].segments[1] == Segment(" one", PLAIN)
    assert bar.render(40)[0].segments[0] == Segment("a", SELECTED)


def test_shortcut_bar_truncates_instead_of_wrapping():
    bar = ShortcutBar([("c-n", "next"), ("c-p", "prev")])
    row = bar.render(8)[0]
    assert len(bar.render(80)) == 1  # a bar is always a single row
    assert row.text == "c-n nex\u2026" and row.width == 8
    assert bar.render(6)[0].text == "c-n n\u2026"
    assert ShortcutBar([]).render(20) == [Line()]  # an empty bar is one empty row
    assert ShortcutBar([]).render(0) == [Line()]


def test_shortcut_bar_counts_wide_characters_by_display_width():
    bar = ShortcutBar([("\u4e2d", "wide"), ("c-p", "prev")])
    row = bar.render(8)[0]
    assert row.text == "\u4e2d wide\u2026"  # 2 + 5 display cells, then the marker
    assert row.width == 8
    assert bar.render(4)[0].text == "\u4e2d \u2026"  # a cut inside the label's run
    assert bar.render(2)[0].text == "\u2026"  # no single cell holds the wide key
    assert bar.render(1)[0].text == "\u2026"
