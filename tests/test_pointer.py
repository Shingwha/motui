"""Tests for the pointer tier: hover tracking and stationary clicks.

The pointer watches mouse reports beside the selection gesture: a button-free
motion flips the hover of the leaf under the cell and answers whether a
repaint is needed, a drag's motion drops the pending click, and a press and
release on one cell dispatch the click through the mounted ring (or to the
deepest clickable leaf).  Everything runs headless -- a real ``TUI`` over a
``HeadlessScreen``, cells resolved through the frame's ownership table --
and the last test drives the documented wiring: the gesture and the pointer
both fed every report of one scripted session.
"""

from __future__ import annotations

import pytest

from motui.app import TUI
from motui.core.events import Key, MouseEvent, Paste, ScriptedKeys
from motui.core.lines import Line, Text
from motui.core.screen import HeadlessScreen
from motui.focus import FocusRing
from motui.gesture import SelectionGesture
from motui.keys import KeyDecoder
from motui.pointer import Pointer
from motui.widgets.button import Button
from motui.widgets.choice import Option, Select
from motui.widgets.layout import Padding


def motion(x: int, y: int, *, button: int = 0) -> MouseEvent:
    """A motion report at a 0-based cell; ``button`` 0 = none (the decode of
    SGR's motion bit with no held button)."""
    return MouseEvent("motion", button=button, x=x, y=y, kind="motion")


def press(x: int, y: int) -> MouseEvent:
    return MouseEvent("left", button=0, x=x, y=y, kind="press")


def release(x: int, y: int) -> MouseEvent:
    return MouseEvent("left", button=0, x=x, y=y, kind="release")


class HoverLeaf:
    """A hoverable, clickable leaf: the pointer's minimum target."""

    def __init__(self, rows: int = 1) -> None:
        self.hover = False
        self.clicks: list[tuple[int, int]] = []
        self.rows = rows

    def render(self, width: int) -> list[Line]:
        return [Line.from_text(f"leaf{i}") for i in range(self.rows)]

    def click(self, row: int, col: int) -> bool:
        self.clicks.append((row, col))
        return True


class RowLeaf(HoverLeaf):
    """A row-level leaf: ``hover_at`` records which of its rows the pointer is on."""

    def __init__(self, rows: int = 3) -> None:
        super().__init__(rows)
        self.hover_row: int | None = None

    def hover_at(self, row: int, col: int) -> bool:
        target = None if row < 0 else row
        changed = target != self.hover_row
        self.hover_row = target
        return changed


def _tui(*components, width: int = 40, height: int = 8) -> TUI:
    """A painted headless TUI holding ``components`` as one block per component."""
    tui = TUI(screen=HeadlessScreen(width, height, hover=True), interactive=False)
    for component in components:
        tui.add(component)
    tui.paint()  # the hit test reads the frame's ownership table
    return tui


# --- hover tracking ---------------------------------------------------------------


def test_a_button_free_motion_enters_the_leaf_and_flips_its_hover():
    leaf = HoverLeaf()
    tui = _tui(leaf)
    pointer = Pointer(tui)
    assert (pointer.hovered, pointer.position) == (None, None)
    assert pointer.handle(motion(0, 0)) is True
    assert leaf.hover is True
    assert pointer.hovered is leaf
    assert pointer.position == (0, 0)


def test_motion_leaving_to_a_blank_cell_clears_the_hover():
    leaf = HoverLeaf()
    tui = _tui(leaf)
    pointer = Pointer(tui)
    pointer.handle(motion(0, 0))
    assert pointer.handle(motion(0, 1)) is True  # row 1 owns no block
    assert leaf.hover is False and pointer.hovered is None
    assert pointer.handle(motion(0, 1)) is False  # the same blank cell: nothing


def test_a_motion_on_the_same_cell_answers_no_change():
    leaf = HoverLeaf()
    pointer = Pointer(_tui(leaf))
    assert pointer.handle(motion(0, 0)) is True
    assert pointer.handle(motion(0, 0)) is False  # same component, no hover_at
    assert leaf.hover is True


def test_a_motion_within_one_component_moves_its_row_hover():
    leaf = RowLeaf(rows=3)
    pointer = Pointer(_tui(leaf))
    assert pointer.handle(motion(0, 0)) is True  # enter: hover on row 0
    assert (leaf.hover, leaf.hover_row) == (True, 0)
    assert pointer.handle(motion(0, 1)) is True  # another row of the same leaf
    assert leaf.hover_row == 1
    assert pointer.handle(motion(0, 1)) is False  # the same row: zero change
    assert pointer.handle(motion(0, 2)) is True
    assert leaf.hover_row == 2
    assert pointer.handle(motion(0, 3)) is True  # a blank cell: the row clears
    assert leaf.hover is False and leaf.hover_row is None


# --- the click ---------------------------------------------------------------------


def test_a_press_and_release_on_one_cell_dispatch_the_deepest_leaf():
    leaf = HoverLeaf()
    padded = Padding(leaf, left=2, top=1)
    tui = _tui(padded)
    pointer = Pointer(tui)
    assert pointer.handle(press(2, 1)) is False  # a press is only remembered
    assert pointer.handle(release(2, 1)) is True  # the stationary click landed
    assert leaf.clicks == [(0, 0)]  # the leaf's own coords, the wrapper descended


def test_a_release_that_ended_a_drag_dispatches_nothing():
    leaf = HoverLeaf()
    tui = _tui(leaf)
    pointer = Pointer(tui)
    pointer.handle(motion(0, 0))
    assert pointer.handle(press(0, 0)) is False
    assert pointer.handle(motion(3, 0, button=1)) is False  # a drag: hover intact
    assert leaf.hover is True
    assert pointer.handle(release(0, 0)) is False  # the press was dropped
    assert leaf.clicks == []


def test_a_click_on_a_blank_cell_answers_false():
    tui = _tui(HoverLeaf())
    pointer = Pointer(tui)
    pointer.handle(press(0, 4))
    assert pointer.handle(release(0, 4)) is False
    pointer.handle(press(-3, 90))  # outside every pane
    assert pointer.handle(release(-3, 90)) is False


def test_a_mounted_ring_runs_its_click_policy_on_the_leaf():
    menu = Select([Option("one"), Option("two")])
    other = Select([Option("x")])
    padded = Padding(menu, left=2, top=1)
    tui = _tui(padded)
    ring = FocusRing([other, menu])
    pointer = Pointer(tui, ring=ring)
    pointer.handle(press(3, 1))  # wrapper cell (1, 3) is the menu's (0, 1)
    assert pointer.handle(release(3, 1)) is True  # the first click focuses
    assert ring.focused is menu
    pointer.handle(press(3, 1))
    assert pointer.handle(release(3, 1)) is True  # the second activates
    assert menu.chosen == Option("one")


def test_a_click_no_clickable_leaf_owns_answers_false():
    class Declining(HoverLeaf):
        def click(self, row: int, col: int) -> bool:
            self.clicks.append((row, col))
            return False

    pointer = Pointer(_tui(Text("plain")))
    pointer.handle(press(0, 0))
    assert pointer.handle(release(0, 0)) is False  # not Clickable at all
    pointer = Pointer(_tui(Declining()))
    pointer.handle(press(0, 0))
    assert pointer.handle(release(0, 0)) is False  # clickable, declined
    assert pointer.position is None  # no motion was ever seen


def test_every_key_and_paste_is_left_alone():
    pointer = Pointer(_tui(HoverLeaf()))
    assert pointer.handle(Key("enter")) is False
    assert pointer.handle(Paste("text")) is False


def test_a_hover_false_pointer_keeps_its_hands_off_the_flags():
    leaf = HoverLeaf()
    pointer = Pointer(_tui(leaf), hover=False)
    assert pointer.handle(motion(0, 0)) is False
    assert leaf.hover is False and pointer.hovered is None
    assert pointer.position == (0, 0)  # the report is still recorded
    assert pointer.handle(press(0, 0)) is False
    assert pointer.handle(release(0, 0)) is True  # the click still dispatches
    assert leaf.clicks == [(0, 0)]


# --- lifecycle ----------------------------------------------------------------------


def test_clear_drops_the_hover_the_position_and_the_pending_click():
    leaf = RowLeaf(rows=2)
    pointer = Pointer(_tui(leaf))
    pointer.handle(motion(0, 1))
    pointer.handle(press(0, 1))
    pointer.clear()
    assert (leaf.hover, leaf.hover_row) == (False, None)
    assert (pointer.hovered, pointer.position) == (None, None)
    assert pointer.handle(release(0, 1)) is False  # the pending click is gone
    assert leaf.clicks == []


def test_detach_is_an_idempotent_inert_unmount():
    leaf = HoverLeaf()
    pointer = Pointer(_tui(leaf))
    pointer.handle(motion(0, 0))
    pointer.detach()
    assert leaf.hover is False and pointer.hovered is None
    assert pointer.handle(motion(0, 0)) is False
    assert pointer.handle(press(0, 0)) is False
    assert pointer.handle(release(0, 0)) is False
    pointer.detach()  # a second unmount is a no-op


# --- the documented wiring -----------------------------------------------------------


async def test_the_gesture_owns_the_reports_and_the_pointer_watches_them():
    """The reference loop: both see every report, neither starves the other."""
    leaf = HoverLeaf()
    tui = TUI(
        screen=HeadlessScreen(40, 8, hover=True),
        keys=ScriptedKeys([motion(0, 0), press(0, 0), release(0, 0), None]),
        interactive=False,
    )
    tui.add(leaf)
    tui.paint()
    gesture = SelectionGesture(tui)
    pointer = Pointer(tui)
    rounds: list[tuple[str, bool, bool]] = []
    while (event := await tui.read_key()) is not None:
        if isinstance(event, MouseEvent):
            rounds.append((event.kind, gesture.handle(event), pointer.handle(event)))
    assert rounds == [
        ("motion", False, True),  # the gesture has no drag: the pointer's hover
        ("press", True, False),  # the gesture anchors; the pointer remembers
        ("release", True, True),  # the gesture closes; the pointer clicks
    ]
    assert leaf.hover is True  # the hover stayed through the click
    assert leaf.clicks == [(0, 0)]
    assert tui.selection is None  # the zero-width press-release cleared it


def test_a_held_button_motion_keeps_its_hands_off_the_hover():
    """SGR 32 -> ``MouseEvent("left", button=0)``: a drag, not a hover.

    Mode 1002's motion report names the button it was sent with (the wire's
    32 is the motion bit plus the left button's low bits), so the pointer's
    motion branch reads the *name*: a button-named motion drops the pending
    click and touches neither the hover nor the recorded position, exactly
    as the hand-built ``button != 0`` spelling does.
    """
    leaf = HoverLeaf()
    tui = _tui(leaf)
    pointer = Pointer(tui)
    decoder = KeyDecoder()
    (drag,) = decoder.feed(b"\x1b[<32;1;1M")
    assert drag == MouseEvent("left", button=0, x=0, y=0, kind="motion")
    pointer.handle(press(0, 0))  # a pending click the drag must drop
    assert pointer.handle(drag) is False
    assert leaf.hover is False and pointer.position is None
    assert pointer.handle(release(0, 0)) is False  # the press was dropped
    assert leaf.clicks == []
    (hover,) = decoder.feed(b"\x1b[<35;1;1M")  # the button-free 35: the hover
    assert pointer.handle(hover) is True
    assert leaf.hover is True and pointer.position == (0, 0)


def test_a_none_named_button_free_motion_is_a_hover():
    """``name="none"`` (or any non-button name), ``button=0``: the hover road."""
    leaf = HoverLeaf()
    pointer = Pointer(_tui(leaf))
    assert pointer.handle(MouseEvent("none", button=0, x=0, y=0, kind="motion")) is True
    assert leaf.hover is True and pointer.position == (0, 0)


@pytest.mark.parametrize("name", ["left", "middle", "right"])
def test_a_button_named_motion_is_a_drag_whatever_its_button_field(name):
    """The name alone decides: a button-named motion with ``button=0`` is a drag."""
    leaf = HoverLeaf()
    pointer = Pointer(_tui(leaf))
    assert pointer.handle(motion(0, 0)) is True  # the hover first
    assert pointer.handle(MouseEvent(name, button=0, x=0, y=0, kind="motion")) is False
    assert leaf.hover is True  # untouched: the drag left the hover where it was
    assert pointer.position == (0, 0)  # and the position with it


# --- the wire chain (no real terminal) ------------------------------------------------


def test_button_free_motion_wire_bytes_drive_a_button_hover():
    """SGR bytes -> decoder -> Pointer.handle -> Button.hover, end to end.

    The wire's 35 (mode 1003's bare pointer move) decodes to the button-free
    ``MouseEvent("none", button=0)`` and drives the hover exactly as the
    hand-built ``motion()`` events above do -- the chain a real terminal
    closes needs no terminal here.
    """
    button = Button("go")
    tui = _tui(button)
    pointer = Pointer(tui)
    decoder = KeyDecoder()
    (enter,) = decoder.feed(b"\x1b[<35;1;1M")  # the pointer enters the button
    assert enter == MouseEvent("none", button=0, x=0, y=0, kind="motion")
    assert pointer.handle(enter) is True
    assert button.hover is True
    (again,) = decoder.feed(b"\x1b[<35;1;1M")  # the same cell: no change
    assert pointer.handle(again) is False
    assert button.hover is True
    (leave,) = decoder.feed(b"\x1b[<35;1;5M")  # a blank cell: the hover clears
    assert pointer.handle(leave) is True
    assert button.hover is False
