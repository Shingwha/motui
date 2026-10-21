"""Decor, layout, padding and the foldable section."""

from dataclasses import replace

import pytest

from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Collapsible, Column, Divider, Padding, Panel, Row, Spacer, Text

from tests.testing import Rows, texts


# -- Divider ------------------------------------------------------------------


@pytest.mark.parametrize("width, expected", [(5, "\u2500" * 5)])
def test_a_divider_fills_the_width_with_one_repeated_char(width, expected):
    assert texts(Divider(), width) == [expected]


def test_a_divider_embeds_a_label_between_rule_segments():
    divider = Divider(label="load")
    assert texts(divider, 20) == ["\u2500\u2500 load " + "\u2500" * 12]
    divider.label = "x"
    assert texts(divider, 20)[0].startswith("\u2500\u2500 x ")


def test_a_divider_cap_shortens_the_span_and_ellipsizes_the_label():
    assert texts(Divider(max_width=6), 20) == ["\u2500" * 6]
    narrow = texts(Divider(label="a long label", max_width=8), 20)[0]
    assert len(narrow) == 8 and narrow.startswith("\u2500\u2500 ")


# -- Panel --------------------------------------------------------------------


def test_a_panel_frames_the_child_with_a_title():
    rows = Panel(Rows("body"), title="T").render(10)
    assert [row.text for row in rows] == [
        "\u250c\u2500 T \u2500\u2500\u2500\u2500\u2510",
        "\u2502 body   \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]


def test_a_panel_below_four_columns_degrades_to_the_bare_child():
    assert texts(Panel(Rows("body")), 3) == ["bo\u2026"]


def test_a_borderless_panel_keeps_the_inset_and_drops_the_title():
    panel = Panel(Rows("body"), title="T", frame=False)
    assert texts(panel, 8) == [" body   "]


def test_a_borderless_panel_style_is_its_ground_under_the_child():
    ground = Style(fg="#101010")
    row = Panel(Rows("body"), frame=False, style=ground).render(8)[0]
    assert all(seg.style == ground for seg in row.segments)
    themed = Panel(
        Rows("body"), frame=False, theme=replace(DEFAULT_THEME, borders=replace(DEFAULT_THEME.borders, base=ground))
    ).render(8)[0]
    assert all(seg.style == Style() for seg in themed.segments)


# -- Row / Column -------------------------------------------------------------


def test_a_row_lays_out_fixed_and_flexible_columns():
    row = Row([Rows("a", "b"), Rows("x")], widths=[2, None], gap=1)
    assert texts(row, 10) == ["a  x      ", "b         "]


def test_a_column_stacks_children_with_gaps():
    column = Column([Rows("a", "b"), Rows("c")], gap=1)
    assert texts(column, 5) == ["a", "b", "", "c"]


def test_containers_nest_one_level():
    nested = Row([Column([Rows("a"), Rows("b")]), Rows("x")], widths=[2, None], gap=1)
    assert texts(nested, 8) == ["a  x    ", "b       "]


# -- Spacer / Padding ---------------------------------------------------------


def test_a_spacer_renders_blank_rows():
    assert texts(Spacer(3), 10) == ["", "", ""]
    assert Spacer(0).render(10) == []
    assert Spacer(-2).render(10) == []


def test_padding_surrounds_the_child_with_plain_spaces():
    padded = Padding(Rows("ab"), left=1, right=1, top=1, bottom=1)
    assert texts(padded, 6) == ["", " ab ", ""]


def test_padding_fill_paints_a_continuous_band_under_the_child():
    fill = Style(fg="#101010")
    row = Padding(Rows("ab"), left=1, right=1, fill_style=fill).render(6)[0]
    assert row.text == " ab   " and row.width == 6
    assert all(seg.style == fill for seg in row.segments)


# -- child_at -----------------------------------------------------------------


def test_a_column_maps_rows_and_owns_its_gaps():
    first, second = Rows("a"), Rows("b", "c")
    column = Column([first, second], gap=1)
    column.render(5)
    assert column.child_at(0, 0) == (first, 0, 0)
    assert column.child_at(1, 0) is None
    assert column.child_at(3, 0) == (second, 1, 0)
    assert column.child_at(4, 0) is None


def test_a_row_maps_columns_and_owns_gaps_and_filler_rows():
    first, second = Rows("a", "b"), Rows("x")
    row = Row([first, second], widths=[2, None], gap=1)
    row.render(10)
    assert row.child_at(0, 0) == (first, 0, 0)
    assert row.child_at(0, 2) is None
    assert row.child_at(0, 3) == (second, 0, 0)
    assert row.child_at(1, 3) is None
    assert Row([first]).child_at(0, 0) is None  # nothing rendered yet


def test_padding_declines_its_own_whitespace():
    child = Rows("ab")
    padded = Padding(child, left=2, top=1)
    padded.render(10)
    assert padded.child_at(0, 2) is None
    assert padded.child_at(1, 1) is None
    assert padded.child_at(1, 2) == (child, 0, 0)
    assert padded.child_at(2, 2) is None


def test_a_panel_maps_only_its_content_cells_to_the_child():
    child = Rows("ab", "cd")
    panel = Panel(child)
    panel.render(10)
    assert panel.child_at(0, 1) is None
    assert panel.child_at(1, 2) == (child, 0, 0)
    assert panel.child_at(2, 2) == (child, 1, 0)
    assert panel.child_at(3, 1) is None


# -- Collapsible --------------------------------------------------------------


def test_a_collapsible_folds_its_body_away_and_back():
    section = Collapsible("options", Text("body one\nbody two"))
    assert texts(section, 20) == ["\u25be options", "  body one", "  body two"]
    section.open = False
    assert texts(section, 20) == ["\u25b8 options"]


def test_click_and_activate_flip_the_section_and_leave_the_state_pending():
    section = Collapsible("options", Text("body"))
    assert section.activate() is True
    assert (section.open, section.take_result()) == (False, False)
    assert section.click(0, 40) is True
    assert (section.open, section.take_result()) == (True, True)
    assert section.click(1, 0) is False and section.take_result() is None


def test_the_collapsible_title_takes_hover_and_focus_bands():
    title = Style(fg="#abcdef")
    hover = Style(italic=True)
    focus = Style(underline=True)
    section = Collapsible(
        "options", Text("body"), title_style=title, hover_style=hover, focus_style=focus
    )
    plain = section.render(20)
    assert section.hover_at(0, 1) is True
    assert section.render(20)[0].segments[0].style == title.merge(hover)
    assert section.render(20)[1] == plain[1]
    section.hover_at(1, 0)
    section.focused = True
    assert section.render(20)[0].segments[0].style == title.merge(focus)
    assert section.hover_at(1, 0) is False
    assert section.render(20)[1] == plain[1]


def test_the_collapsible_child_at_maps_the_body_and_owns_the_title():
    section = Collapsible("options", Text("body one\nbody two"))
    section.render(20)
    assert section.child_at(0, 3) is None
    assert section.child_at(1, 3) == (section.body, 0, 1)
    assert section.child_at(2, 2) == (section.body, 1, 0)
    assert section.child_at(3, 0) is None


def test_a_disabled_collapsible_refuses_both_doors_and_nested_content_fits():
    section = Collapsible("options", Text("body"), disabled=True)
    assert section.activate() is False and section.click(0, 0) is False
    nested = Collapsible("outer", Collapsible("inner", Text("a long body line to wrap")))
    assert all(row.width <= 12 for row in nested.render(12))
