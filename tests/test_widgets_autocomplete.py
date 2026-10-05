"""Tests for mocode_tui.widgets.autocomplete (Autocomplete).

Contracts (the W4 ticket + the module docstring): ``set_query`` filters the
options with prefix matches ranked before substring matches (empty query =
every option, in the original order); the cursor clamps inside the matches
without wrapping; rendering yields at most ``max_rows`` rows with the same
row layout as ``Select`` (``\\u276e `` marker, one continuous selected band,
trailing dim hint); an empty result renders zero rows.
"""

from mocode_tui.widgets.autocomplete import Autocomplete
from mocode_tui.widgets.choice import Option
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import DIM, NONE, SELECTION, Style
from mocode_tui.core.theme import Theme


def _rows(component, width=30):
    return [row.text for row in component.render(width)]


def test_empty_query_shows_every_option_in_order():
    auto = Autocomplete(options=[Option("alpha"), Option("beta"), Option("gamma")])
    assert auto.query == "" and auto.is_empty is False
    assert _rows(auto) == ["\u276e alpha", "  beta", "  gamma"]
    assert auto.selected == Option("alpha")


def test_prefix_matches_rank_before_substring_matches():
    options = [
        Option("read"),
        Option("bread"),
        Option("thread"),
        Option("ready"),
        Option("spread"),
    ]
    auto = Autocomplete(options=options)
    auto.set_query("rea")
    # prefix group first (original order), then the substring group
    assert _rows(auto) == [
        "\u276e read",
        "  ready",
        "  bread",
        "  thread",
        "  spread",
    ]
    assert auto.selected == Option("read")
    auto.set_query("read")  # an exact label is a prefix match of itself
    assert _rows(auto) == [
        "\u276e read",
        "  ready",  # "ready" also starts with "read": prefix group
        "  bread",
        "  thread",
        "  spread",
    ]
    auto.set_query("zzz")
    assert auto.is_empty is True and auto.selected is None
    assert auto.render(30) == []  # an empty result renders zero rows
    assert auto.move(1) is False  # and the cursor cannot move


def test_set_query_resets_the_cursor_and_move_clamps():
    auto = Autocomplete(options=[Option("a1"), Option("a2"), Option("b1")])
    auto.set_query("a")
    auto.move(1)
    assert auto.selected == Option("a2")
    auto.set_query("b")  # a new query replaces the match list
    assert auto.selected == Option("b1")
    auto.move(5)
    assert auto.selected == Option("b1")  # clamped at the end
    auto.move(-9)
    assert auto.selected == Option("b1")  # clamped at the start, no wrap


def test_max_rows_truncates_and_the_window_follows_the_cursor():
    options = [Option(f"item{i}") for i in range(10)]
    auto = Autocomplete(options=options, max_rows=3)
    assert _rows(auto) == ["\u276e item0", "  item1", "  item2"]
    auto.move(2)
    # the window still hangs at the top; the marker follows the cursor
    assert _rows(auto) == ["  item0", "  item1", "\u276e item2"]
    auto.move(1)
    assert _rows(auto) == ["  item1", "  item2", "\u276e item3"]  # scrolled by one
    auto.move(6)
    assert _rows(auto) == ["  item7", "  item8", "\u276e item9"]
    auto.move(-1)
    assert auto.selected == Option("item8")
    assert len(auto.render(30)) == 3  # never more than max_rows


def test_row_layout_matches_select():
    auto = Autocomplete(options=[Option("one", hint="first"), Option("two")])
    auto.move(1)
    rows = auto.render(20)
    assert [row.text for row in rows] == ["  one  first", "\u276e two"]
    assert rows[1].segments == (Segment("\u276e two", SELECTION),)
    assert rows[0].segments == (Segment("  one", NONE), Segment("  first", DIM))


def test_style_injection_wins_over_theme_defaults():
    auto = Autocomplete(
        options=[Option("one", hint="h"), Option("two")],
        label_style=Style(bold=True),
        hint_style=Style(fg="red"),
    )
    auto.move(1)
    rows = auto.render(20)
    assert rows[0].segments == (
        Segment("  one", Style(bold=True)),
        Segment("  h", Style(fg="red")),
    )
    reverse = Autocomplete(options=[Option("one")], selected_style=Style(reverse=True))
    assert reverse.render(20)[0].segments == (
        Segment("\u276e one", Style(reverse=True)),
    )


def test_theme_fallback_and_fit_guard():
    theme = Theme(selection=Style(reverse=True), dim=Style(fg="red"))
    auto = Autocomplete(options=[Option("long-option-label", hint="hint")], theme=theme)
    rows = auto.render(10)
    assert rows[0].width <= 10  # always fit back to the painting width
    assert rows[0].segments[0].style == theme.selection
    hinted = Autocomplete(options=[Option("a", hint="h"), Option("b")], theme=theme)
    hinted.move(1)
    assert hinted.render(20)[0].segments[1].style == theme.dim

    assert Autocomplete(options=[Option("x")]).render(0) == [Line()]
