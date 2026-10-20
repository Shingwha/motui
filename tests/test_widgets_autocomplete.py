
from motui.kernel.lines import Line, Segment
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Theme
from motui.widgets import Autocomplete
from motui.widgets.choice import Option

"""Tests for motui.widgets.autocomplete (Autocomplete).

``Autocomplete`` is the filter layer of the menu family: ``set_query`` narrows
the rows (prefix matches first, an empty query matches all), while the cursor,
the ``max_rows`` window, the ``(i/n)`` counter and the row rendering are the
inherited :class:`~motui.widgets.choice.Select` behaviour.
"""

import pytest


from _doubles import texts

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
DESCRIPTION = Style(fg="#123456")


def test_an_empty_query_matches_every_option_in_order():
    auto = Autocomplete(options=[Option("alpha"), Option("beta"), Option("gamma")])
    assert auto.query == "" and auto.is_empty is False
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(auto, 30) == ["\u2192 alpha", "  beta", "  gamma"]
    assert auto.selected == Option("alpha")


@pytest.mark.parametrize(
    "query, matched",
    [
        ("rea", ["read", "ready", "bread", "thread", "spread"]),  # prefix group first
        ("read", ["read", "ready", "bread", "thread", "spread"]),  # "ready" prefixes too
        ("zzz", []),  # nothing matches
    ],
)
def test_prefix_matches_rank_before_substring_matches(query, matched):
    options = [Option("read"), Option("bread"), Option("thread"), Option("ready"), Option("spread")]
    auto = Autocomplete(options=options)
    auto.set_query(query)
    if not matched:
        assert auto.is_empty is True and auto.selected is None
        assert auto.render(30) == []  # an empty result renders zero rows
        assert auto.move(1) is False  # and the cursor cannot move
        return
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(auto, 30) == [
        "\u2192 " + matched[0],
        *("  " + label for label in matched[1:]),
    ]
    assert auto.selected.label == matched[0]


@pytest.mark.parametrize(
    "start, delta, label, moved",
    [
        (0, 1, "a2", True),
        (1, 1, "a1", True),  # off the last match onto the first
        (0, -1, "a2", True),  # off the first match onto the last
    ],
)
def test_move_wraps_inside_the_matches(start, delta, label, moved):
    auto = Autocomplete(options=[Option("a1"), Option("a2"), Option("b1")])
    auto.set_query("a")  # two matches: a1, a2
    auto.index = start
    assert auto.move(delta) is moved
    assert auto.selected == Option(label)


def test_set_query_replaces_the_matches_and_resets_the_cursor():
    auto = Autocomplete(options=[Option("a1"), Option("a2"), Option("b1")])
    auto.set_query("a")
    auto.index = 1
    auto.set_query("b")
    assert auto.selected == Option("b1")
    auto.set_query("")
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(auto, 30) == ["\u2192 a1", "  a2", "  b1"]


@pytest.mark.parametrize(
    "deltas, rows",
    [
        # D1: the cursor row's band is NONE, so every row keeps its own bytes.
        ([], ["\u2192 item0", "  item1", "  item2", "(1/10)"]),  # the window hangs at the top
        ([2], ["  item0", "  item1", "\u2192 item2", "(3/10)"]),  # the marker follows the cursor
        ([2, 1], ["  item1", "  item2", "\u2192 item3", "(4/10)"]),  # scrolled by one
        ([2, 1, 6], ["  item7", "  item8", "\u2192 item9", "(10/10)"]),  # the cursor as the last row
    ],
)
def test_max_rows_truncates_and_the_window_follows_the_cursor(deltas, rows):
    auto = Autocomplete(options=[Option(f"item{i}") for i in range(10)], max_rows=3)
    for delta in deltas:
        auto.move(delta)
    assert texts(auto, 30) == rows
    assert len(auto.render(30)) == 4  # max_rows rows plus the counter


def test_the_description_column_is_measured_over_the_whole_universe():
    auto = Autocomplete(options=[
        Option("a", description="x"),
        Option("a-long-label", description="y"),
        Option("b", description="z"),
    ])
    # D1: the cursor row's band is NONE, so the row keeps its own bytes.
    assert texts(auto, 40)[0] == "\u2192 a" + " " * 13 + "x"
    auto.set_query("b")  # one match left: the column does not jump
    assert texts(auto, 40)[0] == "\u2192 b" + " " * 13 + "z"


def test_click_selects_a_row_of_the_visible_window():
    auto = Autocomplete(options=[Option(f"item{i}") for i in range(10)], max_rows=3)
    assert auto.click(2, 0) is True and auto.selected == Option("item2")
    # The cursor sits at 5: the window is rows item3..item5, and a click
    # maps against it exactly as the last render drew it.
    scrolled = Autocomplete(options=[Option(f"item{i}") for i in range(10)], max_rows=3)
    scrolled.index = 5
    assert scrolled.click(0, 0) is True and scrolled.selected == Option("item3")
    scrolled.index = 5
    assert scrolled.click(2, 0) is True and scrolled.selected == Option("item5")
    for row in (-1, 3, 9):  # past either end of the window: no hit
        scrolled.index = 5
        assert scrolled.click(row, 0) is False and scrolled.selected == Option("item5")
    scrolled.set_query("zzz")  # nothing matches: no row to hit
    assert scrolled.click(0, 0) is False
    assert Autocomplete(options=[Option("x")], max_rows=0).click(0, 0) is False


def test_styles_round_trip_and_the_row_always_fits():
    theme = Theme(accent=SELECTED, dim=DESCRIPTION)
    # D3: the cursor row carries the ground_active band underneath its
    # styles, so every segment of the row rides on it.  D1: that band is
    # NONE under the default theme, so the label keeps its own style.
    auto = Autocomplete(options=[Option("long-option-label", description="description")], theme=theme)
    rows = auto.render(10)
    assert rows[0].width <= 10  # always fit back to the painting width
    assert rows[0].segments[0].style == SELECTED
    hinted = Autocomplete(options=[Option("a", description="d"), Option("b")], theme=theme)
    hinted.move(1)
    assert hinted.render(20)[0].segments[-1].style == DESCRIPTION  # a resting row
    assert Autocomplete(options=[Option("x")]).render(0) == [Line()]
    # explicit style parameters round-trip exactly like the theme fields
    explicit = Autocomplete(
        options=[Option("one", description="d")],
        selected_style=SELECTED,
        description_style=DESCRIPTION,
    )
    # D1: the band is NONE under the default theme, so the row is its own
    # four segments with no pad.
    assert explicit.render(20)[0].segments == (
        Segment("\u2192 ", SELECTED),
        Segment("one", SELECTED),
        Segment("  "),
        Segment("d", DESCRIPTION),
    )
