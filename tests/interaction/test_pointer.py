"""Pointer: hover tracking, stationary clicks and the gesture wiring."""

from __future__ import annotations

import pytest

from motui.app import TUI
from motui.interaction import FocusManager, Pointer, SelectionGesture
from motui.kernel import HeadlessScreen
from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent
from motui.kernel.lines import Line
from motui.keys import KeyDecoder
from motui.widgets import Padding
from motui.testing import ScriptedEvents
from tests.testing import headless_tui, motion, press, release


class Leaf:
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


class RowLeaf(Leaf):
    """A row-level leaf: ``hover_at`` records which of its rows is hovered."""

    def __init__(self, rows: int = 3) -> None:
        super().__init__(rows)
        self.hover_row: int | None = None

    def hover_at(self, row: int, col: int) -> bool:
        target = None if row < 0 else row
        changed = target != self.hover_row
        self.hover_row = target
        return changed


def _tui(*components, width: int = 40, height: int = 8) -> TUI:
    tui = TUI(screen=HeadlessScreen(width, height, hover=True), interactive=False)
    for component in components:
        tui.add(component)
    tui.paint()
    return tui


# -- hover -------------------------------------------------------------------


def test_a_button_free_motion_enters_the_leaf_and_flips_its_hover():
    leaf = Leaf()
    pointer = Pointer(_tui(leaf))
    assert (pointer.hovered, pointer.position) == (None, None)
    assert pointer.handle(motion(0, 0)) is True
    assert leaf.hover is True
    assert pointer.hovered is leaf and pointer.position == (0, 0)
    assert pointer.handle(motion(0, 0)) is False  # the same cell changes nothing


def test_motion_onto_a_blank_cell_clears_the_hover():
    leaf = Leaf()
    pointer = Pointer(_tui(leaf))
    pointer.handle(motion(0, 0))
    assert pointer.handle(motion(0, 1)) is True
    assert leaf.hover is False and pointer.hovered is None
    assert pointer.handle(motion(0, 1)) is False


def test_a_motion_within_one_component_moves_its_row_hover():
    leaf = RowLeaf(rows=3)
    pointer = Pointer(_tui(leaf))
    assert pointer.handle(motion(0, 0)) is True
    assert (leaf.hover, leaf.hover_row) == (True, 0)
    assert pointer.handle(motion(0, 1)) is True and leaf.hover_row == 1
    assert pointer.handle(motion(0, 1)) is False
    assert pointer.handle(motion(0, 3)) is True
    assert leaf.hover is False and leaf.hover_row is None


def test_a_hover_false_pointer_records_the_cell_but_touches_no_flag():
    leaf = Leaf()
    pointer = Pointer(_tui(leaf), hover=False)
    assert pointer.handle(motion(0, 0)) is False
    assert leaf.hover is False and pointer.hovered is None
    assert pointer.position == (0, 0)
    assert pointer.handle(press(0, 0)) is False
    assert pointer.handle(release(0, 0)) is True
    assert leaf.clicks == [(0, 0)]


# -- clicks ------------------------------------------------------------------


def test_a_press_and_release_on_one_cell_dispatch_the_deepest_leaf():
    leaf = Leaf()
    pointer = Pointer(_tui(Padding(leaf, left=2, top=1)))
    assert pointer.handle(press(2, 1)) is False
    assert pointer.handle(release(2, 1)) is True
    assert leaf.clicks == [(0, 0)]


def test_a_release_that_ended_a_drag_dispatches_nothing():
    leaf = Leaf()
    pointer = Pointer(_tui(leaf))
    pointer.handle(motion(0, 0))
    assert pointer.handle(press(0, 0)) is False
    assert pointer.handle(motion(3, 0, "left")) is False
    assert leaf.hover is True
    assert pointer.handle(release(0, 0)) is False
    assert leaf.clicks == []


def test_a_click_on_a_blank_cell_answers_false():
    pointer = Pointer(_tui(Leaf()))
    pointer.handle(press(0, 4))
    assert pointer.handle(release(0, 4)) is False
    pointer.handle(press(-3, 90))
    assert pointer.handle(release(-3, 90)) is False


def test_a_mounted_ring_runs_its_click_policy_on_the_leaf():
    from motui.widgets.choice import Option, Select

    menu = Select([Option("one"), Option("two")])
    other = Select([Option("x")])
    ring = FocusManager([other, menu])
    pointer = Pointer(_tui(Padding(menu, left=2, top=1)), ring=ring)
    pointer.handle(press(3, 1))
    assert pointer.handle(release(3, 1)) is True
    assert ring.focused is menu
    pointer.handle(press(3, 1))
    assert pointer.handle(release(3, 1)) is True
    assert menu.take_result() == Option("one")


def test_clear_drops_the_hover_the_position_and_the_pending_click():
    leaf = RowLeaf(rows=2)
    pointer = Pointer(_tui(leaf))
    pointer.handle(motion(0, 1))
    pointer.handle(press(0, 1))
    pointer.clear()
    assert (leaf.hover, leaf.hover_row) == (False, None)
    assert (pointer.hovered, pointer.position) == (None, None)
    assert pointer.handle(release(0, 1)) is False
    assert leaf.clicks == []


def test_detach_is_an_idempotent_inert_unmount():
    leaf = Leaf()
    pointer = Pointer(_tui(leaf))
    pointer.handle(motion(0, 0))
    pointer.detach()
    assert leaf.hover is False and pointer.hovered is None
    assert pointer.handle(motion(0, 0)) is False
    assert pointer.handle(press(0, 0)) is False
    assert pointer.handle(release(0, 0)) is False
    pointer.detach()


# -- the wire and the documented wiring --------------------------------------


async def test_the_gesture_owns_the_reports_and_the_pointer_watches_them():
    leaf = Leaf()
    tui = TUI(
        screen=HeadlessScreen(40, 8, hover=True),
        keys=ScriptedEvents([motion(0, 0), press(0, 0), release(0, 0), None]),
        interactive=False,
    )
    tui.add(leaf)
    tui.paint()
    gesture = SelectionGesture(tui)
    pointer = Pointer(tui)
    rounds: list[tuple[str, bool, bool]] = []
    while (event := await tui.read_event()) is not None:
        if isinstance(event, MouseEvent):
            rounds.append((event.kind, gesture.handle(event), pointer.handle(event)))
    assert rounds == [
        ("motion", False, True),
        ("press", True, False),
        ("release", True, True),
    ]
    assert leaf.hover is True
    assert leaf.clicks == [(0, 0)]
    assert tui.selection is None
