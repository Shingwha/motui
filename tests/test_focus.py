"""Tests for the focus tier: FocusRing's registration, cycling, routing, clicks.

The ring owns *who* is focused -- components only carry the flag.  The
constructor validates every target against ``Focusable`` and lands the
focus on the first; a move rewrites every target's ``focused`` flag;
``focus_next`` cycles (wrapping by default); ``handle`` routes by the
class's own table (the focused target's ``handle`` first, then the
arrows/``enter`` verbs, everything else declined); and ``click`` runs the
four-step policy -- dispatch any clickable component's cell, focus a
registered target, activate on the second click, answer whether anything
consumed the click.
"""

from __future__ import annotations

import pytest

from motui.app import Hit
from motui.interaction import FocusRing
from motui.kernel import Block, Document, Pane, Rect, Viewport
from motui.kernel.block import Activable, Clickable, Focusable
from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent
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
    """A clickable component that is not a ring target (a mouse-only widget)."""

    def __init__(self, answer: bool = True) -> None:
        self.answer = answer
        self.cells: list[tuple[int, int]] = []

    def click(self, row: int, col: int) -> bool:
        self.cells.append((row, col))
        return self.answer


def hit(component, row: int = 1, col: int = 2) -> Hit:
    """One hit-test result on a fresh block holding ``component``."""
    pane = Pane("p0", Rect(0, 0, 0, 0), Viewport(Document()))
    return Hit(pane, Block("b0", component), row, col)


# --- construction, registration, cycling ----------------------------------------


def test_the_targets_are_the_registered_components_in_cycle_order():
    a, b = Cursor(), Cursor()
    ring = FocusRing([a, b])
    assert ring.targets == (a, b)


def test_construction_focuses_the_first_target_and_clears_the_rest():
    a, b, c = Cursor(), Cursor(), Cursor()
    for target in (a, b, c):
        target.focused = True  # a hostile start: the ring rewrites every flag
    ring = FocusRing([a, b, c])
    assert ring.focused is a
    assert (a.focused, b.focused, c.focused) == (True, False, False)


def test_an_empty_ring_declines_everything():
    ring = FocusRing()
    assert ring.targets == () and ring.focused is None
    assert ring.focus(Cursor()) is False
    assert ring.focus_next() is False
    assert ring.focus_next(-1) is False
    assert ring.handle(KeyEvent("down")) is False
    assert ring.handle(KeyEvent("enter")) is False
    assert ring.handle(PasteEvent("text")) is False
    assert ring.click(hit(Plain())) is False


def test_a_non_focusable_target_raises_at_construction():
    with pytest.raises(TypeError):
        FocusRing([object()])
    with pytest.raises(TypeError):
        FocusRing([Cursor(), "not a component"])
    assert isinstance(Cursor(), Focusable)  # the accepted shape resolves


def test_focus_moves_between_two_targets_and_flips_both_flags():
    a, b = Cursor(), Cursor()
    ring = FocusRing([a, b])
    assert ring.focus(b) is True
    assert ring.focused is b
    assert (a.focused, b.focused) == (False, True)
    assert ring.focus(a) is True
    assert ring.focused is a
    assert (a.focused, b.focused) == (True, False)


def test_focusing_an_unregistered_target_is_a_false_no_op():
    a, b, stranger = Cursor(), Cursor(), Cursor()
    ring = FocusRing([a, b])
    assert ring.focus(stranger) is False
    assert ring.focused is a
    assert stranger.focused is True  # untouched: the ring only rewrites its own


def test_focusing_the_current_target_changes_nothing():
    a, b = Cursor(), Cursor()
    ring = FocusRing([a, b])
    assert ring.focus(a) is False
    assert ring.focused is a


def test_focus_next_walks_forward_and_wraps_around():
    a, b, c = Cursor(), Cursor(), Cursor()
    ring = FocusRing([a, b, c])
    assert ring.focus_next() is True and ring.focused is b
    assert ring.focus_next(2) is True and ring.focused is a  # wrapped past the end
    assert ring.focus_next(1) is True and ring.focused is b
    assert ring.focus_next(-1) is True and ring.focused is a  # and backwards
    assert ring.focus_next(-1) is True and ring.focused is c  # off the front


def test_a_non_wrapping_ring_clamps_at_both_ends():
    a, b, c = Cursor(), Cursor(), Cursor()
    ring = FocusRing([a, b, c], wrap=False)
    assert ring.focus_next(-1) is False and ring.focused is a  # clamped at the top
    assert ring.focus_next(9) is True and ring.focused is c  # clamped at the bottom
    assert ring.focus_next(9) is False and ring.focused is c  # already there


def test_a_single_target_ring_never_moves():
    only = Cursor()
    ring = FocusRing([only])
    assert ring.focus_next() is False
    assert ring.focus_next(-1) is False
    assert ring.focused is only and only.focused is True


# --- handle: the routing table ---------------------------------------------------


def test_a_focused_fields_handle_goes_first_and_beats_the_ring_verbs():
    field, other = Field(), Cursor()
    ring = FocusRing([field, other])
    for name in ("down", "up", "enter", "backspace"):
        event = KeyEvent(name)
        assert ring.handle(event) is True
        assert field.handled[-1] == event
    assert field.moves == []  # the ring's own move never ran
    paste = PasteEvent("text")
    assert ring.handle(paste) is True
    assert field.handled[-1] == paste  # a paste is the field's too


def test_a_declined_handle_falls_through_to_the_ring_table():
    field = SoftField(consumes=("backspace",))
    ring = FocusRing([field])
    assert ring.handle(KeyEvent("backspace")) is True  # the field took its own key
    assert ring.handle(KeyEvent("down")) is False  # declined, and the field has no move
    assert [getattr(e, "key", "") for e in field.handled] == ["backspace", "down"]


@pytest.mark.parametrize(
    "name, delta",
    [("up", -1), ("left", -1), ("down", 1), ("right", 1)],
)
def test_the_arrows_call_move_with_the_signed_delta(name, delta):
    cursor = Cursor()
    ring = FocusRing([cursor])
    assert ring.handle(KeyEvent(name)) is True
    assert cursor.steps == [delta]
    assert cursor.index == delta


def test_a_target_without_move_falls_back_to_its_own_arrow_verb():
    vertical = Vertical()
    ring = FocusRing([vertical])
    assert ring.handle(KeyEvent("up")) is True and vertical.calls == ["move_up"]
    assert ring.handle(KeyEvent("down")) is True and vertical.calls == ["move_up", "move_down"]
    assert ring.handle(KeyEvent("left")) is False  # no move_left on this shape
    assert ring.handle(KeyEvent("right")) is False
    assert vertical.calls == ["move_up", "move_down"]  # nothing ran for the misses


def test_a_target_with_only_the_horizontal_verbs_answers_left_and_right():
    side = LeftRight()
    ring = FocusRing([side])
    assert ring.handle(KeyEvent("left")) is True and side.calls == ["move_left"]
    assert ring.handle(KeyEvent("right")) is True
    assert side.calls == ["move_left", "move_right"]
    assert ring.handle(KeyEvent("up")) is False  # this shape has no move_up
    assert ring.handle(KeyEvent("down")) is False


def test_enter_activates_an_activable_target():
    pick = Pick()
    ring = FocusRing([pick])
    assert isinstance(pick, Activable)
    assert ring.handle(KeyEvent("enter")) is True
    assert pick.activations == 1


def test_enter_on_a_target_that_is_not_activable_is_false():
    plain = Plain()
    ring = FocusRing([plain])
    assert not isinstance(plain, Activable)
    assert ring.handle(KeyEvent("enter")) is False


def test_an_activation_that_takes_nothing_answers_its_own_false():
    pick = Pick(answer=False)
    ring = FocusRing([pick])
    assert ring.handle(KeyEvent("enter")) is False
    assert pick.activations == 1  # the verb ran; the answer was "nothing to take"


def test_every_other_event_is_left_to_the_host():
    pick = Pick()
    ring = FocusRing([pick])
    for name in ("escape", "tab", "c-c", "page_up", "space", "q"):
        assert ring.handle(KeyEvent(name)) is False
    assert ring.handle(MouseEvent("left", x=1, y=2)) is False  # the click path's
    assert pick.activations == 0


# --- click: the four-step policy --------------------------------------------------


def test_a_click_on_a_non_target_clickable_is_dispatched_and_stops_there():
    target, mouse_only = Cursor(), MouseOnly()
    ring = FocusRing([target])
    assert ring.click(hit(mouse_only, row=3, col=7)) is True
    assert mouse_only.cells == [(3, 7)]  # its own cell, exactly as hit-tested
    assert ring.focused is target  # the ring's focus never moved
    assert target.focused is True


def test_a_click_that_nothing_consumes_answers_false():
    target = Cursor()
    ring = FocusRing([target])
    assert ring.click(hit(Plain())) is False  # not clickable, not registered
    assert ring.click(hit(MouseOnly(answer=False))) is False  # clickable, declined
    assert ring.focused is target


def test_the_first_click_on_a_target_only_focuses_it():
    first, second = Strip(), ClickOnly()
    ring = FocusRing([first, second])  # the focus starts on ``first``
    assert ring.click(hit(second, row=0, col=11)) is True
    assert ring.focused is second
    assert (first.focused, second.focused) == (False, True)
    assert second.cells == [(0, 11)]  # the cell was dispatched on the way
    assert first.activations == 0


def test_the_first_click_answers_true_even_when_the_component_click_missed():
    first, second = Strip(), ClickOnly(answer=False)
    ring = FocusRing([first, second])
    assert ring.click(hit(second)) is True  # the ring consumed it by focusing
    assert second.focused is True and ring.focused is second


def test_the_second_click_on_the_target_activates_it():
    first, second = Strip(), Strip(activation=False)
    ring = FocusRing([first, second])
    assert ring.click(hit(second)) is True  # the first click: focus only
    assert (first.activations, second.activations) == (0, 0)
    assert ring.click(hit(second)) is True  # the second click: activate
    assert second.activations == 1
    assert (first.activations, second.activations) == (0, 1)
    assert second.cells == [(1, 2), (1, 2)]  # both clicks dispatched their cell


def test_a_click_on_the_target_that_already_holds_the_focus_activates_at_once():
    strip = Strip()
    ring = FocusRing([strip])  # the focus starts on it
    assert ring.click(hit(strip)) is True
    assert strip.activations == 1


def test_a_focused_non_activable_answers_its_own_click():
    strip = ClickOnly(answer=False)  # focused, clickable, not Activable
    ring = FocusRing([strip])
    assert not isinstance(strip, Activable)
    assert ring.click(hit(strip, row=4, col=5)) is False
    assert strip.cells == [(4, 5)]


def test_the_activation_answers_a_focused_targets_click():
    pick = Pick(answer=False)  # Activable, not Clickable
    ring = FocusRing([pick])
    assert ring.click(hit(pick)) is False  # the activation ran and took nothing
    assert pick.activations == 1


# --- with the real widgets --------------------------------------------------------


def test_a_ring_of_real_widgets_focuses_and_dims_them():
    from motui.widgets.choice import Option, Select
    from motui.widgets.tree import Tree

    menu = Select([Option("one"), Option("two")])
    tree = Tree([TreeNode("node")])
    ring = FocusRing([menu, tree])
    assert isinstance(menu, Clickable) and isinstance(tree, Clickable)
    assert (menu.focused, tree.focused) == (True, False)
    assert ring.handle(KeyEvent("down")) is True and menu.index == 1  # the menu moved
    assert ring.handle(KeyEvent("enter")) is True and menu.take_result() == Option("two")
    assert ring.focus_next() is True
    assert (menu.focused, tree.focused) == (False, True)
    assert ring.handle(KeyEvent("enter")) is False  # a leaf: nothing to fold


def test_a_click_through_a_container_lands_on_the_leaf_target():
    """The hit names the wrapper; the ring descends before dispatch/focus."""
    from motui.widgets.choice import Option, Select

    menu = Select([Option("one"), Option("two")])
    other = Select([Option("x")])
    padded = Padding(menu, left=2, top=1)
    padded.render(20)  # the geometry ``child_at`` reads
    ring = FocusRing([other, menu])  # ``other`` holds the focus first
    # Wrapper cell (1, 2) is inside the insets: the menu's own (0, 0).
    through = hit(padded, row=1, col=2)
    assert ring.click(through) is True  # the first click focuses the leaf
    assert ring.focused is menu and menu.focused is True and other.focused is False
    assert ring._registered(padded) is False  # the wrapper is not a target
    assert ring.click(through) is True  # the second activates the leaf
    assert menu.take_result() == Option("one")


def test_a_click_through_a_container_translates_the_cell_for_the_leaf():
    """The descend translates columns: a wrapped Tabs resolves its own cell."""
    from motui.widgets.tabs import Tabs

    strip = Tabs(["a", "bb"])
    padded = Padding(strip, left=3)
    padded.render(20)
    ring = FocusRing([strip])
    # The strip paints " a │ bb ": its cell 6 is inside "bb"; wrapper cell 9
    # is that same column behind the 3-cell inset.
    assert ring.click(hit(padded, row=0, col=3 + 6)) is True
    assert strip.index == 1
