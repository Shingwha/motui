"""Tests for motui.interaction.search.

The ``Find`` tier: the query row it owns, the matches a query addresses (in
document order, case-insensitively, columns in display space), the cursor
over them (wrapping), the reveal of the current match through the driver's
viewport, and the overlay's two halves -- the marked rows and the bottom
query row with its ``(i/n)`` counter.
"""

from dataclasses import replace

from _doubles import Rows, key

from motui import DEFAULT_THEME, Key, Style
from motui.interaction import Find
from motui.testing import headless_tui


def _type(find: Find, text: str) -> None:
    """Type ``text`` into the tier's query row, one key at a time."""
    for ch in text:
        assert find.handle(Key(ch, ch)) is True


def _document(tui) -> None:
    """The three-block fixture: two hits in ``a``, one in ``b``, one decoy row."""
    tui.add(Rows("fish one", "no hit", "FISH two"), id="a")
    tui.add(Rows("deep fish three"), id="b")


def _row(tui, text: str):
    """The painted screen row whose plain text is exactly ``text``."""
    return next(row for row in tui.rows if row.text == text)


def test_a_query_addresses_the_matches_in_document_order_case_insensitively():
    tui = headless_tui(40, 10)
    _document(tui)
    tui.paint()
    find = Find(tui)
    assert find in tui.frame.overlays  # constructed mounted, the Toasts rule
    assert (find.is_open, find.query, find.matches, find.index) == (False, "", [], 0)

    find.open()
    assert find.is_open and find.query == "" and find.matches == []
    _type(find, "fish")
    assert find.query == "fish"
    # (block id, row in block, start column, end column): FISH matches fish
    assert find.matches == [("a", 0, 0, 4), ("a", 2, 0, 4), ("b", 0, 5, 9)]
    assert find.index == 0

    _type(find, "h")  # "fishh": no row holds it
    assert find.matches == [] and find.index == 0
    find.handle(key("backspace"))  # "fish" again: the cursor restarts at the first
    assert find.matches == [("a", 0, 0, 4), ("a", 2, 0, 4), ("b", 0, 5, 9)]
    assert find.index == 0


def test_a_closed_tier_consumes_nothing_and_escape_closes_an_open_one():
    tui = headless_tui(40, 10)
    _document(tui)
    tui.paint()
    find = Find(tui)
    assert find.handle(key("f", "f")) is False  # closed: the event is the host's
    assert find.query == "" and find.matches == []

    find.open()
    _type(find, "fish")
    assert find.handle(key("enter")) is True and find.index == 1
    assert find.handle(key("escape")) is True  # the tier's own dismiss key
    assert find.is_open is False
    assert find.handle(key("f", "f")) is False  # and it consumes nothing again
    assert find.query == "fish"  # the row keeps its text for the next open
    find.open()  # a fresh visit starts from the empty query
    assert find.query == "" and find.matches == [] and find.index == 0


def test_enter_and_down_step_forward_and_up_back_with_wrapping():
    tui = headless_tui(40, 10)
    _document(tui)
    tui.paint()
    find = Find(tui)
    find.open()
    _type(find, "fish")

    assert find.handle(key("enter")) is True and find.index == 1
    assert find.handle(key("down")) is True and find.index == 2
    assert find.handle(key("down")) is True and find.index == 0  # off the end: onto the first
    assert find.handle(key("up")) is True and find.index == 2  # off the first: onto the last
    assert find.index == 2 and find.matches[find.index] == ("b", 0, 5, 9)


def test_a_query_change_and_a_step_reveal_the_current_match():
    """The whole reveal road, read off the viewport the tier never touches."""
    tui = headless_tui(40, 10)
    for name, hit in (("head", 1), ("body", 5), ("tail", 7)):
        tui.add(
            Rows(*(f"row {i:02d} " + ("NEEDLE" if i == hit else "plain") for i in range(10))),
            id=name,
        )
    tui.paint()
    assert tui.viewport.offset == 20  # sticks to the bottom

    find = Find(tui)
    find.open()
    assert tui.viewport.offset == 20  # no query yet: nothing to reveal
    _type(find, "needle")  # the rows spell NEEDLE: the match is case-insensitive
    assert find.matches == [("head", 1, 7, 13), ("body", 5, 7, 13), ("tail", 7, 7, 13)]
    assert find.index == 0
    assert tui.viewport.offset == 0  # the head's row 1 centers (1 - 5 clamps to 0)

    assert find.handle(key("enter")) is True  # the body's row 5: address 15, centered
    assert tui.viewport.offset == 10
    assert find.handle(key("enter")) is True  # the tail's row 7: address 27, clamped
    assert tui.viewport.offset == 20
    assert find.handle(key("enter")) is True  # wraps onto the head again
    assert find.index == 0 and tui.viewport.offset == 0
    assert find.handle(key("up")) is True  # and back onto the tail
    assert find.index == 2 and tui.viewport.offset == 20


def test_the_paint_marks_every_match_and_merges_hover_over_the_current_one():
    tui = headless_tui(40, 10)
    _document(tui)
    tui.paint()
    # A distinct hover band makes the current match tell apart from the rest.
    find = Find(tui, theme=replace(DEFAULT_THEME, hover=Style(bold=True)))
    find.open()
    _type(find, "fish")
    assert find.index == 0
    tui.paint()

    current = next(seg for seg in _row(tui, "fish one").segments if seg.style.reverse)
    assert current.text == "fish" and current.style.bold  # selection + hover
    other = next(seg for seg in _row(tui, "FISH two").segments if seg.style.reverse)
    assert other.text == "FISH" and not other.style.bold  # selection alone
    third = next(seg for seg in _row(tui, "deep fish three").segments if seg.style.reverse)
    assert third.text == "fish" and not third.style.bold
    assert not any(seg.style.reverse for seg in _row(tui, "no hit").segments)


def test_the_query_row_lands_on_the_frame_bottom_row_with_the_counter():
    tui = headless_tui(40, 10)
    _document(tui)
    tui.paint()
    find = Find(tui)
    find.open()
    _type(find, "fish")
    find.handle(key("enter"))
    tui.paint()

    bottom = tui.rows[-1]
    assert bottom.text.startswith("find \u276e fish")  # the row's own prompt and query
    assert "(2/3)" in bottom.text  # the second of three matches
    assert not any("\u276e" in row.text for row in tui.rows[:-1])  # only the last row

    _type(find, "zz")  # nothing matches: the counter says so, the row stays
    tui.paint()
    assert find.matches == [] and find.index == 0
    assert "(0/0)" in tui.rows[-1].text
    find.handle(key("enter"))  # no match to step to: still the tier's own key
    assert find.index == 0


def test_a_closed_tier_hands_the_layout_back_untouched():
    tui = headless_tui(40, 10)
    _document(tui)
    tui.paint()
    find = Find(tui)
    before = tui.frame.layout
    assert find.paint(tui.frame) is before  # closed: the very layout, zero rows

    find.open()
    tui.paint()
    assert "(0/0)" in tui.rows[-1].text
    find.handle(key("escape"))
    tui.paint()
    assert not any("\u276e" in row.text for row in tui.rows)
    assert find.paint(tui.frame) is tui.frame.layout


def test_an_address_a_pinned_block_answers_reveal_without_scrolling():
    tui = headless_tui(40, 6)
    tui.add(Rows("pinned needle"), id="head", pin="top")
    tui.add(Rows(*(f"r{i}" for i in range(20))), id="body")
    tui.paint()
    assert tui.viewport.offset == 15  # 20 body rows, a 5-row window

    find = Find(tui)
    find.open()
    _type(find, "needle")
    assert find.matches == [("head", 0, 7, 13)]  # a fixed region is part of the document
    assert tui.viewport.offset == 15  # and never scrolls away: nothing moved
    tui.paint()
    marked = next(seg for seg in _row(tui, "pinned needle").segments if seg.style.reverse)
    assert marked.text == "needle"


def test_match_columns_are_display_columns_not_character_indices():
    tui = headless_tui(40, 6)
    tui.add(Rows("\u6f22\u5b57 fish"), id="wide")
    tui.paint()
    find = Find(tui)
    find.open()
    _type(find, "fish")
    assert find.matches == [("wide", 0, 5, 9)]  # two two-cell glyphs, one space, then fish
    tui.paint()
    marked = next(seg for seg in _row(tui, "\u6f22\u5b57 fish").segments if seg.style.reverse)
    assert marked.text == "fish"  # cut on the columns, not inside a wide cluster


def test_matches_addressed_at_another_width_paint_no_highlight():
    """A reflow re-wraps rows: the addresses' width is not this frame's, so the
    marks stay off until the next query change re-addresses them (the stance
    the selection overlay takes for a width change)."""
    tui = headless_tui(40, 6)
    tui.add(Rows("fish here"), id="a")
    tui.paint()
    find = Find(tui)
    find.open()
    _type(find, "fish")
    assert find.matches == [("a", 0, 0, 4)]

    tui.screen.width = 20  # the pane lays out at a new width on the next paint
    tui.paint()
    assert not any(seg.style.reverse for seg in _row(tui, "fish here").segments)
    assert "(1/1)" in tui.rows[-1].text  # the query row still paints

    _type(find, " ")  # "fish ": one more character re-addresses the matches
    tui.paint()
    assert find.matches == [("a", 0, 0, 5)]
    assert any(seg.style.reverse for seg in _row(tui, "fish here").segments)


def test_detach_unregisters_the_overlay_and_set_theme_keeps_the_query():
    tui = headless_tui(40, 10)
    _document(tui)
    tui.paint()
    find = Find(tui)
    find.open()
    _type(find, "fish")

    find.set_theme(replace(DEFAULT_THEME, accent=Style(fg="red")))
    assert find.is_open and find.query == "fish"  # the row was rebuilt, the text kept
    assert len(find.matches) == 3

    find.detach()
    assert find not in tui.frame.overlays
    find.detach()  # idempotent, by membership
    assert find not in tui.frame.overlays
