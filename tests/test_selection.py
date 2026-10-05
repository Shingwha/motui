"""Tests for mocode_tui.core.selection: the value and the overlay.

The model is a pair of document addresses kept exactly as given (direction
normalizes where the order is known, at use time); ``highlight`` is a pure
overlay that cuts the in-range rows at their column boundaries and merges
SELECTION onto the cut pieces, leaving unowned rows and everything outside
the range untouched.
"""

import pytest

from _doubles import Rows

from mocode_tui.core.block import Document
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.selection import Selection, highlight
from mocode_tui.core.style import SELECTION, Style
from mocode_tui.core.viewport import ScreenLayout, Viewport

#: Injected styles: round-tripped through the merge, never a pinned default.
ACCENTED = Style(fg="#abcdef")
BOLDED = Style(fg="#123456", bold=True)


def _layout(
    rows: list[list[tuple[str, Style]]],
    owners: list[tuple[str, int] | None],
    order: tuple[str, ...],
) -> ScreenLayout:
    """A hand-built layout: one ``(text, style)`` pair list per row."""
    return ScreenLayout(
        rows=[Line([Segment(text, style) for text, style in row]) for row in rows],
        viewport_rows=[],
        row_blocks=owners,
        block_order=order,
    )


def _marked(layout: ScreenLayout) -> list[str]:
    """Per row: the text of the pieces the overlay marked, ``""`` when none.

    A piece counts as marked when it carries SELECTION's attributes --
    ``reverse+dim`` -- which no injected base style in this file carries.
    """
    return [
        "".join(seg.text for seg in row.segments if seg.style.reverse and seg.style.dim)
        for row in layout.rows
    ]


def _rest(layout: ScreenLayout) -> list[str]:
    """Per row: the text of the pieces the overlay left alone."""
    return [
        "".join(
            seg.text
            for seg in row.segments
            if not (seg.style.reverse and seg.style.dim)
        )
        for row in layout.rows
    ]


# --- the value ------------------------------------------------------------------


def test_between_keeps_the_pair_as_given_and_anchors_round_trip():
    anchor, head = ("b1", 2, 4), ("b2", 1, 6)
    selection = Selection.between(anchor, head)
    assert selection.anchors == (anchor, head)
    assert Selection.between(*selection.anchors) == selection


def test_backwards_drag_normalizes_direction_into_the_same_range():
    layout = _layout(
        [[("abcd", Style())], [("efgh", Style())], [("ijkl", Style())]],
        [("b0", 0), ("b0", 1), ("b1", 0)],
        ("b0", "b1"),
    )
    forward = highlight(layout, Selection.between(("b0", 1, 2), ("b1", 0, 3)))
    backward = highlight(layout, Selection.between(("b1", 0, 3), ("b0", 1, 2)))
    assert forward.rows == backward.rows
    assert _marked(forward) == ["", "gh", "ijk"]


def test_selection_is_frozen_hashable_and_comparable():
    selection = Selection.between(("b0", 0, 0), ("b0", 2, 3))
    assert hash(selection) == hash(Selection.between(("b0", 0, 0), ("b0", 2, 3)))
    assert selection == Selection.between(("b0", 0, 0), ("b0", 2, 3))
    assert selection != Selection.between(("b0", 0, 0), ("b0", 2, 4))
    assert selection != Selection.between(("b1", 0, 0), ("b0", 2, 3))
    with pytest.raises(AttributeError):
        selection.anchors = (("b0", 0, 0), ("b0", 0, 1))  # type: ignore[misc]


@pytest.mark.parametrize("col", [0, 2, 4])
def test_empty_range_marks_nothing(col: int):
    layout = _layout([[("abcd", Style())]], [("b0", 0)], ("b0",))
    empty = Selection.between(("b0", 0, col), ("b0", 0, col))
    assert highlight(layout, empty) is layout


# --- the overlay ----------------------------------------------------------------


def test_none_selection_is_the_layout_itself():
    layout = _layout([[("abcd", Style())]], [("b0", 0)], ("b0",))
    assert highlight(layout, None) is layout


def test_mid_row_boundaries_cut_the_marked_piece():
    layout = _layout([[("abcdefgh", Style())]], [("b0", 0)], ("b0",))
    marked = highlight(layout, Selection.between(("b0", 0, 3), ("b0", 0, 6)))
    assert _marked(marked) == ["def"]
    assert [(seg.text, seg.style) for seg in marked.rows[0].segments] == [
        ("abc", Style()),
        ("def", Style().merge(SELECTION)),
        ("gh", Style()),
    ]


def test_injected_styles_round_trip_through_the_selection_merge():
    layout = _layout(
        [[("abc", ACCENTED), ("defg", BOLDED), ("hij", Style())]],
        [("b0", 0)],
        ("b0",),
    )
    marked = highlight(layout, Selection.between(("b0", 0, 4), ("b0", 0, 7))).rows[0]
    assert [(seg.text, seg.style) for seg in marked.segments] == [
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


def test_a_range_spanning_blocks_marks_both_sides():
    layout = _layout(
        [[("abcd", Style())], [("efgh", Style())], [("ijkl", Style())]],
        [("b0", 0), ("b0", 1), ("b1", 0)],
        ("b0", "b1"),
    )
    marked = highlight(layout, Selection.between(("b0", 1, 2), ("b1", 0, 3)))
    assert _marked(marked) == ["", "gh", "ijk"]


@pytest.mark.parametrize(
    ("start", "end", "marked"),
    # The range's first row marks from its column on, its last row up to
    # its column; columns past a short row clamp to that row's edge (D8).
    [(99, 200, ["", "cdef"]), (0, 99, ["ab", "cdef"]), (0, 0, ["ab", ""]), (1, 200, ["b", "cdef"])],
)
def test_columns_clamp_lazily_to_the_row_width(start: int, end: int, marked: list[str]):
    layout = _layout(
        [[("ab", Style())], [("cdef", Style())]],
        [("b0", 0), ("b0", 1)],
        ("b0",),
    )
    over = highlight(layout, Selection.between(("b0", 0, start), ("b0", 1, end)))
    assert _marked(over) == marked
    assert over.rows[0].text == "ab" and over.rows[1].text == "cdef"


def test_unowned_rows_are_untouched():
    layout = _layout(
        [[("abcd", Style())], [("", Style())]],
        [("b0", 0), None],
        ("b0",),
    )
    marked = highlight(layout, Selection.between(("b0", 0, 0), ("b0", 0, 4)))
    assert marked.rows[1] is layout.rows[1]
    assert marked.rows[0] is not layout.rows[0]
    assert _marked(marked) == ["abcd", ""]


def test_a_range_over_a_removed_endpoint_returns_the_layout_itself():
    layout = _layout([[("abcd", Style())]], [("b0", 0)], ("b0",))
    gone = Selection.between(("b9", 0, 0), ("b0", 0, 2))  # the anchor's block is gone
    assert highlight(layout, gone) is layout


def test_a_range_whose_block_owns_no_row_returns_the_layout_itself():
    layout = _layout(
        [[("abcd", Style())], [("efgh", Style())]],
        [("b0", 0), ("b0", 1)],
        ("b0", "b1"),
    )
    elsewhere = Selection.between(("b1", 0, 0), ("b1", 0, 2))
    assert highlight(layout, elsewhere) is layout


# --- the cluster-aware cut ------------------------------------------------------


@pytest.mark.parametrize("cut", [1, 2, 3, 4, 5, 6])
def test_wide_character_boundaries_never_split_a_double_width_cell(cut: int):
    """日本語テキスト -- every cell two columns wide, no cut lands inside one."""
    layout = _layout([[("日本語テキスト", Style())]], [("b0", 0)], ("b0",))
    marked = highlight(layout, Selection.between(("b0", 0, cut), ("b0", 0, 6)))
    row = marked.rows[0]
    # The boundary snaps down to a cell start: every other column in the
    # range marks exactly the cells it covers, never half of one.
    assert _marked(marked) == ["日本語テキスト"[cut // 2 : 3]]
    assert row.text == "日本語テキスト"  # the cut pieces re-concatenate intact
    piece = _marked(marked)[0]
    assert all(seg.style == Style() or seg.style == Style().merge(SELECTION) for seg in row.segments)


def test_a_boundary_inside_a_double_width_cell_snaps_to_the_cell_start():
    layout = _layout([[("a界b", Style())]], [("b0", 0)], ("b0",))
    # Column 2 is the right half of 界 (columns 1-2): the cut snaps down to
    # column 1, so 界 is either wholly in or wholly out -- never halved.
    marked = highlight(layout, Selection.between(("b0", 0, 2), ("b0", 0, 3)))
    assert _marked(marked) == ["界"]
    assert [seg.text for seg in marked.rows[0].segments] == ["a", "界", "b"]


# --- purity over a real layout --------------------------------------------------


def _two_blocks() -> Viewport:
    document = Document()
    document.add(Rows("first", "second", "third")).seal()
    document.add(Rows("fourth", "fifth")).seal()
    return Viewport(document)


def test_the_overlay_keeps_the_sealed_cache_values_unchanged():
    view = _two_blocks()
    layout = view.layout(80, 3)  # sticks to the bottom: third, fourth, fifth
    before = list(layout.rows)
    marked = highlight(layout, Selection.between(("b0", 2, 0), ("b1", 1, 1)))
    assert _marked(marked) == ["third", "fourth", "f"]
    after = view.layout(80, 3).rows
    assert after == before  # the same cached values, not even re-rendered
    assert all(kept is fresh for kept, fresh in zip(before, after))


def test_the_highlight_follows_the_document_when_the_view_scrolls():
    view = _two_blocks()
    selection = Selection.between(("b0", 1, 1), ("b0", 1, 3))
    bottom = highlight(view.layout(80, 3), selection)  # the window shows b1 only
    assert _marked(bottom) == ["", "", ""]  # b0 row 1 is scrolled out of the window
    view.scroll_up(1)  # second, third, more-below
    scrolled = highlight(view.layout(80, 3), selection)
    assert _marked(scrolled) == ["ec", "", ""]
