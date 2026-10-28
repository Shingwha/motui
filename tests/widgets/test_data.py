"""List, Table and Tree: windowed data views, their cursors and gestures."""

from dataclasses import replace

import pytest

from motui.kernel.glyphs import GLYPHS
from motui.kernel.cell import Segment, Surface
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.text import WrapMode
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import List, Table, TreeNode, Tree

from tests.testing import key, many, paste, texts


# -- List ---------------------------------------------------------------------


def test_a_long_list_renders_a_window_and_counters():
    lst = List(many(1000), window=8)
    rows = texts(lst, 40)
    assert len(rows) == 9
    assert rows[0] == "\u2192 r0" and rows[-1] == "\u2193 992 more"
    lst.index = 500
    assert texts(lst, 40) == [
        "\u2191 496 more",
        "  r496",
        "  r497",
        "  r498",
        "  r499",
        "\u2192 r500",
        "  r501",
        "  r502",
        "  r503",
        "\u2193 496 more",
    ]


def test_a_short_list_renders_every_item_without_counters():
    lst = List(["one", "two", "three"], window=8)
    assert texts(lst, 20) == ["\u2192 one", "  two", "  three"]


def test_move_clamps_at_the_ends_and_clears_the_pending_pick():
    lst = List(["a", "b", "c"], window=2)
    assert lst.on_action("activate") is True and lst.take() == "a"
    assert lst.move(1) is True and lst.index == 1 and lst.take() is None
    assert lst.move(9) is True and lst.index == 2
    assert lst.move(1) is False
    assert lst.move(-9) is True and lst.index == 0
    assert lst.move(0) is False
    assert lst.end() is True and lst.index == 2
    assert lst.end() is False
    assert lst.home() is True and lst.index == 0


def test_index_clamps_and_an_empty_list_is_inert():
    lst = List(["a", "b", "c"])
    lst.index = 99
    assert lst.index == 2
    lst.index = -7
    assert lst.index == 0
    empty = List()
    empty.index = 5
    assert empty.index == 0 and list(empty.render(Constraints(width=20))) == []
    assert empty.move(1) is False and empty.on_action("activate") is False
    assert empty.home() is False and empty.end() is False


def test_activate_lands_the_cursor_item_once():
    lst = List(["a", "b", "c"], window=2)
    lst.index = 1
    assert lst.on_action("activate") is True and lst.take() == "b"
    assert lst.take() is None


def test_click_maps_rendered_rows_and_refuses_the_counter_rows():
    lst = List(many(100), window=4)
    lst.index = 50
    rows = texts(lst, 30)
    assert rows[0] == "\u2191 48 more" and rows[-1] == "\u2193 48 more"
    assert lst.on_click(Pos(x=0, y=0)) is False
    assert lst.on_click(Pos(x=0, y=len(rows) - 1)) is False
    assert lst.on_click(Pos(x=0, y=len(rows))) is False
    assert lst.on_click(Pos(x=99, y=2)) is True
    assert lst.index == 49 and lst.take() == "r49"


def test_the_prefix_jump_scans_from_the_top_case_insensitively():
    lst = List(["alpha", "Beta", "beta two", "Gamma", "delta"], window=3)
    lst.index = 4
    assert lst.on_key(key("b", "b")) is True
    assert lst.index == 1
    assert lst.on_key(key("d", "d")) is True and lst.index == 4
    assert lst.on_key(key("z", "z")) is True and lst.index == 4


def test_handle_consumes_its_own_keys_and_declines_the_hosts():
    lst = List(["a", "b", "c"], window=2)
    assert lst.on_key(key("down")) is True and lst.index == 1
    assert lst.on_key(key("up")) is True and lst.index == 0
    assert lst.on_key(key("end")) is True and lst.index == 2
    assert lst.on_key(key("home")) is True and lst.index == 0
    for event in (key("enter"), key("tab"), key("c-n"), key("space", " ")):
        assert lst.on_key(event) is False
    assert lst.on_paste(paste("text")) is False


def test_the_list_keymap_routes_its_keys_through_named_actions():
    lst = List(["a", "b", "c"], window=2)
    assert lst.on_action("next") is True and lst.index == 1
    assert lst.on_action("prev") is True and lst.index == 0
    assert lst.on_action("last") is True and lst.index == 2
    assert lst.on_action("first") is True and lst.index == 0
    # A movement action is consumed even at an edge, the old handle's rule.
    assert lst.on_action("prev") is True and lst.index == 0
    assert lst.on_action("activate") is True and lst.take() == "a"
    assert lst.on_action("toggle") is True and list(lst.marked) == [0]
    assert lst.on_action("nope") is False and list(lst.marked) == [0]
    assert not hasattr(List, "handle")
    assert List.keymap["down"] == "next"


def test_an_instance_keymap_rebind_never_writes_through_the_class_table():
    lst = List(["a", "b", "c"])
    other = List(["a", "b", "c"])
    lst.keymap["j"] = "next"
    assert "j" not in List.keymap
    assert "j" not in other.keymap
    assert lst.on_key(key("j", "j")) is True and lst.index == 1
    # The unbound list still falls through to its printable prefix jump.
    assert other.on_key(key("j", "j")) is True and other.index == 0
    del lst.keymap["j"]
    assert lst.on_key(key("j", "j")) is True and lst.index == 1


def test_the_typed_hooks_forward_to_the_1x_click_and_hover_verbs():
    lst = List(many(100), window=4)
    lst.index = 50
    assert lst.on_click(Pos(y=2, x=99)) is True
    assert lst.index == 49 and lst.take() == "r49"
    assert lst.on_hover(Pos(y=2, x=0)) is True
    assert lst.on_hover(Pos(y=2, x=0)) is False
    assert lst.on_hover(None) is True
    assert lst.on_click(Pos(y=0, x=0)) is False  # the counter row


def test_the_list_declares_its_capabilities():
    lst = List(["a"])
    assert (lst.focusable, lst.clickable, lst.hoverable, lst.activatable) == (
        True,
        True,
        True,
        True,
    )


def test_the_list_window_must_hold_at_least_one_row():
    with pytest.raises(ValueError):
        List(["a"], window=0)


def test_the_mark_column_appears_with_the_first_mark():
    lst = List(["alpha", "beta", "gamma"], window=4)
    plain = texts(lst, 30)
    assert lst.toggle() is True and list(lst.marked) == [0]
    assert texts(lst, 30) == ["\u2192 [x] alpha", "  [ ] beta", "  [ ] gamma"]
    assert lst.toggle() is True
    assert texts(lst, 30) == plain


def test_the_glyph_vocabulary_reaches_the_rows_and_counters():
    custom = replace(GLYPHS, cursor=">", more_up="^", more_down="v")
    lst = List(["a", "b"], window=1, glyphs=custom)
    assert texts(lst, 20) == ["> a", "v 1 more"]
    lst.index = 1
    assert texts(lst, 20) == ["^ 1 more", "> b"]
    wide = List(["alpha"], window=1, glyphs=replace(GLYPHS, cursor="\u6811"))
    assert texts(wide, 20) == ["\u6811 alpha"]
    bare = List(
        ["alpha", "beta"], window=2, glyphs=replace(GLYPHS, cursor="")
    )
    assert texts(bare, 20) == ["alpha", "beta"]


def test_the_mark_glyphs_are_padded_to_their_wider_member():
    lst = List(
        ["alpha", "beta"],
        window=2,
        glyphs=replace(GLYPHS, check_on="[x]", check_off="\u6811"),
    )
    lst.toggle()
    rows = lst.render(Constraints(width=20))
    assert rows[0].text == "\u2192 [x] alpha"
    assert rows[1].text == "  \u6811  beta"


def test_disabled_items_are_visible_but_skipped_and_refused():
    lst = List(["a", "b", "c", "d"], window=4, disabled_items=(1, 2))
    assert texts(lst, 20) == ["\u2192 a", "  b", "  c", "  d"]
    assert lst.move(1) is True and lst.index == 3
    assert lst.move(1) is False
    lst.index = 1
    assert lst.on_action("activate") is False and lst.take() is None
    assert lst.toggle() is False
    assert lst.on_click(Pos(x=0, y=1)) is False


def test_a_disabled_list_refuses_every_gesture_but_still_renders():
    lst = List(["a", "b"], window=2, disabled=True)
    assert lst.move(1) is False and lst.home() is False and lst.end() is False
    assert lst.on_action("activate") is False and lst.on_click(Pos(x=0, y=0)) is False
    assert lst.on_key(key("down")) is False
    assert texts(lst, 20) == ["\u2192 a", "  b"]


def test_rows_are_fitted_to_the_painting_width():
    lst = List(["a very long item text", "b"], window=2)
    assert all(row.width <= 10 for row in lst.render(Constraints(width=10)))


def test_list_answers_a_surface_and_honours_the_height_budget():
    lst = List(["a", "b", "c"], window=3)
    surface = lst.render(Constraints(width=10, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["\u2192 a", "  b"]
    assert surface.width == 10 and surface.height == 2
    # The 1.x int spelling still answers the whole window.
    assert [row.text for row in lst.render(Constraints(width=10))] == ["\u2192 a", "  b", "  c"]


# -- Table --------------------------------------------------------------------


def test_the_grid_keeps_one_width_and_rules_between_rows():
    rows = Table(["A"], [["1"], ["2"], ["3"]], cell_wrap=WrapMode.ELLIPSIS).render(Constraints(width=9))
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
    assert len({row.width for row in rows}) == 1


def test_an_over_wide_grid_shrinks_and_ellipsizes():
    rows = Table(["A", "B"], [["xxxxxxxxxx", "y"]], cell_wrap=WrapMode.ELLIPSIS).render(Constraints(width=12))
    assert [row.text for row in rows] == [
        "\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u252c\u2500\u2500\u2500\u2510",
        "\u2502 A    \u2502 B \u2502",
        "\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u253c\u2500\u2500\u2500\u2524",
        "\u2502 xxx\u2026 \u2502 y \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2534\u2500\u2500\u2500\u2518",
    ]


def test_cell_wrap_selects_how_an_over_wide_cell_fits():
    def render(mode: WrapMode) -> list[str]:
        table = Table(["A", "B"], [["xxxxxxxxxx", "y"]], cell_wrap=mode)
        return [row.text for row in table.render(Constraints(width=16))]

    ellipsis = render(WrapMode.ELLIPSIS)
    assert any("xxxxxxx\u2026" in text for text in ellipsis)
    clip = render(WrapMode.CLIP)
    assert any("xxxxxxxx" in text for text in clip)
    assert not any("\u2026" in text for text in clip)
    wrapped = render(WrapMode.WORD)
    assert len(wrapped) > len(ellipsis)  # the record takes more visual rows
    assert wrapped[3:5] == [
        "\u2502 xxxxxx \u2502 y   \u2502",
        "\u2502 xxxx   \u2502     \u2502",
    ]


def test_cell_wrap_char_breaks_between_cells_not_words():
    word = [
        row.text
        for row in Table(["n"], [["aaa bbb"]], cell_wrap=WrapMode.WORD).render(
            Constraints(width=9)
        )
    ]
    char = [
        row.text
        for row in Table(["n"], [["aaa bbb"]], cell_wrap=WrapMode.CHAR).render(
            Constraints(width=9)
        )
    ]
    assert word[3:5] == ["\u2502 aaa   \u2502", "\u2502 bbb   \u2502"]
    assert char[3:5] == ["\u2502 aaa b \u2502", "\u2502 bb    \u2502"]


def test_cell_wrap_overflow_keeps_the_natural_grid_width():
    cell = "x" * 200
    table = Table(["A"], [[cell]], cell_wrap=WrapMode.OVERFLOW)
    surface = table.render(Constraints(width=80))
    assert surface.width == 204  # one rule + two pads + 200 + one rule
    assert surface.height == 5
    # The header, the rules and the data row all share the natural width.
    assert {row.width for row in surface} == {204}
    assert surface[3].text == "\u2502 " + cell + " \u2502"
    # A pinned header keeps the same natural width as the grid.
    assert [line.width for line in table.header_lines(80)] == [204]
    # The default modes still answer the constrained width.
    for mode in (WrapMode.WORD, WrapMode.ELLIPSIS):
        narrow = Table(["A"], [[cell]], cell_wrap=mode).render(Constraints(width=80))
        assert narrow.width == 80
        assert all(row.width <= 80 for row in narrow)


def test_cell_wrap_overflow_honours_set_widths_pins():
    table = Table(["A"], [["x" * 200]], cell_wrap=WrapMode.OVERFLOW)
    table.set_widths([12])
    surface = table.render(Constraints(width=80))
    assert surface.width == 80  # 12 + two pads + two rules is still narrow
    assert surface[3].text == "\u2502 xxxxxxxxxxxx \u2502"
    assert not any("\u2026" in row.text for row in surface)


def test_cell_wrap_is_part_of_the_render_answer():
    headers, rows = ["A"], [["the quick brown fox"]]
    plain = Table(headers, rows, cell_wrap=WrapMode.WORD)
    clipped = Table(headers, rows, cell_wrap=WrapMode.ELLIPSIS)
    assert [row.text for row in plain.render(Constraints(width=12))] != [
        row.text for row in clipped.render(Constraints(width=12))
    ]


def test_a_long_cell_wraps_instead_of_ellipsizing():
    rows = [row.text for row in Table(["note"], [["the quick brown fox jumps"]]).render(Constraints(width=16))]
    assert rows[3:6] == [
        "\u2502 the quick    \u2502",
        "\u2502 brown fox    \u2502",
        "\u2502 jumps        \u2502",
    ]
    assert not any("\u2026" in text for text in rows)


def test_the_second_visual_line_maps_onto_its_record_for_click_and_hover():
    table = Table(["A"], [["one two three four"]])
    table.render(Constraints(width=12))
    assert table.on_click(Pos(x=0, y=4)) is True and table.index == 0
    assert table.on_hover(Pos(x=0, y=4)) is True
    assert table.on_hover(Pos(x=0, y=5)) is False  # the same record: the marking did not move
    assert table.on_click(Pos(x=0, y=6)) is False     # the bottom rule carries no data


def test_wrapping_keeps_segment_styles_links_and_actions():
    cell = [
        Segment("alpha ", Style(bold=True)),
        Segment("beta gamma", Style(italic=True), link="https://example.test"),
    ]
    rows = Table(["A"], [[cell]]).render(Constraints(width=12))
    runs = [seg for row in rows[3:6] for seg in row.segments if seg.text.strip()]
    assert any(seg.text.startswith("alpha") and seg.style.bold for seg in runs)
    linked = [seg for seg in runs if seg.link == "https://example.test"]
    assert any(seg.text.startswith("beta") and seg.style.italic for seg in linked)
    assert any(seg.text.startswith("gamma") and seg.style.italic for seg in linked)


def test_a_wrapped_record_bands_every_visual_line_and_marks_only_the_first():
    band = Style(reverse=True)
    table = Table(
        ["A"],
        [["one two three four"]],
        styles=Styles(rows=replace(DEFAULT_THEME.rows, active=band)),
    )
    table.index = 0
    assert table.toggle() is True
    rows = table.render(Constraints(width=12))
    data = rows[3:7]
    assert data[0].text == "\u2502 [x] one  \u2502"
    assert all("[x]" not in row.text for row in data[1:])
    assert all(row.text.startswith("\u2502") and row.text.endswith("\u2502") for row in data)
    assert all(any(seg.style.reverse for seg in row.segments) for row in data)
    assert not any(seg.style.reverse for seg in rows[1].segments)


@pytest.mark.parametrize("width", [0])
def test_a_degenerate_width_keeps_the_frame_structure(width):
    rows = Table(["A", "B"], [["1", "2"]]).render(Constraints(width=width))
    assert len(rows) == 5
    assert all(row.width <= width for row in rows)


def test_columns_are_measured_by_visible_width():
    rows = Table(["\u540d\u524d"], [["\u65e5\u672c"]]).render(Constraints(width=10))
    assert rows[3].text == "\u2502 \u65e5\u672c \u2502"
    assert len({row.width for row in rows}) == 1


def test_the_column_and_border_styles_reach_their_cells():
    injected = Style(underline=True)
    rows = Table(
        ["A", "B"],
        [[("1", injected), "x"]],
        styles=Styles(
            text=replace(DEFAULT_THEME.text, base=Style(bold=True)),
            borders=replace(DEFAULT_THEME.borders, grid=Style(italic=True)),
        ),
    ).render(Constraints(width=12))
    assert rows[1].segments[1].style.bold is False
    assert rows[1].segments[1].style.italic is False
    assert rows[3].segments[1].style.underline is True
    assert rows[3].segments[1].style.italic is False
    assert rows[0].segments[0].style.italic is True


@pytest.mark.parametrize(
    "aligns, header, data",
    [
        (
            ["right", "center", "left"],
            "\u2502   l \u2502  c  \u2502 r    \u2502",
            "\u2502   a \u2502 bb  \u2502 cccc \u2502",
        ),
    ],
)
def test_alignments_pad_inside_the_column_budget(aligns, header, data):
    rows = Table(["l", "c", "r"], [["a", "bb", "cccc"]], aligns=aligns).render(Constraints(width=20))
    assert rows[1].text == header and rows[3].text == data


def test_the_cursor_bands_the_data_cells_of_its_row_only():
    band = Style(reverse=True)
    table = Table(
        ["A", "B"],
        [["1", "x"], ["2", "y"]],
        styles=Styles(rows=replace(DEFAULT_THEME.rows, active=band)),
    )
    table.index = 1
    rows = table.render(Constraints(width=12))
    assert any(seg.style.reverse for seg in rows[5].segments)
    assert not any(seg.style.reverse for seg in rows[3].segments)
    assert not any(seg.style.reverse for seg in rows[1].segments)
    assert [row.text for row in rows] == [
        row.text for row in Table(["A", "B"], [["1", "x"], ["2", "y"]]).render(Constraints(width=12))
    ]


def test_index_clamps_and_none_clears_the_cursor():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    assert table.index is None
    table.index = 99
    assert table.index == 2 and table.selected == ["3"]
    table.index = -5
    assert table.index == 0
    table.index = None
    assert table.index is None and table.selected is None
    empty = Table(["A"], [])
    empty.index = 0
    assert empty.index is None and empty.selected is None


def test_move_clamps_and_the_first_step_lands_on_the_edge_it_leaves():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    assert table.move(1) is True and table.index == 0
    assert table.move(-1) is False
    assert table.move(2) is True and table.index == 2
    assert table.move(1) is False
    up = Table(["A"], [["1"], ["2"], ["3"]])
    assert up.move(-1) is True and up.index == 2
    assert Table(["A"], []).move(1) is False


def test_click_maps_rendered_data_rows_and_misses_the_frame():
    table = Table(["A"], [["1"], ["2"], ["3"]])
    rendered = table.render(Constraints(width=9))
    assert table.on_click(Pos(x=0, y=3)) is True and table.index == 0
    assert table.on_click(Pos(x=99, y=5)) is True and table.index == 1
    assert table.on_click(Pos(x=0, y=7)) is True and table.index == 2
    for row in (0, 1, 2, 4, 6, 8, 9, -1):
        assert table.on_click(Pos(x=0, y=row)) is False
    assert table.index == 2
    assert len(rendered) == 9


def test_activate_takes_the_row_index_once():
    table = Table(["A"], [["1"], ["2"]])
    assert table.on_action("activate") is False and table.take() is None
    table.index = 1
    assert table.on_action("activate") is True and table.take() == 1
    assert table.take() is None


def test_a_step_or_a_landing_click_clears_a_pending_result():
    table = Table(["A"], [["1"], ["2"]])
    table.index = 1
    assert table.on_action("activate") is True
    assert table.move(0) is False and table.take() is None
    assert table.on_action("activate") is True
    assert table.on_click(Pos(x=0, y=3)) is True and table.take() is None


def test_sort_by_orders_on_the_rendered_text_and_is_stable():
    table = Table(["state", "note"], [["b", "2"], ["a", "1"], ["b", "0"]])
    assert table.sort_by(0) is True
    assert [row.text for row in table.render(Constraints(width=16))] == [
        row.text for row in Table(["state", "note"], [["a", "1"], ["b", "2"], ["b", "0"]]).render(Constraints(width=16))
    ]
    assert table.sort_by(0) is False
    assert table.sort_by(0, reverse=True) is True
    assert [row.text for row in table.render(Constraints(width=16))] == [
        row.text
        for row in Table(["state", "note"], [["b", "2"], ["b", "0"], ["a", "1"]]).render(Constraints(width=16))
    ]
    assert Table(["A"], []).sort_by(0) is False


def test_sort_by_keeps_the_cursor_and_marks_on_their_records():
    table = Table(["k"], [["c"], ["a"], ["b"]])
    table.index = 0
    assert table.toggle() is True
    assert table.sort_by(0) is True
    assert table.index == 2 and table.selected == ["c"]
    assert list(table.marked) == [2]
    assert any("[x] c" in row.text for row in table.render(Constraints(width=20)))


def test_set_widths_pins_budgets_and_the_render_clamps_them():
    table = Table(["A", "B"], [["xx", "yyyyyyyy"]], cell_wrap=WrapMode.ELLIPSIS)
    natural = [row.text for row in table.render(Constraints(width=30))]
    table.set_widths([6, 2])
    pinned = [row.text for row in table.render(Constraints(width=30))]
    assert pinned[1] == "\u2502 A      \u2502 B  \u2502"
    assert pinned[3] == "\u2502 xx     \u2502 y\u2026 \u2502"
    table.set_widths(None)
    assert [row.text for row in table.render(Constraints(width=30))] == natural
    table.set_widths([40, 40])
    squeezed = table.render(Constraints(width=20))
    assert len({row.width for row in squeezed}) == 1
    assert squeezed[0].width <= 20


@pytest.mark.parametrize("width", [12])
def test_header_line_is_the_grids_own_header_row(width):
    table = Table(["state", "note"], [["ok", "fine"]], aligns=["left", "right"])
    line = table.header_line(width)
    assert line is not None and line == table.render(Constraints(width=width))[1]
    assert Table([], [["x"]]).header_line(20) is None


def test_the_mark_column_rides_the_first_cell_of_every_data_row():
    table = Table(["name", "value"], [["alpha", "1"], ["beta", "2"]])
    plain = [row.text for row in table.render(Constraints(width=40))]
    table.index = 1
    assert table.toggle() is True and list(table.marked) == [1]
    marked = [row.text for row in table.render(Constraints(width=40))]
    assert any("[x] beta" in text for text in marked)
    assert any("[ ] alpha" in text for text in marked)
    assert len(marked) == len(plain)
    table.toggle()
    assert [row.text for row in table.render(Constraints(width=40))] == plain


def test_disabled_rows_and_tables_refuse_their_gestures():
    table = Table(["A"], [["0"], ["1"], ["2"], ["3"]], disabled_items=(1, 2))
    assert table.move(1) is True and table.index == 0
    assert table.move(1) is True and table.index == 3
    table.index = 1
    assert table.on_action("activate") is False and table.toggle() is False
    assert table.on_click(Pos(x=0, y=5)) is False
    assert table.on_click(Pos(x=0, y=9)) is True and table.index == 3
    dead = Table(["A"], [["1"]], disabled=True)
    assert dead.move(1) is False and dead.on_click(Pos(x=0, y=3)) is False


def test_table_answers_a_surface_and_honours_the_height_budget():
    table = Table(["A"], [["1"], ["2"], ["3"]], cell_wrap=WrapMode.ELLIPSIS)
    surface = table.render(Constraints(width=9, max_height=5))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == [
        "\u250c\u2500\u2500\u2500\u2510",
        "\u2502 A \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
        "\u2502 1 \u2502",
        "\u251c\u2500\u2500\u2500\u2524",
    ]
    assert surface.width == 9 and surface.height == 5
    # The 1.x int spelling still answers the whole grid; the budget did not
    # enter the memory's key, so the memo serves both answers.
    full = table.render(Constraints(width=9))
    assert len(full) == 9
    again = table.render(Constraints(width=9, max_height=5))
    assert [row.text for row in again] == [row.text for row in surface]


def test_the_table_keymap_routes_its_keys_through_named_actions():
    table = Table(["A"], [["0"], ["1"], ["2"]])
    assert table.on_key(key("down")) is True and table.index == 0
    assert table.on_key(key("down")) is True and table.index == 1
    assert table.on_key(key("up")) is True and table.index == 0
    assert table.on_key(key("up")) is False  # clamped at the first data row
    assert table.on_key(key("end")) is False  # unbound: home/end stay the host's
    assert table.on_key(key("enter")) is True and table.take() == 0
    assert table.on_action("toggle") is True and list(table.marked) == [0]
    assert table.on_action("nope") is False
    assert not hasattr(Table, "handle")
    assert Table.keymap["down"] == "next" and Table.keymap["enter"] == "activate"


def test_an_instance_table_keymap_rebind_is_private_to_the_instance():
    table = Table(["A"], [["0"], ["1"]])
    other = Table(["A"], [["0"], ["1"]])
    table.keymap["j"] = "next"
    assert "j" not in Table.keymap
    assert "j" not in other.keymap
    assert table.on_key(key("j", "j")) is True and table.index == 0
    assert other.on_key(key("j", "j")) is False and other.index is None


def test_the_table_typed_hooks_forward_to_click_and_hover():
    table = Table(["A"], [["0"], ["1"]])
    table.render(Constraints(width=9))
    assert table.on_click(Pos(y=5, x=99)) is True and table.index == 1
    assert table.on_hover(Pos(y=5, x=0)) is True
    assert table.on_hover(Pos(y=5, x=0)) is False
    assert table.on_hover(None) is True
    assert table.on_click(Pos(y=0, x=0)) is False  # the top rule


def test_take_reads_the_table_result_once():
    table = Table(["A"], [["0"]])
    table.index = 0
    assert table.take() is None
    assert table.on_action("activate") is True and table.take() == 0
    table.on_action("activate")
    assert table.take() == 0


def test_the_table_declares_its_capabilities():
    table = Table(["A"], [["0"]])
    assert (table.focusable, table.clickable, table.hoverable, table.activatable) == (
        True,
        True,
        True,
        True,
    )


# -- Tree ---------------------------------------------------------------------


def sample() -> TreeNode:
    """A collapsed folder with a leaf and a nested collapsed folder."""
    return TreeNode(
        "src",
        children=[
            TreeNode("app.py"),
            TreeNode("lib", children=[TreeNode("a.py"), TreeNode("b.py")]),
        ],
    )


def test_a_collapsed_root_renders_one_row():
    tree = Tree([sample()])
    assert texts(tree, 30) == ["\u25b8 src"]
    assert tree.selected is tree.root_nodes[0]


def test_activate_expands_and_collapses_the_visible_rows():
    tree = Tree([sample()])
    assert tree.on_action("activate") is True
    assert texts(tree, 30) == ["\u25be src", "    app.py", "  \u25b8 lib"]
    assert tree.on_action("activate") is True
    assert texts(tree, 30) == ["\u25b8 src"]


def test_nested_expansion_indents_with_spaces_only():
    tree = Tree([sample()])
    tree.on_action("activate")
    tree.move(2)
    assert tree.on_action("activate") is True
    assert texts(tree, 30) == [
        "\u25be src",
        "    app.py",
        "  \u25be lib",
        "      a.py",
        "      b.py",
    ]
    assert all("\u2502" not in row for row in texts(tree, 30))


def test_move_clamps_inside_the_visible_rows():
    tree = Tree([sample()])
    tree.on_action("activate")
    tree.move(1)
    assert tree.selected.label == "app.py"
    tree.move(-9)
    assert tree.selected.label == "src"
    tree.move(99)
    assert tree.selected.label == "lib"
    assert tree.move(1) is False


def test_click_places_the_cursor_on_the_visible_row_and_ignores_the_column():
    tree = Tree([sample()])
    tree.on_action("activate")
    for col in (0, 3, 999):
        assert tree.on_click(Pos(x=col, y=1)) is True and tree.selected.label == "app.py"
    for row in (-1, 3, 9):
        assert tree.on_click(Pos(x=0, y=row)) is False
    assert tree.selected.label == "app.py"


def test_a_leaf_and_an_empty_tree_decline_activation():
    leaf = Tree([TreeNode("solo")])
    assert leaf.on_action("activate") is False and texts(leaf, 20) == ["  solo"]
    empty = Tree([])
    assert empty.on_action("activate") is False and empty.move(1) is False
    assert empty.selected is None and list(empty.render(Constraints(width=10))) == []


def test_collapsing_re_clamps_the_cursor_into_the_new_rows():
    tree = Tree([sample()])
    tree.on_action("activate")
    lib = tree.root_nodes[0].children[1]
    lib.expanded = True
    tree.move(2)
    assert tree.on_action("activate") is True and tree.selected is lib
    assert len(tree.render(Constraints(width=30))) == 3
    lib.expanded = True
    tree.move(4)
    lib.expanded = False
    assert tree.selected is lib


def test_filter_prunes_to_the_matches_and_keeps_ancestors_open():
    tree = Tree(
        [
            sample(),
            TreeNode("docs", children=[TreeNode("guide")]),
        ]
    )
    assert tree.filter("lib") is True
    assert texts(tree, 30) == ["\u25be src", "  \u25b8 lib"]
    assert tree.filter("B.PY") is True
    assert texts(tree, 30) == ["\u25be src", "  \u25be lib", "      b.py"]
    assert tree.filter("guide") is True
    assert texts(tree, 30) == ["\u25be docs", "    guide"]
    assert tree.filter("nope") is True
    assert list(tree.render(Constraints(width=30))) == [] and tree.selected is None
    assert tree.filter(None) is True
    assert tree.filter(None) is False


def test_filter_never_rewrites_the_users_expansion_flags():
    tree = Tree([sample()])
    src = tree.root_nodes[0]
    src.children[1].expanded = True
    before = texts(tree, 30)
    assert tree.filter("a.py") is True
    assert src.expanded is False and src.children[1].expanded is True
    assert tree.filter(None) is True
    assert texts(tree, 30) == before


def test_jump_steps_to_the_next_visible_label_and_wraps():
    tree = Tree([sample()])
    src = tree.root_nodes[0]
    src.expanded = True
    src.children[1].expanded = True
    src.children[1].children[1].label = "Beta"
    assert tree.jump("b") is True and tree.selected.label == "Beta"
    assert tree.jump("s") is True and tree.selected.label == "src"
    assert tree.jump("B") is True and tree.selected.label == "Beta"
    assert tree.jump("B") is False
    assert tree.jump("z") is False and tree.jump("") is False and tree.jump("ab") is False


def test_the_fold_glyphs_come_from_the_vocabulary():
    custom = Tree(
        [sample()], glyphs=replace(GLYPHS, fold_open="v", fold_closed=">")
    )
    custom.on_action("activate")
    assert texts(custom, 30) == ["v src", "    app.py", "  > lib"]
    bare = Tree(
        [sample()], glyphs=replace(GLYPHS, fold_open="", fold_closed="")
    )
    bare.on_action("activate")
    assert texts(bare, 30) == ["src", "  app.py", "  lib"]
    wide = Tree(
        [sample()], glyphs=replace(GLYPHS, fold_open="\u5f00", fold_closed="\u5173")
    )
    wide.on_action("activate")
    assert texts(wide, 30) == ["\u5f00 src", "     app.py", "  \u5173 lib"]


def test_disabled_nodes_are_skipped_and_refused():
    tree = Tree(
        [
            TreeNode("a"),
            TreeNode("b", disabled=True),
            TreeNode("c"),
        ]
    )
    assert tree.move(1) is True and tree.selected.label == "c"
    assert tree.on_click(Pos(x=0, y=1)) is False
    tree.move(-9)
    assert tree.on_action("activate") is False  # a leaf, and the first row is enabled
    dead = Tree([sample()], disabled=True)
    assert dead.move(1) is False and dead.on_click(Pos(x=0, y=0)) is False
    assert dead.on_action("activate") is False


def test_tree_answers_a_surface_and_honours_the_height_budget():
    tree = Tree([sample()])
    tree.on_action("activate")
    surface = tree.render(Constraints(width=30, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["\u25be src", "    app.py"]
    assert surface.width == 30 and surface.height == 2
    # The 1.x int spelling still answers every visible row.
    assert [row.text for row in tree.render(Constraints(width=30))] == [
        "\u25be src",
        "    app.py",
        "  \u25b8 lib",
    ]


def test_the_tree_keymap_folds_and_moves_through_named_actions():
    tree = Tree([sample()])
    assert tree.on_key(key("enter")) is True
    assert texts(tree, 30)[0] == "\u25be src"
    assert tree.on_action("collapse") is True
    assert texts(tree, 30) == ["\u25b8 src"]
    assert tree.on_action("collapse") is False
    assert tree.on_action("expand") is True
    assert tree.on_action("next") is True and tree.selected.label == "app.py"
    assert tree.on_action("prev") is True and tree.selected.label == "src"
    assert tree.on_action("prev") is False  # clamped at the first visible row
    assert tree.on_action("nope") is False
    assert not hasattr(Tree, "handle")
    assert tree.take() is None


def test_an_instance_tree_keymap_rebind_is_private_to_the_instance():
    tree = Tree([sample()])
    other = Tree([sample()])
    tree.on_action("activate")  # the root opens, so a step has somewhere to land
    tree.keymap["j"] = "next"
    assert "j" not in Tree.keymap
    assert "j" not in other.keymap
    assert tree.on_key(key("j", "j")) is True and tree.selected.label == "app.py"
    assert other.on_key(key("j", "j")) is False and other.selected.label == "src"


def test_the_tree_typed_hooks_forward_to_click_and_hover():
    tree = Tree([sample()])
    tree.on_action("activate")
    assert tree.on_click(Pos(y=1, x=0)) is True and tree.selected.label == "app.py"
    assert tree.on_hover(Pos(y=1, x=0)) is True
    assert tree.on_hover(Pos(y=1, x=0)) is False
    assert tree.on_hover(None) is True


def test_the_tree_declares_its_capabilities():
    tree = Tree([sample()])
    assert (tree.focusable, tree.clickable, tree.hoverable, tree.activatable) == (
        True,
        True,
        True,
        True,
    )
