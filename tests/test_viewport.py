"""Tests for mocode_tui.core.viewport.

``layout(width, height)`` returns exactly ``height`` rows with the pinned
regions outside the window; the offset clamps and re-attaches at the bottom.
"""

import pytest

from _doubles import Rows, many

from mocode_tui.core.block import Document
from mocode_tui.core.lines import Line
from mocode_tui.core.style import MUTED
from mocode_tui.core.text import Text
from mocode_tui.core.viewport import MORE_BELOW, ScreenLayout, Viewport


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


@pytest.mark.parametrize(("scrolled", "offset"), [(0, 6), (1, 5), (3, 3), (100, 0)])
def test_the_layout_carries_the_window_offset_and_total_rows(scrolled: int, offset: int):
    """Chrome renders from the layout: the scroll state travels with it."""
    view = Viewport(_doc(*many(10)))
    view.layout(80, 4)  # sticks to the bottom: the window starts at row 6
    view.scroll_up(scrolled)
    layout = view.layout(80, 4)
    assert (layout.offset, layout.total_rows) == (offset, 10)
    assert (layout.offset, layout.total_rows) == (view.offset, view.total_rows)


def test_total_rows_counts_the_body_only_and_offset_clamps_to_the_window():
    doc = Document()
    doc.add(Rows(*many(10)))
    doc.add(Rows("t1", "t2"), pin="top")
    doc.add(Rows("b1"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 6)  # the window keeps 6 - 3 rows
    assert layout.total_rows == 10  # fixed-region rows are not body rows
    assert (view.viewport_height, layout.offset) == (3, 7)


def test_a_layout_without_scroll_state_defaults_to_nothing_known():
    empty = Viewport(Document()).layout(80, 3)
    assert (empty.offset, empty.total_rows) == (0, 0)
    assert (ScreenLayout(rows=[], viewport_rows=[]).offset) == 0
    assert (ScreenLayout(rows=[], viewport_rows=[]).total_rows) == 0


def _materialized_body(doc: Document, width: int) -> tuple[list[Line], list[tuple[str, int]]]:
    """The body rows and their owners by full materialization.

    Every unpinned block rendered and concatenated with its ``(id, row)``
    owners -- the shape the window slicing must reproduce out of per-block
    geometry, reconstructed here without touching the viewport.
    """
    rows: list[Line] = []
    owners: list[tuple[str, int]] = []
    for block in doc.blocks():
        if block.pin is None:
            rendered = block.render(width)
            rows.extend(rendered)
            owners.extend((block.id, i) for i in range(len(rendered)))
    return rows, owners


@pytest.mark.parametrize("width", [12, 80])
@pytest.mark.parametrize("height", [3, 6, 45])
@pytest.mark.parametrize("scrolled", [0, 1, 7, 200])
def test_the_window_equals_full_materialization_at_any_address(
    scrolled: int, height: int, width: int
):
    """T1: the window sliced from per-block geometry must hold the very rows
    a full concatenation gives -- at any offset, window height and width.
    """
    doc = Document()
    for i in range(60):
        # Rows long enough to wrap at width 12 but not 80, so the per-block
        # counts genuinely differ with the width.
        doc.add(Text(f"line {i}: " + "abcd " * 6)).seal()
    view = Viewport(doc)
    view.layout(width, height)  # sticks to the bottom first
    view.scroll_up(scrolled)  # then detaches and moves (clamped at 0)
    layout = view.layout(width, height)
    rows, owners = _materialized_body(doc, width)
    total = len(rows)
    offset, vh = view.offset, view.viewport_height
    expect = rows[offset : offset + vh]
    if not view.at_bottom and vh and offset + vh < total:
        expect[-1] = MORE_BELOW  # the marker replaces the last window row
    if len(expect) < vh:
        expect.extend(Line() for _ in range(vh - len(expect)))  # blank fill
    assert _texts(layout.viewport_rows) == _texts(expect)
    assert (layout.total_rows, layout.offset) == (total, offset)
    visible = owners[offset : offset + vh]
    assert layout.row_blocks == visible + [None] * (vh - len(visible))


def _screen_table_reference(
    doc: Document, width: int, height: int, offset: int
) -> list[tuple[str, int] | None]:
    """The documented row-ownership table for one screen, from first principles.

    The bottom region wins what fits, the top region keeps only the leading
    rows that still fit after it, the window's body owners sit between them
    padded with ``None`` for the blank fill -- the layout's own construction,
    rebuilt here over fully materialized blocks.
    """
    top_owners: list[tuple[str, int]] = []
    bottom_owners: list[tuple[str, int]] = []
    body_owners: list[tuple[str, int]] = []
    for block in doc.blocks():
        owners = [(block.id, i) for i in range(len(block.render(width)))]
        if block.pin == "top":
            top_owners.extend(owners)
        elif block.pin == "bottom":
            bottom_owners.extend(owners)
        else:
            body_owners.extend(owners)
    bottom_kept = len(bottom_owners[:height])
    top_kept = len(top_owners[: max(0, height - bottom_kept)])
    vh = max(0, height - top_kept - bottom_kept)
    visible = body_owners[offset : offset + vh]
    return [
        *top_owners[:top_kept],
        *visible,
        *([None] * (vh - len(visible))),
        *bottom_owners[:bottom_kept],
    ]


@pytest.mark.parametrize("height", [4, 8])
@pytest.mark.parametrize("scrolled", [0, 3, 9, 50])
def test_the_ownership_table_is_identical_row_for_row(scrolled: int, height: int):
    """T1: every screen row must resolve to the same document address a full
    materialization's slice gives -- varied block sizes, pinned regions, the
    marker row (which keeps the ownership of the body row it covers) and the
    blank fill included, at any offset."""
    doc = Document()
    doc.add(Rows("t1", "t2"), pin="top")
    for size in (1, 2, 3, 4, 5):
        doc.add(Rows(*[f"b{size}r{i}" for i in range(size)])).seal()
    doc.add(Rows("b1"), pin="bottom")
    view = Viewport(doc)
    view.layout(80, height)
    view.scroll_up(scrolled)
    layout = view.layout(80, height)
    assert layout.row_blocks == _screen_table_reference(doc, 80, height, view.offset)


def test_an_open_block_between_sealed_ones_lands_its_rows_at_the_right_addresses():
    """T1: an open block renders fresh each layout, so the per-block counts
    that place the blocks after it must move with its content -- and slicing
    must never hand out (or let a layout overwrite) a sealed block's rows."""
    doc = Document()
    head = doc.add(Rows("a", "b", "c"))
    head.seal()  # body rows 0..2
    mid = doc.add(Rows("m0", "m1"))  # body rows 3..4, open: re-rendered
    tail = doc.add(Rows("t0", "t1", "t2"))
    tail.seal()  # body rows 5..7
    view = Viewport(doc)
    layout = view.layout(80, 4)  # sticks to the bottom: rows 4..7
    assert view.total_rows == 8
    assert layout.block_order == (head.id, mid.id, tail.id)
    assert _texts(layout.viewport_rows) == ["m1", "t0", "t1", "t2"]
    assert layout.row_blocks == [
        (mid.id, 1),
        (tail.id, 0),
        (tail.id, 1),
        (tail.id, 2),
    ]
    mid.component.texts = ["m0", "m1", "m2", "m3"]  # the stream grows it
    layout = view.layout(80, 4)
    assert view.total_rows == 10  # the fresh render re-counts the block
    assert view.offset == 6  # still sticking to the tail, which moved down
    assert _texts(layout.viewport_rows) == ["m3", "t0", "t1", "t2"]
    assert layout.row_blocks == [
        (mid.id, 3),
        (tail.id, 0),
        (tail.id, 1),
        (tail.id, 2),
    ]
    view.scroll_up(5)  # rows 1..4: the window straddles head and mid
    layout = view.layout(80, 4)
    assert _texts(layout.viewport_rows) == ["b", "c", "m0", MORE_BELOW.text]
    assert layout.row_blocks == [
        (head.id, 1),  # the sealed head's second row
        (head.id, 2),
        (mid.id, 0),  # the open mid's first row
        (mid.id, 1),  # the marker keeps the ownership of the row it covers
    ]
    view.scroll_to_bottom()
    assert _texts(view.layout(80, 4).viewport_rows) == ["m3", "t0", "t1", "t2"]
