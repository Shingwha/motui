"""Tests for the focus tier: FocusManager's registration, cycling, routing, clicks.

The manager owns *who* is focused -- components only carry the flag.  The
constructor focuses nothing; ``focus_next`` from that state picks the first
target (the last for a negative delta); a move rewrites every ``Focusable``
target's flag; ``focus_next`` cycles (wrapping by default); ``handle`` routes
by the class's own table (the focused target's ``handle`` first, then the
arrows/``enter`` verbs, everything else declined); ``click`` runs the
four-step policy -- dispatch any clickable component's cell, focus a
registered target, activate on the second click, answer whether anything
consumed the click.  ``add``/``remove`` maintain the cycle, ``on_change``
fires after a real move, and traps narrow/restore the target set for nested
modals.  A non-``Focusable`` target is still a legal routing target.
"""

from __future__ import annotations

import pytest

from motui.interaction import FocusManager
from motui.kernel import Block, Document, Pane, Rect, Viewport
from motui.kernel.block import Activable, Clickable, Focusable
from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent
from motui.kernel.host import Hit
from motui.kernel.lines import Line
from motui.widgets import Padding, TreeNode

# --- the doubles ---------------------------------------------------------------


class Plain:
    """The minimum Focusable: one flag and a render."""

    def __init__(self) -> None:
        self.focused = True

    def render(self, width: int) -> list[Line]:
        return [Line.from_text("plain").fit(width)]


class Cursor(Plain):
    """A list target: ``move(delta)`` steps its cursor and answers ``True``."""

    def __init__(self) -> None:
        super().__init__()
        self.index = 0
        self.steps: list[int] = []

    def move(self, delta: int) -> bool:
        self.steps.append(delta)
        self.index += delta
        return True


class Field(Plain):
    """A field target: its ``handle`` consumes everything, ahead of any verb."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list = []
        self.moves: list[int] = []

    def handle(self, event) -> bool:
        self.handled.append(event)
        return True

    def move(self, delta: int) -> bool:
        self.moves.append(delta)  # only reachable when ``handle`` declines
        return True


class SoftField(Plain):
    """A field that consumes only its own editing keys (the TextBuffer shape)."""

    def __init__(self, consumes: tuple[str, ...] = ("backspace",)) -> None:
        super().__init__()
        self.consumes = set(consumes)
        self.handled: list = []

    def handle(self, event) -> bool:
        self.handled.append(event)
        return getattr(event, "key", "") in self.consumes


class Vertical(Plain):
    """A text field's shape: no ``move``, only the ``move_up``/``move_down`` pair."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def move_up(self) -> bool:
        self.calls.append("move_up")
        return True

    def move_down(self) -> bool:
        self.calls.append("move_down")
        return True


class LeftRight(Plain):
    """The other half of the pair: only ``move_left``/``move_right``."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def move_left(self) -> bool:
        self.calls.append("move_left")
        return True

    def move_right(self) -> bool:
        self.calls.append("move_right")
        return True


class Pick(Plain):
    """An Activable target: ``activate()`` counts and answers as configured."""

    def __init__(self, answer: bool = True) -> None:
        super().__init__()
        self.answer = answer
        self.activations = 0

    def activate(self) -> bool:
        self.activations += 1
        return self.answer


class ClickOnly(Plain):
    """A clickable target without ``activate`` -- a tab strip's real shape."""

    def __init__(self, answer: bool = True) -> None:
        super().__init__()
        self.answer = answer
        self.cells: list[tuple[int, int]] = []

    def click(self, row: int, col: int) -> bool:
        self.cells.append((row, col))
        return self.answer


class Strip(ClickOnly):
    """The full target shape: clickable *and* activable (a menu)."""

    def __init__(self, *, answer: bool = True, activation: bool = True) -> None:
        super().__init__(answer)
        self.activation = activation
        self.activations = 0

    def activate(self) -> bool:
        self.activations += 1
        return self.activation


class MouseOnly:
    """A clickable component that is not a manager target (a mouse-only widget)."""

    def __init__(self, answer: bool = True) -> None:
        self.answer = answer
        self.cells: list[tuple[int, int]] = []

    def click(self, row: int, col: int) -> bool:
        self.cells.append((row, col))
        return self.answer


class RouteOnly:
    """A non-Focusable route target (a Dialog's shape): ``handle`` only."""

    def __init__(self) -> None:
        self.seen: list = []

    def handle(self, event) -> bool:
        self.seen.append(event)
        return True


def hit(component, row: int = 1, col: int = 2) -> Hit:
    """One hit-test result on a fresh block holding ``component``."""
    pane = Pane("p0", Rect(0, 0, 0, 0), Viewport(Document()))
    return Hit(pane, Block("b0", component), row, col)


# --- construction, registration, cycling ----------------------------------------


def test_the_targets_are_the_registered_components_in_cycle_order():
    a, b = Cursor(), Cursor()
    manager = FocusManager([a, b])
    assert manager.targets == (a, b)


def test_construction_does_not_focus_and_touches_no_flag():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a, b, c])
    assert manager.focused is None
    # A hostile start is left exactly as it was: the constructor writes nothing.
    assert (a.focused, b.focused, c.focused) == (True, True, True)
    assert manager.handle(KeyEvent("down")) is False


def test_an_empty_manager_declines_everything():
    manager = FocusManager()
    assert manager.targets == () and manager.focused is None
    assert manager.focus(Cursor()) is False
    assert manager.focus_next() is False
    assert manager.focus_next(-1) is False
    assert manager.focus_previous() is False
    assert manager.handle(KeyEvent("down")) is False
    assert manager.handle(KeyEvent("enter")) is False
    assert manager.handle(PasteEvent("text")) is False
    assert manager.click(hit(Plain())) is False


def test_a_non_focusable_target_is_a_routing_target_not_an_error():
    route = RouteOnly()
    manager = FocusManager([route])
    assert not isinstance(route, Focusable)
    assert manager.focus_next() is True and manager.focused is route
    assert manager.handle(KeyEvent("down")) is True
    assert len(route.seen) == 1
    assert not hasattr(route, "focused")  # no flag was written


def test_focus_moves_between_two_targets_and_flips_both_flags():
    a, b = Cursor(), Cursor()
    manager = FocusManager([a, b])
    assert manager.focus(a) is True
    assert manager.focused is a
    assert (a.focused, b.focused) == (True, False)
    assert manager.focus(b) is True
    assert manager.focused is b
    assert (a.focused, b.focused) == (False, True)


def test_focusing_an_unregistered_target_is_a_false_no_op():
    a, b, stranger = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a, b])
    manager.focus_next()
    assert manager.focus(stranger) is False
    assert manager.focused is a
    assert stranger.focused is True  # untouched: the manager only rewrites its own


def test_focusing_the_current_target_changes_nothing():
    a, b = Cursor(), Cursor()
    manager = FocusManager([a, b])
    manager.focus_next()
    assert manager.focus(a) is False
    assert manager.focused is a


def test_add_appends_in_order_and_refuses_a_duplicate():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a])
    assert manager.add(b) is True
    assert manager.add(c) is True
    assert manager.add(b) is False  # identity duplicate
    assert manager.targets == (a, b, c)
    assert manager.focused is None  # adding never moves the focus


def test_remove_drops_a_target_and_clears_the_focus_when_it_was_focused():
    a, b = Cursor(), Cursor()
    changes: list = []
    manager = FocusManager([a, b], on_change=changes.append)
    manager.focus_next()
    assert manager.remove(b) is True
    assert manager.targets == (a,)
    assert manager.focused is a and changes == [a]
    assert manager.remove(a) is True
    assert manager.targets == () and manager.focused is None
    assert a.focused is False
    assert changes == [a, None]
    assert manager.remove(a) is False  # already gone


def test_remove_of_a_non_focused_target_leaves_the_focus_and_notifies_nothing():
    a, b = Cursor(), Cursor()
    changes: list = []
    manager = FocusManager([a, b], on_change=changes.append)
    manager.focus_next()
    changes.clear()
    assert manager.remove(b) is True
    assert manager.focused is a and changes == []


def test_on_change_fires_after_a_real_move_only():
    a, b = Cursor(), Cursor()
    changes: list = []
    manager = FocusManager([a, b], on_change=changes.append)
    assert changes == []  # construction is silent
    manager.focus_next()
    assert changes == [a]
    manager.focus(a)  # already focused
    assert changes == [a]
    manager.focus(b)
    assert changes == [a, b]
    manager.focus_next(-1)
    assert changes == [a, b, a]


def test_focus_next_walks_forward_and_wraps_around():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a, b, c])
    assert manager.focus_next() is True and manager.focused is a  # from no focus
    assert manager.focus_next() is True and manager.focused is b
    assert manager.focus_next(2) is True and manager.focused is a  # wrapped past the end
    assert manager.focus_next(1) is True and manager.focused is b
    assert manager.focus_next(-1) is True and manager.focused is a  # and backwards
    assert manager.focus_next(-1) is True and manager.focused is c  # off the front
    assert manager.focus_previous() is True and manager.focused is b


def test_focus_next_from_no_focus_picks_the_delta_edge():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a, b, c])
    assert manager.focus_next(2) is True and manager.focused is a
    manager2 = FocusManager([a, b, c])
    assert manager2.focus_next(-1) is True and manager2.focused is c
    manager3 = FocusManager([a, b, c])
    assert manager3.focus_next(0) is False and manager3.focused is None


def test_a_non_wrapping_manager_clamps_at_both_ends():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a, b, c], wrap=False)
    assert manager.focus_next() is True and manager.focused is a
    assert manager.focus_next(-1) is False and manager.focused is a  # clamped at the top
    assert manager.focus_next(9) is True and manager.focused is c  # clamped at the bottom
    assert manager.focus_next(9) is False and manager.focused is c  # already there


def test_a_single_target_manager_never_moves_after_the_first_step():
    only = Cursor()
    manager = FocusManager([only])
    assert manager.focus_next() is True and manager.focused is only
    assert manager.focus_next() is False
    assert manager.focus_next(-1) is False
    assert manager.focused is only and only.focused is True


# --- traps -----------------------------------------------------------------------


def test_push_trap_narrows_the_targets_and_pop_restores_them():
    a, b, route = Cursor(), Cursor(), RouteOnly()
    manager = FocusManager([a, b])
    manager.focus_next()  # a
    manager.push_trap([route])
    assert manager.targets == (route,)
    assert manager.focused is route
    assert a.focused is False  # the escapee's flag is cleared
    assert manager.handle(KeyEvent("down")) is True  # routed to the trapped dialog
    manager.pop_trap()
    assert manager.targets == (a, b)
    assert manager.focused is a
    assert (a.focused, b.focused) == (True, False)


def test_traps_nest_and_unwind_in_order():
    a, b, first, second = Cursor(), Cursor(), RouteOnly(), RouteOnly()
    manager = FocusManager([a, b])
    manager.focus_next()
    manager.push_trap([first])
    manager.push_trap([second])
    assert manager.targets == (second,) and manager.focused is second
    manager.pop_trap()
    assert manager.targets == (first,) and manager.focused is first
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
    assert a.focused is True and changes == [None, a]


def test_pop_trap_without_a_push_is_an_error():
    manager = FocusManager()
    with pytest.raises(IndexError):
        manager.pop_trap()


# --- handle: the routing table ---------------------------------------------------


def test_a_focused_fields_handle_goes_first_and_beats_the_manager_verbs():
    field, other = Field(), Cursor()
    manager = FocusManager([field, other])
    manager.focus_next()
    for name in ("down", "up", "enter", "backspace"):
        event = KeyEvent(name)
        assert manager.handle(event) is True
        assert field.handled[-1] == event
    assert field.moves == []  # the manager's own move never ran
    paste = PasteEvent("text")
    assert manager.handle(paste) is True
    assert field.handled[-1] == paste  # a paste is the field's too


def test_a_declined_handle_falls_through_to_the_manager_table():
    field = SoftField(consumes=("backspace",))
    manager = FocusManager([field])
    manager.focus_next()
    assert manager.handle(KeyEvent("backspace")) is True  # the field took its own key
    assert manager.handle(KeyEvent("down")) is False  # declined, and the field has no move
    assert [getattr(e, "key", "") for e in field.handled] == ["backspace", "down"]


@pytest.mark.parametrize(
    "name, delta",
    [("up", -1), ("left", -1), ("down", 1), ("right", 1)],
)
def test_the_arrows_call_move_with_the_signed_delta(name, delta):
    cursor = Cursor()
    manager = FocusManager([cursor])
    manager.focus_next()
    assert manager.handle(KeyEvent(name)) is True
    assert cursor.steps == [delta]
    assert cursor.index == delta


def test_a_target_without_move_falls_back_to_its_own_arrow_verb():
    vertical = Vertical()
    manager = FocusManager([vertical])
    manager.focus_next()
    assert manager.handle(KeyEvent("up")) is True and vertical.calls == ["move_up"]
    assert manager.handle(KeyEvent("down")) is True and vertical.calls == ["move_up", "move_down"]
    assert manager.handle(KeyEvent("left")) is False  # no move_left on this shape
    assert manager.handle(KeyEvent("right")) is False
    assert vertical.calls == ["move_up", "move_down"]  # nothing ran for the misses


def test_a_target_with_only_the_horizontal_verbs_answers_left_and_right():
    side = LeftRight()
    manager = FocusManager([side])
    manager.focus_next()
    assert manager.handle(KeyEvent("left")) is True and side.calls == ["move_left"]
    assert manager.handle(KeyEvent("right")) is True
    assert side.calls == ["move_left", "move_right"]
    assert manager.handle(KeyEvent("up")) is False  # this shape has no move_up
    assert manager.handle(KeyEvent("down")) is False


def test_enter_activates_an_activable_target():
    pick = Pick()
    manager = FocusManager([pick])
    manager.focus_next()
    assert isinstance(pick, Activable)
    assert manager.handle(KeyEvent("enter")) is True
    assert pick.activations == 1


def test_enter_on_a_target_that_is_not_activable_is_false():
    plain = Plain()
    manager = FocusManager([plain])
    manager.focus_next()
    assert not isinstance(plain, Activable)
    assert manager.handle(KeyEvent("enter")) is False


def test_an_activation_that_takes_nothing_answers_its_own_false():
    pick = Pick(answer=False)
    manager = FocusManager([pick])
    manager.focus_next()
    assert manager.handle(KeyEvent("enter")) is False
    assert pick.activations == 1  # the verb ran; the answer was "nothing to take"


def test_every_other_event_is_left_to_the_host():
    pick = Pick()
    manager = FocusManager([pick])
    manager.focus_next()
    for name in ("escape", "tab", "c-c", "page_up", "space", "q"):
        assert manager.handle(KeyEvent(name)) is False
    assert manager.handle(MouseEvent("left", x=1, y=2)) is False  # the click path's
    assert pick.activations == 0


# --- click: the four-step policy --------------------------------------------------


def test_a_click_on_a_non_target_clickable_is_dispatched_and_stops_there():
    target, mouse_only = Cursor(), MouseOnly()
    manager = FocusManager([target])
    manager.focus_next()
    assert manager.click(hit(mouse_only, row=3, col=7)) is True
    assert mouse_only.cells == [(3, 7)]  # its own cell, exactly as hit-tested
    assert manager.focused is target  # the manager's focus never moved
    assert target.focused is True


def test_a_click_that_nothing_consumes_answers_false():
    target = Cursor()
    manager = FocusManager([target])
    manager.focus_next()
    assert manager.click(hit(Plain())) is False  # not clickable, not registered
    assert manager.click(hit(MouseOnly(answer=False))) is False  # clickable, declined
    assert manager.focused is target


def test_the_first_click_on_a_target_only_focuses_it():
    first, second = Strip(), ClickOnly()
    manager = FocusManager([first, second])
    manager.focus_next()  # the focus starts on ``first``
    assert manager.click(hit(second, row=0, col=11)) is True
    assert manager.focused is second
    assert (first.focused, second.focused) == (False, True)
    assert second.cells == [(0, 11)]  # the cell was dispatched on the way
    assert first.activations == 0


def test_the_first_click_answers_true_even_when_the_component_click_missed():
    first, second = Strip(), ClickOnly(answer=False)
    manager = FocusManager([first, second])
    manager.focus_next()
    assert manager.click(hit(second)) is True  # the manager consumed it by focusing
    assert second.focused is True and manager.focused is second


def test_the_second_click_on_the_target_activates_it():
    first, second = Strip(), Strip(activation=False)
    manager = FocusManager([first, second])
    manager.focus_next()
    assert manager.click(hit(second)) is True  # the first click: focus only
    assert (first.activations, second.activations) == (0, 0)
    assert manager.click(hit(second)) is True  # the second click: activate
    assert second.activations == 1
    assert (first.activations, second.activations) == (0, 1)
    assert second.cells == [(1, 2), (1, 2)]  # both clicks dispatched their cell


def test_a_click_on_the_target_that_already_holds_the_focus_activates_at_once():
    strip = Strip()
    manager = FocusManager([strip])
    manager.focus_next()  # the focus lands on it
    assert manager.click(hit(strip)) is True
    assert strip.activations == 1


def test_a_focused_non_activable_answers_its_own_click():
    strip = ClickOnly(answer=False)  # focused, clickable, not Activable
    manager = FocusManager([strip])
    manager.focus_next()
    assert not isinstance(strip, Activable)
    assert manager.click(hit(strip, row=4, col=5)) is False
    assert strip.cells == [(4, 5)]


def test_the_activation_answers_a_focused_targets_click():
    pick = Pick(answer=False)  # Activable, not Clickable
    manager = FocusManager([pick])
    manager.focus_next()
    assert manager.click(hit(pick)) is False  # the activation ran and took nothing
    assert pick.activations == 1


# --- with the real widgets --------------------------------------------------------


def test_a_manager_of_real_widgets_focuses_and_dims_them():
    from motui.widgets.choice import Option, Select
    from motui.widgets.tree import Tree

    menu = Select([Option("one"), Option("two")])
    tree = Tree([TreeNode("node")])
    manager = FocusManager([menu, tree])
    manager.focus_next()
    assert isinstance(menu, Clickable) and isinstance(tree, Clickable)
    assert (menu.focused, tree.focused) == (True, False)
    assert manager.handle(KeyEvent("down")) is True and menu.index == 1  # the menu moved
    assert manager.handle(KeyEvent("enter")) is True and menu.take_result() == Option("two")
    assert manager.focus_next() is True
    assert (menu.focused, tree.focused) == (False, True)
    assert manager.handle(KeyEvent("enter")) is False  # a leaf: nothing to fold


def test_a_click_through_a_container_lands_on_the_leaf_target():
    """The hit names the wrapper; the manager descends before dispatch/focus."""
    from motui.widgets.choice import Option, Select

    menu = Select([Option("one"), Option("two")])
    other = Select([Option("x")])
    padded = Padding(menu, left=2, top=1)
    padded.render(20)  # the geometry ``child_at`` reads
    manager = FocusManager([other, menu])
    manager.focus_next()  # ``other`` holds the focus first
    # Wrapper cell (1, 2) is inside the insets: the menu's own (0, 0).
    through = hit(padded, row=1, col=2)
    assert manager.click(through) is True  # the first click focuses the leaf
    assert manager.focused is menu and menu.focused is True and other.focused is False
    assert manager._registered(padded) is False  # the wrapper is not a target
    assert manager.click(through) is True  # the second activates the leaf
    assert menu.take_result() == Option("one")


def test_a_click_through_a_container_translates_the_cell_for_the_leaf():
    """The descend translates columns: a wrapped Tabs resolves its own cell."""
    from motui.widgets.tabs import Tabs

    strip = Tabs(["a", "bb"])
    padded = Padding(strip, left=3)
    padded.render(20)
    manager = FocusManager([strip])
    manager.focus_next()
    # The strip paints " a │ bb ": its cell 6 is inside "bb"; wrapper cell 9
    # is that same column behind the 3-cell inset.
    assert manager.click(hit(padded, row=0, col=3 + 6)) is True
    assert strip.index == 1
