"""Tests for mocode_tui.core.frame: the rect algebra and the compositor.

``split_rect`` tiles a rectangle with the widgets' fixed/flex vocabulary
(lifted, minus the gap); ``Frame`` lays every pane's viewport out at the
pane's rectangle, splices the rows into the frame rows, and builds the
ownership table a hit test routes through.  A lone pane whose rectangle is
the whole frame composes to its pane's own layout -- pass-through, not
re-derivation.
"""

import pytest

from _doubles import Rows

from mocode_tui.core.block import Document
from mocode_tui.core.frame import Frame, FrameSpan, Pane, Rect, split_rect
from mocode_tui.core.lines import Line
from mocode_tui.core.viewport import Viewport


def _doc(*texts: str) -> Document:
    """A one-block document rendering ``texts`` as its rows."""
    doc = Document()
    doc.add(Rows(*texts))
    return doc


def _pane(pane_id: str, rect: Rect, *texts: str) -> Pane:
    """A pane over a fresh one-block document of ``texts``."""
    return Pane(pane_id, rect, Viewport(_doc(*texts)))


def _side_by_side() -> Frame:
    """A 20x3 frame over two documents, split down the middle."""
    left, right = split_rect(Rect(0, 0, 20, 3), "vertical", (None, None))
    return Frame(
        [
            _pane("left", left, "l0", "l1", "l2"),
            _pane("right", right, "r0", "r1", "r2"),
        ]
    )


# --- the split algebra ---------------------------------------------------------


@pytest.mark.parametrize(
    ("orientation", "sizes", "expected"),
    [
        # flexible panes share the span, the remainder discarded
        ("vertical", (None, None), [40, 40]),
        ("horizontal", (None, None), [6, 6]),
        ("vertical", (None, None, None), [26, 26, 26]),
        # fixed cells first, the flexible one takes what remains
        ("vertical", (20, None), [20, 60]),
        ("horizontal", (2, None), [2, 10]),
        ("vertical", (25, None, None), [25, 27, 27]),
        # a fixed size that overruns the span is clipped, never overlapping
        ("vertical", (50, 40), [50, 30]),
        ("horizontal", (5, 9), [5, 7]),
        # zero and negative fixed sizes take nothing and eat no remainder
        ("vertical", (0, None), [0, 80]),
        ("vertical", (-5, None), [0, 80]),
        # a remainder the fixed sizes already exhausted leaves flex nothing
        ("vertical", (90, None), [80, 0]),
    ],
)
def test_split_sizes_tile_the_span_the_row_arithmetic_way(
    orientation: str, sizes: tuple[int | None, ...], expected: list[int]
):
    """The widgets' division, lifted: fixed first, flex share the remainder."""
    rects = split_rect(Rect(0, 0, 80, 12), orientation, sizes)
    axis = (rect.width for rect in rects) if orientation == "vertical" else (
        rect.height for rect in rects
    )
    assert list(axis) == expected


def test_split_rect_tiles_along_the_axis_and_inherits_the_cross_axis():
    rect = Rect(2, 3, 80, 12)
    assert split_rect(rect, "vertical", (20, None)) == [
        Rect(2, 3, 20, 12),
        Rect(22, 3, 60, 12),
    ]
    assert split_rect(rect, "horizontal", (None, 5)) == [
        Rect(2, 3, 80, 7),
        Rect(2, 10, 80, 5),
    ]


@pytest.mark.parametrize("sizes", [(), []])
def test_split_of_no_pane_sizes_returns_nothing(sizes):
    assert split_rect(Rect(0, 0, 80, 24), "vertical", sizes) == []


def test_split_rejects_an_unknown_orientation():
    with pytest.raises(ValueError):
        split_rect(Rect(0, 0, 80, 24), "diagonal", (None,))


@pytest.mark.parametrize("size", [(-1, 24), (80, -1)])
def test_a_rect_size_is_never_negative(size: tuple[int, int]):
    with pytest.raises(ValueError):
        Rect(0, 0, *size)


# --- composition ---------------------------------------------------------------


def test_a_two_pane_frame_composes_both_documents_side_by_side():
    frame = _side_by_side()
    layout = frame.compose(20, 3)
    assert [row.text for row in layout.rows] == [
        "l0" + " " * 8 + "r0",
        "l1" + " " * 8 + "r1",
        "l2" + " " * 8 + "r2",
    ]
    assert frame.table.rows == (
        (FrameSpan("left", "b0", 0, 0, 10), FrameSpan("right", "b0", 0, 10, 20)),
        (FrameSpan("left", "b0", 1, 0, 10), FrameSpan("right", "b0", 1, 10, 20)),
        (FrameSpan("left", "b0", 2, 0, 10), FrameSpan("right", "b0", 2, 10, 20)),
    )


def test_a_four_pane_nested_frame_composes_every_quadrant():
    left, right = split_rect(Rect(0, 0, 20, 4), "vertical", (None, None))
    lt, lb = split_rect(left, "horizontal", (None, None))
    rt, rb = split_rect(right, "horizontal", (None, None))
    frame = Frame(
        [
            _pane("lt", lt, "a0", "a1"),
            _pane("lb", lb, "a2", "a3"),
            _pane("rt", rt, "b0", "b1"),
            _pane("rb", rb, "b2", "b3"),
        ]
    )
    layout = frame.compose(20, 4)
    assert [row.text for row in layout.rows] == [
        "a0" + " " * 8 + "b0",
        "a1" + " " * 8 + "b1",
        "a2" + " " * 8 + "b2",
        "a3" + " " * 8 + "b3",
    ]
    assert frame.table.rows == (
        (FrameSpan("lt", "b0", 0, 0, 10), FrameSpan("rt", "b0", 0, 10, 20)),
        (FrameSpan("lt", "b0", 1, 0, 10), FrameSpan("rt", "b0", 1, 10, 20)),
        (FrameSpan("lb", "b0", 0, 0, 10), FrameSpan("rb", "b0", 0, 10, 20)),
        (FrameSpan("lb", "b0", 1, 0, 10), FrameSpan("rb", "b0", 1, 10, 20)),
    )


def test_a_lone_full_frame_pane_composes_to_its_own_layout():
    """The single-pane pass-through: the composed layout IS the pane's layout."""
    pane = _pane("primary", Rect(0, 0, 80, 4), "r0", "r1", "r2", "r3", "r4")
    frame = Frame([pane])
    composed = frame.compose(80, 4)
    assert composed is frame.pane_layouts[0]
    assert composed.rows is frame.pane_layouts[0].rows
    assert composed.rows == [Line.from_text(t) for t in ("r1", "r2", "r3", "r4")]
    assert composed.row_blocks == [("b0", 1), ("b0", 2), ("b0", 3), ("b0", 4)]
    assert frame.table.rows == tuple(
        (FrameSpan("primary", "b0", row, 0, 80),) for row in (1, 2, 3, 4)
    )


def test_a_full_width_pane_passes_its_rows_through_the_frame_rows():
    """Stacked panes keep their rows unchanged: no slicing, no padding."""
    top, bottom = split_rect(Rect(0, 0, 40, 4), "horizontal", (None, None))
    frame = Frame([_pane("top", top, "t0", "t1"), _pane("below", bottom, "u0", "u1")])
    layout = frame.compose(40, 4)
    assert [row.text for row in layout.rows] == ["t0", "t1", "u0", "u1"]
    assert layout.rows[0] is frame.pane_layouts[0].rows[0]
    assert layout.rows[1] is frame.pane_layouts[0].rows[1]
    assert layout.rows[2] is frame.pane_layouts[1].rows[0]
    assert layout.rows[3] is frame.pane_layouts[1].rows[1]


def test_a_pane_composes_at_its_rect_not_the_frame_origin():
    frame = Frame([_pane("corner", Rect(2, 1, 8, 2), "x")])
    layout = frame.compose(12, 4)
    assert [row.text for row in layout.rows] == ["", "  x  ", "    ", ""]
    assert frame.table.rows == (
        (),
        (FrameSpan("corner", "b0", 0, 2, 10),),
        (FrameSpan("corner", None, 0, 2, 10),),  # the blank fill: claimed, unowned
        (),
    )


def test_a_pane_past_the_frame_edge_paints_nothing():
    """A rectangle the frame does not cover contributes no rows and no table."""
    frame = Frame(
        [
            _pane("visible", Rect(0, 0, 10, 4), "r0", "r1", "r2", "r3"),
            _pane("popped", Rect(0, 4, 10, 2), "n0", "n1"),
        ]
    )
    layout = frame.compose(10, 2)
    assert [row.text for row in layout.rows] == ["r0", "r1"]
    assert frame.table.rows == (
        (FrameSpan("visible", "b0", 0, 0, 10),),
        (FrameSpan("visible", "b0", 1, 0, 10),),
    )


# --- the ownership table ---------------------------------------------------------


def test_the_table_resolves_the_claiming_span_and_clamps_outside_columns():
    frame = _side_by_side()
    frame.compose(20, 3)
    table = frame.table
    assert table.resolve(0, 0).pane_id == "left"
    assert table.resolve(0, 9).pane_id == "left"
    assert table.resolve(0, 10).pane_id == "right"
    assert table.resolve(0, 19).pane_id == "right"
    assert table.resolve(0, 40).pane_id == "right"  # clamped to the row's last span
    assert table.resolve(0, -3).pane_id == "left"  # clamped to the row's first span
    assert table.resolve(3, 0) is None  # past the rows the composition painted


def test_the_table_resolves_a_span_to_its_pane_document_block():
    doc = _doc("l0", "l1", "l2")
    pane = Pane("left", Rect(0, 0, 20, 3), Viewport(doc))
    frame = Frame([pane])
    frame.compose(20, 3)
    span = frame.table.resolve(1, 5)
    assert (span.block_id, span.row_in_block) == ("b0", 1)
    assert pane.viewport.document.get(span.block_id) is doc.blocks()[0]


# --- the frame around the panes ---------------------------------------------------


def test_the_frame_rect_is_the_bounding_box_of_the_tiling():
    frame = _side_by_side()
    assert frame.rect == Rect(0, 0, 20, 3)
    assert frame.pane("left") is frame.panes[0]
    assert frame.pane("nowhere") is None
    assert frame.focused_pane is frame.panes[0]


def test_an_empty_frame_composes_a_blank_screen():
    frame = Frame()
    layout = frame.compose(3, 2)
    assert [row.text for row in layout.rows] == ["", ""]
    assert frame.table.rows == ((), ())
    assert frame.rect is None and frame.focused_pane is None
    assert frame.layout is layout and frame.panes == ()
