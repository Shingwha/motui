"""Tests for mocode_tui.widgets.layout (Row / Column).

Contracts (the module docstring + COMPONENTS.md): a ``Row`` places children
side by side in columns of fixed or shared (flex) width with gaps, the tallest
child sets the height, and a final ``fit(width)`` keeps rows inside the width;
a ``Column`` stacks children vertically with optional blank rows between.
"""

from mocode_tui import Column, Row
from mocode_tui.core.block import Component
from mocode_tui.widgets.markdown import Markdown
from mocode_tui.core.text import Text


def _rows(component, width):
    return [row.text for row in component.render(width)]


def test_row_fixed_and_flex_widths():
    fixed = Row([Text("a"), Text("b")], widths=[3, 2], gap=1)
    assert _rows(fixed, 10) == ["a   b "]  # "a" -> 3 cols, 1 gap, "b" -> 2 cols
    flex = Row([Text("a"), Text("b")], gap=1)
    assert _rows(flex, 10) == ["a    b   "]  # 9 shared -> 4 each, the odd column discarded
    mixed = Row([Text("a"), Text("b")], widths=[2, None], gap=1)
    assert _rows(mixed, 10) == ["a  b      "]
    short = Row([Text("a"), Text("b"), Text("c")], widths=[2], gap=0)
    assert _rows(short, 9) == ["a b  c  "]  # children beyond widths are flexible


def test_row_gap_and_tallest_child_height():
    row = Row([Text("a\nb\nc"), Text("x")], gap=1)
    rows = row.render(10)
    assert len(rows) == 3  # the tallest child sets the height
    assert [r.text for r in rows] == ["a    x   ", "b        ", "c        "]


def test_row_over_constrained_widths_stay_within_width():
    row = Row([Text("aaa"), Text("bbb")], widths=[8, 8], gap=1)
    rows = row.render(10)
    assert rows and all(r.width <= 10 for r in rows)
    assert rows[0].text.startswith("aaa")
    assert Row([]).render(10) == []


def test_column_stacks_with_gap():
    assert _rows(Column([Text("a"), Text("b")], gap=2), 10) == ["a", "", "", "b"]
    assert _rows(Column([Text("a"), Text("b")]), 10) == ["a", "b"]  # gap defaults to 0
    assert Column([]).render(10) == []


def test_row_and_column_nest_one_level_and_are_components():
    assert isinstance(Row([Text("x")]), Component)
    assert isinstance(Column([Text("x")]), Component)
    row = Row([Column([Text("a"), Text("b")]), Text("z")], gap=1)
    assert _rows(row, 10) == ["a    z   ", "b        "]
    # Both containers drop into a single flexible / stacked painting width.
    assert _rows(Column([Markdown("# Title"), Text("tail")]), 40) == ["Title", "tail"]
