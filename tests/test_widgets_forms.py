"""The form widgets: ``Radio``, ``Slider``, ``Collapsible``, ``ShortcutBar``.

The four components the widgets-basic wave adds, each asserted as its own
contract: the state it holds, the controller methods a host routes (and the
``chosen`` value each writes for a single read), the row-level ``hover_at``
marking that must render zero extra bytes when it cleared, and the focus
band that must be told apart from the plain render.
"""

from __future__ import annotations

import pytest

from _doubles import texts

from mocode_tui.core.block import Activable, Clickable, Component, Focusable, Hoverable
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import NONE, Style
from mocode_tui.core.theme import DEFAULT_THEME, Theme
from mocode_tui.widgets.choice import Option
from mocode_tui.widgets.radio import FILLED_MARK, Radio

#: Injected styles: they flow back out of the render equal.
SELECTED = Style(fg="#abcdef")
PLAIN = Style(fg="#123456")
HOVER = Style(italic=True)
FOCUS = Style(underline=True)


# --- Radio ----------------------------------------------------------------------


def test_radio_renders_one_marked_row_per_label():
    group = Radio(["one", "two", "three"])
    rows = group.render(30)
    assert texts(group, 30) == ["(\u2022) one", "( ) two", "( ) three"]
    assert rows[0].segments == (
        Segment(FILLED_MARK, DEFAULT_THEME.accent),
        Segment("one", DEFAULT_THEME.accent),
    )
    assert rows[1].segments == (Segment("( ) ", NONE), Segment("two", NONE))
    assert isinstance(group, Component)


def test_radio_index_clamps_and_selected_reads_the_label():
    group = Radio(["a", "b", "c"], index=7)
    assert group.index == 2 and group.selected == "c"
    group.index = -4
    assert group.index == 0 and group.selected == "a"
    assert texts(group, 20)[0] == "(\u2022) a"
    empty = Radio([])
    assert empty.index == 0 and empty.selected is None and empty.render(20) == []


def test_radio_move_steps_and_clamps_and_lands_the_new_selection():
    group = Radio(["one", "two", "three"])
    assert group.chosen is None
    assert group.move(1) is True
    assert (group.index, group.chosen) == (1, "two")
    group.chosen = None
    assert group.move(-9) is True  # clamped at the start
    assert (group.index, group.chosen) == (0, "one")
    group.chosen = None
    assert group.move(-1) is False  # already there: nothing moved, nothing chosen
    assert group.chosen is None
    assert Radio([]).move(1) is False


def test_radio_click_is_the_mouse_door_and_ignores_the_column():
    group = Radio(["one", "two", "three"])
    assert isinstance(group, Clickable)
    for col in (0, 3, 40):  # a row owns the whole width
        assert group.click(2, col) is True and group.chosen == "three"
        assert group.index == 2
    assert group.click(2, 0) is True  # a hit even when it already was selected
    for row in (-1, 3, 9):
        group.chosen = None
        assert group.click(row, 0) is False and group.chosen is None
        assert group.index == 2


def test_radio_activate_takes_the_selection_and_reads_once():
    group = Radio(["one", "two"])
    assert isinstance(group, Activable)
    group.move(1)
    group.chosen = None
    assert group.activate() is True and group.chosen == "two"
    assert Radio([]).activate() is False and Radio([]).chosen is None


def test_radio_takes_option_payloads_into_chosen():
    group = Radio([Option("alpha", 1), Option("beta", 2), Option("plain")])
    assert group.labels == ["alpha", "beta", "plain"]
    assert group.move(1) is True and group.chosen == 2
    group.chosen = None
    assert group.click(2, 0) is True and group.chosen == "plain"  # value None: the label
    group.chosen = None
    assert group.move(-1) is True and group.chosen == 2


def test_radio_marks_the_row_under_a_cell_and_clears_back():
    group = Radio(["one", "two", "three"], selected_style=SELECTED, label_style=PLAIN)
    plain = group.render(20)
    assert group.hover_at(2, 0) is True
    marked = group.render(20)
    assert marked[2].segments[0].style == PLAIN.merge(DEFAULT_THEME.hover)
    assert marked[2].segments[1].style == PLAIN.merge(DEFAULT_THEME.hover)
    assert marked[0] == plain[0] and marked[1] == plain[1]
    assert group.hover_at(2, 9) is False  # the same row: nothing to repaint
    assert group.hover_at(1, 0) is True
    assert group.render(20)[2] == plain[2]  # the old row let the band go
    assert group.hover_at(-1, -1) is True  # the pointer left
    assert group.render(20) == plain  # byte-for-byte the un-hovered rows
    assert group.hover_at(9, 0) is False  # past the labels: nothing was marked
    # the selected row keeps its own band underneath the hover mark
    assert group.hover_at(0, 0) is True
    assert group.render(20)[0].segments[0].style == SELECTED.merge(DEFAULT_THEME.hover)


def test_radio_focus_band_is_told_apart_from_the_plain_render():
    def build(focused):
        return Radio(
            ["one", "two"],
            selected_style=SELECTED,
            label_style=PLAIN,
            hover_style=HOVER,
            focus_style=FOCUS,
            focused=focused,
        )

    plain, focused = build(False), build(True)
    assert focused.render(20)[0].segments[0] == Segment(FILLED_MARK, SELECTED.merge(FOCUS))
    assert focused.render(20)[1] == plain.render(20)[1]  # only the selected row carries it
    assert plain.render(20)[0].segments[0] == Segment(FILLED_MARK, SELECTED)


def test_radio_declares_its_capabilities():
    group = Radio(["one"])
    assert isinstance(group, Hoverable) and isinstance(group, Focusable)
    assert isinstance(group, Clickable) and isinstance(group, Activable)
