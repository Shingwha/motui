"""Autocomplete: a Select whose rows are the filtered matches of one query."""

from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.widgets import Autocomplete, Option
from tests.testing import texts


def test_an_empty_query_matches_every_option_in_order():
    auto = Autocomplete(options=[Option("alpha"), Option("beta"), Option("gamma")])
    assert auto.query == "" and auto.is_empty is False
    assert texts(auto, 30) == ["\u2192 alpha", "  beta", "  gamma"]
    assert auto.selected == Option("alpha")


def test_prefix_matches_rank_before_substring_matches():
    options = [Option("read"), Option("bread"), Option("thread"), Option("ready")]
    for query, matched in [("rea", ["read", "ready", "bread", "thread"]), ("zzz", [])]:
        auto = Autocomplete(options=options)
        auto.set_query(query)
        if not matched:
            assert auto.is_empty is True and auto.selected is None
            assert list(auto.render(Constraints(width=30))) == [] and auto.move(1) is False
            continue
        assert texts(auto, 30) == [
            "\u2192 " + matched[0],
            *("  " + label for label in matched[1:]),
        ]


def test_the_filter_is_case_insensitive_and_keeps_the_labels_case():
    auto = Autocomplete([Option("Alpha"), Option("beta"), Option("GAMMA")])
    auto.set_query("a")
    assert texts(auto, 30) == ["\u2192 Alpha", "  beta", "  GAMMA"]
    auto.set_query("GA")
    assert texts(auto, 30) == ["\u2192 GAMMA"]


def test_move_wraps_inside_the_matches():
    for start, delta, label in [(0, 1, "a2"), (1, 1, "a1"), (0, -1, "a2")]:
        auto = Autocomplete([Option("a1"), Option("a2"), Option("b1")])
        auto.set_query("a")
        auto.index = start
        assert auto.move(delta) is True
        assert auto.selected == Option(label)


def test_set_query_resets_the_cursor_and_clears_a_pending_pick():
    auto = Autocomplete([Option("a1"), Option("a2"), Option("b1")])
    auto.set_query("a")
    auto.index = 1
    auto.on_action("activate")
    auto.set_query("b")
    assert auto.selected == Option("b1") and auto.take() is None
    auto.set_query("")
    assert texts(auto, 30) == ["\u2192 a1", "  a2", "  b1"]


def test_max_rows_windows_the_matches_with_a_counter():
    for deltas, rows in [
        ([], ["\u2192 item0", "  item1", "  item2", "(1/10)"]),
        ([2, 1, 6], ["  item7", "  item8", "\u2192 item9", "(10/10)"]),
    ]:
        auto = Autocomplete([Option(f"item{i}") for i in range(10)], max_rows=3)
        for delta in deltas:
            auto.move(delta)
        assert texts(auto, 30) == rows


def test_the_description_column_is_measured_over_the_whole_universe():
    auto = Autocomplete(
        [
            Option("a", description="x"),
            Option("a-long-label", description="y"),
            Option("b", description="z"),
        ]
    )
    assert texts(auto, 40)[0] == "\u2192 a" + " " * 13 + "x"
    auto.set_query("b")
    assert texts(auto, 40)[0] == "\u2192 b" + " " * 13 + "z"


def test_click_selects_a_row_of_the_visible_window():
    auto = Autocomplete([Option(f"item{i}") for i in range(10)], max_rows=3)
    auto.index = 5
    assert auto.on_click(Pos(x=0, y=0)) is True and auto.selected == Option("item3")
    auto.index = 5
    assert auto.on_click(Pos(x=0, y=2)) is True and auto.selected == Option("item5")
    auto.index = 5
    assert auto.on_click(Pos(x=0, y=3)) is False and auto.selected == Option("item5")


def test_set_query_clears_the_pointer_mark():
    auto = Autocomplete([Option("alpha"), Option("beta")])
    assert auto.on_hover(Pos(x=0, y=1)) is True
    auto.set_query("beta")
    assert auto.on_hover(None) is False
    assert texts(auto, 20) == ["\u2192 beta"]
