"""Find: match addressing, stepping, reveal, the overlay and unmounting."""

from __future__ import annotations

from dataclasses import replace

from motui import DEFAULT_THEME, Style
from motui.interaction import Find
from motui.kernel.events import KeyEvent
from tests.testing import Rows, headless_tui, key


def type_text(find: Find, text: str) -> None:
    for char in text:
        assert find.handle(KeyEvent(char, char)) is True


def document(tui) -> None:
    tui.add(Rows("fish one", "no hit", "FISH two"), id="a")
    tui.add(Rows("deep fish three"), id="b")


def row(tui, text: str):
    return next(row for row in tui.rows if row.text == text)


def test_a_query_addresses_matches_in_document_order_case_insensitively():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui)
    assert find in tui.frame.overlays
    assert (find.is_open, find.query, find.matches, find.index) == (False, "", [], 0)

    find.open()
    assert find.is_open and find.query == "" and find.matches == []
    type_text(find, "fish")
    assert find.query == "fish"
    assert find.matches == [("a", 0, 0, 4), ("a", 2, 0, 4), ("b", 0, 5, 9)]
    assert find.index == 0

    type_text(find, "h")
    assert find.matches == [] and find.index == 0
    find.handle(key("backspace"))
    assert find.matches == [("a", 0, 0, 4), ("a", 2, 0, 4), ("b", 0, 5, 9)]
    assert find.index == 0


def test_a_closed_tier_consumes_nothing_and_escape_closes_an_open_one():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui)
    assert find.handle(key("f", "f")) is False
    assert find.query == "" and find.matches == []

    find.open()
    type_text(find, "fish")
    assert find.handle(key("enter")) is True and find.index == 1
    assert find.handle(key("escape")) is True
    assert find.is_open is False
    assert find.handle(key("f", "f")) is False
    assert find.query == "fish"

    find.open()
    assert find.query == "" and find.matches == [] and find.index == 0


def test_enter_and_down_step_forward_and_up_back_with_wrapping():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui)
    find.open()
    type_text(find, "fish")

    assert find.handle(key("enter")) is True and find.index == 1
    assert find.handle(key("down")) is True and find.index == 2
    assert find.handle(key("down")) is True and find.index == 0
    assert find.handle(key("up")) is True and find.index == 2
    assert find.matches[find.index] == ("b", 0, 5, 9)


def test_a_query_change_and_a_step_reveal_the_current_match():
    tui = headless_tui(40, 10)
    for name, hit in (("head", 1), ("body", 5), ("tail", 7)):
        tui.add(
            Rows(
                *(
                    f"row {index:02d} " + ("NEEDLE" if index == hit else "plain")
                    for index in range(10)
                )
            ),
            id=name,
        )
    tui.paint()
    assert tui.viewport.offset == 20

    find = Find(tui)
    find.open()
    assert tui.viewport.offset == 20
    type_text(find, "needle")
    assert find.matches == [("head", 1, 7, 13), ("body", 5, 7, 13), ("tail", 7, 7, 13)]
    assert find.index == 0
    assert tui.viewport.offset == 0

    assert find.handle(key("enter")) is True
    assert tui.viewport.offset == 10
    assert find.handle(key("enter")) is True
    assert tui.viewport.offset == 20
    assert find.handle(key("enter")) is True
    assert find.index == 0 and tui.viewport.offset == 0
    assert find.handle(key("up")) is True
    assert find.index == 2 and tui.viewport.offset == 20


def test_the_paint_marks_every_match_and_merges_hover_over_the_current_one():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui, theme=replace(DEFAULT_THEME, hover=Style(bold=True)))
    find.open()
    type_text(find, "fish")
    tui.paint()

    current = next(seg for seg in row(tui, "fish one").segments if seg.style.reverse)
    assert current.text == "fish" and current.style.bold
    other = next(seg for seg in row(tui, "FISH two").segments if seg.style.reverse)
    assert other.text == "FISH" and not other.style.bold
    third = next(
        seg for seg in row(tui, "deep fish three").segments if seg.style.reverse
    )
    assert third.text == "fish" and not third.style.bold
    assert not any(seg.style.reverse for seg in row(tui, "no hit").segments)


def test_the_query_row_lands_on_the_bottom_row_with_the_counter():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui)
    find.open()
    type_text(find, "fish")
    find.handle(key("enter"))
    tui.paint()

    bottom = tui.rows[-1]
    assert bottom.text.startswith("find \u276e fish")
    assert "(2/3)" in bottom.text
    assert not any("\u276e" in item.text for item in tui.rows[:-1])

    type_text(find, "zz")
    tui.paint()
    assert find.matches == [] and find.index == 0
    assert "(0/0)" in tui.rows[-1].text
    find.handle(key("enter"))
    assert find.index == 0


def test_a_closed_tier_hands_the_layout_back_untouched():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui)
    before = tui.frame.layout
    assert find.paint(tui.frame) is before

    find.open()
    tui.paint()
    assert "(0/0)" in tui.rows[-1].text
    find.handle(key("escape"))
    tui.paint()
    assert not any("\u276e" in item.text for item in tui.rows)
    assert find.paint(tui.frame) is tui.frame.layout


def test_a_pinned_block_answers_reveal_without_scrolling():
    tui = headless_tui(40, 6)
    tui.add(Rows("pinned needle"), id="head", pin="top")
    tui.add(Rows(*(f"r{i}" for i in range(20))), id="body")
    tui.paint()
    assert tui.viewport.offset == 15

    find = Find(tui)
    find.open()
    type_text(find, "needle")
    assert find.matches == [("head", 0, 7, 13)]
    assert tui.viewport.offset == 15
    tui.paint()
    marked = next(seg for seg in row(tui, "pinned needle").segments if seg.style.reverse)
    assert marked.text == "needle"


def test_match_columns_are_display_columns():
    tui = headless_tui(40, 6)
    tui.add(Rows("\u6f22\u5b57 fish"), id="wide")
    tui.paint()
    find = Find(tui)
    find.open()
    type_text(find, "fish")
    assert find.matches == [("wide", 0, 5, 9)]
    tui.paint()
    marked = next(
        seg for seg in row(tui, "\u6f22\u5b57 fish").segments if seg.style.reverse
    )
    assert marked.text == "fish"


def test_matches_addressed_at_another_width_paint_no_highlight():
    tui = headless_tui(40, 6)
    tui.add(Rows("fish here"), id="a")
    tui.paint()
    find = Find(tui)
    find.open()
    type_text(find, "fish")
    assert find.matches == [("a", 0, 0, 4)]

    tui.screen.width = 20
    tui.paint()
    assert not any(seg.style.reverse for seg in row(tui, "fish here").segments)
    assert "(1/1)" in tui.rows[-1].text

    type_text(find, " ")
    tui.paint()
    assert find.matches == [("a", 0, 0, 5)]
    assert any(seg.style.reverse for seg in row(tui, "fish here").segments)


def test_detach_unregisters_and_set_theme_keeps_the_query():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui)
    find.open()
    type_text(find, "fish")

    find.set_theme(replace(DEFAULT_THEME, accent=Style(fg="red")))
    assert find.is_open and find.query == "fish"
    assert len(find.matches) == 3

    find.detach()
    assert find not in tui.frame.overlays
    find.detach()
    assert find not in tui.frame.overlays


def test_a_detached_tier_is_inert_whatever_the_key():
    tui = headless_tui(40, 10)
    document(tui)
    tui.paint()
    find = Find(tui)
    find.open()
    type_text(find, "fish")
    find.detach()
    assert find not in tui.frame.overlays
    assert find.is_open is True
    for name, char in (
        ("f", "f"),
        ("enter", ""),
        ("down", ""),
        ("up", ""),
        ("escape", ""),
        ("backspace", ""),
    ):
        assert find.handle(key(name, char)) is False, name
    assert find.query == "fish" and len(find.matches) == 3 and find.index == 0
    assert find.is_open is True
