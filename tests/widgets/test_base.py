"""Widget tree plumbing: parent/children, walk order, and generation touch."""

from __future__ import annotations

from motui.widgets.base import Widget


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


def test_walk_is_preorder_and_starts_with_self():
    root = Node()
    left, right = Node(), Node()
    left_a, left_b = Node(), Node()
    right_a = Node()
    left.children = [left_a, left_b]
    right.children = [right_a]
    root.children = [left, right]

    assert walked(root) == [root, left, left_a, left_b, right, right_a]


def test_walk_visits_a_shared_child_once_at_its_first_position():
    root = Node()
    left, right = Node(), Node()
    shared = Node()
    left.children = [shared]
    right.children = [shared]
    root.children = [left, right]

    assert walked(root) == [root, left, shared, right]


def test_walk_visits_children_that_are_not_widgets():
    root = Node()
    plain = Plain()
    child = Node()
    root.children = [plain, child]

    assert walked(root) == [root, plain, child]
    # A plain object has no ``parent`` slot: the setter must leave it alone.
    assert not hasattr(plain, "parent")


def test_walk_terminates_on_a_parent_child_cycle():
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


def test_a_widget_that_skips_init_can_still_assign_walk_and_touch():
    # A third-party subclass may not call ``super().__init__``; the setters
    # and the tree readers must stay safe on the unset slots.
    raw = object.__new__(State)
    assert raw.generation == 0
    assert walked(raw) == [raw]

    raw.value = 3

    assert raw.value == 3
    assert raw.generation == 1
