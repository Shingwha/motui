"""FocusManager: registration, cycling, traps, routing and the click policy."""

from __future__ import annotations

import pytest

from motui.app import FocusManager
from motui.app.focus import focus_targets
from motui.kernel import Constraints, Document, Pane, Rect, Section, Surface, Viewport
from motui.kernel.document import Placement, descend_chain
from motui.kernel.events import KeyEvent
from motui.kernel.geom import Pos
from motui.kernel.hit import Hit
from motui.kernel.cell import Line
from motui.kernel.text import WrapMode
from motui.testing import headless_tui
from motui.widgets import Button, Field as FormField, Form, Input, Padding, Row
from motui.kernel.layout import Constraints


class Plain:
    """A focusable target with nothing but its flag."""

    def __init__(self) -> None:
        self.focused = True

    def render(self, c: Constraints) -> Surface:
        return Surface.clipped([Line.from_text("plain").clip(WrapMode.ELLIPSIS, c.width)], c.width)


class Cursor(Plain):
    """A list-shaped target: ``move(delta)`` records the signed step."""

    def __init__(self) -> None:
        super().__init__()
        self.steps: list[int] = []

    def move(self, delta: int) -> bool:
        self.steps.append(delta)
        return True


class Field(Plain):
    """A field-shaped target: its ``on_key`` consumes everything first."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list = []
        self.steps: list[int] = []

    def on_key(self, event) -> bool:
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

    def on_key(self, event) -> bool:
        self.handled.append(event)
        return getattr(event, "key", "") == "backspace"


class Keyed(Plain):
    """A target with a key table and both typed hooks."""

    keymap = {"j": "next", "k": "prev"}

    def __init__(self) -> None:
        super().__init__()
        self.actions: list[str] = []
        self.keys: list[str] = []

    def on_action(self, name: str) -> bool:
        self.actions.append(name)
        return name == "next"

    def on_key(self, event) -> bool:
        self.keys.append(getattr(event, "key", ""))
        return getattr(event, "key", "") == "backspace"


class Pick(Plain):
    """An activatable target."""

    activatable = True

    def __init__(self, answer: bool = True) -> None:
        super().__init__()
        self.answer = answer
        self.activations = 0

    def on_action(self, name: str) -> bool:
        if name != "activate":
            return False
        self.activations += 1
        return self.answer


class Strip(Plain):
    """A clickable and activatable target (a menu row)."""

    clickable = True
    activatable = True

    def __init__(self, *, answer: bool = True, activation: bool = True) -> None:
        super().__init__()
        self.answer = answer
        self.activation = activation
        self.cells: list[tuple[int, int]] = []
        self.activations = 0

    def on_click(self, pos: Pos) -> bool:
        self.cells.append((pos.y, pos.x))
        return self.answer

    def on_action(self, name: str) -> bool:
        if name != "activate":
            return False
        self.activations += 1
        return self.activation


class Recorder(Plain):
    """A focusable, clickable target that records the typed click position."""

    focusable = True
    clickable = True

    def __init__(self) -> None:
        super().__init__()
        self.positions: list[Pos] = []

    def on_click(self, pos: Pos) -> bool:
        self.positions.append(pos)
        return True


class RouteOnly:
    """A non-focusable route target (a Dialog s shape)."""

    def __init__(self) -> None:
        self.seen: list = []

    def on_key(self, event) -> bool:
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
    assert not getattr(route, "focusable", False)
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


def test_sync_replaces_the_targets_and_keeps_a_surviving_focus():
    a, b, c = Cursor(), Cursor(), Cursor()
    manager = FocusManager([a])
    manager.focus_next()
    manager.sync([a, b, c])
    assert manager.targets == (a, b, c)
    assert manager.focused is a and a.focused is True
    assert (b.focused, c.focused) == (False, False)
    manager.sync([b, c])
    assert manager.targets == (b, c)
    assert manager.focused is None and a.focused is False


def test_sync_clears_the_focus_only_when_it_left_the_set():
    a, b = Cursor(), Cursor()
    changes: list = []
    manager = FocusManager([a, b], on_change=changes.append)
    manager.focus_next()
    manager.sync([b])
    assert manager.focused is None and a.focused is False
    assert changes == [a, None]
    manager.sync([b, a])
    manager.sync([b, a])
    assert manager.focused is None and changes == [a, None]


def test_sync_without_a_focus_leaves_the_widgets_own_flags_alone():
    a, b = Cursor(), Cursor()  # both construct focused=True
    manager = FocusManager()
    manager.sync([a, b])
    assert manager.targets == (a, b)
    assert (a.focused, b.focused) == (True, True)


def test_focus_next_steps_and_wraps_both_ways():
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


# -- the ring derived from the mounted tree ---------------------------------


def test_focus_targets_are_the_tree_preorder_with_containers_transparent():
    tui = headless_tui(40, 8)
    first = Button("first")
    second = Button("second")
    field = Input()
    tui.add(first)
    tui.add(Row([second, field]))

    assert focus_targets(tui) == (first, second, field)


def test_a_focus_scope_is_a_target_and_its_subtree_is_not():
    tui = headless_tui(40, 12)
    form = Form([FormField("name", Input()), FormField("email", Input())])
    tui.add(form)

    assert focus_targets(tui) == (form,)


def test_the_ring_tracks_removed_and_added_subtrees():
    tui = headless_tui(40, 8)
    button = Button("go")
    row = Row([button, Input()])
    block = tui.add(row)
    assert focus_targets(tui) == (button, row.children[1])

    tui.remove(block)
    assert focus_targets(tui) == ()

    other = Button("other")
    tui.add(other)
    assert focus_targets(tui) == (other,)


def test_docked_blocks_join_the_ring_after_the_content_panes():
    tui = headless_tui(40, 8)
    body = Button("body")
    footer = Button("footer")
    tui.add(body)
    tui.dock(footer, placement=Placement.BOTTOM)

    assert focus_targets(tui) == (body, footer)


def test_focus_next_from_an_empty_focus_selects_the_first_tree_target():
    tui = headless_tui(40, 8)
    first, second = Button("a"), Button("b")
    tui.add(Row([first, second]))
    manager = FocusManager(focus_targets(tui))

    assert manager.focus_next() is True
    assert manager.focused is first
    assert manager.focus_next() is True
    assert manager.focused is second
    assert manager.focus_next() is True
    assert manager.focused is first


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


def test_a_declined_hook_leaves_the_key_to_the_host():
    field = SoftField()
    manager = FocusManager([field])
    manager.focus_next()
    assert manager.handle(KeyEvent("backspace")) is True
    assert manager.handle(KeyEvent("down")) is False
    assert [getattr(event, "key", "") for event in field.handled] == [
        "backspace",
        "down",
    ]


def test_a_keymap_action_runs_before_and_instead_of_on_key():
    keyed = Keyed()
    manager = FocusManager([keyed])
    manager.focus_next()
    assert manager.handle(KeyEvent("j", "j")) is True
    assert keyed.actions == ["next"]
    assert keyed.keys == []


def test_an_unconsumed_keymap_action_falls_through_to_on_key():
    keyed = Keyed()
    manager = FocusManager([keyed])
    manager.focus_next()
    assert manager.handle(KeyEvent("backspace")) is True
    assert keyed.keys == ["backspace"]


def test_a_rebound_instance_key_drives_the_data_view():
    from motui.widgets import List

    listing = List(["a", "b", "c"])
    manager = FocusManager([listing])
    manager.focus_next()
    listing.keymap["j"] = "next"
    assert manager.handle(KeyEvent("j", "j")) is True
    assert listing.index == 1


def test_a_text_field_keeps_its_own_arrow_keys():
    field = Input("ab")
    manager = FocusManager([field])
    manager.focus_next()
    assert field.cursor == (0, 0)
    assert manager.handle(KeyEvent("right")) is True
    assert field.cursor == (0, 1)
    assert manager.handle(KeyEvent("left")) is True
    assert field.cursor == (0, 0)


def test_a_scope_routes_keys_to_its_own_fields():
    first, second = Input(), Input()
    form = Form([FormField("first", first), FormField("second", second)])
    manager = FocusManager([form])
    manager.focus_next()
    assert manager.handle(KeyEvent("tab")) is True
    assert form.index == 1
    assert manager.handle(KeyEvent("b", "b")) is True
    assert second.text == "b" and first.text == ""


def test_enter_activates_an_activable_target():
    pick = Pick()
    manager = FocusManager([pick])
    manager.focus_next()
    assert pick.activatable is True
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
    padded.render(Constraints(width=20))
    manager = FocusManager([other, menu])
    manager.focus_next()
    assert manager.click(hit(padded, row=1, col=2)) is True
    assert manager.focused is menu
    assert manager.click(hit(padded, row=1, col=2)) is True
    assert menu.take() == Option("one")


def test_the_arrows_call_move_with_the_signed_delta():
    cursor = Cursor()
    cursor.keymap = {"up": "prev", "left": "prev", "down": "next", "right": "next"}
    cursor.on_action = lambda name: cursor.move(-1 if name == "prev" else 1)
    manager = FocusManager([cursor])
    manager.focus_next()
    for name, delta in (("up", -1), ("left", -1), ("down", 1), ("right", 1)):
        assert manager.handle(KeyEvent(name)) is True
        assert cursor.steps[-1] == delta


def test_a_click_carries_the_leaf_cell_as_a_pos():
    recorder = Recorder()
    manager = FocusManager([recorder])
    manager.focus_next()
    assert manager.click(hit(recorder, row=3, col=7)) is True
    assert recorder.positions == [Pos(x=7, y=3)]
