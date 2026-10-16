"""Tests for mocode_tui.widgets.statusline (StatusLine).

One row always: the left part at column 0, the right one column short of the
width with a gutter between; an over-wide row keeps the left, cuts the right.
"""

import pytest

from mocode_tui.core.lines import Line, Segment
from mocode_tui.core.style import ACCENT, DIM, MUTED, Style
from mocode_tui.core.text import visible_width
from mocode_tui.core.theme import Theme
from mocode_tui.widgets.statusline import StatusLine

#: Gutter rule: left at column 0, right ending one column short of ``width``.
_GUTTER = 1


def _expected(left: str, right: str, width: int, style: Style = DIM) -> Line:
    """The row the demo's ``_StatusRow``-style composition builds."""
    used = visible_width(left) + visible_width(right)
    gutter = max(_GUTTER, width - used - 1)
    return Line.from_text(f"{left}{' ' * gutter}{right}", style).fit(width)


@pytest.mark.parametrize(
    ("left", "right", "width"),
    [
        (("left",), ("right",), 40),  # a wide screen: a deep gutter
        (("ab",), ("cd",), 6),  # the minimum gutter is one column
        (("a-much-too-long-left-part",), ("r",), 12),  # no room for the right
        (("l", "b", ("c", DIM)), ("d",), 12),  # adjacent equal styles coalesce
        ((), ("only-right",), 30),  # an empty left side
        (("only-left",), (), 30),  # an empty right side
        ((), (), 10),  # both empty: the gutter alone
        (("l",), ("r",), -3),  # degenerate widths still yield exactly one row
        (("l",), ("r",), 0),
        (("l",), ("r",), 1),
        (("l",), ("r",), 2),
    ],
)
def test_the_row_composes_left_gutter_right(left, right, width):
    bar = StatusLine(left=left, right=right)
    rows = bar.render(width)
    assert len(rows) == 1  # always exactly one row
    assert rows[0].width <= max(0, width)

    left_text = "".join(x if isinstance(x, str) else x[0] for x in left)
    right_text = "".join(x if isinstance(x, str) else x[0] for x in right)
    expected = _expected(left_text, right_text, width)
    assert rows[0].text == expected.text
    assert rows[0] == expected


@pytest.mark.parametrize(
    ("width", "marker"),
    [
        (14, "keep-me drop-…"),  # the right part is cut from its tail
        (15, "keep-me drop-m…"),
        (11, "keep-me dr…"),
    ],
)
def test_overflow_keeps_the_left_and_cuts_the_right_tail(width, marker):
    bar = StatusLine(left=("keep-me",), right=("drop-me-please",))
    (row,) = bar.render(width)
    assert row.width == width
    assert row.text.startswith("keep-me")  # the left part survives intact
    assert row.text.endswith("…")  # the right part is ellipsized
    assert row.text == marker  # cut from the tail, not from the head


def test_styles_resolve_explicit_element_over_gutter_over_theme():
    bar = StatusLine(
        left=(("ctx", ACCENT), "plain"),
        right=("r", ("tail", MUTED)),
        gap_style=Style(reverse=True),
    )
    (row,) = bar.render(30)
    # Only adjacent elements with *equal* styles fuse, so the gutter keeps
    # its own run and "plain" stays in the dim default beside it.
    assert row.segments == (
        Segment("ctx", ACCENT),
        Segment("plain", DIM),
        Segment(" " * 16, Style(reverse=True)),  # the computed gutter
        Segment("r", DIM),
        Segment("tail", MUTED),
    )
    # Bare strings with a custom gutter style stay dim, exactly like the demo.
    bar = StatusLine(left=("l",), right=("r",), gap_style=Style(reverse=True))
    (row,) = bar.render(10)
    assert row.segments == (
        Segment("l", DIM),
        Segment(" " * 7, Style(reverse=True)),
        Segment("r", DIM),
    )
    # A row of plain elements fuses into one dim run, like the demo's own
    # ``Line.from_text(row, DIM)``.
    bar = StatusLine(left=("a", "b", ("c", DIM)), right=("d",))
    (row,) = bar.render(12)
    assert row.segments == (Segment("abc" + " " * 7 + "d", DIM),)
    # The whole row's default comes from the theme when nothing is explicit.
    bar = StatusLine(left=("l",), right=("r",), theme=Theme(dim=MUTED))
    (row,) = bar.render(20)
    assert row.segments == (Segment("l" + " " * 17 + "r", MUTED),)
    # An explicit gap style still wins over the themed default.
    bar = StatusLine(left=("l",), right=("r",), theme=Theme(dim=MUTED), gap_style=ACCENT)
    (row,) = bar.render(20)
    assert row.segments[1].style == ACCENT


def test_left_and_right_are_reassignable_between_renders():
    bar = StatusLine(left=("one",), right=("two",))
    assert "one" in bar.render(40)[0].text
    bar.left = [("three", ACCENT)]
    bar.right = ()
    row = bar.render(40)[0]
    assert row.text == "three" + " " * 34  # left plus the gutter; no right part


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
        assert bar.render(width) == [_expected(left, right, width)]


def test_the_row_locks_its_bytes_after_the_move():
    """One sample row, byte for byte: the migration's own lock.

    ``StatusLine`` moved into the widgets library with rendering
    unchanged; this literal lock (text plus segments) fails on a
    single shifted space or fused segment.
    """
    bar = StatusLine(left=(("19.9k", ACCENT), " ready"), right=(("v4.1-flash", MUTED),))
    (row,) = bar.render(40)
    assert row.text == "19.9k ready" + " " * 18 + "v4.1-flash"
    assert row.segments == (
        Segment("19.9k", ACCENT),  # the explicit element style survives
        Segment(" ready" + " " * 18, DIM),  # bare text fuses with the gutter
        Segment("v4.1-flash", MUTED),
    )
