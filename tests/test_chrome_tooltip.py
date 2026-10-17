"""Tests for motui.chrome: the Tooltip overlay.

The band is driven headlessly against a real :class:`~motui.app.TUI`: a
leaf carrying a ``hint`` attribute on a plain block, a real
:class:`~motui.pointer.Pointer` fed the documented reports, and the
painted rows read off the frame.  The cases the spec names: a hint and no
hint, the flip on the frame's last row, the clamp into the frame, ``detach``,
and a hint changed under a live pointer.
"""

from __future__ import annotations

import pytest

from motui.chrome import Tooltip
from motui.kernel.events import MouseEvent
from motui.kernel.lines import Line
from motui.kernel.style import Style
from motui.kernel.theme import Theme
from motui.pointer import Pointer
from motui.testing import headless_tui

# --- helpers ------------------------------------------------------------------


class Leaf:
    """A hoverable leaf: rows of text, and a ``hint`` when one is asked for."""

    def __init__(self, *, rows: int = 1, hint: object = None, has_hint: bool = True):
        self.hover = False
        self.rows = rows
        if has_hint:
            self.hint = hint

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(f"leaf{i}") for i in range(self.rows)]


def motion(x: int, y: int) -> MouseEvent:
    """The button-free motion a 1003 host sees (the decoder's normalized 35)."""
    return MouseEvent("none", button=0, x=x, y=y, kind="motion")


def mounted(leaf, *, width: int = 30, height: int = 6, theme=None):
    """A painted TUI with ``leaf`` mounted, a Pointer over it, and a Tooltip."""
    tui = headless_tui(width, height)
    tui.add(leaf)
    tui.paint()
    pointer = Pointer(tui)
    tooltip = Tooltip(tui, pointer, theme=theme)
    return tui, pointer, tooltip


def rows_text(tui) -> list[str]:
    return [row.text for row in tui.rows]


# --- the paint -------------------------------------------------------------------


def test_a_hint_paints_a_one_row_band_under_the_pointers_cell():
    leaf = Leaf(rows=2, hint="press enter to ship")
    tui, pointer, _ = mounted(leaf)
    pointer.handle(motion(2, 1))  # over the leaf's second row
    tui.paint()
    assert tui.rows[1].text == "leaf1"  # the pointer's own row is spared
    assert tui.rows[2].text.rstrip() == "  press enter to ship"
    assert tui.rows[0].text == "leaf0"


@pytest.mark.parametrize(
    "leaf",
    [
        Leaf(has_hint=False),  # no hint attribute at all
        Leaf(hint=""),  # an empty hint is no hint
        Leaf(hint=5),  # a non-str hint is not read as one
        Leaf(hint=None),  # nor is None
    ],
)
def test_a_leaf_without_a_usable_hint_paints_nothing(leaf):
    tui, pointer, _ = mounted(leaf)
    before = rows_text(tui)
    pointer.handle(motion(2, 0))
    tui.paint()
    assert rows_text(tui) == before


def test_a_pointer_that_never_moved_paints_nothing():
    leaf = Leaf(rows=2, hint="hidden")
    tui, _, _ = mounted(leaf)
    tui.paint()
    assert [row.text for row in tui.rows[:3]] == ["leaf0", "leaf1", ""]


def test_moving_off_the_leaf_takes_the_band_away():
    leaf = Leaf(hint="here")
    tui, pointer, _ = mounted(leaf, height=4)
    pointer.handle(motion(2, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "  here"
    pointer.handle(motion(2, 3))  # a blank cell: nothing is hovered any more
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", "", ""]


def test_the_band_flips_above_a_pointer_on_the_last_row():
    leaf = Leaf(rows=3, hint="<<flip>>")
    tui, pointer, _ = mounted(leaf, height=3)
    pointer.handle(motion(1, 1))  # room below: the band goes there
    tui.paint()
    assert "<<flip>>" in tui.rows[2].text
    tui.screen.height = 2  # the pointer's row is the last one now
    pointer.handle(motion(1, 1))
    tui.paint()
    assert "<<flip>>" in tui.rows[0].text  # the band flipped above it
    assert "<<flip>>" not in tui.rows[1].text


def test_the_band_is_clamped_into_the_frames_width():
    leaf = Leaf(hint="nineteen characters")
    tui, pointer, _ = mounted(leaf, width=20, height=3)
    pointer.handle(motion(18, 0))  # near the right edge: the band clamps left
    tui.paint()
    assert tui.rows[1].text == " nineteen characters"[:20]
    assert len(tui.rows[1].text) == 20


def test_a_hint_wider_than_a_narrow_frame_is_fit_to_it():
    leaf = Leaf(hint="a long hint")
    tui, pointer, _ = mounted(leaf, width=1, height=2)
    pointer.handle(motion(0, 0))
    tui.paint()
    assert len(tui.rows[1].text) == 1  # never wider than the frame


# --- the band's style ---------------------------------------------------------------


def test_the_band_paints_with_the_themes_toast_style():
    leaf = Leaf(hint="hi")
    band = Style(fg="#333333")
    tui, pointer, _ = mounted(leaf, theme=Theme(toast=band))
    pointer.handle(motion(0, 0))
    tui.paint()
    assert band in [seg.style for seg in tui.rows[1].segments]


# --- the lifecycle ------------------------------------------------------------------


def test_detach_unregisters_the_overlay_and_stops_the_paint():
    leaf = Leaf(hint="gone")
    tui, pointer, tooltip = mounted(leaf, height=3)
    assert any(held is tooltip for held in tui.frame.overlays)
    pointer.handle(motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "gone"  # the band is live
    tooltip.detach()
    assert all(held is not tooltip for held in tui.frame.overlays)
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", ""]  # the band left the frame
    tooltip.detach()  # idempotent


def test_a_hint_changed_under_a_live_pointer_shows_on_the_next_frame():
    leaf = Leaf(hint="old")
    tui, pointer, _ = mounted(leaf, height=4)
    pointer.handle(motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "old"
    leaf.hint = "new"  # the leaf restyles itself; the overlay caches nothing
    tui.paint()
    assert tui.rows[1].text.rstrip() == "new"


def test_a_host_repoints_the_band_by_mounting_the_new_pointers_tooltip():
    """The gallery's own rule: a page switch mounts a fresh pair."""
    leaf = Leaf(hint="left pane")
    tui, pointer, tooltip = mounted(leaf, height=3)
    pointer.handle(motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "left pane"
    tooltip.detach()  # the retarget: the old pointer's band goes with it
    fresh = Pointer(tui)
    Tooltip(tui, fresh)
    tui.paint()
    assert rows_text(tui) == ["leaf0", "", ""]  # the fresh pointer saw no motion
    fresh.handle(motion(0, 0))
    tui.paint()
    assert tui.rows[1].text.rstrip() == "left pane"
