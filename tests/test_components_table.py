"""Tests for mocode_tui.components.table (Table)."""

import pytest

from mocode_tui.components.table import Table
from mocode_tui.lines import Line, Segment
from mocode_tui.style import BORDER, NONE, Style


# --- natural widths -------------------------------------------------------------------


def test_natural_column_widths_and_rule_shape():
    rows = Table(["ID", "Name"], [["1", "alice"], ["2", "bob"]]).render(14)
    assert [row.text for row in rows] == [
        "\u2502 ID \u2502 Name  \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 1  \u2502 alice \u2502",
        "\u2502 2  \u2502 bob   \u2502",
    ]
    assert all(row.width == 14 for row in rows)


def test_table_below_width_is_not_stretched():
    rows = Table(["ID", "Name"], [["1", "alice"]]).render(30)
    assert rows[0].text == "\u2502 ID \u2502 Name  \u2502"
    assert all(row.width == 14 for row in rows)  # natural size, left aligned


def test_empty_rows_render_header_and_rule_only():
    rows = Table(["A", "B"], []).render(12)
    assert [row.text for row in rows] == ["\u2502 A \u2502 B \u2502", "\u251c\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524"]


def test_cjk_column_widths_use_visible_width():
    rows = Table(["\u540d\u524d"], [["\u65e5\u672c"]]).render(10)
    assert [row.text for row in rows] == [
        "\u2502 \u540d\u524d \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 \u65e5\u672c \u2502",
    ]
    assert all(row.width == 8 for row in rows)


def test_single_column():
    rows = Table(["H"], [["a"], ["b"]]).render(9)
    assert [row.text for row in rows] == [
        "\u2502 H \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 a \u2502",
        "\u2502 b \u2502",
    ]
    assert all(row.width == 5 for row in rows)


# --- shrinking and ellipsizing ------------------------------------------------------------


def test_over_width_shrinks_proportionally_and_ellipsizes():
    rows = Table(["A", "B"], [["xxxxxxxxxx", "y"]]).render(12)
    assert [row.text for row in rows] == [
        "\u2502 A    \u2502 B \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",
        "\u2502 xxx\u2026 \u2502 y \u2502",
    ]
    assert all(row.width == 12 for row in rows)


def test_one_column_short_of_natural_shrinks():
    rows = Table(["ID", "Name"], [["1", "alice"]]).render(13)
    assert [row.text for row in rows] == [
        "\u2502 \u2026 \u2502 Name \u2502",
        "\u251c\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 1 \u2502 ali\u2026 \u2502",
    ]
    assert all(row.width == 12 for row in rows)


def test_short_row_is_padded_and_long_row_truncated_at_the_last_header():
    rows = Table(["A", "B"], [["only-a"], ["1", "2", "3"]]).render(12)
    assert [row.text for row in rows] == [
        "\u2502 A    \u2502 B \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",
        "\u2502 onl\u2026 \u2502   \u2502",
        "\u2502 1    \u2502 2 \u2502",
    ]
    assert all(row.width == 12 for row in rows)


# --- styles ---------------------------------------------------------------------------------


def test_first_column_style_touches_data_rows_only():
    rows = Table(["A", "B"], [["1", "x"]]).render(12)
    header, rule, data = rows
    assert header.segments[1] == Segment(" A ", Style(bold=True))
    assert header.segments[3] == Segment(" B ", Style(bold=True))
    assert data.segments[1] == Segment(" 1 ", Style(fg="magenta", bold=True))
    assert data.segments[3] == Segment(" x ", NONE)
    assert rule.segments == (Segment("\u251c\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524", BORDER),)


def test_header_and_first_column_styles_are_overridable():
    rows = Table(["A", "B"], [["1", "x"]], header_style=Style(underline=True),
                 first_column_style=Style(fg="blue")).render(12)
    assert rows[0].segments[1].style == Style(underline=True)
    assert rows[2].segments[1].style == Style(fg="blue")
    assert rows[2].segments[3].style == NONE


def test_styled_cell_wins_over_the_column_default():
    rows = Table(["A", "B"], [[("1", Style(fg="red")), ("x", Style(bg="white"))]]).render(12)
    data = rows[2]
    assert data.segments[1] == Segment(" 1 ", Style(fg="red"))
    assert data.segments[3] == Segment(" x ", Style(bg="white"))


# --- degenerate ------------------------------------------------------------------------------


def test_no_headers_render_one_empty_row():
    assert Table([], [["x"]]).render(10) == [Line()]


@pytest.mark.parametrize("width", [0, 1])
def test_degenerate_widths_do_not_crash(width):
    rows = Table(["A", "B"], [["1", "2"]]).render(width)
    assert len(rows) == 3  # structure survives, rows are empty
    assert all(row.width <= width for row in rows)


@pytest.mark.parametrize("width", range(0, 25))
def test_rows_never_exceed_width(width):
    rows = Table(["\u540d\u524d", "Note"], [["\u65e5\u672c", "a longer note"], ["x", ""]]).render(width)
    assert rows
    assert all(row.width <= width for row in rows)
