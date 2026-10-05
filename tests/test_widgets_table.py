"""Tests for mocode_tui.widgets.table (Table).

Contracts (COMPONENTS.md): a full box frame (top rule / header / header rule /
bottom rule) with uncolored grid lines by default (``border_style`` tints
them); natural column widths from the widest cell plus one padding cell per
side; proportional shrink + ellipsis when over width, never stretched below
natural size; ``first_column_style`` colors data rows' first column only;
cells are ``str`` or ``(str, Style)``.
"""

from mocode_tui.widgets.table import TABLE_BORDER, Table
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import NONE, Style

_GRID_CHARS = set("\u2502\u251c\u253c\u2524\u2500\u250c\u252c\u2510\u2514\u2534\u2518")


def test_natural_widths_and_full_box_frame():
    rows = Table(["ID", "Name"], [["1", "alice"], ["2", "bob"]]).render(14)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 ID \u2502 Name  \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 1  \u2502 alice \u2502",
        "\u2502 2  \u2502 bob   \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]
    assert all(row.width == 14 for row in rows)
    # Below the natural total the grid keeps its size (never stretched).
    assert all(row.width == 14 for row in Table(["ID", "Name"], [["1", "alice"]]).render(30))
    assert Table([], [["x"]]).render(10) == [Line()]  # no headers: one empty row


def test_over_width_shrinks_proportionally_and_ellipsizes():
    rows = Table(["A", "B"], [["xxxxxxxxxx", "y"]]).render(12)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2510",
        "\u2502 A    \u2502 B \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",
        "\u2502 xxx\u2026 \u2502 y \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2518",
    ]
    assert all(row.width == 12 for row in rows)
    # A short row is padded, a long row truncated at the last header.
    ragged = Table(["A", "B"], [["only-a"], ["1", "2", "3"]]).render(12)
    assert ragged[3].text == "\u2502 onl\u2026 \u2502   \u2502"
    assert ragged[4].text == "\u2502 1    \u2502 2 \u2502"


def test_cjk_columns_use_visible_width():
    rows = Table(["\u540d\u524d"], [["\u65e5\u672c"]]).render(10)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 \u540d\u524d \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 \u65e5\u672c \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]


def test_column_and_cell_styles():
    # first_column_style colors data rows' first column only; a styled cell
    # replaces the column default.
    rows = Table(["A", "B"], [[("1", Style(fg="red")), "x"]]).render(12)
    _, header, _, data, _ = rows
    assert header.segments[1] == Segment(" A ", Style(bold=True))  # header is bold
    assert data.segments[1] == Segment(" 1 ", Style(fg="red"))  # styled cell wins
    assert data.segments[3] == Segment(" x ", NONE)
    plainer = Table(["A", "B"], [["1", "x"]], first_column_style=Style(fg="blue")).render(12)
    assert plainer[3].segments[1].style == Style(fg="blue")
    assert plainer[1].segments[1].style == Style(bold=True)


def test_grid_lines_use_the_table_border():
    # Uncolored by default -- the terminal default traces the box cleanest
    # on any background; border_style tints them.
    assert TABLE_BORDER.fg is None
    for row in Table(["A", "B"], [["1", "x"]]).render(12):
        assert all(
            seg.style == TABLE_BORDER
            for seg in row.segments
            if seg.text and set(seg.text) <= _GRID_CHARS
        )
    tinted = Table(["A", "B"], [["1", "x"]], border_style=Style(fg="red")).render(12)
    assert all(
        seg.style == Style(fg="red")
        for row in tinted
        for seg in row.segments
        if seg.text and set(seg.text) <= _GRID_CHARS
    )


def test_narrow_width_guard():
    for width in (0, 1):
        rows = Table(["A", "B"], [["1", "2"]]).render(width)
        assert len(rows) == 5  # the frame structure survives
        assert all(row.width <= width for row in rows)
