"""The App's default orchestration: focus routing, bindings and wheel routing."""

from __future__ import annotations

from motui.app import App
from motui.kernel import Theme
from motui.terminal import HeadlessScreen
from motui.kernel.events import KeyEvent
from motui.widgets import Button, Field, Form, Input, ScrollView
from tests.testing import (
    Rows,
    ScriptedEvents,
    key,
    many,
    motion,
    press,
    release,
    wheel,
)


class _Controller:
    """A host controller double: consumes one key, records theme updates."""

    def __init__(self) -> None:
        self.keys: list[str] = []
        self.themes: list[Theme] = []

    def handle(self, event) -> bool:
        if getattr(event, "key", None) == "x":
            self.keys.append(event.key)
            return True
        return False

    def set_theme(self, theme: Theme) -> None:
        self.themes.append(theme)


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
    view = ScrollView(Rows(*many(10)), height=3, bar=True)
    app.add(view)
    app.tui.paint()

    assert app.dispatch(wheel(0, 0, "down")) is True
    assert view.offset == 3
    assert app.dispatch(wheel(0, 0, "up")) is True
    assert view.offset == 0

    app.set_focus_targets([view])
    assert app.dispatch(key("page_down")) is True
    assert view.offset == 3  # the focused ScrollView pages one window
    assert app.dispatch(key("page_up")) is True
    assert view.offset == 0


def test_a_bar_drag_moves_the_scroll_view_without_a_selection():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollView(Rows(*many(10)), height=3, bar=True)
    app.add(view)
    app.tui.paint()

    assert app.dispatch(press(39, 0)) is True
    assert app.tui.selection is None  # the drag took the press, not the gesture
    assert app.dispatch(motion(39, 2)) is True
    assert view.offset == 7
    assert app.tui.selection is None
    assert app.dispatch(release(39, 2)) is True
    assert app.tui.selection is None
    assert app.dispatch(motion(39, 1)) is True  # the pointer's hover cue now
    assert view.offset == 7


def test_mounted_controllers_dispatch_before_bindings_and_theme():
    app = App(screen=HeadlessScreen(40, 6), keys=ScriptedEvents(()))
    controller = _Controller()
    app.mount(controller)
    fired: list[str] = []
    app.bind("x", lambda: fired.append("binding"))
    app.add(Input())

    assert app.controllers == (controller,)
    assert app.dispatch(key("x", "x")) is True
    assert controller.keys == ["x"]
    assert fired == []

    theme = Theme.dark()
    assert app.theme is not theme
    app.theme = theme
    assert controller.themes == [theme]
    assert app.toasts is not None and app.toasts._theme is theme

    assert app.unmount(controller) is True
    assert app.controllers == ()
    assert app.dispatch(key("x", "x")) is True  # the binding is the next tier
    assert fired == ["binding"]
    assert controller.keys == ["x"]


def test_a_non_dispatching_mount_is_kept_but_not_fed():
    app = App(screen=HeadlessScreen(40, 6), keys=ScriptedEvents(()))
    controller = _Controller()
    app.mount(controller, dispatch=False)

    assert app.dispatch(key("x", "x")) is False
    assert controller.keys == []
    assert app.controllers == (controller,)


def test_a_form_owns_its_fields_and_a_click_moves_its_cursor():
    app = App(screen=HeadlessScreen(40, 12), keys=ScriptedEvents(()))
    name, email = Input(), Input()
    form = Form(
        [
            Field("name", name, label="Name"),
            Field("email", email, label="Email"),
        ],
        gap=1,
    )
    app.add(form, id="form")
    assert app.focus_manager is not None
    assert app.focus_manager.targets == (form,)  # fields are not separate targets
    assert app.focus(form) is True
    app.tui.paint()

    row = next(y for y, line in enumerate(app.tui.rows) if "Email" in line.text) + 1
    hit = app.tui.hit(0, row)
    assert hit is not None
    assert app.focus_manager.click(hit) is True
    assert form.index == 1
    assert form.handle(KeyEvent("b", "b")) is True
    assert email.text == "b"
    assert name.text == ""

