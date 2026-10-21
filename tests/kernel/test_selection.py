"""Document-space selection: the value, the highlight overlay and text
extraction across blocks.

A Selection is a pair of (block, row, column) addresses kept as given;
direction is normalized where document order is known.  ``highlight``
restyles only the addressed cells of a laid-out frame, and ``extract``
returns the same text regardless of viewport position.
"""

from __future__ import annotations

import pytest

from motui.kernel.block import Document
from motui.kernel.lines import Line, Segment
from motui.kernel.selection import Selection, extract, highlight
from motui.kernel.style import Style
from motui.kernel.viewport import ScreenLayout, Viewport
from tests.testing import Rows

SELECTION = Style(reverse=True)
ACCENTED = Style(fg="#abcdef")
BOLDED = Style(fg="#123456", bold=True)


def _layout(rows, owners, order) -> ScreenLayout:
    return ScreenLayout(
        rows=[Line([Segment(text, style) for text, style in row]) for row in rows],
        body_rows=[],
        row_blocks=owners,
        block_order=order,
    )


def _marked(layout: ScreenLayout) -> list[str]:
    return [
        "".join(segment.text for segment in row.segments if segment.style.reverse)
        for row in layout.rows
    ]


def test_between_round_trips_and_the_selection_is_a_frozen_value():
    anchor, head = ("b1", 2, 4), ("b2", 1, 6)
    selection = Selection.between(anchor, head)
    assert selection.anchors == (anchor, head)
    assert Selection.between(*selection.anchors) == selection
    assert hash(selection) == hash(Selection.between(anchor, head))
    assert selection != Selection.between(anchor, (head[0], head[1], 7))
    with pytest.raises(AttributeError):
        selection.anchors = (anchor, head)  # type: ignore[misc]


def test_a_backwards_drag_normalizes_into_the_same_range():
    layout = _layout(
        [[("abcd", Style())], [("efgh", Style())], [("ijkl", Style())]],
        [("b0", 0), ("b0", 1), ("b1", 0)],
        ("b0", "b1"),
    )
    forward = highlight(layout, Selection.between(("b0", 1, 2), ("b1", 0, 3)))
    backward = highlight(layout, Selection.between(("b1", 0, 3), ("b0", 1, 2)))
    assert forward.rows == backward.rows
    assert _marked(forward) == ["", "gh", "ijk"]


def test_none_and_empty_selections_leave_the_layout_alone():
    layout = _layout([[("abcd", Style())]], [("b0", 0)], ("b0",))
    assert highlight(layout, None) is layout
    for column in (0, 2, 4):
        empty = Selection.between(("b0", 0, column), ("b0", 0, column))
        assert highlight(layout, empty) is layout


def test_mid_row_boundaries_cut_the_marked_piece():
    layout = _layout([[("abcdefgh", Style())]], [("b0", 0)], ("b0",))
    marked = highlight(layout, Selection.between(("b0", 0, 3), ("b0", 0, 6)))
    assert _marked(marked) == ["def"]
    assert [(segment.text, segment.style) for segment in marked.rows[0].segments] == [
        ("abc", Style()),
        ("def", Style().merge(SELECTION)),
        ("gh", Style()),
    ]


def test_highlight_takes_an_explicit_style_token():
    layout = _layout([[("abcd", Style())]], [("b0", 0)], ("b0",))
    band = Style(underline=True)
    selection = Selection.between(("b0", 0, 1), ("b0", 0, 3))
    marked = highlight(layout, selection, style=band)
    assert [(segment.text, segment.style) for segment in marked.rows[0].segments] == [
        ("a", Style()),
        ("bc", Style(underline=True)),
        ("d", Style()),
    ]
    assert highlight(layout, selection).rows[0].segments[1].style == Style().merge(
        SELECTION
    )


def test_injected_styles_round_trip_through_the_selection_merge():
    layout = _layout(
        [[("abc", ACCENTED), ("defg", BOLDED), ("hij", Style())]],
        [("b0", 0)],
        ("b0",),
    )
    marked = highlight(layout, Selection.between(("b0", 0, 4), ("b0", 0, 7))).rows[0]
    assert [(segment.text, segment.style) for segment in marked.segments] == [
        ("abc", ACCENTED),
        ("d", BOLDED),
        ("efg", BOLDED.merge(SELECTION)),
        ("hij", Style()),
    ]


def test_whole_rows_inside_the_range_are_fully_marked():
    layout = _layout(
        [[("abcd", Style())], [("efgh", Style())], [("ijkl", Style())]],
        [("b0", 0), ("b0", 1), ("b0", 2)],
        ("b0",),
    )
    marked = highlight(layout, Selection.between(("b0", 0, 2), ("b0", 2, 3)))
    assert _marked(marked) == ["cd", "efgh", "ijk"]


def test_columns_clamp_lazily_to_the_row_width():
    layout = _layout(
        [[("ab", Style())], [("cdef", Style())]],
        [("b0", 0), ("b0", 1)],
        ("b0",),
    )
    cases = [
        (99, 200, ["", "cdef"]),
        (0, 99, ["ab", "cdef"]),
        (0, 0, ["ab", ""]),
        (1, 200, ["b", "cdef"]),
    ]
    for start, end, expected in cases:
        over = highlight(layout, Selection.between(("b0", 0, start), ("b0", 1, end)))
        assert _marked(over) == expected


def test_unowned_rows_are_untouched():
    layout = _layout([[("abcd", Style())], [("", Style())]], [("b0", 0), None], ("b0",))
    marked = highlight(layout, Selection.between(("b0", 0, 0), ("b0", 0, 4)))
    assert marked.rows[1] is layout.rows[1]
    assert marked.rows[0] is not layout.rows[0]


def test_a_range_whose_endpoint_owns_no_row_leaves_the_layout_alone():
    layout = _layout([[("abcd", Style())]], [("b0", 0)], ("b0",))
    assert highlight(layout, Selection.between(("b9", 0, 0), ("b0", 0, 2))) is layout
    elsewhere = _layout(
        [[("abcd", Style())], [("efgh", Style())]],
        [("b0", 0), ("b0", 1)],
        ("b0", "b1"),
    )
    assert (
        highlight(elsewhere, Selection.between(("b1", 0, 0), ("b1", 0, 2)))
        is elsewhere
    )


def test_a_wide_cell_boundary_snaps_to_the_cell_start():
    layout = _layout([[("a\u754cb", Style())]], [("b0", 0)], ("b0",))
    marked = highlight(layout, Selection.between(("b0", 0, 2), ("b0", 0, 3)))
    assert _marked(marked) == ["\u754c"]
    assert [segment.text for segment in marked.rows[0].segments] == [
        "a",
        "\u754c",
        "b",
    ]
    cjk = _layout([[("\u65e5\u672c\u8a9e\u30c6\u30ad\u30b9\u30c8", Style())]], [("b0", 0)], ("b0",))
    for cut in (1, 3, 6):
        out = highlight(cjk, Selection.between(("b0", 0, cut), ("b0", 0, 6)))
        assert _marked(out) == ["\u65e5\u672c\u8a9e\u30c6\u30ad\u30b9\u30c8"[cut // 2 : 3]]
        assert out.rows[0].text == "\u65e5\u672c\u8a9e\u30c6\u30ad\u30b9\u30c8"


def test_the_highlight_follows_the_document_when_the_view_scrolls():
    document = Document()
    document.add(Rows("first", "second", "third")).seal()
    document.add(Rows("fourth", "fifth")).seal()
    view = Viewport(document)
    selection = Selection.between(("b0", 1, 1), ("b0", 1, 3))
    assert _marked(highlight(view.layout(80, 3), selection)) == ["", "", ""]
    view.scroll_up(1)
    assert _marked(highlight(view.layout(80, 3), selection)) == ["ec", "", ""]


def test_extract_walks_blocks_in_order_and_slices_the_edges():
    document = Document()
    document.add(Rows("aa0", "aa1", "aa2")).seal()
    document.add(Rows("bb0", "bb1", "bb2")).seal()
    document.add(Rows("cc0")).seal()
    text = extract(document, Selection.between(("b0", 1, 1), ("b2", 0, 2)), width=80)
    assert text == "a1\naa2\nbb0\nbb1\nbb2\ncc"
    assert extract(
        document, Selection.between(("b0", 0, 1), ("b0", 2, 2)), width=80
    ) == "a0\naa1\naa"
    forward = Selection.between(("b0", 1, 1), ("b1", 1, 2))
    backward = Selection.between(("b1", 1, 2), ("b0", 1, 1))
    assert extract(document, forward, width=80) == extract(document, backward, width=80)


def test_extract_skips_removed_blocks_and_empty_ranges():
    document = Document()
    document.add(Rows("aa0", "aa1", "aa2")).seal()
    document.add(Rows("bb0", "bb1", "bb2")).seal()
    document.add(Rows("cc0")).seal()
    document.remove("b1")
    assert extract(
        document, Selection.between(("b0", 1, 1), ("b2", 0, 2)), width=80
    ) == "a1\naa2\ncc"
    document.remove("b0")
    assert extract(
        document, Selection.between(("b0", 1, 1), ("b2", 0, 2)), width=80
    ) == ""
    assert extract(document, Selection.between(("b2", 0, 0), ("b2", 0, 0)), width=80) == ""
    assert extract(document, None, width=80) == ""


def test_extract_never_splits_a_double_width_cell():
    document = Document()
    document.add(Rows("\u65e5\u672c\u8a9e", "\u30c6\u30ad\u30b9\u30c8")).seal()
    text = extract(document, Selection.between(("b0", 0, 3), ("b0", 1, 5)), width=80)
    assert text == "\u672c\u8a9e\n\u30c6\u30ad"


def test_extract_reaches_past_the_viewport_window():
    document = Document()
    document.add(Rows("aa0", "aa1", "aa2")).seal()
    document.add(Rows("bb0", "bb1", "bb2")).seal()
    document.add(Rows("cc0")).seal()
    view = Viewport(document)
    assert [row.text for row in view.layout(80, 2).rows] == ["bb2", "cc0"]
    text = extract(document, Selection.between(("b0", 0, 1), ("b1", 0, 2)), width=80)
    assert text == "a0\naa1\naa2\nbb"
