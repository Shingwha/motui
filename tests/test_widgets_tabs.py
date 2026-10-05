"""Tests for mocode_tui.widgets.tabs (Tabs).

Contracts (the W4 ticket + the module docstring): rendering is always
exactly one row shaped ``" name \\u2502 name "``; the active tab carries
``active_style`` (theme ``selection`` by default) and the rest plain;
``move``/``activate`` clamp into range without wrapping; an over-wide strip
truncates with a ``\\u2026`` instead of wrapping.
"""

import pytest

from mocode_tui.widgets.tabs import Tabs
from mocode_tui.core.block import Component
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import NONE, SELECTION, Style

#: Injected styles: they flow back out of the render equal.
ACTIVE = Style(fg="#abcdef")
INACTIVE = Style(fg="#123456")


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


@pytest.mark.parametrize(
    "start, delta, active, changed",
    [
        (0, 1, 1, True),
        (0, 5, 2, True),  # clamped at the end
        (2, -9, 0, True),  # clamped at the start, no wrap-around
        (0, -1, 0, False),  # already at the top: nothing changed
    ],
)
def test_move_clamps_without_wrapping(start, delta, active, changed):
    tabs = Tabs(["a", "b", "c"], active=start)
    assert tabs.move(delta) is changed
    assert tabs.active == active
    assert tabs.activate(1) is (active != 1)  # already active: nothing changed
    assert Tabs(["a", "b"], active=7).active == 1  # clamped on construction
    assert Tabs([], active=3).active == 0
    assert Tabs([]).move(1) is False


def test_active_highlight_follows_the_selection():
    tabs = Tabs(["a", "b"])
    tabs.move(1)
    segments = tabs.render(20)[0].segments
    assert segments[1].style == NONE  # "a" went quiet
    assert segments[3].style == SELECTION  # "b" is highlighted


def test_an_over_wide_strip_truncates_instead_of_wrapping():
    tabs = Tabs(["alpha", "beta", "gamma"])
    rows = tabs.render(6)
    assert len(rows) == 1 and rows[0].width == 6
    assert rows[0].text == " alph\u2026"
    assert tabs.render(0) == [Line()]  # a zero painting width empties the row


def test_style_injection_round_trips():
    custom = Tabs(
        ["a", "b"],
        divider="|",
        active_style=ACTIVE,
        inactive_style=INACTIVE,
    )
    segments = custom.render(20)[0].segments
    assert segments[0].text == " " and segments[2].text == " | "  # the custom divider
    assert segments[1] == Segment("a", ACTIVE)
    assert segments[3] == Segment("b", INACTIVE)


def test_empty_tabs_render_one_empty_row():
    rows = Tabs([]).render(10)
    assert len(rows) == 1 and rows[0].text == ""
