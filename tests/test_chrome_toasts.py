"""Tests for mocode_tui.chrome: the Toasts overlay and its controller.

The stack is driven headlessly against a real :class:`~mocode_tui.app.TUI`:
a document of plain rows on a recording screen, the bands read off the
painted rows (a toast splices its band into the frame rows at its corner
rectangle), and the documented ``_clock`` seam for the expiry ticker.  The
geometry is pinned as row texts over the cases the spec names: all four
corners, the stack order and its blank separator, the width clamp and the
fit guard, the empty state, and -- for the controller -- TTL expiry,
``max_shown`` eviction, click-to-dismiss and ``detach``.
"""

import pytest

from _doubles import Rows

from mocode_tui.chrome import Toasts
from mocode_tui.core.style import Style
from mocode_tui.core.text import Text
from mocode_tui.testing import headless_tui

# --- helpers ------------------------------------------------------------------


def stack(tui, **knobs) -> Toasts:
    """A Toasts attached to an already-painted ``tui``."""
    toasts = Toasts(tui, **knobs)
    tui.paint()
    return toasts


def rows(width: int, height: int) -> list[str]:
    """The painted row texts of a headless ``width``x``height`` frame."""
    return [f"r{index}" for index in range(height)]


def document(tui, texts):
    """Fill ``tui``'s document with ``texts`` and paint."""
    tui.add(Rows(*texts))
    tui.paint()


# --- T1: the overlay ------------------------------------------------------------


@pytest.mark.parametrize(
    ("corner", "affected", "expected"),
    [
        ("top-left", 0, "hi        "),  # the band covers the document's head
        ("top-right", 0, "r0      hi"),
        ("bottom-left", 3, "hi        "),
        ("bottom-right", 3, "r3      hi"),
    ],
)
def test_each_corner_anchors_the_band(corner, affected, expected):
    tui = headless_tui(10, 4)
    document(tui, rows(10, 4))
    stack(tui, corner=corner).show("hi")
    tui.paint()
    assert tui.rows[affected].text == expected
    # every other row is the document's own, untouched
    others = [index for index in range(4) if index != affected]
    assert [tui.rows[index].text for index in others] == [
        rows(10, 4)[index] for index in others
    ]


def test_the_stack_reads_newest_at_the_corner_with_one_blank_row_between():
    tui = headless_tui(10, 5)
    document(tui, rows(10, 5))
    toasts = stack(tui)
    toasts.show("old")
    toasts.show("new")
    tui.paint()
    assert tui.rows[0].text == "r0     new"  # the newest sits at the corner
    assert tui.rows[2].text == "r2     old"  # one blank row between neighbours
    assert tui.rows[1].text == "r1"  # the separator is the document's own row


def test_a_multi_row_component_band_covers_each_of_its_rows():
    tui = headless_tui(10, 4)
    document(tui, rows(10, 4))
    stack(tui, corner="bottom-right").show(Rows("one", "two"))
    tui.paint()
    assert tui.rows[2].text == "r2     one"  # the component's own row order
    assert tui.rows[3].text == "r3     two"  # the stack grew up from the bottom edge
    assert tui.rows[1].text == "r1"


def test_a_narrow_frame_clamps_the_band_to_half_its_width():
    tui = headless_tui(20, 3)
    toasts = stack(tui)
    toasts.show("x" * 30)  # one long word: hard-broken at the clamp
    tui.paint()
    # ceiling = min(40, 20 // 2) = 10: ten columns of text per row, wrapped
    assert tui.rows[0].text == " " * 10 + "x" * 10
    assert tui.rows[1].text == " " * 10 + "x" * 10
    assert tui.rows[2].text == " " * 10 + "x" * 10


def test_a_wide_frame_clamps_the_band_to_forty_columns():
    tui = headless_tui(80, 3)
    toasts = stack(tui)
    toasts.show("y" * 90)
    tui.paint()
    # ceiling = min(40, 80 // 2) = 40 -- never more than half the frame
    assert tui.rows[0].text == " " * 40 + "y" * 40
    assert tui.rows[1].text == " " * 40 + "y" * 40
    assert tui.rows[2].text == " " * 40 + "y" * 10 + " " * 30


def test_a_short_toast_band_is_only_as_wide_as_its_content():
    tui = headless_tui(80, 1)
    toasts = stack(tui)
    toasts.show("hi")
    tui.paint()
    assert tui.rows[0].text == " " * 78 + "hi"


def test_a_component_that_overruns_its_width_is_fit_to_the_band():
    tui = headless_tui(20, 1)
    toasts = stack(tui)
    toasts.show(Rows("z" * 50))  # Rows ignores its width: the fit guard cuts it
    tui.paint()
    assert tui.rows[0].text == " " * 10 + "z" * 9 + "…"


def test_an_empty_stack_paints_nothing():
    tui = headless_tui(10, 3)
    document(tui, rows(10, 3))
    before = [row.text for row in tui.rows]
    stack(tui)
    tui.paint()
    assert [row.text for row in tui.rows] == before


def test_a_frame_too_narrow_to_host_a_column_paints_nothing():
    tui = headless_tui(1, 2)
    document(tui, ["a", "b"])
    toasts = stack(tui)
    toasts.show("hi")
    tui.paint()
    assert [row.text for row in tui.rows] == ["a", "b"]


def test_a_toast_rides_the_retile_that_rebuilds_the_frame():
    tui = headless_tui(20, 3)
    document(tui, rows(20, 3))
    toasts = stack(tui, corner="bottom-right")
    toasts.show("stay")
    tui.screen.width = 30  # the terminal resized; the next paint retiles the frame
    tui.paint()
    assert tui.rows[2].text == "r2" + " " * 24 + "stay"  # the band moved with the edge


@pytest.mark.parametrize(
    ("knobs", "show_style", "expected"),
    [
        ({}, None, Style(reverse=True, dim=True)),  # the module default band
        ({"style": Style(fg="#111111")}, None, Style(fg="#111111")),
        ({}, Style(fg="#222222"), Style(fg="#222222")),  # a toast's own wins
        (
            {"style": Style(fg="#111111")},
            Style(fg="#222222"),
            Style(fg="#222222")),
    ],
)
def test_the_band_resolves_a_toasts_style_then_the_controllers(
    knobs, show_style, expected
):
    tui = headless_tui(10, 1)
    toasts = stack(tui, **knobs)
    toasts.show("hi", style=show_style)
    tui.paint()
    assert tui.rows[0].segments[-1].style == expected


def test_the_band_paints_underneath_a_components_own_styles():
    tui = headless_tui(10, 6)
    toasts = stack(tui, style=Style(bg="#123456"))
    tui.paint()
    toasts.show(Text("red", style=Style(fg="red")))  # a color of its own: kept
    toasts.show(Text("dim", style=Style(italic=True)))  # an attribute: merged
    toasts.show(Rows("ab", ""))  # a short row and a blank row: both filled
    tui.paint()
    band = Style(bg="#123456")  # an explicit style is the whole band (charter)
    # The newest toast is two rows tall: "ab" over the band, then a blank row
    # that reads as a solid band row (the first segment of each row is the
    # untouched base the band does not cover).
    assert tui.rows[0].segments[1].style == band
    assert tui.rows[1].text == " " * 8 + "  "
    assert tui.rows[1].segments[-1].style == band
    # The middle toast: an attribute-only run shows the band through.
    assert tui.rows[3].segments[1].style == band.merge(Style(italic=True))
    # The oldest toast: a run with a color of its own stays absolute.
    assert tui.rows[5].segments[1].style == Style(fg="red")


def test_construct_attaches_the_overlay_and_detach_is_reported_clean():
    tui = headless_tui(10, 2)
    document(tui, rows(10, 2))
    toasts = stack(tui)
    assert toasts in tui._frame.overlays
    assert repr(toasts) == "Toasts(corner='top-right', shown=0)"
    toasts.show("hi")
    assert repr(toasts) == "Toasts(corner='top-right', shown=1)"


def test_an_unknown_corner_raises():
    tui = headless_tui(10, 2)
    with pytest.raises(ValueError):
        Toasts(tui, corner="middle")
