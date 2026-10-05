"""Tests for mocode_tui.widgets.tabs (Tabs).

Contracts (the W4 ticket + the module docstring): rendering is always
exactly one row shaped ``" name \\u2502 name "``; the active tab carries
``active_style`` (theme ``selection`` by default) and the rest plain;
``move``/``activate`` clamp into range without wrapping; an over-wide strip
truncates with a ``\\u2026`` instead of wrapping.
"""

from mocode_tui.widgets.tabs import Tabs
from mocode_tui.core.block import Component
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import NONE, SELECTION, Style
from mocode_tui.core.theme import Theme


def test_render_is_one_row_of_space_separated_names():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(40)
    assert len(rows) == 1  # a tab strip is always a single row
    assert rows[0].text == " alpha \u2502 beta \u2502 gamma "
    assert rows[0].segments == (
        Segment(" "),
        Segment("alpha", SELECTION),
        Segment(" \u2502 "),
        Segment("beta", NONE),
        Segment(" \u2502 "),
        Segment("gamma", NONE),
        Segment(" "),
    )
    assert isinstance(tabs, Component)


def test_move_and_activate_clamp_without_wrapping():
    tabs = Tabs(["a", "b", "c"])
    assert tabs.active == 0
    assert tabs.move(1) is True and tabs.active == 1
    tabs.move(5)
    assert tabs.active == 2  # clamped at the end
    tabs.move(-9)
    assert tabs.active == 0  # clamped at the start, no wrap-around
    assert tabs.move(-1) is False
    assert tabs.activate(1) is True and tabs.active == 1
    assert tabs.activate(1) is False  # already active: nothing changed
    assert tabs.activate(99) is True and tabs.active == 2
    assert Tabs(["a", "b"], active=7).active == 1  # clamped on construction
    assert Tabs([], active=3).active == 0
    assert Tabs([]).move(1) is False


def test_active_highlight_follows_the_selection():
    tabs = Tabs(["a", "b"])
    tabs.move(1)
    segments = tabs.render(20)[0].segments
    assert segments[1].style == NONE  # "a" went quiet
    assert segments[3].style == SELECTION  # "b" is highlighted


def test_over_width_truncates_with_an_ellipsis():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(6)
    assert len(rows) == 1 and rows[0].width == 6
    assert rows[0].text == " alph\u2026"
    assert tabs.render(0) == [Line()]  # a zero painting width empties the row


def test_custom_divider_styles_and_theme_fallback():
    custom = Tabs(
        ["a", "b"],
        divider="|",
        active_style=Style(fg="red"),
        inactive_style=Style(dim=True),
    )
    segments = custom.render(20)[0].segments
    assert segments[0].text == " " and segments[2].text == " | "
    assert segments[1] == Segment("a", Style(fg="red"))
    assert segments[3] == Segment("b", Style(dim=True))

    theme = Theme(selection=Style(reverse=True))
    segments = Tabs(["a", "b"], theme=theme).render(10)[0].segments
    assert segments[1].style == theme.selection
    assert segments[3].style == NONE


def test_empty_tabs_render_one_empty_row():
    rows = Tabs([]).render(10)
    assert len(rows) == 1 and rows[0].text == ""
