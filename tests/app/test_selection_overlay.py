"""The driver's document-space selection overlay: marks, scroll, reflow, panes."""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.app import TUI
from motui.kernel import DEFAULT_THEME, HeadlessScreen, Selection, Style, Text
from tests.testing import Rows, headless_tui, many, marked, rows, snapshot


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


def test_a_block_style_round_trips_under_the_selection_merge():
    tui = headless_tui(80, 6)
    styled = Style(fg="#abcdef")
    tui.add(Text("alpha", style=styled))
    tui.paint()
    tui.set_selection(Selection.between(("b0", 0, 2), ("b0", 0, 5)))
    tui.paint()
    selection_style = DEFAULT_THEME.selection
    assert [(seg.text, seg.style) for seg in tui.rows[0].segments] == [
        ("al", styled),
        ("pha", styled.merge(selection_style)),
    ]


def test_the_overlay_paints_with_the_drivers_theme():
    band = Style(underline=True)
    tui = TUI(
        screen=HeadlessScreen(20, 3),
        theme=replace(DEFAULT_THEME, selection=band),
        interactive=False,
    )
    tui.add(Rows("alpha"))
    tui.paint()
    tui.set_selection(Selection.between(("b0", 0, 1), ("b0", 0, 3)))
    tui.paint()
    assert [(seg.text, seg.style) for seg in tui.rows[0].segments] == [
        ("a", Style()),
        ("lp", Style(underline=True)),
        ("ha", Style()),
    ]


def test_clearing_the_selection_restores_the_exact_rows():
    tui = headless_tui(80, 6)
    tui.add(Rows("alpha", "beta", "gamma"))
    tui.paint()
    plain = tui.rows
    tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 2, 3)))
    tui.paint()
    assert marked(tui) == ["alpha", "beta", "gam", "", "", ""]

    written = len(tui.screen.output)
    tui.set_selection(None)
    assert tui.selection is None
    tui.paint()
    assert tui.rows == plain
    assert tui.screen.output[written:]


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


def test_the_overlay_is_scoped_to_the_named_pane():
    tui = headless_tui(40, 4)
    left, right = tui.split("vertical")
    left.document.add(Rows("left"))
    right.document.add(Rows("right"))
    tui.paint()
    tui.set_selection(
        Selection.between(("b0", 0, 0), ("b0", 0, 5)), pane=right.id
    )
    tui.paint()
    assert tui.selection_pane is right
    left_cells = tui.rows[0].segments[:1]
    assert not any(seg.style.reverse for seg in left_cells)
    assert any(
        seg.style.reverse and seg.text == "right" for seg in tui.rows[0].segments
    )


def test_an_unknown_pane_is_rejected():
    tui = headless_tui()
    with pytest.raises(ValueError):
        tui.set_selection(Selection.between(("b0", 0, 0), ("b0", 0, 1)), pane="ghost")
    assert tui.selection is None
