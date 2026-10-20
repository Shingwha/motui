"""Tests for motui.widgets.table (Table).

A full box frame with natural column widths, proportional shrink plus ellipsis
over width, one rule between every two data rows; styles round-trip.  The row
cursor is the interactive half: the band on the cursor row's data cells, the
clamped `move`, the render-driven `click` mapping and `activate`/`chosen`.
"""

import pytest

from motui import FocusRing, Key
from motui.kernel.lines import Segment
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.testing import headless_tui
from motui.widgets.table import DEFAULT_HEADER_STYLE, Table

#: Injected style: a round trip through the style parameters, never a pinned
#: default color.
INJECTED = Style(fg="#abcdef")

_GRID_CHARS = set("\u2502\u251c\u253c\u2524\u2500\u250c\u252c\u2510\u2514\u2534\u2518")


def _rules(rows) -> int:
    """How many rows are pure horizontal rules."""
    return sum(
        1
        for row in rows
        if (body := row.text.replace(" ", "")) and set(body) <= _GRID_CHARS
    )


def _texts(rows) -> list[str]:
    """The plain texts of an already-rendered row list."""
    return [row.text for row in rows]


def _row_of(rows, text) -> int:
    """The block row whose rendered text is exactly ``text``."""
    return next(i for i, row in enumerate(rows) if row.text == text)


def _data_rows(rows) -> list[str]:
    """The rendered body rows (the ``│ … │`` lines under the header rule)."""
    return [row.text for row in rows if row.text.lstrip(" ").startswith("\u2502")][1:]


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


# --- the row cursor -------------------------------------------------------------------


def test_the_cursor_bands_every_data_cell_of_its_row_and_nothing_else():
    band = Style(reverse=True)
    table = Table(["A", "B"], [["1", "x"], ["2", "y"]], selected_style=band)
    plain = Table(["A", "B"], [["1", "x"], ["2", "y"]]).render(12)
    table.index = 1
    rows = table.render(12)
    # The cursor adds the band and nothing else: the grid's own text and
    # geometry are untouched, and the band hugs the row's own cells.
    assert [row.text for row in rows] == [row.text for row in plain]
    assert [row.width for row in rows] == [9, 9, 9, 9, 9, 9, 9]
    assert rows[5].width == 9  # the cursor changes no geometry
    banded = [seg for seg in rows[5].segments if seg.text != "\u2502"]
    assert [seg.text for seg in banded] == [" 2 ", " y "]
    # Every data cell takes the band.
    assert banded[0].style == DEFAULT_THEME.first_column.merge(band)
    assert banded[1].style == band
    for i, row in enumerate(rows):
        if i != 5:  # the cursor row is the only banded one
            assert not any(seg.style.reverse for seg in row.segments)
    assert rows[1].segments[1] == Segment(" A ", DEFAULT_HEADER_STYLE)  # header: untouched
    assert rows[0].segments[0].style == DEFAULT_THEME.table_border  # rules: untouched
    # D1: the shipped ``ground_active`` is NONE, so an un-themed table's
    # cursor row paints no band at all and keeps the grid's natural width.
    default = Table(["A", "B"], [["1", "x"], ["2", "y"]])
    default.index = 1
    assert default.render(12)[5].width == 9
    assert not any(
        seg.style.reverse for seg in default.render(12)[5].segments
    )


def test_a_styled_cell_in_the_cursor_row_still_takes_the_band():
    # The selection rides on top of whatever style the cell carries: a tuple
    # cell keeps its color and gains the band (the rule for every data cell).
    # D1: the shipped ``ground_active`` is NONE, so the band is injected here.
    band = Style(reverse=True)
    table = Table(["A", "B"], [["1", ("x", INJECTED)]], selected_style=band)
    table.index = 0
    row = table.render(12)[3]
    assert row.segments[3].text == " x "
    assert row.segments[3].style == INJECTED.merge(band)
    assert row.segments[1].style == DEFAULT_THEME.first_column.merge(band)


def test_selected_style_resolves_explicit_then_the_theme():
    explicit = Table(["A"], [["1"]], selected_style=INJECTED)
    explicit.index = 0
    assert explicit.render(9)[3].segments[2].style == INJECTED.merge(
        DEFAULT_THEME.first_column
    )
    themed = Theme(ground_active=Style(fg="blue", reverse=True))
    picked = Table(["A"], [["1"]], theme=themed)
    picked.index = 0
    assert picked.render(9)[3].segments[2].style == themed.ground_active.merge(
        themed.first_column
    )


def test_an_unfocused_table_dims_the_band():
    table = Table(["A"], [["1"], ["2"]], focused=False)
    table.index = 0
    rows = table.render(9)
    assert rows[3].segments[2].style == DEFAULT_THEME.ground_active.merge(
        DEFAULT_THEME.dim
    )
    assert rows[5].segments[2].style == DEFAULT_THEME.first_column  # the other row: unchanged
    assert [row.text for row in rows] == [
        row.text for row in Table(["A"], [["1"], ["2"]]).render(9)
    ]


def test_a_background_band_keeps_the_unfocused_cursor_undimmed():
    """SGR ``dim`` is a foreground attribute: it never rides a background.

    A background band is its own position signal; merging ``dim`` onto it
    would dim the text into the surface instead of weakening the band.
    """
    background = Style(bg="#1b3a5b")
    table = Table(["A"], [["1"]], selected_style=background, focused=False)
    table.index = 0
    row = table.render(9)[3]
    assert row.segments[1].style == background.merge(DEFAULT_THEME.first_column)
    assert row.segments[1].style.dim is False
    # Without a background the dim merge is exactly as it was.
    backgroundless = Table(["A"], [["1"]], selected_style=Style(fg="#0000ff"),
                           focused=False)
    backgroundless.index = 0
    assert backgroundless.render(9)[3].segments[1].style == Style(
        fg="#0000ff", dim=True
    ).merge(DEFAULT_THEME.first_column)


def test_the_ground_style_resolves_and_rests_under_the_whole_grid():
    ground = Style(fg="#101010")
    table = Table(["A"], [["1"]], ground_style=ground)
    rows = table.render(9)
    # The ground rests under every row of the grid -- the rules and the
    # header included, none of them taking the engaged band -- and it hugs
    # the grid's own cells: the five-column box, never the nine-cell pane.
    assert all(seg.style == ground for row in rows for seg in row.segments)
    assert all(row.width == 5 for row in rows)
    plain = Table(["A"], [["1"]]).render(9)
    assert [row.text for row in rows] == [row.text for row in plain]  # no pad
    # the theme field is the fallback the explicit style wins over
    themed = Table(["A"], [["1"]], theme=Theme(ground=ground))
    assert all(seg.style == ground for row in themed.render(9) for seg in row.segments)
    assert all(row.width == 5 for row in themed.render(9))


def test_the_cursor_never_changes_the_row_count_or_the_column_widths():
    table = Table(
        ["State", "Note"],
        [["ok", "fine"], ["\u26a0\ufe0f Blocked", "hmm"], ["x", "y"]],
    )
    rows = [["ok", "fine"], ["\u26a0\ufe0f Blocked", "hmm"], ["x", "y"]]

    for width in (0, 1, 8, 20, 80):
        table.index = None
        plain = table.render(width)
        table.index = 1
        banded = table.render(width)
        assert len(banded) == len(plain)  # the row structure is untouched
        assert [row.text for row in banded] == [row.text for row in plain]
        assert [row.width for row in banded] == [row.width for row in plain]


def test_index_clamps_into_the_rows_and_clears_with_none():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    assert table.index is None  # no cursor until one is put there
    table.index = 99
    assert table.index == 2
    table.index = -5
    assert table.index == 0
    assert table.selected == ["1"]
    table.index = None
    assert table.index is None and table.selected is None
    empty = Table(["A"], [])
    empty.index = 0
    assert empty.index is None and empty.selected is None
    table.index = 1
    table.rows.clear()  # a host swapping the rows out reads as no cursor
    assert table.selected is None


def test_move_clamps_at_the_edges_and_never_wraps():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    assert table.move(1) is True and table.index == 0  # no cursor yet: down lands on row 0
    assert table.move(-1) is False and table.index == 0  # the first row is a real edge
    assert table.move(1) is True and table.index == 1
    assert table.move(2) is True and table.index == 2
    assert table.move(1) is False and table.index == 2  # ...and so is the last
    assert table.move(-10) is True and table.index == 0
    up = Table(["A"], [["1"], ["2"], ["3"]])
    assert up.move(-1) is True and up.index == 2  # no cursor yet: up lands on the last row
    quiet = Table(["A"], [["1"], ["2"]])
    assert quiet.move(0) is False and quiet.index is None  # a zero step lights nothing
    empty = Table(["A"], [])
    assert empty.move(1) is False and empty.index is None


def test_click_maps_the_rendered_row_onto_a_data_row():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    rendered = table.render(9)  # no cursor yet: the plain grid
    for index, label in enumerate(("1", "2", "3")):
        block_row = _row_of(rendered, f"\u2502 {label} \u2502")
        assert table.click(block_row, 0) is True and table.index == index
    misses = [r for r in range(len(rendered)) if r not in (3, 5, 7)]
    assert [table.click(r, 0) for r in misses] == [False] * len(misses)  # header and rules
    assert table.index == 2  # a miss changed nothing
    assert table.click(len(rendered), 0) is False and table.click(-1, 0) is False
    # The column never narrows a hit: every column owns the whole data row.
    assert table.click(3, 0) is True and table.click(5, 10**6) is True
    assert table.index == 1
    empty = Table(["A"], [])
    assert [empty.click(r, 0) for r in range(len(empty.render(9)))] == [False] * 4
    headerless = Table([], [["x"]])
    assert [row.text for row in headerless.render(9)] == [""]  # one blank row
    assert headerless.click(0, 0) is False  # one blank row, no data row on it


def test_click_follows_the_rendered_shape_across_widths():
    # Table ellipsizes an over-wide cell, it never wraps one into a second
    # rendered row -- so the frame shape holds at every width.  The mapping
    # is read off the same layout ``render`` emits, never a row offset, and
    # this pins it: at each width the ``\u2502...\u2502`` body rows are
    # exactly the data rows, in order.
    table = Table(["a long header", "b"], [["one", "1"], ["two", "2"], ["three", "3"]])
    for width in (9, 12, 20, 40):
        rendered = table.render(width)
        assert len(rendered) == 2 * len(table.rows) + 3  # ellipsized, never wrapped
        data_rows = [
            i for i, row in enumerate(rendered)
            if row.text.lstrip(" ").startswith("\u2502") and i != 1  # not the header
        ]
        assert len(data_rows) == len(table.rows)
        for index, block_row in enumerate(data_rows):
            assert table.click(block_row, 0) is True and table.index == index
        table.index = None
        for block_row in range(len(rendered)):
            if block_row not in data_rows:
                assert table.click(block_row, 0) is False
        assert table.index is None  # every miss left the cursor alone


def test_the_click_map_follows_the_rows_when_the_host_swaps_them():
    # The layout is derived from the row list at call time, never pinned: a
    # host that appends a record gets it mapped the moment it renders, and a
    # table whose rows were taken away has no data row left to click.
    table = Table(["A"], [["1"]])
    assert len(table.render(9)) == 5
    assert table.click(3, 0) is True and table.index == 0
    table.rows.append(["2"])
    assert len(table.render(9)) == 7  # a new data row: two more rendered rows
    assert table.click(5, 0) is True and table.index == 1
    table.rows.clear()
    assert len(table.render(9)) == 4  # back to the bare frame
    assert [table.click(r, 0) for r in range(4)] == [False] * 4
    assert table.index == 1  # a miss changed nothing


def test_activate_takes_the_row_index_and_the_host_reads_it_once():
    table = Table(["A"], [["1"], ["2"]])
    assert table.activate() is False and table.chosen is None  # no cursor: nothing to take
    table.index = 1
    assert table.activate() is True and table.chosen == 1
    table.chosen = None  # the host reads the pick exactly once
    assert table.chosen is None
    assert table.activate() is True and table.chosen == 1  # the cursor stayed
    empty = Table(["A"], [])
    assert empty.activate() is False and empty.chosen is None


def test_a_step_or_a_landing_click_clears_a_pending_chosen():
    table = Table(["A"], [["1"], ["2"]])
    table.index = 1
    assert table.activate() is True and table.chosen == 1
    assert table.move(0) is False and table.chosen is None  # even a step that goes nowhere
    assert table.activate() is True
    assert table.click(3, 0) is True and table.chosen is None  # a landing click clears it too
    assert table.activate() is True and table.chosen == 0  # the click moved the cursor to row 0
    assert table.click(2, 0) is False and table.chosen == 0  # a miss leaves the pick alone


def test_a_ring_drives_the_table_by_key():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    ring = FocusRing([table])
    assert ring.focused is table and table.focused is True
    assert ring.handle(Key("down")) is True and table.index == 0
    assert ring.handle(Key("down")) is True and table.index == 1
    assert ring.handle(Key("up")) is True and table.index == 0
    assert ring.handle(Key("enter")) is True
    assert table.chosen == 0  # the host reads the row index exactly once
    table.chosen = None


def test_a_real_hit_test_click_lands_on_the_data_row():
    tui = headless_tui(24, 12)
    table = Table(["A"], [["1"], ["2"], ["3"]])
    block = tui.add(table)
    tui.paint()
    hit = tui.hit_test(3, 5)  # the block's sixth row: the second data row
    assert hit is not None and hit.block is block and (hit.row, hit.col) == (5, 3)
    assert hit.block.component.click(hit.row, hit.col) is True
    assert table.index == 1
    # The row the host's click landed on is the one the band wraps -- the box's
    # own borders riding it, the pill ending at the grid's last cell.  D1: the
    # shipped ``ground_active`` is NONE, so the band is injected here.
    banded_table = Table(
        ["A"], [["1"], ["2"], ["3"]], selected_style=Style(reverse=True)
    )
    banded_table.index = 1
    banded = "".join(
        seg.text
        for row in banded_table.render(24)
        for seg in row.segments
        if seg.style.reverse
    )
    assert banded == "\u2502 2 \u2502"  # the band rides the grid; no pad
    for block_row in (0, 1, 2, 4):  # the top rule, the header, and two rules
        miss = tui.hit_test(3, block_row)
        assert miss is not None and miss.block is block
        assert miss.block.component.click(miss.row, miss.col) is False
    assert table.index == 1  # a click on the frame moved nothing


# --- sorting, explicit widths and the header line -------------------------------------


def test_sort_by_orders_on_the_rendered_text_and_is_stable():
    table = Table(["state", "note"], [["b", "2"], ["a", "1"], ["b", "0"]])
    assert table.sort_by(0) is True  # the first change: b, a, b -> a, b, b
    # The reordered table renders exactly like one built in the new order.
    assert _texts(table.render(16)) == _texts(
        Table(["state", "note"], [["a", "1"], ["b", "2"], ["b", "0"]]).render(16)
    )
    assert table.sort_by(0) is False  # already in that order: a no-op answers False
    # reverse reverses the keys, not the ties: b, b keep their order, a last.
    assert table.sort_by(0, reverse=True) is True
    assert _texts(table.render(16)) == _texts(
        Table(["state", "note"], [["b", "2"], ["b", "0"], ["a", "1"]]).render(16)
    )
    # The key is the *rendered* text: styles and multi-segment cells sort by
    # their plain string, tuples by their string half.
    styled = Table(
        ["x"],
        [
            [[Segment("zz", INJECTED)]],
            [("aa", INJECTED)],
            ["mm"],
        ],
    )
    assert styled.sort_by(0, reverse=True) is True
    assert _data_rows(styled.render(10)) == ["\u2502 zz \u2502", "\u2502 mm \u2502", "\u2502 aa \u2502"]
    # A column the headers do not cover (or a negative one) reads as the
    # empty string for every row: the stable sort leaves the order alone.
    assert table.sort_by(9) is False
    assert table.sort_by(-1) is False
    assert Table(["A"], []).sort_by(0) is False  # nothing to order
    # The header row is never part of the sort: it stays the header.
    assert table.render(16)[1].text == "\u2502 state \u2502 note \u2502"


def test_sort_by_follows_the_record_not_the_row_number():
    table = Table(["k"], [["c"], ["a"], ["b"]])
    table.index = 0  # the cursor sits on "c"
    assert table.activate() is True and table.chosen == 0
    table.hover = True
    table.hover_at(3, 0)  # the pointer marks the first data row ("c")
    assert table.sort_by(0) is True  # a, b, c
    assert table.index == 2 and table.selected == ["c"]  # the cursor followed "c"
    assert table.chosen == 2  # the pending pick names the same record
    assert table.render(9)[7].text == "\u2502 c \u2502"  # ... the banded row
    # D1: the shipped ``ground_active`` and ``hover`` are NONE, so a default
    # render paints no band on either the cursor row or the hovered one.
    assert not any(seg.style.reverse for seg in table.render(9)[7].segments)
    # A stale position (a host swapped the rows out) is left as it reads.
    table.rows.clear()
    table.sort_by(0)
    assert table.index == 2 and table.selected is None  # still reads "no row"
    # And the click map follows the new order: row 3 now renders "a".
    reordered = Table(["k"], [["b"], ["a"]])
    assert reordered.sort_by(0) is True
    assert reordered.click(3, 0) is True and reordered.selected == ["a"]
    assert reordered.click(5, 0) is True and reordered.selected == ["b"]


def test_set_widths_pins_budgets_and_the_render_clamps_them():
    table = Table(["A", "B"], [["xx", "yyyyyyyy"]])
    natural = table.render(30)
    assert natural[0].text == "\u250c\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510"
    table.set_widths([6, 2])  # an explicit budget pads and ellipsizes per column
    pinned = table.render(30)
    assert _texts(pinned) == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2500\u2510",
        "\u2502 A      \u2502 B  \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2500\u2524",
        "\u2502 xx     \u2502 y\u2026 \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2500\u2518",
    ]
    table.set_widths(None)  # ... and None is the way back to the measured widths
    assert _texts(table.render(30)) == _texts(natural)
    # The clamp: a too-large total shrinks proportionally, a budget below one
    # reads as one, and no row ever exceeds the width (the frame stays one
    # width, whatever the budgets came to).
    table.set_widths([40, 40])
    squeezed = table.render(20)
    assert len({row.width for row in squeezed}) == 1
    assert squeezed[0].width <= 20
    assert _texts(squeezed)[1] == "\u2502 A      \u2502 B      \u2502"  # 6 + 6, floored
    table.set_widths([0, -5])
    floored = table.render(12)
    assert len({row.width for row in floored}) == 1 and floored[0].width <= 12
    assert _texts(floored)[1] == "\u2502 A \u2502 B \u2502"  # two one-column budgets
    # A pinned list shorter than the columns leaves the rest measured.
    table.set_widths([2])
    assert _texts(table.render(30))[3] == "\u2502 xx \u2502 yyyyyyyy \u2502"
    # The pinned list is copied: a caller's later edit does not leak in.
    widths = [3, 3]
    table.set_widths(widths)
    widths[0] = 30
    assert _texts(table.render(30))[3] == "\u2502 xx  \u2502 yy\u2026 \u2502"
    # Sorting and pinning compose: the budgets are the render's, the order
    # the host's.
    ordering = Table(["A"], [["b"], ["a"]])
    ordering.set_widths([5])
    assert ordering.sort_by(0) is True
    assert _data_rows(ordering.render(20)) == ["\u2502 a     \u2502", "\u2502 b     \u2502"]


@pytest.mark.parametrize("width", [4, 9, 10, 12, 20, 40, 80])
def test_header_line_is_byte_identical_to_the_grids_header_row(width):
    table = Table(
        ["state", "note"],
        [["ok", "fine"], ["\u26a0\ufe0f Blocked", "hmm"]],
        aligns=["left", "right"],
    )
    line = table.header_line(width)
    assert line is not None and line == table.render(width)[1]
    assert line.styled() == table.render(width)[1].styled()
    # Explicit widths are the same budgets for both: the pinned line and the
    # scrolled header still agree.
    table.set_widths([8, 4])
    for pinned_width in (10, 30, 60):
        pinned = table.header_line(pinned_width)
        assert pinned is not None and pinned == table.render(pinned_width)[1]
    # The line never exceeds the width it was asked for.
    assert len(table.header_line(6).text) == 6
    # A table with no headers has no header line (its render is one blank row).
    assert Table([], [["x"]]).header_line(20) is None
    assert Table([], []).header_line(20) is None


def test_header_line_renders_through_the_recipe_as_a_pinned_row():
    """The documented sticky-header recipe: a one-row component, pinned top."""
    tui = headless_tui(30, 8)
    table = Table(["a", "b"], [[str(i), "x" * i] for i in range(6)])

    class StickyHeader:
        """The recipe's component: the table's header, rendered at the width."""

        def __init__(self, table):
            self.table = table

        def render(self, width):
            line = self.table.header_line(width)
            return [] if line is None else [line]

    tui.add(table, id="grid")
    tui.add(StickyHeader(table), id="sticky", pin="top")
    tui.paint()
    # The pinned row rides the top of the screen and carries the header line
    # the width asks for; the grid itself scrolls below it.
    assert tui.rows[0].text.startswith(table.header_line(30).text)
    assert tui.rows[0].text.startswith("\u2502 a \u2502 b ")
    below = [row.text for row in tui.rows[1:]]
    assert any(row.startswith("\u2502 5 \u2502") for row in below)  # the body is under it
    # The same call at a narrower width is the same line the grid draws there.
    narrow = table.header_line(10)
    assert narrow is not None and narrow == table.render(10)[1]
    assert narrow.width <= 10


# --- the marks ------------------------------------------------------------------------


def test_the_mark_column_appears_with_the_first_mark_and_leaves_the_grid_alone():
    """``toggle`` writes the cursor row's mark; the prefix rides the first cell."""
    table = Table(["name", "value"], [["alpha", "1"], ["beta", "2"]])
    plain = table.render(40)
    assert not any("[" in row.text for row in plain)  # unmarked: the bytes the table always had
    table.index = 1
    assert table.toggle() is True and list(table.marked) == [1]
    marked = table.render(40)
    assert any("[x] beta" in row.text for row in marked)  # the marked row
    assert any("[ ] alpha" in row.text for row in marked)  # and the pair on every other one
    assert len(marked) == len(plain)  # the frame and the row count are untouched
    # D1: the cursor row's band is NONE under the default theme, so the rows'
    # own text is what the cleared set restores (a themed band still spans
    # the width -- ``test_the_cursor_bands_every_data_cell_of_its_row_and_nothing_else``).
    assert marked[5].text.startswith("\u2502 [x] beta")  # the marked row
    table.toggle()
    assert [row.text.rstrip() for row in table.render(40)] == [
        row.text.rstrip() for row in plain
    ]  # a cleared set is the old grid again


def test_the_marks_are_a_row_input_the_snapshot_sees_and_the_sort_follows():
    """The revision names the marks, and a re-order re-points them at their records."""
    table = Table(["name"], [["b"], ["a"]])
    table.index = 1  # the "a" record
    before = table.revision()
    table.toggle()
    assert table.revision() != before  # the mark column is a row input
    assert any("[x] a" in row.text for row in table.render(40))
    assert table.sort_by(0) is True  # b, a -> a, b
    assert list(table.marked) == [0]  # the mark followed its record, not the row number
    assert any("[x] a" in row.text for row in table.render(40))
