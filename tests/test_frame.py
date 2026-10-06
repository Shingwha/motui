"""Tests for mocode_tui.core.frame: the rect algebra and the compositor.

``Rect`` is the screen's rectangle value; ``Split.rects`` tiles one with
the split's ratios (the last child taking the remainder the floors left,
``min_size`` the floor); ``Frame`` lays every pane's viewport out at the
pane's rectangle -- the chrome bands it carries subtract their budgets
first, clipped before they could empty the viewport -- splices the rows
and the granted strips into the frame rows, and builds the ownership
table a hit test routes through.  The overlay registry then paints over
the composed frame in registration order, a pane-relative edit spliced
back through the frame's own helpers.  A lone pane whose rectangle is
the whole frame composes to its pane's own layout -- pass-through, not
re-derivation.  A split records its division on the pane;
:meth:`~mocode_tui.core.frame.Pane.close` is its symmetric: a leaf leaves
its parent's tiling, the survivors re-divide the rectangle or the parent
collapses back to a leaf, and the divider of the gap that closed is
stripped by its ``Chrome.name`` mark.
"""

import pytest
from dataclasses import replace

from _doubles import Rows

from mocode_tui.core.block import Document
from mocode_tui.core.frame import (
    Chrome,
    Frame,
    FrameSpan,
    Pane,
    Rect,
    Split,
    splice_row,
)
from mocode_tui.core.lines import Line, cut_line
from mocode_tui.core.lines import Text
from mocode_tui.core.viewport import ScreenLayout, Viewport


def _doc(*texts: str) -> Document:
    """A one-block document rendering ``texts`` as its rows."""
    doc = Document()
    doc.add(Rows(*texts))
    return doc


def _pane(pane_id: str, rect: Rect, *texts: str) -> Pane:
    """A pane over a fresh one-block document of ``texts``."""
    return Pane(pane_id, rect, Viewport(_doc(*texts)))


def _wrapping_pane(pane_id: str, rect: Rect, *texts: str) -> Pane:
    """A pane over one wrapping ``Text`` block: content re-wraps at any width."""
    document = Document()
    document.add(Text("\n".join(texts)))
    return Pane(pane_id, rect, Viewport(document))


def _side_by_side() -> Frame:
    """A 20x3 frame over two documents, split down the middle."""
    left, right = Split("vertical", (1, 1)).rects(Rect(0, 0, 20, 3))
    return Frame(
        [
            _pane("left", left, "l0", "l1", "l2"),
            _pane("right", right, "r0", "r1", "r2"),
        ]
    )


# --- the rect -------------------------------------------------------------------


@pytest.mark.parametrize("size", [(-1, 24), (80, -1)])
def test_a_rect_size_is_never_negative(size: tuple[int, int]):
    with pytest.raises(ValueError):
        Rect(0, 0, *size)


# --- the split ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("orientation", "span", "ratios", "expected"),
    [
        # the ratios tile the span exactly: no gap, no overlap, the last
        # pane takes the odd cell a floor division leaves
        ("vertical", 40, (1, 1), [20, 20]),
        ("vertical", 41, (1, 1), [20, 21]),
        ("vertical", 10, (2, 1), [6, 4]),
        ("horizontal", 12, (1, 3), [3, 9]),
        ("vertical", 12, (1, 1, 1), [4, 4, 4]),
        # min_size floors a share below it; an unhostable span clips the tail
        ("vertical", 5, (1, 1), [2, 3]),
        ("vertical", 4, (3, 1), [3, 1]),
        ("vertical", 3, (3, 1), [2, 1]),
        ("vertical", 1, (1, 1), [1, 0]),
    ],
)
def test_split_ratios_tile_the_span_exactly(
    orientation: str, span: int, ratios: tuple[int, ...], expected: list[int]
):
    """The children partition the span; a divider is chrome, never a gap."""
    rect = Rect(0, 0, span, 3) if orientation == "vertical" else Rect(0, 0, 3, span)
    rects = Split(orientation, ratios, 1).rects(rect)
    sizes = [rect.width if orientation == "vertical" else rect.height for rect in rects]
    assert sizes == expected
    # the tiling is exact and never overlaps: origins follow the panes before them
    if orientation == "vertical":
        assert [rect.x for rect in rects] == [
            sum(expected[:index]) for index in range(len(expected))
        ]


def test_a_split_pane_keeps_its_document_and_chrome_in_the_first_child():
    """The pane before a split inherits; the ones after it open empty."""
    pane = _wrapping_pane("primary", Rect(0, 0, 20, 4), "kept")
    marker = _marker_chrome("right", 1, "#")
    pane.add_chrome(marker)
    before = pane.document
    left, right = pane.split("vertical", ratios=(2, 1))
    assert left.id == "primary" and right.id == "primary-1"
    assert left.viewport is pane.viewport and left.document is before
    assert left.chrome == (marker,)  # the registered chrome rides the split
    assert right.document is not before and right.document.blocks() == ()
    assert pane.division is not None and pane.children == (left, right)
    # the split pane is a container: the leaves compose, it composes nothing
    frame = Frame([pane])
    assert frame.compose(20, 4).rows[0].text.startswith("kept")  # the pane still lays out
    assert frame.panes == (left, right) and frame.pane("primary-1") is right
    assert frame.focused_pane is left


def test_the_divider_cell_is_the_pane_before_it_budgeted_as_chrome():
    """The pane before the gap holds the divider: one cell of its own rectangle."""
    pane = _pane("primary", Rect(0, 0, 10, 2), "01234", "VWXYZ")
    left, right = pane.split("vertical", ratios=(1, 1))
    assert (left.rect, right.rect) == (Rect(0, 0, 5, 2), Rect(5, 0, 5, 2))
    right.document.add(Rows("ABCD"))
    assert [row.text for row in Frame([pane]).compose(10, 2).rows] == [
        "01234ABCD ",
        "VWXYZ" + " " * 5,
    ]

    # The divider is chrome of the pane before the gap, never a gap of its
    # own: a host registering one on the first child takes that child's last
    # column, whose content lays out at four and is cut back from five.
    pane = _pane("primary", Rect(0, 0, 10, 2), "01234", "VWXYZ")
    left, right = pane.split("vertical", ratios=(1, 1))
    left.add_chrome(_divider_chrome("right", "#"))
    assert (left.rect, right.rect) == (Rect(0, 0, 5, 2), Rect(5, 0, 5, 2))
    right.document.add(Rows("ABCD"))
    assert [row.text for row in Frame([pane]).compose(10, 2).rows] == [
        "0123#ABCD ",
        "VWXY#" + " " * 5,
    ]


def test_a_split_the_caller_may_not_have_is_refused():
    pane = _pane("primary", Rect(0, 0, 20, 2), "a")
    for bad in ((), (0, 0), (-1, 1)):
        with pytest.raises(ValueError):
            pane.split("vertical", ratios=bad)
    with pytest.raises(ValueError):
        pane.split("diagonal")
    with pytest.raises(ValueError):
        pane.split("vertical", min_size=-1)
    pane.split("vertical")
    with pytest.raises(RuntimeError):
        pane.split("horizontal")


# --- the un-split ------------------------------------------------------------------


def test_closing_one_of_two_collapses_the_parent_and_strips_the_divider():
    """The un-split: the parent keeps its own id and rectangle and takes the
    survivor's window, and the divider of the gap that closed goes -- read
    off its mark, so a scrollbar sharing the divider's edge and size stays."""
    pane = _wrapping_pane("primary", Rect(0, 0, 20, 4), "0123456789")
    bar = _marker_chrome("right", 1, "#")  # a 1-cell right-edge chrome, no divider
    pane.add_chrome(bar)
    left, right = pane.split("vertical", ratios=(2, 1))
    left.add_chrome(_divider_chrome("right"))  # the divider of the new gap
    right.document.add(Rows("R"))
    frame = Frame([pane])
    assert left.chrome == (bar, left.chrome[1])  # the bar, then the divider
    assert left.chrome[1].name == "separator"
    right.focus()
    right.close()
    assert left.chrome == (bar,)  # the divider went, the bar stayed
    assert pane.chrome is left.chrome
    assert pane.division is None and pane.children == ()
    assert pane.rect == Rect(0, 0, 20, 4)  # the parent kept its own rectangle
    assert pane.viewport is left.viewport  # and took the survivor's window
    assert frame.panes == (pane,)  # the parent itself is the leaf now
    assert frame.focused_pane is pane  # the close handed the focus back to it
    assert frame.pane("primary-1") is None  # the closed child's id died with it
    # the bar's column is the only chrome left, so the pane re-wraps at nineteen
    assert [row.text for row in frame.compose(20, 4).rows] == [
        "0123456789         #",
        "                   -",
        "                   -",
        "                   -",
    ]


def test_the_collapsed_parent_keeps_its_id_and_a_later_childs_dies():
    """The id rule on a collapse onto a later child: the parent's id
    survives, the survivor's own dies with the split -- and a focus keyed
    on the dead id falls to the pane that took its rectangle, not to the
    frame's first leaf."""
    other = _pane("other", Rect(0, 0, 20, 3), "o")  # a second root, painted first
    root = _pane("primary", Rect(0, 0, 30, 3), "a")
    frame = Frame([other, root])
    panes = root.split("vertical", ratios=(1, 1, 1))
    panes[2].focus()
    panes[0].close()  # a re-divide: the focus rides its own pane
    assert frame.focused_pane is panes[2]
    panes[1].close()  # a collapse onto the later child
    assert [pane.id for pane in frame.panes] == ["other", "primary"]
    assert frame.pane("primary-2") is None  # the survivor's own id died
    assert frame.pane("primary") is root  # the very pane object, not a rebuilt one
    assert root.viewport is panes[2].viewport  # its window taken
    assert frame.focused_pane is root  # the focus re-keyed to the collapsed parent


@pytest.mark.parametrize("closed", [0, 1, 2])
def test_closing_one_of_three_redivides_over_the_survivors(closed: int):
    """With siblings left the parent re-divides its rectangle over them, the
    ratios trimmed in order; the divider of a gap that survives rides the
    pane before it, and the survivors of a middle close abut."""
    root = Pane("primary", Rect(0, 0, 30, 3), Viewport(Document()))
    frame = Frame([root])
    panes = root.split("vertical", ratios=(1, 1, 1))
    for before in panes[:-1]:  # the driver registers one per gap
        before.add_chrome(_divider_chrome("right"))
    for index, pane in enumerate(panes):
        pane.document.add(Rows(f"p{index}"))
    panes[closed].close()
    survivors = tuple(
        pane for index, pane in enumerate(panes) if index != closed
    )
    assert frame.panes == survivors
    assert root.division.ratios == (1, 1)  # trimmed in order, the weights kept
    assert [pane.rect for pane in survivors] == [
        Rect(0, 0, 15, 3),
        Rect(15, 0, 15, 3),
    ]
    # one divider for the gap between the first and second child that
    # survives, none for the gap that closed
    held = {0: [1, 0], 1: [0, 0], 2: [1, 0]}[closed]
    assert [
        len([chrome for chrome in pane.chrome if chrome.name == "separator"])
        for pane in survivors
    ] == held
    layout = frame.compose(30, 3)
    assert frame.table.rows[0] == (
        FrameSpan(survivors[0].id, "b0", 0, 0, 15),
        FrameSpan(survivors[1].id, "b0", 0, 15, 30),
    )
    first = {0: "p1", 1: "p0", 2: "p0"}[closed]
    second = {0: "p2", 1: "p2", 2: "p1"}[closed]
    # the divider cell is the pane before it: three blanks stand between
    # the two survivors' rows when one survives, and the two panes abut
    assert layout.rows[0].text == first + " " * 13 + second + " " * 13
    assert [row.text for row in layout.rows[1:]] == [" " * 30] * 2


@pytest.mark.parametrize("closed", [0, 1, 2])
def test_a_focused_close_hands_focus_to_the_pane_that_took_its_place(closed: int):
    """Focus falls to the survivor at the closed child's index -- or to the
    last survivor, when the closed child was the last."""
    root = _pane("primary", Rect(0, 0, 30, 3))
    frame = Frame([root])
    panes = root.split("vertical", ratios=(1, 1, 1))
    panes[closed].focus()
    panes[closed].close()
    survivors = [pane for index, pane in enumerate(panes) if index != closed]
    assert frame.focused_pane is survivors[min(closed, len(survivors) - 1)]


def test_close_refuses_a_root_a_container_and_a_second_close():
    frame = Frame([_pane("primary", Rect(0, 0, 20, 3), "a")])
    root = frame.panes[0]
    with pytest.raises(RuntimeError):
        root.close()  # a root: no split holds it
    left, right = root.split("vertical")
    with pytest.raises(RuntimeError):
        root.close()  # a container: a close is a leaf's
    left.close()  # the collapse leaves the parent a leaf named "primary"
    with pytest.raises(RuntimeError):
        left.close()  # a second close: the pane left the tiling already
    with pytest.raises(RuntimeError):
        _pane("loose", Rect(0, 0, 4, 1), "x").close()  # held by no frame
    assert frame.panes == (root,)


@pytest.mark.parametrize("span", [41, 23, 17, 7])
def test_the_survivors_tile_the_span_exactly_after_a_close(span: int):
    """The re-division keeps the tiling exact at odd sizes: no hole, no
    overlap, the last survivor ending at the span."""
    root = _pane("primary", Rect(0, 0, span, 3))
    frame = Frame([root])
    panes = root.split("vertical", ratios=(2, 1, 1))
    panes[1].close()
    first, second = frame.panes
    assert first.rect.x == 0 and first.rect.height == 3
    assert second.rect.x == first.rect.right and second.rect.right == span
    assert second.rect.height == 3
    assert frame.rect == Rect(0, 0, span, 3)


def test_closing_the_last_of_a_stacked_split_strips_the_bottom_divider():
    """The strip is the split orientation's edge: bottom for a horizontal
    one, and the collapsed parent takes the pane area whole."""
    pane = _pane("primary", Rect(0, 0, 10, 6), "t", "b")
    top, bottom = pane.split("horizontal", ratios=(1, 1))
    top.add_chrome(_divider_chrome("bottom"))
    frame = Frame([pane])
    assert (top.rect, bottom.rect) == (Rect(0, 0, 10, 3), Rect(0, 3, 10, 3))
    assert [chrome.edge for chrome in top.chrome] == ["bottom"]
    bottom.close()
    assert top.chrome == ()  # the divider of the gap that closed went
    assert pane.chrome is top.chrome and pane.division is None
    assert pane.rect == Rect(0, 0, 10, 6)
    assert [row.text for row in frame.compose(10, 6).rows] == [
        "t",
        "b",
        "",
        "",
        "",
        "",
    ]


def test_closing_the_only_child_of_a_one_child_split_restores_the_leaf():
    """A degenerate division: the parent resumes the leaf it was, its own
    window and rectangle intact."""
    pane = _pane("primary", Rect(0, 0, 12, 2), "a", "b")
    frame = Frame([pane])
    (only,) = pane.split("vertical", ratios=(1,))
    assert only.chrome == ()  # a sole child divides no gap
    only.close()
    assert pane.division is None and pane.children == ()
    assert frame.panes == (pane,) and frame.focused_pane is pane
    assert [row.text for row in frame.compose(12, 2).rows] == ["a", "b"]


def test_closing_inside_a_nested_split_keeps_the_outer_tree():
    """A close rewrites the subtree it sits in: the outer division, the
    sibling's rectangle and the nested parent's own rectangle stand."""
    root = _pane("primary", Rect(0, 0, 40, 8))
    frame = Frame([root])
    left, right = root.split("vertical", ratios=(1, 1))
    top, bottom = right.split("horizontal", ratios=(1, 1))
    frame.retile(Rect(0, 0, 40, 8))
    bottom.close()
    assert right.division is None and right.children == ()
    assert right.viewport is top.viewport
    assert right.rect == Rect(20, 0, 20, 8)  # the nested parent kept its rectangle
    assert root.division.ratios == (1, 1)  # and the outer division stands
    assert [pane.rect for pane in frame.panes] == [
        Rect(0, 0, 20, 8),
        Rect(20, 0, 20, 8),
    ]


def test_retile_re_divides_the_tree_and_keeps_every_panes_state():
    """A resize re-divides the recorded split: same panes, new rectangles."""
    frame = Frame([_pane("primary", Rect(0, 0, 0, 0), "r0")])
    left, right = frame.panes[0].split("vertical", ratios=(1, 1))
    spy = _spy_chrome("right", 1, [], "s")
    left.add_chrome(spy)
    frame.retile(Rect(0, 0, 40, 4))
    assert (left.rect, right.rect) == (Rect(0, 0, 20, 4), Rect(20, 0, 20, 4))
    assert frame.panes == (left, right)  # the very objects, not rebuilt ones
    assert left.chrome == (spy,)  # the registration rides the retile in place

    frame.retile(Rect(0, 0, 20, 4))  # the terminal resized: re-divide the same tree
    assert (left.rect, right.rect) == (Rect(0, 0, 10, 4), Rect(10, 0, 10, 4))
    assert left.chrome == (spy,) and frame.panes == (left, right)


def test_a_nested_split_re_divides_both_axes():
    frame = Frame([_pane("primary", Rect(0, 0, 0, 0), "a")])
    left, right = frame.panes[0].split("vertical", ratios=(1, 1))
    top, bottom = right.split("horizontal", ratios=(1, 1))
    frame.retile(Rect(0, 0, 40, 8))
    assert [pane.rect for pane in frame.panes] == [
        Rect(0, 0, 20, 8),
        Rect(20, 0, 20, 4),
        Rect(20, 4, 20, 4),
    ]
    assert frame.focused_pane is left is frame.panes[0]


def test_focus_names_the_pane_input_routes_to():
    frame = _side_by_side()
    frame.focus("right")
    assert frame.focused_pane is frame.panes[1]
    frame.focus(frame.panes[0])
    assert frame.focused_pane is frame.panes[0]
    with pytest.raises(ValueError):
        frame.focus("nowhere")
    # a pane that is no longer a leaf resolves through the child that
    # inherited its id, never silently to the first pane
    frame = Frame([_pane("primary", Rect(0, 0, 0, 0), "a")])
    frame.focus("primary")
    first, second = frame.panes[0].split("vertical")
    frame.retile(Rect(0, 0, 20, 4))
    assert frame.focused_pane is first  # the id lived on, on the first child
    frame.focus("primary-1")
    assert frame.focused_pane is second
    first.focus()
    assert frame.focused_pane is first
    with pytest.raises(RuntimeError):
        _pane("loose", Rect(0, 0, 4, 1), "x").focus()  # held by no frame


def test_the_band_composes_beneath_the_panes_and_joins_the_ownership_table():
    """A band is a region of the frame: painted, routable, never a content pane."""
    frame = Frame([_pane("primary", Rect(0, 0, 0, 0), "l0", "l1", "l2")])
    left, right = frame.panes[0].split("vertical", ratios=(1, 1))
    right.document.add(Rows("r0", "r1", "r2"))
    band = Pane("band", Rect(0, 3, 20, 1), Viewport(_doc("f0")))
    frame.set_band(band)
    frame.retile(Rect(0, 0, 20, 3), band=Rect(0, 3, 20, 1))
    frame.compose(20, 4)
    assert [row.text for row in frame.layout.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
        "f0",
    ]
    assert frame.panes == (left, right)  # the band is not a content pane
    assert frame.band is band and frame.pane("band") is band
    assert frame.focused_pane is left  # and it never holds focus
    assert frame.table.rows[3] == (FrameSpan("band", "b0", 0, 0, 20),)
    assert frame.rect == Rect(0, 0, 20, 4)  # the band belongs to the frame
    assert frame.region("primary") == Rect(0, 0, 10, 3)
    assert frame.region("band") == Rect(0, 3, 20, 1)
    assert [row.text for row in frame.pane_layout("band").rows] == ["f0"]
    with pytest.raises(ValueError):
        frame.focus("band")


def test_a_split_grows_the_pane_area_the_band_takes_back():
    """The band's rows sit beneath the pane area, which shrinks by exactly them."""
    pane = _pane("primary", Rect(0, 0, 8, 2), "r0", "r1")
    frame = Frame([pane], band=Pane("band", Rect(0, 2, 8, 1), Viewport(_doc("f"))))
    frame.retile(Rect(0, 0, 8, 1), band=Rect(0, 1, 8, 1))
    # two regions: the frame is no longer one document's layout, and the pane's
    # own layout still holds the rows it laid out
    assert frame.compose(8, 2) is not frame.pane_layout("primary")
    assert [row.text for row in frame.layout.rows] == ["r1", "f"]
    assert [row.text for row in frame.pane_layout("primary").rows] == ["r1"]
    assert frame.region("primary") == Rect(0, 0, 8, 1)
    assert frame.region("band") == Rect(0, 1, 8, 1)
    assert frame.region("nowhere") is None


# --- composition ---------------------------------------------------------------


def test_a_two_pane_frame_composes_both_documents_side_by_side():
    frame = _side_by_side()
    layout = frame.compose(20, 3)
    assert [row.text for row in layout.rows] == [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
    ]
    assert frame.table.rows == (
        (FrameSpan("left", "b0", 0, 0, 10), FrameSpan("right", "b0", 0, 10, 20)),
        (FrameSpan("left", "b0", 1, 0, 10), FrameSpan("right", "b0", 1, 10, 20)),
        (FrameSpan("left", "b0", 2, 0, 10), FrameSpan("right", "b0", 2, 10, 20)),
    )


def test_a_four_pane_nested_frame_composes_every_quadrant():
    left, right = Split("vertical", (1, 1)).rects(Rect(0, 0, 20, 4))
    lt, lb = Split("horizontal", (1, 1)).rects(left)
    rt, rb = Split("horizontal", (1, 1)).rects(right)
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
    assert composed is frame.pane_layout("primary")
    assert composed.rows is frame.pane_layout("primary").rows
    assert composed.rows == [Line.from_text(t) for t in ("r1", "r2", "r3", "r4")]
    assert composed.row_blocks == [("b0", 1), ("b0", 2), ("b0", 3), ("b0", 4)]
    assert frame.table.rows == tuple(
        (FrameSpan("primary", "b0", row, 0, 80),) for row in (1, 2, 3, 4)
    )


def test_a_full_width_pane_passes_its_rows_through_the_frame_rows():
    """Stacked panes keep their rows unchanged: no slicing, no padding."""
    top, bottom = Split("horizontal", (1, 1)).rects(Rect(0, 0, 40, 4))
    frame = Frame([_pane("top", top, "t0", "t1"), _pane("below", bottom, "u0", "u1")])
    layout = frame.compose(40, 4)
    assert [row.text for row in layout.rows] == ["t0", "t1", "u0", "u1"]
    assert layout.rows[0] is frame.pane_layout("top").rows[0]
    assert layout.rows[1] is frame.pane_layout("top").rows[1]
    assert layout.rows[2] is frame.pane_layout("below").rows[0]
    assert layout.rows[3] is frame.pane_layout("below").rows[1]


def test_a_pane_composes_at_its_rect_not_the_frame_origin():
    frame = Frame([_pane("corner", Rect(2, 1, 8, 2), "x")])
    layout = frame.compose(12, 4)
    assert [row.text for row in layout.rows] == ["", "  x" + " " * 9, " " * 12, ""]
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


# --- the frame row is a grid -----------------------------------------------------


def test_splice_row_tiles_a_frame_row_across_cluster_boundaries():
    # Red before the fix: the pieces were cut by a per-character walk, so on
    # a row carrying VS16 emoji the middle piece overran its window and the
    # composed row came back wider than the frame -- splice_row of a
    # one-column window into a 180-column frame composed 181 columns, and
    # every region after it slid one column left of its own rectangle.
    assert splice_row(Line.from_text("A\u26a0\ufe0fB     "), Line.from_text("#"), 6, 1, 10).width == 10
    # A region's own row reads back exactly as its viewport laid it out, at
    # its own columns, over a base that already carries a neighbour's
    # content: the pane's first column is the same column on every row.
    left = Line.from_text("Obj \u26a0\ufe0f").pad_to(8)
    right = Line.from_text("\u26a0\ufe0f Nature").pad_to(12)
    family = Line.from_text("\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466 fam").pad_to(12)
    for pane_row in (right, family):
        row = splice_row(splice_row(Line(), left, 0, 8, 20), pane_row, 8, 12, 20)
        assert row.width == 20
        assert cut_line(row, 0, 8).text == left.text  # the neighbour keeps its cells
        assert cut_line(row, 8, 20).text == pane_row.text
    # A granted chrome strip lands inside its own column and moves nothing:
    # the row stays a grid and the region beside it keeps its cells.
    row = splice_row(splice_row(Line(), left, 0, 8, 20), right, 8, 12, 20)
    chrome = splice_row(row, Line.from_text("#"), 19, 1, 20)
    assert chrome.width == 20
    assert cut_line(chrome, 19, 20).text == "#"
    assert cut_line(chrome, 8, 19).text == cut_line(row, 8, 19).text


def test_splice_row_resolves_its_base_cuts_in_one_walk():
    # The splice resolves the base row's three cut points in one call, so the
    # row's prefix is walked once.  What must not move is the result: every
    # piece is still the one cut_line of that range hands back -- a cut *is*
    # slice_line at resolved indices -- over every base shape, every window
    # position, and every cluster the corpus carries.
    rows = [
        "Obj \u26a0\ufe0f",
        "caf\u00e9 \U0001F600 \u4e2d\u6587",
        "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8",
        "x\U0001F468\u200D\U0001F469\u200dy",
        "a\tb\tc",
        "plain ascii row",
    ]
    for text in rows:
        for base_width in (0, 1, 5, 12, 20):
            base = Line.from_text(text).pad_to(base_width)
            for x in range(0, base_width + 1):
                for width in range(1, base_width - x + 1):
                    frame_width = base_width
                    if x == 0 and width == frame_width:
                        continue
                    window = Line.from_text("##")
                    row = splice_row(base, window, x, width, frame_width)
                    assert row == (
                        cut_line(base, 0, x).pad_to(x)
                        + cut_line(window, 0, width).pad_to(width)
                        + cut_line(base, x + width, frame_width).pad_to(
                            frame_width - x - width
                        )
                    )


# --- chrome budgets ---------------------------------------------------------------


def _marker_chrome(edge: str, size: int, mark: str = "*") -> Chrome:
    """A chrome double: ``mark`` fills the strip's first cell, ``-`` the rest.

    The paint protocol in one function -- one row per strip cell, each
    exactly the band's width: a left/right band returns the pane's height in
    rows of ``size`` columns, a top/bottom one ``size`` rows of the pane's
    width (the ``length`` the compositor hands the painter).
    """

    def paint(layout: ScreenLayout, length: int) -> list[Line]:
        rows = length if edge in ("left", "right") else size
        width = size if edge in ("left", "right") else length
        return [
            Line.from_text((mark if index == 0 else "-").ljust(width)[:width])
            for index in range(rows)
        ]

    return Chrome(edge, size, paint)


def _divider_chrome(edge: str, mark: str = " ") -> Chrome:
    """A stand-in for the divider the driver registers: a 1-cell band.

    The driver's themed ``_Separator`` speaks both kernel mechanisms this
    file exercises -- negotiation stacks the band name outermost, and a
    close strips it by that name -- so a test registers its mark here, with
    a blank default that paints like the divider without asserting on it.
    """

    def paint(layout: ScreenLayout, length: int) -> list[Line]:
        rows = length if edge in ("left", "right") else 1
        width = 1 if edge in ("left", "right") else length
        return [Line.from_text(mark * width) for _ in range(rows)]

    return Chrome(edge, 1, paint, name="separator")


def _spy_chrome(
    edge: str, size: int, painted: list[tuple[str, int]], mark: str = " "
) -> Chrome:
    """A chrome double: records ``(edge, length)`` and paints a filled band."""

    def paint(layout: ScreenLayout, length: int) -> list[Line]:
        painted.append((edge, length))
        rows = length if edge in ("left", "right") else size
        width = size if edge in ("left", "right") else length
        return [Line.from_text((mark * width)[:width]) for _ in range(rows)]

    return Chrome(edge, size, paint)


def test_a_right_chrome_reserves_its_column_and_the_pane_rewraps_beside_it():
    left, right = Split("vertical", (1, 1)).rects(Rect(0, 0, 20, 3))
    framed = _wrapping_pane("right", right, "0123456789")
    framed.add_chrome(_marker_chrome("right", 1))
    frame = Frame([_pane("left", left, "l0", "l1", "l2"), framed])
    layout = frame.compose(20, 3)
    # one column of the pane goes to the strip; the content re-wraps at nine
    assert [row.text for row in layout.rows] == [
        "l0" + " " * 8 + "012345678*",
        "l1" + " " * 8 + "9" + " " * 8 + "-",
        "l2" + " " * 8 + " " * 9 + "-",
    ]
    # the strip column rides the pane's own row claim, address unchanged
    assert frame.table.rows == (
        (FrameSpan("left", "b0", 0, 0, 10), FrameSpan("right", "b0", 0, 10, 20)),
        (FrameSpan("left", "b0", 1, 0, 10), FrameSpan("right", "b0", 1, 10, 20)),
        (FrameSpan("left", "b0", 2, 0, 10), FrameSpan("right", None, 0, 10, 20)),
    )


def test_chromes_on_one_edge_stack_side_by_side_and_add_their_budgets():
    pane = _wrapping_pane("primary", Rect(0, 0, 10, 2), "abcdefghij")
    pane.add_chrome(_marker_chrome("left", 1, "L"))
    pane.add_chrome(_marker_chrome("left", 1, "M"))
    layout = Frame([pane]).compose(10, 2)
    # the outermost column is the first registered; the viewport wraps at 8
    # (a spliced band pads its row out to the frame width, as a pane splice does)
    assert [row.text for row in layout.rows] == ["LMabcdefgh", "--ij      "]


def test_the_divider_stacks_outside_a_chrome_registered_before_the_split():
    """The demo's construction order -- a scrollbar band registered on the
    pane, then the split: the divider is the pane's outermost column and the
    band sits inside it, whatever the registration order was."""
    pane = _wrapping_pane("primary", Rect(0, 0, 20, 3), "0123456789")
    pane.add_chrome(_marker_chrome("right", 1, "#"))  # before the split
    left, right = pane.split("vertical", ratios=(1, 1))
    left.add_chrome(_divider_chrome("right"))  # the driver's divider, after it
    right.document.add(Rows("rst"))
    frame = Frame([pane])
    layout = frame.compose(20, 3)
    # the divider cell is the pane's last column (9, blank), the marker the
    # one before it (8); the viewport wraps at eight
    assert [row.text for row in layout.rows] == [
        "01234567# rst       ",
        "89      -           ",
        "        -           ",
    ]
    assert frame.region("primary") == Rect(0, 0, 8, 3)  # both bands subtracted
    assert (left.rect, right.rect) == (Rect(0, 0, 10, 3), Rect(10, 0, 10, 3))


def test_opposite_edges_both_subtract_from_the_pane():
    painted: list[tuple[str, int]] = []
    pane = _wrapping_pane("primary", Rect(0, 0, 10, 1), "0123456789")
    pane.add_chrome(_spy_chrome("left", 3, painted, "L"))
    pane.add_chrome(_spy_chrome("right", 2, painted, "R"))
    layout = Frame([pane]).compose(10, 1)
    # 3 columns left and 2 right leave 5: the window shows the wrap's tail
    assert [row.text for row in layout.rows] == ["LLL56789RR"]
    assert painted == [("left", 1), ("right", 1)]  # strips run the pane height


@pytest.mark.parametrize(
    ("width", "sizes", "expected_row", "painted_edges"),
    [
        (3, (2, 2), "LLx", ["left"]),  # the left budget wins; the right is clipped
        (4, (2, 2), "LLxR", ["left", "right"]),  # both fit, one cell of viewport left
        (2, (1, 1), "Lx", ["left"]),  # one cell of budget on the whole axis
        (1, (1, 1), "x", []),  # a pane too small to host chrome budgets nothing
    ],
)
def test_chrome_budgets_clip_rather_than_shrink_the_viewport_below_one_cell(
    width: int, sizes: tuple[int, int], expected_row: str, painted_edges: list[str]
):
    painted: list[tuple[str, int]] = []
    pane = _pane("primary", Rect(0, 0, width, 1), "x")
    pane.add_chrome(_spy_chrome("left", sizes[0], painted, "L"))
    pane.add_chrome(_spy_chrome("right", sizes[1], painted, "R"))
    layout = Frame([pane]).compose(width, 1)
    assert layout.rows[0].text == expected_row
    # a clipped-away chrome is never painted, and a strip runs the pane height
    assert [edge for edge, _ in painted] == painted_edges
    assert [length for _, length in painted] == [1] * len(painted_edges)


def test_a_budget_that_would_empty_the_pane_height_is_clipped():
    pane = _pane("primary", Rect(0, 0, 4, 2), "a", "b")
    pane.add_chrome(_marker_chrome("top", 5))
    pane.add_chrome(_marker_chrome("bottom", 5))
    layout = Frame([pane]).compose(4, 2)
    # the top band takes the one row the height can spare; the bottom is clipped
    assert [row.text for row in layout.rows] == ["*   ", "b"]


def test_a_zero_size_chrome_is_a_no_op_seam_that_is_never_painted():
    painted: list[tuple[str, int]] = []
    pane = _pane("primary", Rect(0, 0, 8, 2), "r0", "r1")
    pane.add_chrome(_spy_chrome("right", 0, painted))
    frame = Frame([pane])
    composed = frame.compose(8, 2)
    assert painted == []  # nothing budgeted, nothing painted
    assert [row.text for row in composed.rows] == ["r0", "r1"]
    assert composed is frame.pane_layout("primary")  # the pass-through holds


def test_a_budgeted_chrome_on_a_full_frame_pane_composes_spliced_rows():
    pane = _pane("primary", Rect(0, 0, 8, 2), "r0", "r1")
    pane.add_chrome(_marker_chrome("right", 1))
    frame = Frame([pane])
    composed = frame.compose(8, 2)
    assert composed is not frame.pane_layout("primary")  # strips moved the frame rows
    assert [row.text for row in composed.rows] == [
        "r0" + " " * 5 + "*",
        "r1" + " " * 5 + "-",
    ]


@pytest.mark.parametrize(
    ("edge", "length", "expected_rows"),
    [
        ("left", 3, ["abcde", "f", ""]),  # a left/right band buys width
        ("right", 3, ["abcde", "f", ""]),
        ("top", 6, ["abcdef", ""]),  # a top/bottom band buys height only
        ("bottom", 6, ["abcdef", ""]),
    ],
)
def test_the_chrome_paints_from_the_pane_layout_and_the_strip_length(
    edge: str, length: int, expected_rows: list[str]
):
    seen: list[tuple[ScreenLayout, int]] = []

    def paint(layout: ScreenLayout, strip_length: int) -> list[Line]:
        seen.append((layout, strip_length))
        rows = strip_length if edge in ("left", "right") else 1
        width = 1 if edge in ("left", "right") else strip_length
        return [Line.from_text(" " * width) for _ in range(rows)]

    pane = _wrapping_pane("primary", Rect(0, 0, 6, 3), "abcdef")
    pane.add_chrome(Chrome(edge, 1, paint))
    frame = Frame([pane])
    frame.compose(6, 3)
    # the painter reads the pane's own layout and the strip's length: the
    # pane's height for a left/right band, its width for a top/bottom one
    assert seen == [(frame.pane_layout("primary"), length)]
    # and the pane was laid out at its inner rect: five columns wide, wrapped
    assert [row.text for row in frame.pane_layout("primary").rows] == expected_rows


def test_the_table_claims_the_chrome_columns_and_leaves_band_rows_unowned():
    pane = _pane("primary", Rect(0, 0, 6, 3), "a", "b", "c")
    pane.add_chrome(_marker_chrome("right", 1))
    pane.add_chrome(_marker_chrome("bottom", 1))
    frame = Frame([pane])
    layout = frame.compose(6, 3)
    assert [row.text for row in layout.rows] == ["b    *", "c    -", "*     "]
    assert frame.table.rows == (
        (FrameSpan("primary", "b0", 1, 0, 6),),  # the strip column rides along
        (FrameSpan("primary", "b0", 2, 0, 6),),
        (FrameSpan("primary", None, 0, 0, 6),),  # the bottom band: claimed, unowned
    )


@pytest.mark.parametrize("edge", ["middle", "up", ""])
def test_chrome_rejects_an_edge_it_does_not_know(edge: str):
    with pytest.raises(ValueError):
        Chrome(edge, 1, lambda layout, length: [])


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


# --- the overlay registry ---------------------------------------------------------


class _Tagger:
    """An overlay double: appends its tag to every row, recording what it saw."""

    def __init__(self, tag: str, seen: list[list[str]]) -> None:
        self._tag = tag
        self._seen = seen

    def paint(self, frame: Frame) -> ScreenLayout:
        layout = frame.layout
        self._seen.append([row.text for row in layout.rows])
        return replace(
            layout,
            rows=[Line.from_text(row.text + self._tag) for row in layout.rows],
        )


class _Passthrough:
    """An overlay double that hands the rows back exactly as they are."""

    def paint(self, frame: Frame) -> ScreenLayout:
        return frame.layout


def test_an_empty_registry_hands_the_composed_layout_through():
    frame = _side_by_side()
    composed = frame.compose(20, 3)
    assert frame.overlays == ()
    assert frame.apply_overlays(composed) is composed


def test_overlays_paint_in_registration_order_each_over_the_last():
    seen: list[list[str]] = []
    frame = _side_by_side()
    composed = frame.compose(20, 3)
    first, second = _Tagger("A", seen), _Tagger("B", seen)
    frame.add_overlay(first)
    frame.add_overlay(second)
    assert frame.overlays == (first, second)
    painted = frame.apply_overlays(composed)
    plain = [
        "l0" + " " * 8 + "r0" + " " * 8,
        "l1" + " " * 8 + "r1" + " " * 8,
        "l2" + " " * 8 + "r2" + " " * 8,
    ]
    # the second overlay composes over the rows the first one painted
    assert seen == [plain, [row + "A" for row in plain]]
    assert [row.text for row in painted.rows] == [row + "AB" for row in plain]


def test_an_overlay_that_rewrites_nothing_leaves_the_layout_alone():
    frame = _side_by_side()
    composed = frame.compose(20, 3)
    frame.add_overlay(_Passthrough())
    assert frame.apply_overlays(composed) is composed


def test_pane_layout_hands_back_the_panes_own_layout():
    frame = _side_by_side()
    frame.compose(20, 3)
    left, right = frame.pane_layout("left"), frame.pane_layout("right")
    assert left is not right
    assert [row.text for row in left.rows] == ["l0", "l1", "l2"]
    assert [row.text for row in right.rows] == ["r0", "r1", "r2"]
    assert frame.pane_layout("nowhere") is None


def test_a_pane_relative_overlay_splices_its_rewrite_back_at_the_pane():
    left, right = Split("vertical", (1, 1)).rects(Rect(0, 0, 20, 2))
    frame = Frame([_pane("left", left, "l0", "l1"), _pane("right", right, "r0", "r1")])
    composed = frame.compose(20, 2)
    painted = frame.with_pane_rows(
        "right", [Line.from_text("R0"), Line.from_text("R1")]
    )
    assert [row.text for row in painted.rows] == [
        "l0" + " " * 8 + "R0" + " " * 8,
        "l1" + " " * 8 + "R1" + " " * 8,
    ]
    assert painted.rows[0] is not composed.rows[0]  # the pane's rows moved ...
    assert painted.rows[1] is not composed.rows[1]
    assert painted.rows[0] is not frame.pane_layout("right").rows[0]  # ... not in place


def test_a_full_frame_panes_rewritten_rows_pass_through_unchanged():
    pane = _pane("primary", Rect(0, 0, 8, 2), "r0", "r1")
    frame = Frame([pane])
    composed = frame.compose(8, 2)
    assert frame.with_pane_rows("primary", composed.rows) is composed
    marked = frame.with_pane_rows(
        "primary", [Line.from_text("R0"), Line.from_text("R1")]
    )
    assert [row.text for row in marked.rows] == ["R0", "R1"]

def test_split_children_are_adopted_the_moment_they_exist():
    frame = Frame([Pane("primary", Rect(0, 0, 20, 4), Viewport(Document()))])
    left, right = frame.panes[0].split("vertical")
    # Without adoption at split time, a split after the frame's first
    # composition leaves the children focusable by no frame (the retile
    # no-ops on an unchanged tiling and never adopts them).
    right.focus()
    assert frame.focused_pane is right
