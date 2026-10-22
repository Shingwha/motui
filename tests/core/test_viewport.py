"""Viewport layout and scroll state: window geometry, offset clamping,
stick-to-bottom and row ownership.

A layout always returns exactly ``height`` rows: the pinned top region, the
scrolling window and the pinned bottom region.  The window sticks to the
document tail until a scroll detaches it, and every screen row carries the
document address it shows.
"""

from __future__ import annotations

import pytest

from motui.core.block import Document
from motui.core.lines import Line, Text
from motui.core.viewport import Viewport
from tests.testing import Rows, document, many


def _texts(rows) -> list[str]:
    return [row.text for row in rows]


class _Counting:
    """A ``Revisioned`` component double that counts its renders."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.renders = 0

    def render(self, width: int) -> list[Line]:
        self.renders += 1
        return [Line.from_text(t) for t in self.texts]

    def revision(self) -> object:
        return tuple(self.texts)


class _WidthShaped:
    """A ``Revisioned`` double whose row count follows the width alone."""

    def __init__(self) -> None:
        self.renders = 0

    def render(self, width: int) -> list[Line]:
        self.renders += 1
        return [
            Line.from_text(f"w{width} row {i}") for i in range(max(1, width // 10))
        ]

    def revision(self) -> object:
        return "stable"  # the same snapshot at every width


class _Open:
    """A component double with no revision protocol: never cacheable."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.renders = 0

    def render(self, width: int) -> list[Line]:
        self.renders += 1
        return [Line.from_text(t) for t in self.texts]


def test_initial_state_is_an_empty_attached_viewport():
    view = Viewport(Document())
    assert (view.offset, view.at_bottom) == (0, True)
    layout = view.layout(80, 3)
    assert (layout.offset, layout.total_rows) == (0, 0)
    assert _texts(layout.rows) == ["", "", ""]


def test_layout_returns_exactly_height_rows():
    doc = Document()
    doc.add(Rows(*many(10)))
    doc.add(Rows("t1", "t2"), pin="top")
    doc.add(Rows("b1"), pin="bottom")
    view = Viewport(doc)
    for height in (0, 1, 2, 3, 4, 7):
        layout = view.layout(80, height)
        assert len(layout.rows) == height
        assert len(layout.body_rows) == max(0, height - 3)
        if height >= 3:
            assert _texts(layout.rows[:2]) == ["t1", "t2"]
            assert _texts(layout.rows[-1:]) == ["b1"]


def test_layout_reports_its_rectangle_and_scroll_state():
    view = Viewport(document(*many(10)))
    layout = view.layout(37, 5)
    assert (layout.width, layout.height) == (37, 5)
    assert layout.height == len(layout.rows)
    assert (layout.offset, layout.total_rows) == (5, 10)
    assert view.layout(80, 3).width == 80


def test_short_document_is_top_aligned_and_blank_padded():
    view = Viewport(document("a", "b"))
    layout = view.layout(80, 5)
    assert _texts(layout.rows) == ["a", "b", "", "", ""]
    assert (view.offset, view.at_bottom) == (0, True)


def test_long_document_sticks_to_the_bottom():
    view = Viewport(document(*many(10)))
    assert _texts(view.layout(80, 4).rows) == many(10)[6:]
    assert (view.offset, view.at_bottom) == (6, True)


def test_scrolling_clamps_and_reattaches_at_the_bottom():
    view = Viewport(document(*many(10)))
    view.layout(80, 4)
    view.scroll_up(100)
    assert (view.offset, view.at_bottom) == (0, False)
    assert _texts(view.layout(80, 4).rows) == many(10)[:4]
    view.scroll_down(100)
    assert (view.offset, view.at_bottom) == (6, True)
    view.scroll_up(1)
    view.scroll_down(1)
    assert (view.offset, view.at_bottom) == (6, True)


def test_scroll_to_clamps_at_both_edges_and_reattaches():
    view = Viewport(document(*many(10)))
    view.layout(80, 4)
    view.scroll_to(3)
    assert (view.offset, view.at_bottom) == (3, False)
    assert _texts(view.layout(80, 4).rows) == ["r3", "r4", "r5", "r6"]
    view.scroll_to(100)
    assert (view.offset, view.at_bottom) == (6, True)
    view.scroll_to(-5)
    assert (view.offset, view.at_bottom) == (0, False)


def test_scroll_to_before_the_first_layout_keeps_the_tail():
    view = Viewport(document("a", "b"))
    view.scroll_to(50)
    assert (view.offset, view.at_bottom) == (0, True)
    layout = view.layout(80, 5)
    assert layout.offset == 0 and _texts(layout.rows) == ["a", "b", "", "", ""]


def test_scroll_to_bottom_follows_new_content():
    doc = document(*many(10))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(2)
    view.scroll_to_bottom()
    assert view.at_bottom is True
    assert view.layout(80, 4).offset == 6
    doc.add(Rows("tail"))
    layout = view.layout(80, 4)
    assert view.offset == 7
    assert _texts(layout.rows) == [*many(10)[7:], "tail"]


def test_pinned_regions_never_scroll_and_are_not_body_rows():
    for pin in ("bottom", "top"):
        doc = Document()
        doc.add(Rows(*many(10)))
        doc.add(Rows("pin"), pin=pin)
        view = Viewport(doc)
        view.layout(80, 4)
        view.scroll_up(100)
        layout = view.layout(80, 4)
        assert layout.total_rows == 10
        assert _texts(layout.rows)[-1 if pin == "bottom" else 0] == "pin"
        assert "pin" not in _texts(layout.body_rows)


def test_bottom_region_wins_when_fixed_regions_overflow():
    doc = Document()
    doc.add(Rows(*many(10)))
    doc.add(Rows("t1", "t2", "t3"), pin="top")
    doc.add(Rows("b1", "b2", "b3", "b4"), pin="bottom")
    layout = Viewport(doc).layout(80, 4)
    assert layout.body_rows == ()
    assert _texts(layout.rows) == ["b1", "b2", "b3", "b4"]


def test_row_ownership_names_the_block_and_row_and_is_immutable():
    view = Viewport(document("a"))
    layout = view.layout(80, 2)
    assert layout.row_blocks == (("b0", 0), None)
    assert isinstance(layout.row_blocks, tuple)
    assert view.layout(80, 3).row_blocks == (("b0", 0), None, None)
    with pytest.raises(AttributeError):
        layout.row_blocks.append(None)  # type: ignore[attr-defined]


def test_block_order_lists_every_block_in_document_order():
    doc = Document()
    first = doc.add(Rows("a"))
    second = doc.add(Rows("b"), pin="top")
    third = doc.add(Rows("c"), pin="bottom")
    layout = Viewport(doc).layout(80, 4)
    assert layout.block_order == (first.id, second.id, third.id)


def test_the_window_equals_a_full_materialization():
    for width in (12, 80):
        for height in (3, 6):
            for scrolled in (0, 2, 50):
                doc = Document()
                for index in range(12):
                    doc.add(Text(f"line {index}: " + "abcd " * 6))
                view = Viewport(doc)
                view.layout(width, height)
                view.scroll_up(scrolled)
                layout = view.layout(width, height)
                rendered = [row for block in doc.blocks() for row in block.render(width)]
                owners = [
                    (block.id, row)
                    for block in doc.blocks()
                    for row in range(len(block.render(width)))
                ]
                offset = view.offset
                window = rendered[offset : offset + len(layout.body_rows)]
                window += [Line() for _ in range(len(layout.body_rows) - len(window))]
                assert _texts(layout.body_rows) == _texts(window)
                assert (layout.total_rows, layout.offset) == (len(rendered), offset)
                expected = owners[offset : offset + len(layout.body_rows)]
                expected += [None] * (len(layout.body_rows) - len(expected))
                assert layout.row_blocks == tuple(expected)


def test_natural_height_sums_every_block():
    doc = Document()
    doc.add(Rows("a", "b"))
    doc.add(Text("hello world"))
    view = Viewport(doc)
    assert view.natural_height(5) == 2 + 2
    assert view.natural_height(80) == 2 + 1


def test_streaming_content_recounts_the_body():
    doc = Document()
    head = doc.add(Rows("a", "b", "c"))
    mid = doc.add(Rows("m0", "m1"))
    tail = doc.add(Rows("t0", "t1", "t2"))
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert layout.total_rows == 8
    assert _texts(layout.body_rows) == ["m1", "t0", "t1", "t2"]
    assert layout.row_blocks[0] == (mid.id, 1)
    mid.component.texts = ["m0", "m1", "m2", "m3"]
    layout = view.layout(80, 4)
    assert layout.total_rows == 10
    assert view.offset == 6
    assert _texts(layout.body_rows) == ["m3", "t0", "t1", "t2"]
    assert layout.row_blocks[0] == (mid.id, 3)


def test_a_moved_block_remeasures_alone():
    doc = Document()
    head = _Counting("h0", "h1")
    mid = _Counting("m0", "m1")
    tail = _Counting("t0", "t1", "t2")
    doc.add(head)
    doc.add(mid)
    doc.add(tail)
    view = Viewport(doc)
    view.layout(80, 4)
    assert (head.renders, mid.renders, tail.renders) == (1, 1, 1)
    mid.texts = ["m0", "m1", "m2", "m3"]  # the snapshot moves: only mid re-renders
    view.layout(80, 4)
    assert (head.renders, mid.renders, tail.renders) == (1, 2, 1)


def test_add_and_remove_in_the_middle_keep_the_addresses_true():
    doc = Document()
    doc.add(_Counting(*many(3)))
    mid = doc.add(_Counting("m0", "m1", "m2", "m3"))
    doc.add(_Counting(*many(2)))
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert (layout.total_rows, layout.offset) == (9, 5)
    assert _texts(layout.body_rows) == ["m2", "m3", "r0", "r1"]
    assert layout.row_blocks == (("b1", 2), ("b1", 3), ("b2", 0), ("b2", 1))
    doc.remove(mid.id)
    layout = view.layout(80, 4)
    assert (layout.total_rows, layout.offset) == (5, 1)
    assert _texts(layout.body_rows) == ["r1", "r2", "r0", "r1"]
    assert layout.row_blocks == (("b0", 1), ("b0", 2), ("b2", 0), ("b2", 1))


def test_a_width_change_rebuilds_every_entry():
    doc = Document()
    shaped = _WidthShaped()
    doc.add(shaped)
    view = Viewport(doc)
    assert view.layout(80, 5).total_rows == 8
    rendered_wide = shaped.renders
    narrow = view.layout(40, 5)
    assert narrow.total_rows == 4  # the same snapshot, a different shape
    assert shaped.renders == rendered_wide + 1  # the width change rebuilt it
    assert view.layout(80, 5).total_rows == 8
    assert shaped.renders == rendered_wide + 2  # and back is a rebuild again


def test_an_unrevisioned_block_rerenders_every_frame():
    doc = Document()
    open_block = _Open("only")
    doc.add(open_block)
    view = Viewport(doc)
    view.layout(80, 3)
    view.layout(80, 3)
    view.layout(80, 3)
    assert open_block.renders == 3  # no snapshot, no memory: never frozen
    open_block.texts = ["moved"]
    assert _texts(view.layout(80, 3).body_rows) == ["moved", "", ""]
    assert open_block.renders == 4
