"""Widget base: tree plumbing, generation touch, typed hooks and capabilities."""

from __future__ import annotations

from motui.kernel.events import KeyEvent, MouseEvent, PasteEvent, ResizeEvent
from motui.kernel.geom import Pos
from motui.widgets.base import Container, Cursor, HasResult, MarkSet, Widget
from motui.widgets.cursor import Cursor as DirectCursor
from motui.widgets.mark import MarkSet as DirectMarkSet


class Node(Widget):
    """A bare widget with no state beyond the base's."""

    __slots__ = ()


class Plain:
    """A non-widget child object: ``walk`` must still visit it."""

    __slots__ = ()


class State(Widget):
    """One public slot and one private slot for the setter rules."""

    __slots__ = ("_hidden", "value")


def walked(widget: Widget) -> list[Widget]:
    """The ids of ``widget.walk()`` in order (ids stay stable on the stack)."""
    nodes = list(widget.walk())
    assert len({id(node) for node in nodes}) == len(nodes)
    return nodes


def test_a_fresh_widget_starts_with_no_parent_no_children_and_zero_generation():
    widget = Node()
    assert widget.parent is None
    assert widget.children == []
    assert widget.generation == 0


def test_the_tree_is_preorder_and_starts_with_self():
    root = Node()
    left, right = Node(), Node()
    left_a, left_b = Node(), Node()
    right_a = Node()
    left.children = [left_a, left_b]
    right.children = [right_a]
    root.children = [left, right]

    assert walked(root) == [root, left, left_a, left_b, right, right_a]


def test_the_tree_visits_a_shared_child_once_at_its_first_position():
    root = Node()
    left, right = Node(), Node()
    shared = Node()
    left.children = [shared]
    right.children = [shared]
    root.children = [left, right]

    assert walked(root) == [root, left, shared, right]


def test_the_tree_visits_children_that_are_not_widgets():
    root = Node()
    plain = Plain()
    child = Node()
    root.children = [plain, child]

    assert walked(root) == [root, plain, child]
    # A plain object has no ``parent`` slot: the setter must leave it alone.
    assert not hasattr(plain, "parent")


def test_the_tree_terminates_on_a_parent_child_cycle():
    root = Node()
    child = Node()
    root.children = [child]
    child.children = [root]

    assert walked(root) == [root, child]


def test_assigning_children_accepts_an_iterable_and_sets_the_parent():
    root = Node()
    first, second = Node(), Node()
    root.children = (first, second)

    assert root.children == [first, second]
    assert isinstance(root.children, list)
    assert first.parent is root and second.parent is root


def test_reassigning_children_sets_the_new_parent_and_leaves_the_old_one():
    root = Node()
    old, new = Node(), Node()
    root.children = [old]
    root.children = [new]

    assert new.parent is root
    # Documented behaviour: reassignment adopts the new children but does
    # not detach the old ones; the caller owns that edit.
    assert old.parent is root


def test_touch_bubbles_one_generation_through_every_ancestor():
    root = Node()
    middle = Node()
    leaf = Node()
    sibling = Node()
    middle.children = [leaf]
    root.children = [middle, sibling]
    before = {id(node): node.generation for node in walked(root)}

    leaf.touch()

    assert leaf.generation == before[id(leaf)] + 1
    assert middle.generation == before[id(middle)] + 1
    assert root.generation == before[id(root)] + 1
    assert sibling.generation == before[id(sibling)]


def test_touch_on_a_root_reaches_no_descendant():
    root = Node()
    child = Node()
    root.children = [child]
    before = (root.generation, child.generation)

    root.touch()

    assert root.generation == before[0] + 1
    assert child.generation == before[1]


def test_a_public_assignment_touches_the_widget_and_its_ancestors():
    root = Node()
    child = State()
    root.children = [child]
    before = (child.generation, root.generation)

    child.value = 7

    assert child.value == 7
    assert child.generation == before[0] + 1
    assert root.generation == before[1] + 1


def test_an_underscore_assignment_stays_silent():
    widget = State()
    before = widget.generation

    widget._hidden = "internal"

    assert widget._hidden == "internal"
    assert widget.generation == before


def test_assigning_parent_is_tree_plumbing_and_does_not_touch():
    root = Node()
    child = Node()
    before = (root.generation, child.generation)

    child.parent = root

    assert child.parent is root
    assert not root.children
    assert (root.generation, child.generation) == before


def test_assigning_children_touches_the_container_and_its_ancestors():
    root = Node()
    middle = Node()
    root.children = [middle]
    before = (root.generation, middle.generation)

    child = Node()
    middle.children = [child]

    assert middle.generation == before[1] + 1
    assert root.generation == before[0] + 1


def test_touch_survives_a_parent_cycle():
    first, second = Node(), Node()
    first.parent = second
    second.parent = first

    first.touch()

    assert (first.generation, second.generation) == (1, 1)


def test_a_widget_that_skips_init_can_still_assign_a_tree_and_touch():
    # A third-party subclass may not call ``super().__init__``; the setters
    # and the tree readers must stay safe on the unset slots.
    raw = object.__new__(State)
    assert raw.generation == 0
    assert walked(raw) == [raw]

    raw.value = 3

    assert raw.value == 3
    assert raw.generation == 1


class Typed(Widget):
    """A 2.0-shaped widget: it overrides only the typed interaction hooks."""

    __slots__ = ("_log", "result")

    def __init__(self, result: object | None = None) -> None:
        super().__init__()
        self._log: list[tuple] = []
        self.result = result

    def on_key(self, event):
        self._log.append(("key", event))
        return True

    def on_mouse(self, event):
        self._log.append(("mouse", event))
        return True

    def on_paste(self, event):
        self._log.append(("paste", event))
        return True

    def on_click(self, pos: Pos) -> bool:
        self._log.append(("click", pos.y, pos.x))
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        self._log.append(("hover", None if pos is None else (pos.y, pos.x)))
        return True

    def on_drag(self, pos: Pos, phase: str) -> bool:
        self._log.append(("drag", pos.y, pos.x, phase))
        return True

    def on_action(self, name: str) -> bool:
        self._log.append(("action", name))
        return name == "activate"

    def take(self) -> object | None:
        return self.result


class Taker:
    """A non-widget object with the one result method the protocol needs."""

    def take(self) -> object | None:
        return 5


# -- the typed hooks are the only interaction doors --------------------------


def test_the_key_mouse_and_paste_hooks_dispatch_directly():
    widget = Typed()
    key = KeyEvent("a", "a")
    mouse = MouseEvent(x=2, y=1)
    paste = PasteEvent("hi")

    assert widget.on_key(key) is True
    assert widget.on_mouse(mouse) is True
    assert widget.on_paste(paste) is True
    assert widget._log == [("key", key), ("mouse", mouse), ("paste", paste)]


def test_the_click_hook_takes_a_pos():
    widget = Typed()

    assert widget.on_click(Pos(x=3, y=1)) is True
    assert widget._log == [("click", 1, 3)]


def test_the_hover_and_drag_hooks_take_a_pos():
    widget = Typed()

    assert widget.on_hover(Pos(x=3, y=1)) is True
    assert widget.on_hover(None) is True
    assert widget.on_drag(Pos(x=3, y=1), "motion") is True
    assert widget._log == [
        ("hover", (1, 3)),
        ("hover", None),
        ("drag", 1, 3, "motion"),
    ]


def test_the_action_hook_is_the_named_action_door():
    widget = Typed()

    assert widget.on_action("activate") is True
    assert widget.on_action("next") is False
    assert widget._log == [("action", "activate"), ("action", "next")]


def test_the_untyped_verbs_are_gone_from_the_base():
    widget = Widget()
    for name in ("handle", "click", "hover_at", "drag", "activate", "take_result"):
        assert not hasattr(widget, name), name


def test_the_resize_hook_is_a_no_op_on_the_base():
    widget = Typed()

    assert widget.on_resize(ResizeEvent(80, 24)) is None
    assert widget._log == []


def test_the_focus_hook_flips_the_focused_flag():
    widget = Typed()

    widget.on_focus(True)
    assert widget.focused is True
    widget.on_focus(False)
    assert widget.focused is False


def test_take_keeps_false_distinct_from_none():
    assert Typed().take() is None
    assert Typed(False).take() is False
    assert Typed(0).take() == 0
    picked = object()
    assert Typed(picked).take() is picked


def test_a_plain_widget_declines_every_default_hook():
    widget = Widget()

    assert widget.on_key(KeyEvent("a")) is False
    assert widget.on_mouse(MouseEvent()) is False
    assert widget.on_paste(PasteEvent("x")) is False
    assert widget.on_resize(ResizeEvent(10, 5)) is None
    assert widget.on_click(Pos()) is False
    assert widget.on_hover(None) is False
    assert widget.on_drag(Pos(), "press") is False
    assert widget.on_action("activate") is False
    assert widget.on_action("anything") is False
    assert widget.take() is None


# -- capability flags and class-level state --------------------------------


def test_capability_flags_and_keymap_default_to_off_and_empty():
    for widget in (Widget(), Container()):
        assert widget.focusable is False
        assert widget.clickable is False
        assert widget.hoverable is False
        assert widget.activatable is False
        assert widget.focus_scope is False
        assert not hasattr(widget, "owns_focus")
    assert Widget.keymap == {}
    assert Container.keymap == {}


def test_has_result_is_a_runtime_checkable_protocol():
    assert isinstance(Typed(), HasResult)
    assert isinstance(Taker(), HasResult)
    assert not isinstance(object(), HasResult)


def test_container_is_a_widget_whose_child_at_declines_by_default():
    container = Container()

    assert isinstance(container, Widget)
    assert container.child_at(0, 0) is None
    assert container.child_at(7, 11) is None


# -- re-exports -------------------------------------------------------------


def test_cursor_and_mark_set_are_reexported_from_their_own_modules():
    assert Cursor is DirectCursor
    assert MarkSet is DirectMarkSet
    cursor = Cursor(count=3)
    assert cursor.move(1) is True and cursor.index == 1
    marks = MarkSet([2])
    assert marks.toggle(2) is False and 2 not in marks


def test_the_new_base_names_stay_out_of_the_package_facades():
    # This wave publishes the tree and hooks from ``motui.widgets.base``
    # only; the root facade is W5's to converge, so nothing leaks here yet.
    import motui
    import motui.kernel
    import motui.widgets

    for facade in (motui, motui.widgets, motui.kernel):
        for name in ("Container", "Cursor", "HasResult", "MarkSet"):
            assert not hasattr(facade, name), (facade.__name__, name)
