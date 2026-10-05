"""Tests for mocode_tui.widgets.table (Table).

A full box frame with natural column widths, proportional shrink plus ellipsis
over width, one rule between every two data rows; styles round-trip.
"""

import pytest

from mocode_tui.core.lines import Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.table import DEFAULT_HEADER_STYLE, Table

#: Injected style: a round trip through the style parameters, never a pinned
#: default color.
INJECTED = Style(fg="#abcdef")

_GRID_CHARS = set("\u2502\u251c\u253c\u2524\u2500\u250c\u252c\u2510\u2514\u2534\u2518")


def _rules(rows) -> int:
    """How many rows are pure horizontal rules."""
    return sum(1 for row in rows if row.text and set(row.text) <= _GRID_CHARS)


def _texts(rows) -> list[str]:
    """The plain texts of an already-rendered row list."""
    return [row.text for row in rows]


def test_full_grid_structure_and_natural_widths():
    # The one full box grid: top rule, header, header rule, then row|rule
    # pairs closed by the bottom rule -- one rule between every two rows.
    rows = Table(["A"], [["1"], ["2"], ["3"]]).render(9)
    assert _texts(rows) == [
        "\u250c\u2500\u2500\u2500\u2510",
        "\u2502 A \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 1 \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 2 \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 3 \u2502",
        "\u2514\u2500\u2500\u2500\u2518",
    ]
    assert len({row.width for row in rows}) == 1  # frame consistency
    assert _rules(rows) == 5
    # Below the natural total the grid keeps its size (never stretched).
    wide = Table(["A"], [["1"]]).render(30)
    assert _texts(wide) == [
        "\u250c\u2500\u2500\u2500\u2510",
        "\u2502 A \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 1 \u2502",
        "\u2514\u2500\u2500\u2500\u2518",
    ]
    assert all(row.width == 5 for row in wide)  # one column of 3 cells, never stretched to 30
    # An empty body keeps the four-row frame; no headers yield one empty row.
    assert _rules(Table(["A"], []).render(9)) == 3
    assert _texts(Table([], [["x"]]).render(10)) == [""]


def test_over_width_shrinks_proportionally_and_ellipsizes():
    rows = Table(["A", "B"], [["xxxxxxxxxx", "y"]]).render(12)
    assert _texts(rows) == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2510",
        "\u2502 A    \u2502 B \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",
        "\u2502 xxx\u2026 \u2502 y \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2518",
    ]
    assert all(row.width == 12 for row in rows)
    # A short row is padded, a long row truncated at the last header.
    ragged = Table(["A", "B"], [["only-a"], ["1", "2", "3"]]).render(12)
    assert _texts(ragged)[3:] == [
        "\u2502 onl\u2026 \u2502   \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",  # the new mid-grid rule
        "\u2502 1    \u2502 2 \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2518",
    ]


@pytest.mark.parametrize("width", [0, 1])
def test_a_degenerate_width_keeps_the_frame_structure(width):
    rows = Table(["A", "B"], [["1", "2"]]).render(width)
    assert len(rows) == 5  # the frame structure survives
    assert all(row.width <= width for row in rows)


def test_column_widths_follow_the_visible_width():
    # "名前" measures 4 columns, and the vs16 emoji is wider as a whole than
    # the sum of its characters: either way the budgets follow the visible
    # width, so no row slips past the others.
    rows = Table(["\u540d\u524d"], [["\u65e5\u672c"]]).render(10)
    assert _rules(rows) == 3  # top, header rule, bottom
    assert _texts(rows)[3] == "\u2502 \u65e5\u672c \u2502"
    assert len({row.width for row in rows}) == 1
    for width in range(20, 81):
        rows = Table(
            ["State", "Note"],
            [["ok", "fine"], ["\u26a0\ufe0f Blocked", "hmm"], ["x", "y"]],
        ).render(width)
        widths = {row.width for row in rows}
        assert len(widths) == 1, (width, widths)
        assert widths.pop() <= width


def test_column_and_cell_styles_round_trip():
    # first_column_style colors data rows' first column only; a styled cell
    # replaces the column default; the header is plain by default.
    rows = Table(["A", "B"], [[("1", INJECTED), "x"]]).render(12)
    assert rows[1].segments[1] == Segment(" A ", DEFAULT_HEADER_STYLE)  # plain header by default
    assert rows[3].segments[1] == Segment(" 1 ", INJECTED)  # styled cell wins
    plainer = Table(["A", "B"], [["1", "x"]], first_column_style=INJECTED).render(12)
    assert plainer[3].segments[1].style == INJECTED
    assert plainer[1].segments[1].style == DEFAULT_HEADER_STYLE  # the header is untouched
    # The grid lines carry the injected border style; by default they carry
    # no foreground at all rather than a pinned color.
    tinted = Table(["A", "B"], [["1", "x"]], border_style=INJECTED).render(12)
    assert all(
        seg.style == INJECTED
        for row in tinted
        for seg in row.segments
        if seg.text and set(seg.text) <= _GRID_CHARS
    )
    plain = Table(["A", "B"], [["1", "x"]]).render(12)
    assert all(
        seg.style.fg is None
        for row in plain
        for seg in row.segments
        if seg.text and set(seg.text) <= _GRID_CHARS
    )


def test_multi_segment_cells_merge_attribute_only_runs_onto_the_base():
    # A colored segment stays absolute; an attribute-only one (bold, no
    # color) is merged onto the cell's base -- the inline-engine rule.
    # The header base (plain) and the data base (first_column_style) are
    # injected here.
    cells = [
        [
            [
                Segment("plain"),
                Segment("bold", Style(bold=True)),
                Segment("red", Style(fg="red")),
            ]
        ]
    ]
    rows = Table([[Segment("H1 "), Segment("bold", Style(bold=True))]], cells).render(16)
    header, data = rows[1], rows[3]
    assert header.segments == (
        Segment("\u2502"),
        Segment(" H1 ", DEFAULT_HEADER_STYLE),
        Segment("bold", Style(bold=True)),  # attribute-only: merged onto the header base
        Segment("      ", DEFAULT_HEADER_STYLE),  # the pad rides the cell's base style
        Segment("\u2502"),
    )
    assert data.segments == (
        Segment("\u2502"),
        Segment(" plain", DEFAULT_THEME.first_column),  # the literal run keeps the plain base
        Segment("bold", Style(bold=True)),  # attribute-only: merged onto the base
        Segment("red", Style(fg="red")),  # colored: absolute
        Segment(" ", DEFAULT_THEME.first_column),  # the pad rides the cell's base style
        Segment("\u2502"),
    )
    assert len({row.width for row in rows}) == 1  # frame consistency


def test_multi_segment_cells_truncate_and_keep_frame_consistency():
    rows = Table(
        [[Segment("H1 "), Segment("bold", Style(bold=True))]],
        [[[Segment("long value", Style(fg="green"))]]],
    ).render(12)
    rendered = _texts(rows)
    assert rendered[1] == "\u2502 H1 bold  \u2502"  # header padded to the data width
    assert rendered[3] == "\u2502 long va\u2026 \u2502"  # the data cell is ellipsized
    assert len({row.width for row in rows}) == 1  # frame consistency


@pytest.mark.parametrize(
    "headers, data, aligns, width, header_row, data_row",
    [
        # Alignment pads inside the column budget (the widest cell in the
        # column): a right-aligned cell loses its tail pad, a centered one
        # splits it with the extra space on the right.
        (
            ["l", "c", "r"],
            [["a", "bb", "cccc"]],
            ["right", "center", "left"],
            20,
            "\u2502 l \u2502 c  \u2502 r    \u2502",
            "\u2502 a \u2502 bb \u2502 cccc \u2502",
        ),
        # A short aligns list leaves the remaining columns left-aligned.
        (["a", "b"], [["x", "yy"]], ["right"], 20, "\u2502 a \u2502 b  \u2502", "\u2502 x \u2502 yy \u2502"),
        # center with an odd gap puts the extra space on the right.
        (["c"], [["ab"]], ["center"], 10, "\u2502 c  \u2502", "\u2502 ab \u2502"),
        # An unknown alignment name reads as left.
        (["x"], [["y"]], ["middle"], 12, "\u2502 x \u2502", "\u2502 y \u2502"),
    ],
)
def test_aligns_pad_and_shift_columns(headers, data, aligns, width, header_row, data_row):
    rows = Table(headers, data, aligns=aligns).render(width)
    assert rows[1].text == header_row
    assert rows[3].text == data_row
