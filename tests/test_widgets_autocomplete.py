"""Tests for mocode_tui.widgets.autocomplete (Autocomplete).

``set_query`` filters the options, prefix matches first (an empty query
matches all); the cursor clamps, the rows follow the shared ``Select`` layout.
"""

import pytest

from mocode_tui.widgets.autocomplete import Autocomplete
from mocode_tui.widgets.choice import Option
from mocode_tui.core.block import Clickable
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import Style
from mocode_tui.core.theme import Theme

from _doubles import texts

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
HINT = Style(fg="#123456")


def test_an_empty_query_matches_every_option_in_order():
    auto = Autocomplete(options=[Option("alpha"), Option("beta"), Option("gamma")])
    assert auto.query == "" and auto.is_empty is False
    assert texts(auto, 30) == ["\u276e alpha", "  beta", "  gamma"]
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
    assert texts(auto, 30) == ["\u276e " + matched[0], *("  " + label for label in matched[1:])]
    assert auto.selected.label == matched[0]


@pytest.mark.parametrize(
    "start, delta, label, moved",
    [
        (0, 1, "a2", True),
        (1, 5, "a2", False),  # already at the end: clamped, nothing moved
        (1, -9, "a1", True),  # clamped at the start, no wrap
        (0, -1, "a1", False),  # already at the top
    ],
)
def test_move_clamps_inside_the_matches(start, delta, label, moved):
    auto = Autocomplete(options=[Option("a1"), Option("a2"), Option("b1")])
    auto.set_query("a")  # two matches: a1, a2
    auto.index = start
    assert auto.move(delta) is moved
    assert auto.selected == Option(label)
    auto.set_query("b")  # a new query replaces the match list and resets the cursor
    assert auto.selected == Option("b1")


@pytest.mark.parametrize(
    "deltas, rows",
    [
        ([], ["\u276e item0", "  item1", "  item2"]),  # the window hangs at the top
        ([2], ["  item0", "  item1", "\u276e item2"]),  # the marker follows the cursor
        ([2, 1], ["  item1", "  item2", "\u276e item3"]),  # scrolled by one
        ([2, 1, 6], ["  item7", "  item8", "\u276e item9"]),  # the cursor as the last row
    ],
)
def test_max_rows_truncates_and_the_window_follows_the_cursor(deltas, rows):
    auto = Autocomplete(options=[Option(f"item{i}") for i in range(10)], max_rows=3)
    for delta in deltas:
        auto.move(delta)
    assert texts(auto, 30) == rows
    assert len(auto.render(30)) == 3  # never more than max_rows


def test_click_selects_a_row_of_the_visible_window():
    auto = Autocomplete(options=[Option(f"item{i}") for i in range(10)], max_rows=3)
    assert isinstance(auto, Clickable)
    assert auto.click(2) is True and auto.selected == Option("item2")
    # The cursor sits at 5: the window is rows item3..item5, and a click
    # maps against it exactly as the last render drew it.
    scrolled = Autocomplete(options=[Option(f"item{i}") for i in range(10)], max_rows=3)
    scrolled.index = 5
    assert scrolled.click(0) is True and scrolled.selected == Option("item3")
    scrolled.index = 5
    assert scrolled.click(2) is True and scrolled.selected == Option("item5")
    for row in (-1, 3, 9):  # past either end of the window: no hit
        scrolled.index = 5
        assert scrolled.click(row) is False and scrolled.selected == Option("item5")
    scrolled.set_query("zzz")  # nothing matches: no row to hit
    assert scrolled.click(0) is False
    assert Autocomplete(options=[Option("x")], max_rows=0).click(0) is False


def test_styles_round_trip_and_the_row_always_fits():
    theme = Theme(selection=SELECTED, dim=HINT)
    auto = Autocomplete(options=[Option("long-option-label", hint="hint")], theme=theme)
    rows = auto.render(10)
    assert rows[0].width <= 10  # always fit back to the painting width
    assert rows[0].segments[0].style == SELECTED
    hinted = Autocomplete(options=[Option("a", hint="h"), Option("b")], theme=theme)
    hinted.move(1)
    assert hinted.render(20)[0].segments[1].style == HINT
    assert Autocomplete(options=[Option("x")]).render(0) == [Line()]
    # explicit style parameters round-trip exactly like the theme fields
    explicit = Autocomplete(
        options=[Option("one", hint="h")], selected_style=SELECTED, hint_style=HINT
    )
    assert explicit.render(20)[0].segments == (Segment("\u276e one  h", SELECTED),)
