"""The driver's document-space selection overlay: marks, scroll, reflow, panes."""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.app import Runtime
from motui.kernel import DEFAULT_THEME, Selection, Style
from motui.widgets.text import Text
from motui.terminal import HeadlessScreen, Terminal, TerminalOptions
from tests.testing import Rows, headless_tui, many, marked, snapshot


def test_set_selection_marks_the_in_range_rows_and_leaves_the_rest():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta", "gamma"))
    tui.paint()
    plain = tui.rows
    written = len(tui.screen.output)

    selection = Selection.between(("b0", 0, 2), ("b0", 1, 3))
    tui.set_selection(selection)
    assert tui.selection is selection
    tui.paint()

    assert marked(tui) == ["pha", "bet", "", "", "", ""]
    assert [row.text for row in tui.rows] == [row.text for row in plain]
    assert tui.rows[2] == plain[2]
    fresh = tui.screen.output[written:]
    assert "pha" in fresh and "gamma" not in fresh

    written = len(tui.screen.output)
    tui.set_selection(None)
    assert tui.selection is None
    tui.paint()
    assert tui.rows == plain
    assert tui.screen.output[written:]


def test_a_block_style_round_trips_under_the_selection_merge():
    tui = headless_tui(80, 6)
    styled = Style(fg="#abcdef")
    tui.add(Text("alpha", style=styled))
    tui.paint()
    tui.set_selection(Selection.between(("b0", 0, 2), ("b0", 0, 5)))
    tui.paint()
    selection_style = DEFAULT_THEME.text.selection
    assert [(seg.text, seg.style) for seg in tui.rows[0].segments] == [
        ("al", styled),
        ("pha", styled.merge(selection_style)),
    ]


def test_the_overlay_paints_with_the_drivers_theme():
    band = Style(underline=True)
    tui = Runtime(
        Terminal(TerminalOptions(screen=HeadlessScreen(20, 3))),
        theme=replace(DEFAULT_THEME, text=replace(DEFAULT_THEME.text, selection=band)),
        interactive=False,
    )
    tui.workspace.add(Rows("alpha"))
    tui.paint()
    tui.workspace.set_selection(Selection.between(("b0", 0, 1), ("b0", 0, 3)))
    tui.paint()
    assert [(seg.text, seg.style) for seg in tui.workspace.rows[0].segments] == [
        ("a", Style()),
        ("lp", Style(underline=True)),
        ("ha", Style()),
    ]


def test_scrolling_moves_the_text_under_a_stationary_selection():
    tui = headless_tui(80, 6)
    tui.add(Rows(*many(10)))
    tui.paint()
    selection = Selection.between(("b0", 1, 1), ("b0", 3, 2))
    tui.set_selection(selection)
    tui.paint()
    assert marked(tui) == [""] * 6

    tui.scroll_up(3)
    tui.paint()
    assert tui.selection is selection
    assert marked(tui) == ["1", "r2", "r3", "", "", ""]

    tui.scroll_to_bottom()
    tui.paint()
    assert tui.selection is selection
    assert marked(tui) == [""] * 6


def test_a_width_change_clears_the_selection_and_a_height_change_keeps_it():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta"))
    tui.paint()
    selection = Selection.between(("b0", 0, 0), ("b0", 1, 2))
    tui.set_selection(selection)
    tui.paint()

    tui.screen.height = 12
    tui.paint()
    assert tui.selection is selection
    assert marked(tui)[:2] == ["alpha", "be"]

    tui.screen.width = 40
    tui.paint()
    assert tui.selection is None
    assert not any(marked(tui))


def test_a_selection_over_a_removed_block_marks_nothing():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha"))
    tui.add(Rows("beta"))
    tui.paint()
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 0, 5)))
    tui.remove("b0")
    tui.paint()
    assert tui.selection is not None
    assert not any(marked(tui))


def test_the_presented_frame_marks_while_the_document_view_stays_plain():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta"))
    tui.paint()
    before = snapshot(tui)
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 1, 2)))
    tui.paint()
    assert marked(tui)[:2] == ["alpha", "be"]
    assert snapshot(tui) == before


def test_an_unknown_pane_is_rejected():
    tui = headless_tui()
    with pytest.raises(ValueError):
        tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 0, 1)), pane="ghost")
    assert tui.selection is None
