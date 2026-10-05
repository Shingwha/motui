"""Tests for mocode_tui.chat.statusline (StatusLine).

Contract: one row always; the left part at column 0, the right part one
column short of ``width``, at least one gutter column between them; bare
strings render in the theme's ``dim``; an over-wide row keeps the left
part and ellipsizes the right part's tail (the demo's ``_StatusRow``
behaviour); ``left``/``right`` are reassignable between renders.
"""

from mocode_tui.chat.statusline import StatusLine
from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import ACCENT, DIM, MUTED, Style
from mocode_tui.core.text import visible_width
from mocode_tui.core.theme import Theme


def test_two_sides_align_with_one_trailing_margin():
    bar = StatusLine(left=("left",), right=("right",))
    (row,) = bar.render(40)
    assert row.text == "left" + " " * 30 + "right"
    assert row.width == 39  # width - 1: the right margin column stays blank


def test_minimum_gutter_is_one_column():
    bar = StatusLine(left=("ab",), right=("cd",))
    (row,) = bar.render(6)
    assert row.text == "ab cd"  # gutter 1; the row ends one column early
    assert row.width == 5


def test_overflow_keeps_the_left_and_cuts_the_right_tail():
    bar = StatusLine(left=("keep-me",), right=("drop-me-please",))
    (row,) = bar.render(14)
    assert row.width == 14
    assert row.text.startswith("keep-me")  # the left part survives intact
    assert row.text.endswith("\u2026")  # the right part is ellipsized
    assert "please" not in row.text  # cut from the tail, not from the head


def test_left_alone_fills_the_row_when_nothing_remains():
    bar = StatusLine(left=("a-much-too-long-left-part",), right=("r",))
    (row,) = bar.render(12)
    assert row.width == 12
    assert row.text == "a-much-too-\u2026"  # the right part has no room left


def test_bare_strings_are_dim_by_default_and_merge_into_one_segment():
    bar = StatusLine(left=("l",), right=("r",))
    (row,) = bar.render(10)
    assert row.segments == (
        Segment("l" + " " * 7 + "r", DIM),
    )  # one dim run, like the demo's Line.from_text(row, DIM)


def test_tuple_elements_carry_their_own_style():
    bar = StatusLine(
        left=(("ctx", ACCENT), "plain"),
        right=("r", ("tail", MUTED)),
    )
    (row,) = bar.render(30)
    assert row.text == "ctxplain" + " " * 16 + "rtail"
    assert row.segments[0] == Segment("ctx", ACCENT)
    assert row.segments[1] == Segment("plain" + " " * 16 + "r", DIM)
    assert row.segments[-1] == Segment("tail", MUTED)


def test_adjacent_equal_style_elements_merge_into_one_segment():
    bar = StatusLine(left=("a", "b", ("c", DIM)), right=("d",))
    (row,) = bar.render(12)
    assert row.segments == (Segment("abc" + " " * 7 + "d", DIM),)


def test_gap_style_overrides_only_the_gutter():
    bar = StatusLine(left=("l",), right=("r",), gap_style=Style(reverse=True))
    (row,) = bar.render(10)
    assert row.segments == (
        Segment("l", DIM),
        Segment(" " * 7, Style(reverse=True)),
        Segment("r", DIM),
    )


def test_render_is_always_exactly_one_row():
    bar = StatusLine(left=("l",), right=("r",))
    for width in (-3, 0, 1, 2, 5, 80):
        rows = bar.render(width)
        assert len(rows) == 1
        assert rows[0].width <= max(0, width)


def test_empty_sides_render_the_gutter_only():
    bar = StatusLine()
    (row,) = bar.render(10)
    assert row.text == " " * 9  # gutter only: the right margin stays blank


def test_left_and_right_are_reassignable_between_renders():
    bar = StatusLine(left=("one",), right=("two",))
    assert "one" in bar.render(40)[0].text
    bar.left = [("three", ACCENT)]
    bar.right = ()
    row = bar.render(40)[0]
    assert row.text == "three" + " " * 34  # left plus the gutter; no right part


def test_theme_drives_the_default_style():
    theme = Theme(dim=MUTED)
    bar = StatusLine(left=("l",), right=("r",), theme=theme)
    (row,) = bar.render(20)
    assert row.segments == (Segment("l" + " " * 17 + "r", MUTED),)
    # An explicit gap style still wins over the themed default.
    bar = StatusLine(left=("l",), right=("r",), theme=theme, gap_style=ACCENT)
    (row,) = bar.render(20)
    assert row.segments[1].style == ACCENT


def test_matches_the_demo_status_row_row_for_row():
    """Demo alignment: the released _StatusRow row, segment for segment.

    The demo built ``f"{left}{' ' * gutter}{right}"`` in ``DIM`` and closed
    it with ``fit``; a StatusLine of plain strings renders the same row --
    text and segments alike -- at every width, over-wide ones included.
    """
    left = "19.9k \u21921.4k R32k CH98.0% $0.003 1.0%/1.0M (auto)"
    right = "(commandcode) deepseek/deepseek-v4.1-flash-fast \u2022 medium"
    bar = StatusLine(left=(left,), right=(right,))
    for width in (0, 1, 7, 40, 107, 108, 121, 300):
        used = visible_width(left) + visible_width(right)
        gutter = max(1, width - used - 1)
        expected = Line.from_text(f"{left}{' ' * gutter}{right}", DIM).fit(width)
        assert bar.render(width) == [expected]
