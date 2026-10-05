"""Tests for mocode_tui.widgets.table (Table).

Contracts (COMPONENTS.md): a full box frame (top rule / header / header rule /
bottom rule) with uncolored grid lines by default (``border_style`` tints
them); natural column widths from the widest cell plus one padding cell per
side; proportional shrink + ellipsis when over width, never stretched below
natural size; ``first_column_style`` colors data rows' first column only;
cells are ``str``, ``(str, Style)`` or ``Sequence[Segment]``; one ``├─┼─┤``
rule separates every two data rows (a full grid).
"""

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import NONE, Style
from mocode_tui.core.theme import DEFAULT_THEME
from mocode_tui.widgets.table import DEFAULT_HEADER_STYLE, Table

_GRID_CHARS = set("\u2502\u251c\u253c\u2524\u2500\u250c\u252c\u2510\u2514\u2534\u2518")


def test_natural_widths_and_full_box_frame():
    rows = Table(["ID", "Name"], [["1", "alice"], ["2", "bob"]]).render(14)
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510",
        "\u2502 ID \u2502 Name  \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 1  \u2502 alice \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524",
        "\u2502 2  \u2502 bob   \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]
    assert all(row.width == 14 for row in rows)
    # Below the natural total the grid keeps its size (never stretched).
    assert all(row.width == 14 for row in Table(["ID", "Name"], [["1", "alice"]]).render(30))
    assert Table([], [["x"]]).render(10) == [Line()]  # no headers: one empty row


def test_one_rule_between_every_two_data_rows():
    # The full grid: top, header, header rule, then row|rule pairs closed
    # by the bottom rule -- and an empty body keeps the old four-row frame.
    rows = Table(["A"], [["1"], ["2"], ["3"]]).render(9)
    assert [row.text for row in rows] == [
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
    empty = Table(["A"], []).render(9)
    assert [row.text for row in empty] == [
        "\u250c\u2500\u2500\u2500\u2510",
        "\u2502 A \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2514\u2500\u2500\u2500\u2518",
    ]


def test_frame_consistency_across_widths_with_vs16_emoji_cell():
    # The cell is wider as a whole than the sum of its characters ("⚠️"
    # measures 2 whole, 1 per character): one row must not slip past the
    # others at any width (the T1 measurement fix in action).
    for width in range(20, 81):
        rows = Table(
            ["State", "Note"],
            [["ok", "fine"], ["\u26a0\ufe0f Blocked", "hmm"], ["x", "y"]],
        ).render(width)
        widths = {row.width for row in rows}
        assert len(widths) == 1, (width, widths)
        assert widths.pop() <= width


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
    assert ragged[4].text == "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524"  # the new mid-grid rule
    assert ragged[5].text == "\u2502 1    \u2502 2 \u2502"


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
    assert DEFAULT_THEME.table_border.fg is None
    for row in Table(["A", "B"], [["1", "x"]]).render(12):
        assert all(
            seg.style == DEFAULT_THEME.table_border
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


def test_multi_segment_cells_merge_attribute_only_runs_onto_the_base():
    # A colored segment stays absolute; an attribute-only one (bold, no
    # color) is merged onto the cell's base -- the inline-engine rule.
    # The cell is one list of runs; the header base (bold) and the data
    # base (theme.first_column) are injected here.
    cells = [
        [
            [
                Segment("plain"),
                Segment("bold", Style(bold=True)),
                Segment("red", Style(fg="red")),
            ]
        ]
    ]
    rows = Table(["H"], cells).render(20)
    header, data = rows[1], rows[3]
    assert header.segments == (
        Segment("\u2502"),
        Segment(" H            ", DEFAULT_HEADER_STYLE),
        Segment("\u2502"),
    )
    base = DEFAULT_THEME.first_column
    assert data.segments == (
        Segment("\u2502"),
        Segment(" plainbold", base),  # runs fused: one style per edge run
        Segment("red", Style(fg="red")),  # colored: absolute
        Segment(" ", base),  # the pad rides the cell's base style
        Segment("\u2502"),
    )


def test_multi_segment_headers_and_truncation_keep_frame_consistency():
    headers = [[Segment("H1 "), Segment("bold", Style(bold=True))]]
    rows = Table(headers, [[[Segment("long value", Style(fg="green"))]]]).render(12)
    texts = [row.text for row in rows]
    assert texts[1] == "\u2502 H1 bold  \u2502"  # header padded to the data width
    assert texts[3] == "\u2502 long va\u2026 \u2502"  # the data cell is ellipsized
    assert len({row.width for row in rows}) == 1  # frame consistency


def test_aligns_pad_and_shift_columns():
    # Alignment pads inside the column budget (the widest cell in the
    # column): a right-aligned cell loses its tail pad, a centered one
    # splits it with the extra space on the right.
    rows = Table(
        ["l", "c", "r"], [["a", "bb", "cccc"]], aligns=["right", "center", "left"]
    ).render(20)
    assert rows[1].text == "\u2502 l \u2502 c  \u2502 r    \u2502"
    assert rows[3].text == "\u2502 a \u2502 bb \u2502 cccc \u2502"
    # A short aligns list leaves the remaining columns left-aligned.
    short = Table(["a", "b"], [["x", "yy"]], aligns=["right"]).render(20)
    assert short[3].text == "\u2502 x \u2502 yy \u2502"
    # center with an odd gap puts the extra space on the right.
    tight = Table(["c"], [["ab"]], aligns=["center"]).render(10)
    assert tight[3].text == "\u2502 ab \u2502"
    assert tight[1].text == "\u2502 c  \u2502"
    # An unknown alignment name reads as left.
    odd = Table(["x"], [["y"]], aligns=["middle"]).render(12)
    assert odd[1].text == "\u2502 x \u2502"
