"""The App's default orchestration: focus routing, bindings and wheel routing."""

from __future__ import annotations

from motui.app import App
from motui.kernel import Theme
from motui.kernel.cell import Line, Surface
from motui.kernel.document import Sizing
from motui.kernel.layout import Constraints
from motui.terminal import HeadlessScreen
from motui.kernel.events import KeyEvent
from motui.widgets import Button, Field, Form, Input, Panel, Row, ScrollPanel
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


class _Wide:
    """A 200-column, three-row child: the horizontal-overflow producer."""

    def __init__(self, columns: int = 200, rows: int = 3) -> None:
        self.columns = columns
        self.row_count = rows

    def render(self, c: Constraints) -> Surface:
        lines = [
            Line.from_text("".join(chr(ord("a") + (row + col) % 26) for col in range(self.columns)))
            for row in range(self.row_count)
        ]
        return Surface.of(lines, self.columns, pad=False)


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


def test_fill_replaces_the_pane_and_mounts_theme_and_focus():
    app = App(screen=HeadlessScreen(20, 5), keys=ScriptedEvents(()))
    app.add(Rows("head"))
    button = Button("Go")
    section = app.fill(button)

    assert section.sizing is Sizing.FILL
    assert section.widget is button
    assert button.theme is app.theme  # the fill path walks the theme too
    assert app.focus_manager is not None
    assert button in app.focus_manager.targets
    app.tui.paint()
    assert [row.text for row in app.tui.rows] == [" Go ", "", "", "", ""]


def test_add_themes_every_widget_of_a_nested_tree():
    app = App(screen=HeadlessScreen(30, 6), keys=ScriptedEvents(()))
    name, button = Input(), Button("Go")
    panel = Panel(Row([name, button]), title="nested")

    app.add(panel)

    assert panel.theme is app.theme
    assert name.theme is app.theme
    assert button.theme is app.theme


def test_add_themes_a_forms_fields_through_its_scope():
    app = App(screen=HeadlessScreen(30, 8), keys=ScriptedEvents(()))
    form = Form([Field("name", Input()), Field("email", Input())])

    app.add(form)

    assert form.theme is app.theme
    assert [field.component.theme for field in form.fields] == [app.theme, app.theme]


def test_removing_a_parent_drops_its_subtree_from_the_ring():
    app = App(screen=HeadlessScreen(30, 6), keys=ScriptedEvents(()))
    button = Button("Go")
    block = app.add(Row([button]))
    assert app.focus(button) is True
    assert app.focus_manager is not None

    app.remove(block)

    assert app.focus_manager.targets == ()
    assert app.focus_manager.focused is None
    assert button.focused is False


def test_set_focus_targets_is_gone():
    app = App(screen=HeadlessScreen(20, 4), keys=ScriptedEvents(()))
    assert not hasattr(app, "set_focus_targets")


def test_a_fill_section_added_through_the_app_takes_the_remainder():
    app = App(screen=HeadlessScreen(20, 5), keys=ScriptedEvents(()))
    app.add(Rows("head"))
    app.add(Rows("game"), sizing=Sizing.FILL)
    app.tui.paint()
    assert [row.text for row in app.tui.rows] == ["head", "game", "", "", ""]


def test_the_wheel_routes_to_the_nearest_scrollable():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(Rows(*many(10)), height=3, bar=True)
    app.add(view)
    app.tui.paint()

    assert app.dispatch(wheel(0, 0, "down")) is True
    assert view.offset == 3
    assert app.dispatch(wheel(0, 0, "up")) is True
    assert view.offset == 0

    app.focus(view)
    assert app.dispatch(key("page_down")) is True
    assert view.offset == 3  # the focused ScrollPanel pages one window
    assert app.dispatch(key("page_up")) is True
    assert view.offset == 0


def test_the_horizontal_wheel_moves_the_x_panel_under_the_pointer():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(_Wide(), height=3, axis="x")
    app.add(view)
    app.tui.paint()

    assert (view.x_offset, view.offset) == (0, 0)
    assert app.dispatch(wheel(5, 1, "right")) is True
    assert view.x_offset == 1
    assert view.offset == 0
    assert app.dispatch(wheel(5, 1, "left")) is True
    assert view.x_offset == 0


def test_the_horizontal_wheel_declines_a_vertical_only_panel():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(Rows(*many(10)), height=3, axis="y")
    app.add(view)
    app.tui.paint()

    assert app.dispatch(wheel(5, 1, "right")) is False
    assert (view.x_offset, view.offset) == (0, 0)


def test_the_vertical_wheel_leaves_the_horizontal_offset_alone():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(_Wide(rows=10), height=3, axis="x")
    app.add(view)
    app.tui.paint()

    assert app.dispatch(wheel(5, 1, "right")) is True
    assert view.x_offset == 1
    # The 1.x route still finds the nearest Scrollable and steps its rows;
    # only the horizontal notch touched x.
    assert app.dispatch(wheel(5, 1, "down")) is True
    assert view.x_offset == 1
    assert view.offset == 3


def test_the_vertical_wheel_still_scrolls_the_pane_outside_a_widget():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    app.add(Rows(*many(30)))
    app.tui.paint()
    pane = app.tui.frame.focused_pane
    before = pane.viewport.offset
    assert before > 0  # the fresh viewport sticks to the tail

    assert app.dispatch(wheel(5, 1, "up")) is True
    assert pane.viewport.offset == before - 3


def test_a_bar_drag_moves_the_scroll_view_without_a_selection():
    app = App(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(Rows(*many(10)), height=3, bar=True)
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

