"""Delegate: the identity wrapper that forwards every protocol surface."""

from motui.widgets import Button, Delegate, Option, Select

from tests.testing import Rows, texts


def test_render_hands_back_the_childs_rows_verbatim():
    child = Rows("a", "b")
    delegate = Delegate(child)
    assert delegate.render(20) == child.render(20)
    assert texts(delegate, 20) == ["a", "b"]


def test_click_and_hover_forward_to_the_child():
    button = Button("Run")
    assert Delegate(button).click(0, 0) is True
    assert button.take_result() is True
    menu = Select([Option("one"), Option("two")])
    delegate = Delegate(menu)
    assert delegate.hover_at(1, 0) is True
    assert delegate.hover_at(1, 0) is False


def test_child_at_maps_every_cell_without_rendering_first():
    child = Rows("a")
    delegate = Delegate(child)
    assert delegate.child_at(0, 0) == (child, 0, 0)
    assert delegate.child_at(7, 40) == (child, 7, 40)
    assert delegate.child_at(-1, 0) is None
    assert delegate.child_at(0, -1) is None


def test_the_child_is_a_plain_attribute_a_host_can_swap():
    delegate = Delegate(Rows("old"))
    delegate.child = Rows("new")
    assert texts(delegate, 20) == ["new"]


def test_a_child_without_the_optional_surfaces_declines():
    delegate = Delegate(Rows("a"))
    assert delegate.click(0, 0) is False
    assert delegate.hover_at(0, 0) is False
