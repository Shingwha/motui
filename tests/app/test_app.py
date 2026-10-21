"""The App's default orchestration: focus routing, bindings and wheel routing."""

from __future__ import annotations

from motui.app import App
from motui.core import HeadlessScreen
from motui.widgets import Button, Input, ScrollView
from tests.testing import Rows, ScriptedEvents, key, many, wheel


def test_add_focus_and_bind_reach_the_right_component():
    app = App(
        screen=HeadlessScreen(40, 6),
        keys=ScriptedEvents([key("a", "a"), key("enter"), None]),
    )
    name = app.add(Input(), id="name")
    button = Button("Ship")
    app.add(button)
    app.bind("enter", button.activate)

    assert name == "name"
    assert app.focus("name") is True
    assert app.dispatch(key("a", "a")) is True
    assert app.get("name").text == "a"
    assert app.dispatch(key("enter")) is True
    assert button.take_result() is True


def test_the_wheel_routes_to_the_nearest_scrollable():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollView(Rows(*many(10)), height=3, scrollbar=True)
    app.add(view)
    app.tui.paint()

    assert app.dispatch(wheel(0, 0, "down")) is True
    assert view.offset == 3
    assert app.dispatch(wheel(0, 0, "up")) is True
    assert view.offset == 0
