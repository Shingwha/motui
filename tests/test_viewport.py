"""Tests for mocode_tui.core.viewport.

Contracts (DESIGN.md): ``layout(width, height)`` returns exactly ``height``
rows -- the ``pin="top"`` region above the window, the ``pin="bottom"``
region below it, so neither fixed region ever scrolls away, and the window
height is ``height - top_rows - bottom_rows``; the offset clamps into
``[0, max(0, total - viewport_height)]``; a fresh viewport sticks to the
bottom, scrolling up detaches it, and it re-attaches at the bottom edge or via
``scroll_to_bottom()``; the ``MORE_BELOW`` marker appears only when scrolled
away with content below; the sealed-row cache invalidates on a width change.
The rebuilt per-layout row-ownership table (what a mouse hit test resolves
through) is covered end-to-end by ``test_app``'s public ``hit_test`` path.
"""

from _doubles import Rows, many

from mocode_tui.core.block import Document
from mocode_tui.core.lines import Line
from mocode_tui.core.style import MUTED
from mocode_tui.core.viewport import MORE_BELOW, Viewport


def _texts(rows: list[Line]) -> list[str]:
    return [row.text for row in rows]


def _doc(*texts: str) -> Document:
    doc = Document()
    doc.add(Rows(*texts))
    return doc


def test_initial_state():
    view = Viewport(Document())
    assert (view.offset, view.total_rows, view.viewport_height) == (0, 0, 0)
    assert view.at_bottom is True
    assert _texts(Viewport(Document()).layout(80, 3).rows) == ["", "", ""]


def test_rows_are_exactly_height_and_window_math_accounts_fixed_regions():
    doc = Document()
    doc.add(Rows(*many(10)))
    doc.add(Rows("t1", "t2"), pin="top")
    doc.add(Rows("b1"), pin="bottom")
    view = Viewport(doc)
    for height in (0, 1, 2, 3, 4, 7):
        layout = view.layout(80, height)
        assert len(layout.rows) == height  # exactly height rows, always
        assert len(layout.viewport_rows) == max(0, height - 3)
        assert view.viewport_height == max(0, height - 3)
        if height >= 3:  # the fixed regions never scroll away
            assert _texts(layout.rows[:2]) == ["t1", "t2"]
            assert _texts(layout.rows[-1:]) == ["b1"]


def test_short_document_is_top_aligned_and_blank_padded():
    view = Viewport(_doc("a", "b"))
    layout = view.layout(80, 5)
    assert _texts(layout.rows) == ["a", "b", "", "", ""]
    assert _texts(layout.viewport_rows) == ["a", "b", "", "", ""]
    assert (view.offset, view.at_bottom, view.total_rows) == (0, True, 2)


def test_long_document_sticks_to_the_bottom():
    view = Viewport(_doc(*many(10)))
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == many(10)[6:]
    assert (view.offset, view.at_bottom) == (6, True)


def test_more_below_marker_appears_only_scrolled_away_with_content_below():
    view = Viewport(_doc(*many(10)))
    layout = view.layout(80, 4)
    assert MORE_BELOW not in _texts(layout.rows)  # at the bottom: nothing waits below
    view.scroll_up(1)  # the window shows r5..r8, r9 waits below
    layout = view.layout(80, 4)
    assert layout.viewport_rows[-1] == Line.from_text(MORE_BELOW.text, MUTED)
    assert _texts(layout.rows) == ["r5", "r6", "r7", MORE_BELOW.text]
    view.scroll_down(1)  # r6..r9: nothing waits below, the marker goes away
    assert _texts(view.layout(80, 4).rows) == many(10)[6:]


def test_offset_clamps_at_both_edges_and_reattaches_at_the_bottom():
    view = Viewport(_doc(*many(10)))
    view.layout(80, 4)
    view.scroll_up(100)  # clamped at 0 and detached
    assert (view.offset, view.at_bottom) == (0, False)
    view.scroll_down(100)  # clamped at the last window and re-attached
    assert (view.offset, view.at_bottom) == (6, True)
    view.scroll_up(3)
    view.scroll_down(3)  # lands exactly on the clamp limit
    assert (view.offset, view.at_bottom) == (6, True)


def test_scroll_to_bottom_restores_stickiness_and_follows_new_content():
    doc = _doc(*many(10))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(2)
    view.scroll_to_bottom()
    assert view.at_bottom is True
    layout = view.layout(80, 4)  # the next layout pins the offset to the tail
    assert view.offset == 6
    doc.add(Rows("tail"))  # content that arrives while stuck moves the window
    layout = view.layout(80, 4)
    assert view.offset == 7
    assert _texts(layout.rows) == [*many(10)[7:], "tail"]


def test_bottom_and_top_pinned_rows_never_scroll_away():
    for pin in ("bottom", "top"):
        doc = Document()
        doc.add(Rows(*many(10)))
        doc.add(Rows("pin"), pin=pin)
        view = Viewport(doc)
        view.layout(80, 4)
        view.scroll_up(100)
        layout = view.layout(80, 4)
        assert view.viewport_height == 3
        assert view.total_rows == 10  # fixed-region rows are not body rows
        assert "pin" in _texts(layout.rows)
        assert _texts(layout.rows)[-1 if pin == "bottom" else 0] == "pin"


def test_bottom_region_wins_when_both_fixed_regions_overflow():
    doc = Document()
    doc.add(Rows(*many(10)))
    doc.add(Rows("t1", "t2", "t3"), pin="top")
    doc.add(Rows("b1", "b2", "b3", "b4"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert view.viewport_height == 0 and layout.viewport_rows == []
    assert _texts(layout.rows) == ["b1", "b2", "b3", "b4"]  # the top region gets nothing


def test_sealed_cache_invalidates_when_the_width_changes():
    class Counting(Rows):
        """Rows that remembers the widths it rendered at."""

        def __init__(self, *texts: str) -> None:
            super().__init__(*texts)
            self.calls: list[int] = []

        def render(self, width: int) -> list[Line]:
            self.calls.append(width)
            return super().render(width)

    doc = Document()
    component = Counting("w1")
    doc.add(component).seal()
    view = Viewport(doc)
    view.layout(80, 5)
    assert component.calls == [80]
    view.layout(100, 5)  # a new width: the cache clears and the block re-renders
    assert component.calls == [80, 100]
    view.layout(100, 5)
    assert component.calls == [80, 100]  # cached again at the new width
    assert _texts(view.layout(80, 5).rows) == ["w1", "", "", "", ""]


def test_row_blocks_is_rebuilt_per_layout_and_returned_as_a_copy():
    view = Viewport(_doc("a"))
    view.layout(80, 2)
    assert view.row_blocks == [("b0", 0), None]
    table = view.row_blocks
    table.append(None)
    assert view.row_blocks == [("b0", 0), None]  # the caller cannot corrupt it
    view.layout(80, 3)  # a new height renumbers the rows, blanks included
    assert view.row_blocks == [("b0", 0), None, None]
