"""Tests for mocode_tui.viewport."""

from mocode_tui.block import BlockState, Document
from mocode_tui.lines import Line
from mocode_tui.style import MUTED
from mocode_tui.viewport import Viewport


class Rows:
    """Component rendering one row per given text; records render calls."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.calls: list[int] = []

    def render(self, width: int) -> list[Line]:
        self.calls.append(width)
        return [Line.from_text(t) for t in self.texts]


def _texts(rows: list[Line]) -> list[str]:
    return [row.text for row in rows]


def _many(n: int) -> list[str]:
    return [f"r{i}" for i in range(n)]


# --- initial state ----------------------------------------------------------------


def test_initial_state_before_any_layout():
    view = Viewport(Document())
    assert view.offset == 0
    assert view.total_rows == 0
    assert view.viewport_height == 0
    assert view.at_bottom is True


def test_empty_document_is_all_blank_rows():
    layout = Viewport(Document()).layout(80, 3)
    assert layout.rows == [Line(), Line(), Line()]
    assert layout.viewport_rows == [Line(), Line(), Line()]


# --- basic layout -------------------------------------------------------------------


def test_short_document_is_top_aligned_and_padded():
    doc = Document()
    doc.add(Rows("a", "b"))
    view = Viewport(doc)
    layout = view.layout(80, 5)
    assert _texts(layout.rows) == ["a", "b", "", "", ""]
    assert _texts(layout.viewport_rows) == ["a", "b", "", "", ""]
    assert view.offset == 0
    assert view.at_bottom is True
    assert view.total_rows == 2
    assert view.viewport_height == 5


def test_long_document_sticks_to_bottom_without_indicator():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["r6", "r7", "r8", "r9"]
    assert view.offset == 6
    assert view.at_bottom is True
    assert view.total_rows == 10
    assert view.viewport_height == 4
    # at the bottom nothing waits below, so no marker row
    assert layout.viewport_rows[-1] == Line.from_text("r9")


def test_rows_are_exactly_height_for_odd_heights():
    doc = Document()
    doc.add(Rows(*_many(3)), pin="bottom")
    doc.add(Rows(*_many(40)))
    view = Viewport(doc)
    for height in (0, 1, 2, 7, 24):
        layout = view.layout(80, height)
        assert len(layout.rows) == height
        assert len(layout.viewport_rows) == max(0, height - 3)


# --- scrolling clamps -----------------------------------------------------------------


def test_scroll_up_clamps_at_top_and_leaves_stickiness():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(100)
    assert view.offset == 0
    assert view.at_bottom is False
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["r0", "r1", "r2", "─ more below ─"]


def test_scroll_down_clamps_at_the_last_window():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(100)
    view.scroll_down(2)
    assert view.offset == 2
    view.scroll_down(100)
    assert view.offset == 6
    assert view.at_bottom is True  # landing on the bottom edge re-attaches
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["r6", "r7", "r8", "r9"]


def test_scroll_with_non_positive_n_is_a_noop():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(0)
    view.scroll_down(0)
    view.scroll_up(-5)
    assert view.offset == 6
    assert view.at_bottom is True


def test_new_content_does_not_move_a_scrolled_away_viewport():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(2)
    assert view.offset == 4
    doc.add(Rows("new1", "new2", "new3"))  # arrives while scrolled away
    layout = view.layout(80, 4)
    assert view.offset == 4  # offset untouched
    assert view.at_bottom is False
    assert _texts(layout.rows) == ["r4", "r5", "r6", "─ more below ─"]


def test_scroll_to_bottom_restores_stickiness():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(2)
    view.scroll_to_bottom()
    assert view.at_bottom is True
    layout = view.layout(80, 4)
    assert view.offset == 6
    assert _texts(layout.rows) == ["r6", "r7", "r8", "r9"]
    # new content moves the window again
    doc.add(Rows("tail"))
    layout = view.layout(80, 4)
    assert view.offset == 7
    assert _texts(layout.rows) == ["r7", "r8", "r9", "tail"]


def test_scrolling_down_to_the_bottom_edge_reattaches():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(3)  # detached
    assert view.offset == 3
    assert view.at_bottom is False
    view.scroll_down(2)  # still short of the edge
    assert view.offset == 5
    assert view.at_bottom is False
    view.scroll_down(1)  # lands exactly on the clamp limit
    assert view.offset == 6
    assert view.at_bottom is True
    # pgdn all the way down resumes auto-follow
    doc.add(Rows("tail1", "tail2"))
    layout = view.layout(80, 4)
    assert view.offset == 8
    assert _texts(layout.rows) == ["r8", "r9", "tail1", "tail2"]
    assert "─ more below ─" not in _texts(layout.rows)


def test_scrolling_down_past_the_edge_on_a_short_document_reattaches():
    doc = Document()
    doc.add(Rows("only1", "only2"))
    view = Viewport(doc)
    view.layout(80, 5)
    view.scroll_up(3)  # nothing moved, but the view detached
    assert view.at_bottom is False
    view.scroll_down(1)  # the whole document already fits: bottom edge reached
    assert view.offset == 0
    assert view.at_bottom is True


def test_scrolling_away_from_a_short_document_keeps_the_top():
    doc = Document()
    doc.add(Rows("only1", "only2"))
    view = Viewport(doc)
    view.layout(80, 5)
    view.scroll_up(3)  # nothing to scroll, but the user took control
    assert view.offset == 0
    assert view.at_bottom is False
    doc.add(Rows("late1", "late2", "late3", "late4"))
    layout = view.layout(80, 5)
    assert view.offset == 0  # stays at the top instead of following the tail
    assert _texts(layout.rows) == ["only1", "only2", "late1", "late2", "─ more below ─"]
    assert _texts(layout.viewport_rows) == ["only1", "only2", "late1", "late2", "─ more below ─"]


# --- "more below" marker ---------------------------------------------------------------


def test_marker_appears_only_when_scrolled_away_with_content_below():
    doc = Document()
    doc.add(Rows(*_many(10)))
    view = Viewport(doc)

    bottom = view.layout(80, 4)
    assert "─ more below ─" not in _texts(bottom.rows)

    view.scroll_up(1)  # window shows r5..r8, r9 waits below
    layout = view.layout(80, 4)
    assert layout.viewport_rows[-1] == Line.from_text("─ more below ─", MUTED)
    assert _texts(layout.rows) == ["r5", "r6", "r7", "─ more below ─"]

    view.scroll_down(1)  # window shows r6..r9, nothing waits below
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["r6", "r7", "r8", "r9"]


def test_marker_with_one_row_viewport():
    doc = Document()
    doc.add(Rows("a", "b"))
    view = Viewport(doc)
    view.layout(80, 1)
    view.scroll_up(1)
    layout = view.layout(80, 1)
    assert layout.rows == [Line.from_text("─ more below ─", MUTED)]
    assert layout.viewport_rows == [Line.from_text("─ more below ─", MUTED)]


# --- fixed regions ----------------------------------------------------------------------


def test_bottom_pinned_and_body_render_in_document_order():
    doc = Document()
    doc.add(Rows("body1"))
    doc.add(Rows("pin1"), pin="bottom")
    doc.add(Rows("body2"))
    doc.add(Rows("pin2"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 6)
    # viewport region first (blank-padded to vh), bottom region at the bottom
    assert _texts(layout.rows) == ["body1", "body2", "", "", "pin1", "pin2"]
    assert _texts(layout.viewport_rows) == ["body1", "body2", "", ""]
    assert view.viewport_height == 4


def test_top_pinned_and_body_render_in_document_order():
    doc = Document()
    doc.add(Rows("body1"))
    doc.add(Rows("top1"), pin="top")
    doc.add(Rows("body2"))
    doc.add(Rows("top2"), pin="top")
    view = Viewport(doc)
    layout = view.layout(80, 6)
    # top region above the viewport, in document order
    assert _texts(layout.rows) == ["top1", "top2", "body1", "body2", "", ""]
    assert _texts(layout.viewport_rows) == ["body1", "body2", "", ""]
    assert view.viewport_height == 4


def test_both_regions_render_in_document_order():
    doc = Document()
    doc.add(Rows("top1"), pin="top")
    doc.add(Rows("body1"))
    doc.add(Rows("bottom1"), pin="bottom")
    doc.add(Rows("top2"), pin="top")
    doc.add(Rows("body2"))
    doc.add(Rows("bottom2"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 6)
    assert _texts(layout.rows) == [
        "top1", "top2", "body1", "body2", "bottom1", "bottom2",
    ]
    assert _texts(layout.viewport_rows) == ["body1", "body2"]
    assert view.viewport_height == 2
    assert view.total_rows == 2  # fixed-region rows are not body rows


def test_dual_region_height_accounting():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("t1", "t2"), pin="top")
    doc.add(Rows("b1"), pin="bottom")
    view = Viewport(doc)
    for height in (3, 4, 7, 24):
        layout = view.layout(80, height)
        assert len(layout.rows) == height
        assert view.viewport_height == max(0, height - 3)
        assert _texts(layout.rows[:2]) == ["t1", "t2"]
        assert _texts(layout.rows[-1:]) == ["b1"]


def test_top_region_keeps_the_body_sticking_to_the_bottom():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("top"), pin="top")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["top", "r7", "r8", "r9"]
    assert view.viewport_height == 3


def test_bottom_rows_do_not_scroll_away():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("pin"), pin="bottom")
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(100)
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["r0", "r1", "─ more below ─", "pin"]
    assert view.viewport_height == 3
    assert view.total_rows == 10  # fixed-region rows are not body rows


def test_top_rows_do_not_scroll_away():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("top"), pin="top")
    view = Viewport(doc)
    view.layout(80, 4)
    view.scroll_up(100)
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["top", "r0", "r1", "─ more below ─"]
    assert view.viewport_height == 3
    assert view.total_rows == 10  # fixed-region rows are not body rows


def test_bottom_region_filling_the_screen_leaves_no_viewport():
    doc = Document()
    doc.add(Rows("b1", "b2"))
    doc.add(Rows("p1", "p2", "p3", "p4"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert view.viewport_height == 0
    assert layout.viewport_rows == []
    assert _texts(layout.rows) == ["p1", "p2", "p3", "p4"]


def test_top_region_filling_the_screen_leaves_no_viewport():
    doc = Document()
    doc.add(Rows("b1", "b2"))
    doc.add(Rows("t1", "t2", "t3", "t4"), pin="top")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert view.viewport_height == 0
    assert layout.viewport_rows == []
    assert _texts(layout.rows) == ["t1", "t2", "t3", "t4"]


def test_bottom_taller_than_screen_is_truncated_to_height():
    doc = Document()
    doc.add(Rows("p1", "p2", "p3", "p4", "p5", "p6"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["p1", "p2", "p3", "p4"]
    assert layout.viewport_rows == []


def test_top_taller_than_screen_is_truncated_to_height():
    doc = Document()
    doc.add(Rows("t1", "t2", "t3", "t4", "t5", "t6"), pin="top")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert _texts(layout.rows) == ["t1", "t2", "t3", "t4"]
    assert layout.viewport_rows == []


def test_bottom_region_wins_when_both_regions_overflow():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("t1", "t2", "t3"), pin="top")
    doc.add(Rows("b1", "b2", "b3", "b4"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert view.viewport_height == 0
    assert layout.viewport_rows == []
    # the bottom region is preserved in full; the top region gets nothing
    assert _texts(layout.rows) == ["b1", "b2", "b3", "b4"]


def test_top_region_is_truncated_when_the_pair_overflows():
    doc = Document()
    doc.add(Rows(*_many(10)))
    doc.add(Rows("t1", "t2", "t3", "t4"), pin="top")
    doc.add(Rows("b1", "b2"), pin="bottom")
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert view.viewport_height == 0
    assert layout.viewport_rows == []
    # bottom kept in full, top keeps only its leading rows, viewport empty
    assert _texts(layout.rows) == ["t1", "t2", "b1", "b2"]


# --- sealed-row cache ---------------------------------------------------------------------


def test_open_blocks_render_every_layout_but_sealed_blocks_do_not():
    doc = Document()
    open_block = doc.add(Rows("open"))
    sealed_block = doc.add(Rows("sealed"))
    view = Viewport(doc)
    view.layout(80, 5)
    assert len(open_block.component.calls) == 1
    assert len(sealed_block.component.calls) == 1
    sealed_block.seal()
    view.layout(80, 5)
    view.layout(80, 5)
    assert len(open_block.component.calls) == 3
    assert len(sealed_block.component.calls) == 2  # once open, once to fill the cache


def test_sealed_cache_ignores_a_component_swapped_after_sealing():
    doc = Document()
    block = doc.add(Rows("frozen"))
    block.seal()
    view = Viewport(doc)
    view.layout(80, 5)  # first sealed render fills the cache
    replacement = Rows("replacement")
    block.set_component(replacement)
    layout = view.layout(80, 5)
    assert _texts(layout.rows) == ["frozen", "", "", "", ""]
    assert replacement.calls == []  # the frozen rows never re-render


def test_sealed_cache_is_invalidated_when_the_width_changes():
    doc = Document()
    component = Rows("w1")
    block = doc.add(component)
    block.seal()
    view = Viewport(doc)
    view.layout(80, 5)
    assert component.calls == [80]
    layout = view.layout(100, 5)  # new width: cache cleared, re-rendered once
    assert component.calls == [80, 100]
    assert _texts(layout.rows) == ["w1", "", "", "", ""]  # rows reflect the new render
    view.layout(100, 5)
    assert component.calls == [80, 100]  # cached again at the new width


def test_cache_does_not_leak_rows_of_removed_blocks_into_reused_ids():
    doc = Document()
    first = doc.add(Rows("first"))
    first.seal()
    view = Viewport(doc)
    assert _texts(view.layout(80, 3).rows) == ["first", "", ""]
    doc.remove("b0")
    doc.add(Rows("second"), id="b0").seal()
    layout = view.layout(80, 3)
    assert _texts(layout.rows) == ["second", "", ""]


def test_open_block_sealed_later_starts_using_the_cache():
    doc = Document()
    component = Rows("x")
    block = doc.add(component)
    view = Viewport(doc)
    view.layout(80, 3)
    block.seal()
    view.layout(80, 3)
    assert component.calls == [80, 80]  # rendered once open, once to fill cache


def test_layout_rows_are_immune_to_cache_mutation():
    doc = Document()
    block = doc.add(Rows("a", "b"))
    block.seal()
    view = Viewport(doc)
    layout = view.layout(80, 4)
    assert _texts(layout.viewport_rows) == ["a", "b", "", ""]
    layout.viewport_rows.append(Line.from_text("junk"))
    layout2 = view.layout(80, 4)
    assert _texts(layout2.viewport_rows) == ["a", "b", "", ""]
