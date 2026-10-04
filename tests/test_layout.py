"""Tests for mocode_tui.layout (Row / Column) and the W3 export surface."""

from mocode_tui import Column, Row
from mocode_tui.block import Component
from mocode_tui.components import (
    Confirm,
    Divider,
    Input,
    Markdown,
    Notice,
    Option,
    Panel,
    Select,
    Spinner,
    StatusBar,
    StatusSegment,
    Text,
)


def _rows(component, width: int) -> list[str]:
    return [row.text for row in component.render(width)]


# --- Row: column widths ----------------------------------------------------------


def test_row_fixed_widths_pad_columns():
    row = Row([Text("a"), Text("b")], widths=[3, 2], gap=1)
    assert _rows(row, 10) == ["a   b "]  # "a"->3 cols, 1 gap, "b"->2 cols
    assert all(r.width <= 10 for r in row.render(10))


def test_row_flex_columns_share_remainder_floor():
    row = Row([Text("a"), Text("b")], gap=1)
    # width 10, gap 1 -> 9 left -> 4 each, the odd column is discarded.
    assert _rows(row, 10) == ["a    b   "]


def test_row_mixed_fixed_and_flex():
    row = Row([Text("a"), Text("b")], widths=[2, None], gap=1)
    # fixed 2 + gap 1 -> 7 left, all flexible -> the second column gets 7.
    assert _rows(row, 10) == ["a  b      "]


def test_row_children_beyond_widths_list_are_flexible():
    row = Row([Text("a"), Text("b"), Text("c")], widths=[2], gap=0)
    # fixed 2 + two flexible columns sharing the remaining 7 -> 3 each.
    assert _rows(row, 9) == ["a b  c  "]


# --- Row: height and alignment -----------------------------------------------------


def test_row_height_is_the_tallest_child():
    row = Row([Text("a\nb\nc"), Text("x")], gap=1)
    rows = row.render(10)
    assert len(rows) == 3
    assert rows[0].text == "a    x   "
    assert rows[1].text == "b        "  # short child padded to its column width
    assert rows[2].text == "c        "


def test_row_empty_children_render_no_rows():
    assert Row([]).render(10) == []


def test_row_over_constrained_widths_stay_within_width():
    row = Row([Text("aaa"), Text("bbb")], widths=[8, 8], gap=1)
    rows = row.render(10)
    assert rows  # content survives as much as the width allows
    assert all(r.width <= 10 for r in rows)
    assert rows[0].text.startswith("aaa")


def test_row_narrow_width_does_not_crash():
    row = Row([Text("hello"), Text("world")], gap=1)
    rows = row.render(1)
    assert all(r.width <= 1 for r in rows)
    assert rows  # children still render (wrapped char per row)


# --- Column -----------------------------------------------------------------------


def test_column_stacks_with_gap():
    assert _rows(Column([Text("a"), Text("b")], gap=2), 10) == ["a", "", "", "b"]
    assert _rows(Column([Text("a"), Text("b")]), 10) == ["a", "b"]


def test_column_gap_zero_is_default():
    assert Column([Text("a")]).gap == 0


def test_column_empty_children_render_no_rows():
    assert Column([]).render(10) == []


def test_column_child_rows_fit_width():
    rows = Column([Text("the quick brown fox")]).render(9)
    assert all(r.width <= 9 for r in rows)
    assert rows[0].text == "the quick"


# --- nesting and protocol ----------------------------------------------------------


def test_row_with_column_child_one_level():
    row = Row([Column([Text("a"), Text("b")]), Text("z")], gap=1)
    assert _rows(row, 10) == ["a    z   ", "b        "]


def test_row_and_column_are_components():
    assert isinstance(Row([Text("x")]), Component)
    assert isinstance(Column([Text("x")]), Component)
    # A single flexible column spans the whole width and pads the cell.
    assert Row([Text("x")]).render(5)[0].text == "x    "


def test_row_renders_real_components_side_by_side():
    row = Row([Spinner("up"), Text("ready"), Notice("done", level="info")], gap=1)
    rows = row.render(40)
    assert len(rows) == 1
    assert rows[0].width <= 40
    assert "up" in rows[0].text and "ready" in rows[0].text and "done" in rows[0].text


# --- W3 export surface --------------------------------------------------------------


def test_component_package_exports_every_w3_component():
    names = [
        Confirm,
        Divider,
        Input,
        Markdown,
        Notice,
        Option,
        Panel,
        Select,
        Spinner,
        StatusBar,
        StatusSegment,
        Text,
    ]
    for cls in names:
        assert cls.__name__


def test_row_holds_pinned_footer_pieces():
    footer = Row([StatusBar(segments=[StatusSegment("80x24", 1)]), Spinner("think")], gap=1)
    rows = footer.render(40)
    assert len(rows) == 1
    assert rows[0].text.startswith("80x24")
    assert rows[0].width <= 40


def test_select_and_confirm_flow_through_panel_row():
    panel_row = Row([Panel(Select([Option("yes"), Option("no")], title="Pick?"), title="Modal")], gap=0)
    rows = panel_row.render(24)
    assert len(rows) == 5  # panel frame + title + 2 options + bottom border
    assert all(r.width == 24 for r in rows)


def test_markdown_and_input_in_one_column():
    column = Column([Markdown("# Title"), Input(placeholder="say hi")], gap=1)
    texts = _rows(column, 40)
    assert texts[0] == "Title"
    assert texts[2].startswith("\u276e say hi")
