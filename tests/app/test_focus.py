"""FocusManager: registration, cycling, traps, routing and the click policy."""

from __future__ import annotations

import pytest

from motui.app import FocusManager
from motui.kernel import Section, Document, Pane, Rect, Viewport
from motui.kernel.document import Activable, Focusable, descend_chain
from motui.kernel.events import KeyEvent
from motui.kernel.hit import Hit
from motui.kernel.cell import Line
from motui.widgets import Padding


class Plain:
    """A focusable target with nothing but its flag."""

    def __init__(self) -> None:
        self.focused = True

    def render(self, width: int) -> list[Line]:
        return [Line.from_text("plain").fit(width)]


class Cursor(Plain):
    """A list-shaped target: ``move(delta)`` records the signed step."""

    def __init__(self) -> None:
        super().__init__()
        self.steps: list[int] = []

    def move(self, delta: int) -> bool:
        self.steps.append(delta)
        return True


class Field(Plain):
    """A field-shaped target: its ``handle`` consumes everything first."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list = []
        self.steps: list[int] = []

    def handle(self, event) -> bool:
        self.handled.append(event)
        return True

    def move(self, delta: int) -> bool:
        self.steps.append(delta)
        return True


class SoftField(Plain):
    """A field that consumes only its own keys."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list = []

    def handle(self, event) -> bool:
        self.handled.append(event)
        return getattr(event, "key", "") == "backspace"


class Vertical(Plain):
    """A text-field shape: only the vertical arrow verbs."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def move_up(self) -> bool:
        self.calls.append("move_up")
        return True

    def move_down(self) -> bool:
        self.calls.append("move_down")
        return True


class Pick(Plain):
    """An activable target."""

    def __init__(self, answer: bool = True) -> None:
        super().__init__()
        self.answer = answer
        self.activations = 0

    def activate(self) -> bool:
        self.activations += 1
        return self.answer


class Strip(Plain):
    """A clickable and activable target (a menu row)."""

    def __init__(self, *, answer: bool = True, activation: bool = True) -> None:
        super().__init__()
        self.answer = answer
        self.activation = activation
        self.cells: list[tuple[int, int]] = []
        self.activations = 0

    def click(self, row: int, col: int) -> bool:
        self.cells.append((row, col))
        return self.answer

    def activate(self) -> bool:
        self.activations += 1
        return self.activation


class RouteOnly:
    """A non-Focusable route target (a Dialog's shape)."""

    def __init__(self) -> None:
        self.seen: list = []

    def handle(self, event) -> bool:
        self.seen.append(event)
        return True


def hit(component, row: int = 1, col: int = 2) -> Hit:
    pane = Pane("p0", Rect(x=0, y=0, width=0, height=0), Viewport(Document()))
    block = Section("b0", component)
    return Hit(pane, block, row, col, descend_chain(component, row, col))


# -- registration and cycling ------------------------------------------------


def test_targets_are_the_registered_components_in_cycle_order():
    a, b = Cursor(), Cursor()
    assert FocusManager([a, b]).targets == (a, b)


def test_construction_focuses_nothing_and_touches_no_flag():
    a, b = Cursor(), Cursor()
    manager = FocusManager([a, b])
    assert manager.focused is None
    assert (a.focused, b.focused) == (True, True)
    assert manager.handle(KeyEvent("down")) is False


def test_an_empty_manager_declines_every_verb():
    manager = FocusManager()
    assert manager.targets == () and manager.focused is None
    assert manager.focus(Cursor()) is False
    assert manager.focus_next() is False
    assert manager.focus_next(-1) is False
    assert manager.handle(KeyEvent("enter")) is False
    assert manager.click(hit(Plain())) is False


def test_a_non_focusable_target_is_a_route_target():
    route = RouteOnly()
    manager = FocusManager([route])
    assert not isinstance(route, Focusable)
    assert manager.focus_next() is True and manager.focused is route
    assert manager.handle(KeyEvent("down")) is True
    assert len(route.seen) == 1


def test_focus_flips_every_registered_flag():
    a, b = Cursor(), Cursor()
    manager = FocusManager([a, b])
    assert manager.focus(a) is True
    assert (a.focused, b.focused) == (True, False)
    assert manager.focus(b) is True
    assert (a.focused, b.focused) == (False, True)


def test_focusing_an_unregistered_or_current_target_is_a_false_no_op():
    a, stranger = Cursor(), Cursor()
    manager = FocusManager([a])
    manager.focus_next()
    assert manager.focus(stranger) is False
    assert manager.focused is a and stranger.focused is True
    assert manager.focus(a) is False


def test_add_appends_and_refuses_a_duplicate_without_moving_focus():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a])
    assert manager.add(b) is True
    assert manager.add(c) is True
    assert manager.add(b) is False
    assert manager.targets == (a, b, c)
    assert manager.focused is None


def test_remove_clears_the_focus_only_when_it_held_it():
    a, b = Cursor(), Cursor()
    changes: list = []
    manager = FocusManager([a, b], on_change=changes.append)
    manager.focus_next()
    assert manager.remove(b) is True
    assert manager.focused is a and changes == [a]
    assert manager.remove(a) is True
    assert manager.focused is None and a.focused is False
    assert changes == [a, None]
    assert manager.remove(a) is False


def test_focus_next_walks_and_wraps_both_ways():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a, b, c])
    assert manager.focus_next() is True and manager.focused is a
    assert manager.focus_next(2) is True and manager.focused is c
    assert manager.focus_next(1) is True and manager.focused is a
    assert manager.focus_next(-1) is True and manager.focused is c
    assert manager.focus_previous() is True and manager.focused is b


def test_a_non_wrapping_manager_clamps_at_both_ends():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a, b, c], wrap=False)
    assert manager.focus_next() is True and manager.focused is a
    assert manager.focus_next(-1) is False and manager.focused is a
    assert manager.focus_next(9) is True and manager.focused is c
    assert manager.focus_next(9) is False and manager.focused is c


def test_push_trap_narrows_and_pop_restores_the_layer_below():
    a, b, route = Cursor(), Cursor(), RouteOnly()
    manager = FocusManager([a, b])
    manager.focus_next()
    manager.push_trap([route])
    assert manager.targets == (route,) and manager.focused is route
    assert a.focused is False
    assert manager.handle(KeyEvent("down")) is True
    manager.pop_trap()
    assert manager.targets == (a, b) and manager.focused is a
    assert (a.focused, b.focused) == (True, False)


def test_traps_nest_and_unwind_in_order():
    a, b, first, second = Cursor(), Cursor(), RouteOnly(), RouteOnly()
    manager = FocusManager([a, b])
    manager.focus_next()
    manager.push_trap([first])
    manager.push_trap([second])
    assert manager.targets == (second,)
    manager.pop_trap()
    assert manager.targets == (first,)
    manager.pop_trap()
    assert manager.targets == (a, b) and manager.focused is a


def test_an_empty_trap_holds_no_focus_and_restores_the_previous_one():
    a, changes = Cursor(), []
    manager = FocusManager([a], on_change=changes.append)
    manager.focus_next()
    changes.clear()
    manager.push_trap([])
    assert manager.targets == () and manager.focused is None
    assert a.focused is False and changes == [None]
    manager.pop_trap()
    assert manager.targets == (a,) and manager.focused is a
    assert changes == [None, a]


def test_pop_trap_without_a_push_is_an_error():
    with pytest.raises(IndexError):
        FocusManager().pop_trap()


# -- keyboard routing --------------------------------------------------------


def test_the_focused_targets_handle_goes_first():
    field, other = Field(), Cursor()
    manager = FocusManager([field, other])
    manager.focus_next()
    for name in ("down", "enter", "backspace"):
        event = KeyEvent(name)
        assert manager.handle(event) is True
        assert field.handled[-1] == event
    assert field.steps == []


def test_a_declined_handle_falls_through_to_the_manager_table():
    field = SoftField()
    manager = FocusManager([field])
    manager.focus_next()
    assert manager.handle(KeyEvent("backspace")) is True
    assert manager.handle(KeyEvent("down")) is False
    assert [getattr(event, "key", "") for event in field.handled] == [
        "backspace",
        "down",
    ]


def test_a_target_without_move_falls_back_to_its_arrow_verbs():
    vertical = Vertical()
    manager = FocusManager([vertical])
    manager.focus_next()
    assert manager.handle(KeyEvent("up")) is True
    assert manager.handle(KeyEvent("down")) is True
    assert vertical.calls == ["move_up", "move_down"]
    assert manager.handle(KeyEvent("left")) is False


def test_enter_activates_an_activable_target():
    pick = Pick()
    manager = FocusManager([pick])
    manager.focus_next()
    assert isinstance(pick, Activable)
    assert manager.handle(KeyEvent("enter")) is True
    assert pick.activations == 1


def test_every_other_event_is_left_to_the_host():
    pick = Pick()
    manager = FocusManager([pick])
    manager.focus_next()
    for name in ("escape", "tab", "c-c", "page_up", "q"):
        assert manager.handle(KeyEvent(name)) is False
    assert pick.activations == 0


# -- click policy ------------------------------------------------------------


def test_a_click_on_a_non_target_clickable_is_dispatched_and_stops_there():
    target = Cursor()
    mouse_only = Strip()
    manager = FocusManager([target])
    manager.focus_next()
    assert manager.click(hit(mouse_only, row=3, col=7)) is True
    assert mouse_only.cells == [(3, 7)]
    assert manager.focused is target


def test_the_first_click_focuses_and_the_second_activates():
    first, second = Strip(), Strip(activation=False)
    manager = FocusManager([first, second])
    manager.focus_next()
    assert manager.click(hit(second)) is True
    assert manager.focused is second and second.activations == 0
    assert manager.click(hit(second)) is True
    assert second.activations == 1
    assert second.cells == [(1, 2), (1, 2)]


def test_a_click_through_a_container_lands_on_the_leaf_target():
    from motui.widgets.choice import Option, Select

    menu = Select([Option("one"), Option("two")])
    other = Select([Option("x")])
    padded = Padding(menu, left=2, top=1)
    padded.render(20)
    manager = FocusManager([other, menu])
    manager.focus_next()
    assert manager.click(hit(padded, row=1, col=2)) is True
    assert manager.focused is menu
    assert manager.click(hit(padded, row=1, col=2)) is True
    assert menu.take_result() == Option("one")


def test_the_arrows_call_move_with_the_signed_delta():
    cursor = Cursor()
    manager = FocusManager([cursor])
    manager.focus_next()
    for name, delta in (("up", -1), ("left", -1), ("down", 1), ("right", 1)):
        assert manager.handle(KeyEvent(name)) is True
        assert cursor.steps[-1] == delta
