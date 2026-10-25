"""The frame compositor: Rect values, Split tiling, Pane split/close, chrome
negotiation, composition and overlays.

A split tiles a rectangle exactly; closing a leaf collapses or re-divides
its parent and strips the divider of the gap it leaves.  Composition lays
each pane's viewport out at its chrome-subtracted rectangle, splices the
rows into one grid and records which pane and document address owns each
cell.  Overlays paint over the composed frame back to front by layer.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.kernel.cell import Line, cut_line, slice_line
from motui.kernel.document import Document, Placement
from motui.kernel.geom import Axis
from motui.kernel.frame import (
    Chrome,
    Frame,
    FrameSpan,
    Pane,
    Rect,
    Split,
    splice_row,
)
from motui.kernel.layout import ScreenLayout, Viewport
from motui.kernel.text import index_bounds_at_columns
from motui.widgets.text import Text
from tests.testing import Rows, document


def _pane(pane_id: str, rect: Rect, *texts: str) -> Pane:
    return Pane(pane_id, rect, Viewport(document(*texts)))


def _wrapping_pane(pane_id: str, rect: Rect, *texts: str) -> Pane:
    doc = Document()
    doc.add(Text("\n".join(texts)))
    return Pane(pane_id, rect, Viewport(doc))


def _side_by_side() -> Frame:
    left, right = Split(Axis.X, (1, 1)).rects(Rect(x=0, y=0, width=20, height=3))
    return Frame(
        [
            _pane("left", left, "l0", "l1", "l2"),
            _pane("right", right, "r0", "r1", "r2"),
        ]
    )


def _marker_chrome(edge: str, size: int, mark: str = "*") -> Chrome:
    def paint(layout: ScreenLayout, length: int) -> list[Line]:
        rows = length if edge in ("left", "right") else size
        width = size if edge in ("left", "right") else length
        return [
            Line.from_text((mark if index == 0 else "-").ljust(width)[:width])
            for index in range(rows)
        ]

    return Chrome(edge, size, paint)


def _divider_chrome(edge: str, mark: str = " ") -> Chrome:
    def paint(layout: ScreenLayout, length: int) -> list[Line]:
        rows = length if edge in ("left", "right") else 1
        width = 1 if edge in ("left", "right") else length
        return [Line.from_text(mark * width) for _ in range(rows)]

    return Chrome(edge, 1, paint, name="separator")


def _spy_chrome(
    edge: str, size: int, painted: list[tuple[str, int]], mark: str = " "
) -> Chrome:
    def paint(layout: ScreenLayout, length: int) -> list[Line]:
        painted.append((edge, length))
        rows = length if edge in ("left", "right") else size
        width = size if edge in ("left", "right") else length
        return [Line.from_text((mark * width)[:width]) for _ in range(rows)]

    return Chrome(edge, size, paint)


def test_rect_is_a_non_negative_value_with_edges():
    for size in ((-1, 24), (80, -1)):
        with pytest.raises(ValueError):
            Rect(x=0, y=0, width=size[0], height=size[1])
    rect = Rect(x=2, y=3, width=10, height=4)
    assert (rect.right, rect.bottom) == (12, 7)


def test_split_weights_tile_the_span_exactly():
    cases = [
        (Axis.X, 40, (1, 1), [20, 20]),
        (Axis.X, 41, (1, 1), [20, 21]),
        (Axis.X, 10, (2, 1), [6, 4]),
        (Axis.Y, 12, (1, 3), [3, 9]),
        (Axis.X, 12, (1, 1, 1), [4, 4, 4]),
        (Axis.X, 5, (1, 1), [2, 3]),
        (Axis.X, 3, (3, 1), [2, 1]),
        (Axis.X, 1, (1, 1), [1, 0]),
    ]
    for axis, span, weights, expected in cases:
        rect = (
            Rect(x=0, y=0, width=span, height=3)
            if axis is Axis.X
            else Rect(x=0, y=0, width=3, height=span)
        )
        rects = Split(axis, weights, 1).rects(rect)
        sizes = [
            part.width if axis is Axis.X else part.height for part in rects
        ]
        assert sizes == expected
        if axis is Axis.X:
            assert [part.x for part in rects] == [
                sum(expected[:index]) for index in range(len(expected))
            ]


def test_split_validates_its_arguments():
    for weights in ((), (0, 0), (-1, 1)):
        with pytest.raises(ValueError):
            Split(Axis.X, weights)
    with pytest.raises(ValueError):
        Split("vertical", (1, 1))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Split(Axis.X, (1, 1), -1)


def test_a_split_pane_keeps_its_document_and_chrome_in_the_first_child():
    pane = _wrapping_pane("primary", Rect(x=0, y=0, width=20, height=4), "kept")
    marker = _marker_chrome("right", 1, "#")
    pane.add_chrome(marker)
    left, right = pane.split(Axis.X, weights=(2, 1))
    assert left.id == "primary" and right.id == "pane-1"
    assert left.viewport is pane.viewport and left.chrome == (marker,)
    assert right.document.blocks() == ()
    assert pane.division is not None and pane.children == (left, right)
    with pytest.raises(RuntimeError):
        pane.split(Axis.Y)


def test_closing_one_of_two_collapses_the_parent_and_strips_the_divider():
    pane = _wrapping_pane("primary", Rect(x=0, y=0, width=20, height=4), "0123456789")
    bar = _marker_chrome("right", 1, "#")
    pane.add_chrome(bar)
    left, right = pane.split(Axis.X, weights=(2, 1))
    left.add_chrome(_divider_chrome("right"))
    right.document.add(Rows("R"))
    frame = Frame([pane])
    right.focus()
    right.close()
    assert left.chrome == (bar,)
    assert pane.division is None and pane.children == ()
    assert pane.rect == Rect(x=0, y=0, width=20, height=4)
    assert pane.viewport is left.viewport
    assert frame.panes == (pane,) and frame.focused_pane is pane
    assert frame.pane("pane-1") is None
    assert [row.text for row in frame.compose(20, 4).rows][0].startswith("0123456789")


def test_closing_a_later_child_keeps_the_parents_id():
    other = _pane("other", Rect(x=0, y=0, width=20, height=3), "o")
    root = _pane("primary", Rect(x=0, y=0, width=30, height=3), "a")
    frame = Frame([other, root])
    panes = root.split(Axis.X, weights=(1, 1, 1))
    panes[2].focus()
    panes[0].close()
    assert frame.focused_pane is panes[2]
    panes[1].close()
    assert [pane.id for pane in frame.panes] == ["other", "primary"]
    assert frame.pane("pane-2") is None
    assert frame.pane("primary") is root
    assert root.viewport is panes[2].viewport
    assert frame.focused_pane is root


def test_closing_one_of_three_redivides_over_the_survivors():
    for closed in (0, 1, 2):
        root = Pane("primary", Rect(x=0, y=0, width=30, height=3), Viewport(Document()))
        frame = Frame([root])
        panes = root.split(Axis.X, weights=(1, 1, 1))
        for before in panes[:-1]:
            before.add_chrome(_divider_chrome("right"))
        for index, pane in enumerate(panes):
            pane.document.add(Rows(f"p{index}"))
        panes[closed].close()
        survivors = tuple(pane for index, pane in enumerate(panes) if index != closed)
        assert frame.panes == survivors
        assert root.division.weights == (1, 1)
        assert [pane.rect for pane in survivors] == [
            Rect(x=0, y=0, width=15, height=3),
            Rect(x=15, y=0, width=15, height=3),
        ]
        dividers = {0: [1, 0], 1: [0, 0], 2: [1, 0]}[closed]
        assert [
            len([chrome for chrome in pane.chrome if chrome.name == "separator"])
            for pane in survivors
        ] == dividers
        layout = frame.compose(30, 3)
        assert frame.table.rows[0] == (
            FrameSpan(survivors[0].id, "b0", 0, 0, 15),
            FrameSpan(survivors[1].id, "b0", 0, 15, 30),
        )
        assert [row.text for row in layout.rows[1:]] == [" " * 30] * 2


def test_a_focused_close_hands_focus_to_the_pane_that_took_its_place():
    for closed in (0, 1, 2):
        root = _pane("primary", Rect(x=0, y=0, width=30, height=3))
        frame = Frame([root])
        panes = root.split(Axis.X, weights=(1, 1, 1))
        panes[closed].focus()
        panes[closed].close()
        survivors = [pane for index, pane in enumerate(panes) if index != closed]
        assert frame.focused_pane is survivors[min(closed, len(survivors) - 1)]


def test_close_refuses_a_root_a_container_a_second_close_and_a_loose_pane():
    frame = Frame([_pane("primary", Rect(x=0, y=0, width=20, height=3), "a")])
    root = frame.panes[0]
    with pytest.raises(RuntimeError):
        root.close()
    left, right = root.split(Axis.X)
    with pytest.raises(RuntimeError):
        root.close()
    left.close()
    with pytest.raises(RuntimeError):
        left.close()
    with pytest.raises(RuntimeError):
        _pane("loose", Rect(x=0, y=0, width=4, height=1), "x").close()


def test_closing_inside_a_nested_split_keeps_the_outer_tree():
    root = _pane("primary", Rect(x=0, y=0, width=40, height=8))
    frame = Frame([root])
    left, right = root.split(Axis.X, weights=(1, 1))
    top, bottom = right.split(Axis.Y, weights=(1, 1))
    frame.retile(Rect(x=0, y=0, width=40, height=8))
    bottom.close()
    assert right.division is None and right.viewport is top.viewport
    assert right.rect == Rect(x=20, y=0, width=20, height=8)
    assert root.division.weights == (1, 1)
    assert [pane.rect for pane in frame.panes] == [
        Rect(x=0, y=0, width=20, height=8),
        Rect(x=20, y=0, width=20, height=8),
    ]


def test_closing_the_only_child_restores_the_leaf_and_collapse_adopts_a_subtree():
    pane = _pane("primary", Rect(x=0, y=0, width=12, height=2), "a", "b")
    frame = Frame([pane])
    (only,) = pane.split(Axis.X, weights=(1,))
    only.close()
    assert pane.division is None and frame.panes == (pane,)
    assert [row.text for row in frame.compose(12, 2).rows] == ["a", "b"]

    root = _pane("primary", Rect(x=0, y=0, width=40, height=8))
    frame = Frame([root])
    left, right = root.split(Axis.X, weights=(1, 1))
    top, bottom = right.split(Axis.Y, weights=(1, 1))
    frame.retile(Rect(x=0, y=0, width=40, height=8))
    left.close()
    assert root.division.axis is Axis.Y
    assert root.children == (top, bottom)
    assert [pane.rect for pane in frame.panes] == [
        Rect(x=0, y=0, width=40, height=4),
        Rect(x=0, y=4, width=40, height=4),
    ]


def test_retile_re_divides_the_tree_and_keeps_every_panes_state():
    frame = Frame([_pane("primary", Rect(x=0, y=0, width=0, height=0), "r0")])
    left, right = frame.panes[0].split(Axis.X, weights=(1, 1))
    spy = _spy_chrome("right", 1, [], "s")
    left.add_chrome(spy)
    frame.retile(Rect(x=0, y=0, width=40, height=4))
    assert (left.rect, right.rect) == (Rect(x=0, y=0, width=20, height=4), Rect(x=20, y=0, width=20, height=4))
    assert frame.panes == (left, right) and left.chrome == (spy,)
    frame.retile(Rect(x=0, y=0, width=20, height=4))
    assert (left.rect, right.rect) == (Rect(x=0, y=0, width=10, height=4), Rect(x=10, y=0, width=10, height=4))
    top, bottom = right.split(Axis.Y, weights=(1, 1))
    frame.retile(Rect(x=0, y=0, width=40, height=8))
    assert [pane.rect for pane in frame.panes] == [
        Rect(x=0, y=0, width=20, height=8),
        Rect(x=20, y=0, width=20, height=4),
        Rect(x=20, y=4, width=20, height=4),
    ]
    assert frame.focused_pane is left


def test_focus_names_the_pane_input_routes_to():
    frame = _side_by_side()
    frame.focus("right")
    assert frame.focused_pane is frame.panes[1]
    frame.focus(frame.panes[0])
    assert frame.focused_pane is frame.panes[0]
    with pytest.raises(ValueError):
        frame.focus("nowhere")
    with pytest.raises(RuntimeError):
        _pane("loose", Rect(x=0, y=0, width=4, height=1), "x").focus()


def test_a_dock_composes_beneath_the_panes_and_never_takes_focus():
    frame = Frame([_pane("primary", Rect(x=0, y=0, width=0, height=0), "l0", "l1", "l2")])
    left, right = frame.panes[0].split(Axis.X, weights=(1, 1))
    right.document.add(Rows("r0", "r1", "r2"))
    dock = Pane("dock", Rect(x=0, y=3, width=20, height=1), Viewport(document("f0")))
    frame.set_dock("bottom", dock)
    frame.retile(Rect(x=0, y=0, width=20, height=3), docks={"bottom": Rect(x=0, y=3, width=20, height=1)})
    frame.compose(20, 4)
    assert [row.text for row in frame.layout.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
        "f0",
    ]
    assert frame.panes == (left, right)
    assert frame.dock("bottom") is dock and frame.pane("dock") is dock
    assert frame.focused_pane is left
    assert frame.table.rows[3] == (FrameSpan("dock", "b0", 0, 0, 20),)
    assert frame.rect == Rect(x=0, y=0, width=20, height=4)
    assert frame.region("primary") == Rect(x=0, y=0, width=10, height=3)
    assert frame.region("dock") == Rect(x=0, y=3, width=20, height=1)
    with pytest.raises(ValueError):
        frame.focus("dock")
    with pytest.raises(RuntimeError):
        dock.split(Axis.X)
    with pytest.raises(RuntimeError):
        dock.close()
    frame.retile(Rect(x=0, y=0, width=20, height=3))
    assert dock.rect == Rect(x=0, y=0, width=0, height=0)
    released = frame.compose(20, 3)
    assert [row.text for row in released.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
    ]
    assert frame.region("dock") is None


def test_two_panes_compose_side_by_side_and_own_their_cells():
    frame = _side_by_side()
    layout = frame.compose(20, 3)
    assert [row.text for row in layout.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
    ]
    assert (layout.width, layout.height) == (20, 3)
    assert frame.table.rows[0] == (
        FrameSpan("left", "b0", 0, 0, 10),
        FrameSpan("right", "b0", 0, 10, 20),
    )
    assert frame.table.resolve(0, 0).pane_id == "left"
    assert frame.table.resolve(0, 9).pane_id == "left"
    assert frame.table.resolve(0, 10).pane_id == "right"
    assert frame.table.resolve(0, 40) is None
    assert frame.table.resolve(0, -3) is None
    assert frame.table.resolve(3, 0) is None


def test_a_four_pane_nested_frame_composes_every_quadrant():
    left, right = Split(Axis.X, (1, 1)).rects(Rect(x=0, y=0, width=20, height=4))
    lt, lb = Split(Axis.Y, (1, 1)).rects(left)
    rt, rb = Split(Axis.Y, (1, 1)).rects(right)
    frame = Frame(
        [
            _pane("lt", lt, "a0", "a1"),
            _pane("lb", lb, "a2", "a3"),
            _pane("rt", rt, "b0", "b1"),
            _pane("rb", rb, "b2", "b3"),
        ]
    )
    frame.compose(20, 4)
    assert [row.text for row in frame.layout.rows] == [
        "a0" + " " * 8 + "b0" + " " * 8,
        "a1" + " " * 8 + "b1" + " " * 8,
        "a2" + " " * 8 + "b2" + " " * 8,
        "a3" + " " * 8 + "b3" + " " * 8,
    ]
    assert frame.table.rows[2] == (
        FrameSpan("lb", "b0", 0, 0, 10),
        FrameSpan("rb", "b0", 0, 10, 20),
    )


def test_a_lone_full_frame_pane_composes_to_its_own_layout():
    pane = _pane("primary", Rect(x=0, y=0, width=80, height=4), "r0", "r1", "r2", "r3", "r4")
    frame = Frame([pane])
    composed = frame.compose(80, 4)
    assert composed is frame.pane_layout("primary")
    assert [row.text for row in composed.rows] == ["r1", "r2", "r3", "r4"]
    assert composed.row_blocks == (("b0", 1), ("b0", 2), ("b0", 3), ("b0", 4))
    top, bottom = Split(Axis.Y, (1, 1)).rects(Rect(x=0, y=0, width=40, height=4))
    stacked = Frame([_pane("top", top, "t0", "t1"), _pane("below", bottom, "u0", "u1")])
    assert [row.text for row in stacked.compose(40, 4).rows] == ["t0", "t1", "u0", "u1"]


def test_composing_at_an_unchanged_size_refills_the_same_buffers_from_scratch():
    content = Rows("l0", "l1", "l2")  # held so the text can be rewritten in place
    doc = Document()
    doc.add(content)
    frame = Frame(
        [
            Pane("left", Rect(x=0, y=0, width=10, height=3), Viewport(doc)),
            _pane("right", Rect(x=10, y=0, width=10, height=3), "r0", "r1", "r2"),
        ]
    )
    first = frame.compose(20, 3)
    assert [row.text for row in frame.compose(20, 3).rows] == [
        row.text for row in first.rows
    ]
    # The row buffers are the frame's between compositions; the rows are
    # the composition's.  Rewriting a pane's content at the same size must
    # reach the next product -- and leave the earlier one as it stood.
    content.texts[0] = "L0"
    changed = frame.compose(20, 3)
    assert [row.text for row in first.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
    ]
    assert [row.text for row in changed.rows] == [
        "L0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
    ]


def test_composing_at_a_new_height_rebuilds_the_buffers_with_no_stale_rows():
    frame = _side_by_side()
    assert len(frame.compose(20, 3).rows) == 3
    grown = frame.compose(20, 5)
    assert [row.text for row in grown.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
        "",
        "",
    ]
    shrunk = frame.compose(20, 2)
    assert [row.text for row in shrunk.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
    ]


def test_an_unchanged_plan_still_hands_the_memoized_row_back():
    frame = _side_by_side()
    frame.pane("right").add_chrome(_marker_chrome("right", 1, "#"))
    first = frame.compose(20, 3)
    again = frame.compose(20, 3)
    # No row here is a single full-width write -- two panes plus the chrome
    # band each write into every row -- so each row travels through the
    # memo: the same plan key hands back the very row the previous
    # composition built.
    for before, after in zip(first.rows, again.rows):
        assert after is before
    assert [row.text for row in again.rows] == [
        "l0" + " " * 8 + "r0" + " " * 7 + "#",
        "l1" + " " * 8 + "r1" + " " * 7 + "-",
        "l2" + " " * 8 + "r2" + " " * 7 + "-",
    ]


def test_a_single_full_width_write_composes_to_its_own_line():
    top, bottom = Split(Axis.Y, (1, 1)).rects(Rect(x=0, y=0, width=20, height=4))
    frame = Frame([_pane("top", top, "t0", "t1"), _pane("below", bottom, "u0", "u1")])
    composed = frame.compose(20, 4)
    pane_rows = frame.pane_layout("top").rows
    # The row's one write covers it whole: the composed row is the pane's
    # very line -- no splice ran -- and equals what splicing would build.
    assert composed.rows[0] is pane_rows[0]
    assert (
        composed.rows[0].segments
        == splice_row(Line(), pane_rows[0], 0, 20, 20).segments
    )
    assert [row.text for row in composed.rows] == ["t0", "t1", "u0", "u1"]


def test_a_pane_past_the_frame_edge_paints_nothing():
    frame = Frame(
        [
            _pane("visible", Rect(x=0, y=0, width=10, height=4), "r0", "r1", "r2", "r3"),
            _pane("popped", Rect(x=0, y=4, width=10, height=2), "n0", "n1"),
        ]
    )
    layout = frame.compose(10, 2)
    assert [row.text for row in layout.rows] == ["r0", "r1"]
    assert frame.table.rows == (
        (FrameSpan("visible", "b0", 0, 0, 10),),
        (FrameSpan("visible", "b0", 1, 0, 10),),
    )
    empty = Frame().compose(3, 2)
    assert [row.text for row in empty.rows] == ["", ""]
    assert Frame().rect is None and Frame().focused_pane is None


def test_splice_row_keeps_the_frame_row_a_grid_across_clusters():
    assert splice_row(
        Line.from_text("A\u26a0\ufe0fB     "), Line.from_text("#"), 6, 1, 10
    ).width == 10
    left = Line.from_text("Obj \u26a0\ufe0f").fill(8)
    right = Line.from_text("\u26a0\ufe0f Nature").fill(12)
    family = Line.from_text(
        "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466 fam"
    ).fill(12)
    for pane_row in (right, family):
        row = splice_row(splice_row(Line(), left, 0, 8, 20), pane_row, 8, 12, 20)
        assert row.width == 20
        assert cut_line(row, 0, 8).text == left.text
        assert cut_line(row, 8, 20).text == pane_row.text
    row = splice_row(splice_row(Line(), left, 0, 8, 20), right, 8, 12, 20)
    chrome = splice_row(row, Line.from_text("#"), 19, 1, 20)
    assert chrome.width == 20
    assert cut_line(chrome, 19, 20).text == "#"
    assert cut_line(chrome, 8, 19).text == cut_line(row, 8, 19).text


def test_splice_row_matches_the_three_cut_oracle():
    def slow(base: Line, line: Line, x: int, width: int, frame_width: int) -> Line:
        if x == 0 and width == frame_width:
            return line
        start_at, end_at, frame_at = index_bounds_at_columns(
            base.text, x, x + width, frame_width
        )
        return (
            slice_line(base, 0, start_at).fill(x)
            + cut_line(line, 0, width).fill(width)
            + slice_line(base, end_at, frame_at).fill(frame_width - x - width)
        )

    rows = [
        Line.from_text(""),
        Line.from_text("plain ascii row"),
        Line.from_text("Obj \u26a0\ufe0f"),
        Line.from_text("\u4e2d\u6587\u5b57"),
        Line.from_text("\u0301"),
        Line.from_text("e\u0301"),
        Line.from_text("a\tb"),
        Line.from_text("padded").fill(12),
    ]
    for base in rows:
        for line in rows:
            for frame_width in (0, 5, 12):
                for x in range(frame_width + 1):
                    for width in range(frame_width + 1):
                        assert splice_row(base, line, x, width, frame_width).segments == slow(
                            base, line, x, width, frame_width
                        ).segments


def test_inner_rect_subtracts_every_chrome_budget_and_bands_partition():
    pane = _pane("main", Rect(x=0, y=0, width=20, height=6), "content")
    assert pane.inner_rect == Rect(x=0, y=0, width=20, height=6)
    left = _marker_chrome("left", 2)
    right = _marker_chrome("right", 3)
    top = _marker_chrome("top", 1)
    bottom = _marker_chrome("bottom", 2)
    for chrome in (left, right, top, bottom):
        pane.add_chrome(chrome)
    inner = pane.inner_rect
    assert inner == Rect(x=2, y=1, width=15, height=3)
    assert pane.band(left).width + inner.width + pane.band(right).width == 20
    assert pane.band(top).height + inner.height + pane.band(bottom).height == 6
    for chrome in (left, right, top, bottom):
        band = pane.band(chrome)
        assert (
            inner.right <= band.x
            or band.right <= inner.x
            or inner.bottom <= band.y
            or band.bottom <= inner.y
        )
    assert pane.band(_marker_chrome("left", 1)) is None


def test_a_right_chrome_reserves_its_column_and_the_pane_rewraps_beside_it():
    left, right = Split(Axis.X, (1, 1)).rects(Rect(x=0, y=0, width=20, height=3))
    framed = _wrapping_pane("right", right, "0123456789")
    framed.add_chrome(_marker_chrome("right", 1))
    frame = Frame([_pane("left", left, "l0", "l1", "l2"), framed])
    layout = frame.compose(20, 3)
    assert [row.text for row in layout.rows] == [
        "l0" + " " * 8 + "012345678*",
        "l1" + " " * 8 + "9" + " " * 8 + "-",
        "l2" + " " * 8 + " " * 9 + "-",
    ]
    assert frame.table.rows[0] == (
        FrameSpan("left", "b0", 0, 0, 10),
        FrameSpan("right", "b0", 0, 10, 20),
    )
    assert frame.table.rows[2] == (
        FrameSpan("left", "b0", 2, 0, 10),
        FrameSpan("right", None, 0, 10, 20),
    )


def test_chromes_stack_in_order_and_the_divider_stacks_outermost():
    pane = _wrapping_pane("primary", Rect(x=0, y=0, width=10, height=2), "abcdefghij")
    pane.add_chrome(_marker_chrome("left", 1, "L"))
    pane.add_chrome(_marker_chrome("left", 1, "M"))
    assert [row.text for row in Frame([pane]).compose(10, 2).rows] == [
        "LMabcdefgh",
        "--ij      ",
    ]

    pane = _wrapping_pane("primary", Rect(x=0, y=0, width=20, height=3), "0123456789")
    pane.add_chrome(_marker_chrome("right", 1, "#"))
    left, right = pane.split(Axis.X, weights=(1, 1))
    left.add_chrome(_divider_chrome("right"))
    right.document.add(Rows("rst"))
    frame = Frame([pane])
    layout = frame.compose(20, 3)
    assert [row.text for row in layout.rows] == [
        "01234567# rst       ",
        "89      -           ",
        "        -           ",
    ]
    assert frame.region("primary") == Rect(x=0, y=0, width=8, height=3)


def test_chrome_budgets_clip_rather_than_empty_the_viewport():
    cases = [
        (3, (2, 2), "LLx", ["left"]),
        (4, (2, 2), "LLxR", ["left", "right"]),
        (2, (1, 1), "Lx", ["left"]),
        (1, (1, 1), "x", []),
    ]
    for width, sizes, expected_row, painted_edges in cases:
        painted: list[tuple[str, int]] = []
        pane = _pane("primary", Rect(x=0, y=0, width=width, height=1), "x")
        pane.add_chrome(_spy_chrome("left", sizes[0], painted, "L"))
        pane.add_chrome(_spy_chrome("right", sizes[1], painted, "R"))
        layout = Frame([pane]).compose(width, 1)
        assert layout.rows[0].text == expected_row
        assert [edge for edge, _ in painted] == painted_edges
        assert [length for _, length in painted] == [1] * len(painted_edges)
    pane = _pane("tall", Rect(x=0, y=0, width=4, height=2), "a", "b")
    pane.add_chrome(_marker_chrome("top", 5))
    pane.add_chrome(_marker_chrome("bottom", 5))
    assert [row.text for row in Frame([pane]).compose(4, 2).rows] == ["*   ", "b"]


def test_chrome_painters_read_the_pane_layout_and_the_strip_length():
    cases = [
        ("left", 3, ["abcde", "f", ""]),
        ("right", 3, ["abcde", "f", ""]),
        ("top", 6, ["abcdef", ""]),
        ("bottom", 6, ["abcdef", ""]),
    ]
    for edge, length, expected_rows in cases:
        seen: list[tuple[ScreenLayout, int]] = []

        def paint(layout: ScreenLayout, strip_length: int) -> list[Line]:
            seen.append((layout, strip_length))
            rows = strip_length if edge in ("left", "right") else 1
            width = 1 if edge in ("left", "right") else strip_length
            return [Line.from_text(" " * width) for _ in range(rows)]

        pane = _wrapping_pane("primary", Rect(x=0, y=0, width=6, height=3), "abcdef")
        pane.add_chrome(Chrome(edge, 1, paint))
        frame = Frame([pane])
        frame.compose(6, 3)
        assert seen == [(frame.pane_layout("primary"), length)]
        assert [row.text for row in frame.pane_layout("primary").rows] == expected_rows


def test_a_zero_size_chrome_is_a_no_op_seam():
    painted: list[tuple[str, int]] = []
    pane = _pane("primary", Rect(x=0, y=0, width=8, height=2), "r0", "r1")
    pane.add_chrome(_spy_chrome("right", 0, painted))
    frame = Frame([pane])
    composed = frame.compose(8, 2)
    assert painted == []
    assert [row.text for row in composed.rows] == ["r0", "r1"]
    assert composed is frame.pane_layout("primary")


def test_the_table_claims_chrome_columns_and_leaves_band_rows_unowned():
    pane = _pane("primary", Rect(x=0, y=0, width=6, height=3), "a", "b", "c")
    pane.add_chrome(_marker_chrome("right", 1))
    pane.add_chrome(_marker_chrome("bottom", 1))
    frame = Frame([pane])
    layout = frame.compose(6, 3)
    assert [row.text for row in layout.rows] == ["b    *", "c    -", "*     "]
    assert frame.table.rows == (
        (FrameSpan("primary", "b0", 1, 0, 6),),
        (FrameSpan("primary", "b0", 2, 0, 6),),
        (FrameSpan("primary", None, 0, 0, 6),),
    )
    span = frame.table.resolve(1, 5)
    assert (span.block_id, span.row_in_block) == ("b0", 2)
    assert frame.pane("primary").document.get(span.block_id) is pane.document.blocks()[0]


def test_chrome_rejects_an_unknown_edge():
    for edge in ("middle", "up", ""):
        with pytest.raises(ValueError):
            Chrome(edge, 1, lambda layout, length: [])


def test_chrome_rejects_an_unknown_scope():
    for scope in ("window", "pane ", ""):
        with pytest.raises(ValueError):
            Chrome("right", 1, lambda layout, length: [], scope=scope)


def test_a_body_scope_refuses_an_edge_that_owns_its_rows():
    for edge in ("top", "bottom"):
        with pytest.raises(ValueError):
            Chrome(edge, 1, lambda layout, length: [], scope="body")


def _windowed_pane() -> tuple[Pane, Chrome]:
    """A 6x4 pane with a one-row pinned header and footer: a 2-row window."""
    pane = _pane("primary", Rect(x=0, y=0, width=6, height=4), "a", "b")
    pane.document.add(Rows("head"), id="head", placement=Placement.TOP)
    pane.document.add(Rows("foot"), id="foot", placement=Placement.BOTTOM)
    chrome = Chrome(
        "right",
        1,
        lambda layout, length: [Line.from_text("-")] * length,
        scope="body",
    )
    pane.add_chrome(chrome)
    return pane, chrome


def test_a_body_band_is_the_window_and_nothing_without_one():
    pane, chrome = _windowed_pane()
    assert pane.band(chrome) is None  # no composition: no window to decorate
    frame = Frame([pane])
    frame.compose(6, 4)
    assert pane.band(chrome) == Rect(x=5, y=1, width=1, height=2)


def test_a_body_band_paints_the_window_and_its_length_is_the_window_height():
    seen: list[int] = []

    def paint(layout: ScreenLayout, length: int) -> list[Line]:
        seen.append(length)
        return [Line.from_text("-")] * length

    pane = _pane("primary", Rect(x=0, y=0, width=6, height=4), "a", "b")
    pane.document.add(Rows("head"), id="head", placement=Placement.TOP)
    pane.document.add(Rows("foot"), id="foot", placement=Placement.BOTTOM)
    pane.add_chrome(Chrome("right", 1, paint, scope="body"))
    layout = Frame([pane]).compose(6, 4)
    assert seen == [2]
    assert [row.text[-1] for row in layout.rows] == [" ", "-", "-", " "]


class _Tagger:
    def __init__(self, tag: str, seen: list[list[str]]) -> None:
        self.tag = tag
        self.seen = seen

    def paint(self, frame: Frame) -> ScreenLayout:
        layout = frame.layout
        self.seen.append([row.text for row in layout.rows])
        return replace(
            layout, rows=[Line.from_text(row.text + self.tag) for row in layout.rows]
        )


class _Passthrough:
    def paint(self, frame: Frame) -> ScreenLayout:
        return frame.layout


def test_overlays_paint_back_to_front_by_layer_keeping_registration_order():
    seen: list[list[str]] = []
    frame = _side_by_side()
    composed = frame.compose(20, 3)
    toast, background, later_background = (
        _Tagger("T", seen),
        _Tagger("B", seen),
        _Tagger("C", seen),
    )
    frame.add_overlay(toast, layer="toast")
    frame.add_overlay(background, layer="background")
    frame.add_overlay(later_background, layer="background")
    assert frame.overlays == (toast, background, later_background)
    frame.apply_overlays(composed)
    assert seen[0][0].startswith("l0")
    assert seen[1] == [row + "B" for row in seen[0]]
    assert seen[2] == [row + "C" for row in seen[1]]
    assert [row.text for row in frame.layout.rows] == [row + "BCT" for row in seen[0]]
    assert _Passthrough().paint(frame) is frame.layout
    with pytest.raises(ValueError):
        frame.add_overlay(_Passthrough(), layer="front")


def test_with_pane_rows_splices_a_rewrite_back_at_the_pane():
    left, right = Split(Axis.X, (1, 1)).rects(Rect(x=0, y=0, width=20, height=2))
    frame = Frame([_pane("left", left, "l0", "l1"), _pane("right", right, "r0", "r1")])
    composed = frame.compose(20, 2)
    painted = frame.with_pane_rows(
        "right", [Line.from_text("R0"), Line.from_text("R1"), Line.from_text("R2")]
    )
    assert [row.text for row in painted.rows] == [
        "l0" + " " * 8 + "R0" + " " * 8,
        "l1" + " " * 8 + "R1" + " " * 8,
    ]
    assert painted.rows[0] is not composed.rows[0]
    assert [row.text for row in frame.pane_layout("right").rows] == ["r0", "r1"]
    assert frame.pane_layout("nowhere") is None
    assert frame.with_pane_rows("nowhere", []) is frame.layout


def test_split_children_are_adopted_the_moment_they_exist():
    frame = Frame([Pane("primary", Rect(x=0, y=0, width=20, height=4), Viewport(Document()))])
    left, right = frame.panes[0].split(Axis.X)
    right.focus()
    assert frame.focused_pane is right
