"""The App's default orchestration: focus routing, bindings and wheel routing."""

from __future__ import annotations

import pytest

from motui.app import App, Runtime, Workspace
from motui.app.runtime import Timer
from motui.kernel import Theme
from motui.kernel.cell import Line, Surface
from motui.kernel.document import Placement, Sizing
from motui.kernel.geom import Axis
from motui.kernel.layout import Constraints
from motui.terminal import (
    HeadlessScreen,
    MouseMode,
    Terminal,
    TerminalOptions,
)
from motui.kernel.events import KeyEvent
from motui.widgets import Button, Field, Form, Input, Panel, Row, ScrollPanel
from motui.widgets.base import Widget
from tests.testing import (
    Rows,
    ScriptedEvents,
    key,
    many,
    motion,
    press,
    release,
    resize,
    rows,
    wheel,
)


class _ResizeRecorder(Widget):
    """A widget that records every resize report it receives."""

    __slots__ = ("sizes",)

    def __init__(self) -> None:
        super().__init__()
        self.sizes: list[tuple[int, int]] = []

    def on_resize(self, event) -> None:
        self.sizes.append((event.width, event.height))


class _HostApp(App):
    """An App whose host hook records every event the tiers left alone."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.seen: list = []

    def on_event(self, event) -> bool:
        self.seen.append(event)
        return False


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


def _app(*, screen: object = None, keys: object = None, **kwargs: object) -> App:
    """An App over the 2.0 :class:`TerminalOptions` door."""
    return App(terminal=TerminalOptions(screen=screen, input=keys), **kwargs)  # type: ignore[arg-type]


def test_add_focus_and_bind_reach_the_right_component():
    app = _app(
        screen=HeadlessScreen(40, 6),
        keys=ScriptedEvents([key("a", "a"), key("enter"), None]),
    )
    name = app.add(Input(), id="name")
    button = Button("Ship")
    app.add(button)
    app.bind("enter", lambda: button.on_action("activate"))

    assert name.id == "name"
    assert app.focus("name") is True
    assert app.dispatch(key("a", "a")) is True
    assert app.get("name").widget.text == "a"
    assert app.dispatch(key("enter")) is True
    assert button.take() is True


def test_fill_replaces_the_pane_and_mounts_theme_and_focus():
    app = _app(screen=HeadlessScreen(20, 5), keys=ScriptedEvents(()))
    app.add(Rows("head"))
    button = Button("Go")
    section = app.fill(button)

    assert section.sizing is Sizing.FILL
    assert section.widget is button
    assert button.theme is app.theme  # the fill path walks the theme too
    assert app.focus_manager is not None
    assert button in app.focus_manager.targets
    app.runtime.paint()
    assert [row.text for row in app.runtime.rows] == [" Go ", "", "", "", ""]


def test_add_themes_every_widget_of_a_nested_tree():
    app = _app(screen=HeadlessScreen(30, 6), keys=ScriptedEvents(()))
    name, button = Input(), Button("Go")
    panel = Panel(Row([name, button]), title="nested")

    app.add(panel)

    assert panel.theme is app.theme
    assert name.theme is app.theme
    assert button.theme is app.theme


def test_add_themes_a_scroll_panels_child_through_its_subtree():
    app = _app(screen=HeadlessScreen(30, 6), keys=ScriptedEvents(()))
    child = Input()
    view = ScrollPanel(child, height=2)

    app.add(view)

    assert view.theme is app.theme
    assert child.theme is app.theme


def test_add_themes_a_forms_fields_through_its_scope():
    app = _app(screen=HeadlessScreen(30, 8), keys=ScriptedEvents(()))
    form = Form([Field("name", Input()), Field("email", Input())])

    app.add(form)

    assert form.theme is app.theme
    assert [field.component.theme for field in form.fields] == [app.theme, app.theme]


def test_removing_a_parent_drops_its_subtree_from_the_ring():
    app = _app(screen=HeadlessScreen(30, 6), keys=ScriptedEvents(()))
    button = Button("Go")
    block = app.add(Row([button]))
    assert app.focus(button) is True
    assert app.focus_manager is not None

    app.remove(block)

    assert app.focus_manager.targets == ()
    assert app.focus_manager.focused is None
    assert button.focused is False


def test_app_split_dock_and_undock_accept_the_2_0_enums():
    app = _app(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    left, right = app.split(Axis.X, weights=(2, 1))
    assert [pane.id for pane in app.workspace.panes] == ["primary", "pane-1"]
    assert left.rect.width > right.rect.width

    top = app.dock(Rows("top"), placement=Placement.TOP)
    bottom = app.dock(Rows("foot"), placement=Placement.BOTTOM, size=1)
    assert app.workspace.frame.dock("top") is top
    assert app.workspace.frame.dock("bottom") is bottom
    assert app.undock(Placement.BOTTOM) is bottom
    assert app.undock(Placement.TOP) is top


def test_remove_takes_the_section_add_answered():
    """The 2.0 removal door is the ``Section`` value, not a bare id."""
    app = _app(screen=HeadlessScreen(20, 4), keys=ScriptedEvents(()))
    section = app.add(Rows("one"))

    assert app.remove(section) is section
    assert app.workspace.document.blocks() == ()
    with pytest.raises(TypeError):
        app.remove(section.id)  # type: ignore[arg-type]


def test_app_proxies_the_runtime_schedule_and_paint():
    app = _app(screen=HeadlessScreen(20, 3), keys=ScriptedEvents(()))
    app.runtime._clock = lambda: 0.0
    calls: list[str] = []
    timer = app.every(0.05, lambda: calls.append("tick"))
    animation = app.animation(20, lambda: calls.append("draw"))

    assert isinstance(timer, Timer) and timer.period == 0.05
    assert isinstance(animation, Timer) and animation.period == 0.05
    app.runtime.advance(0.11)
    assert calls.count("tick") == 2
    assert calls.count("draw") == 2

    app.add(Rows("x"))
    app.invalidate()
    app.paint_now()
    assert rows(app.runtime)[0] == "x"


def test_walk_visits_each_mounted_node_once_in_frame_order():
    app = _app(screen=HeadlessScreen(30, 6), keys=ScriptedEvents(()))
    button = Button("Go")
    row = Row([button])
    section = app.add(row)
    docked = Button("Dock")
    app.dock(docked, placement=Placement.BOTTOM)

    nodes = list(app.walk())

    assert section.widget is row
    assert nodes[0] is row and nodes[1] is button
    assert docked in nodes
    assert len(nodes) == len({id(node) for node in nodes})


def test_set_focus_targets_is_gone():
    app = _app(screen=HeadlessScreen(20, 4), keys=ScriptedEvents(()))
    assert not hasattr(app, "set_focus_targets")


def test_resize_reaches_every_widget_and_is_not_consumed():
    app = _HostApp(
        terminal=TerminalOptions(
            screen=HeadlessScreen(40, 8), input=ScriptedEvents(())
        )
    )
    left, right = _ResizeRecorder(), _ResizeRecorder()
    app.add(Form([Field("row", Row([left, right]))]))
    event = resize(100, 30)

    assert app.dispatch(event) is False
    assert left.sizes == [(100, 30)]
    assert right.sizes == [(100, 30)]  # a focus scope's subtree is included
    assert app.seen == [event]  # the host still sees the event


def test_a_fill_section_added_through_the_app_takes_the_remainder():
    app = _app(screen=HeadlessScreen(20, 5), keys=ScriptedEvents(()))
    app.add(Rows("head"))
    app.add(Rows("game"), sizing=Sizing.FILL)
    app.runtime.paint()
    assert [row.text for row in app.runtime.rows] == ["head", "game", "", "", ""]


def test_the_wheel_routes_to_the_nearest_scrollable():
    app = _app(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(Rows(*many(10)), height=3, bar=True)
    app.add(view)
    app.runtime.paint()

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
    app = _app(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(_Wide(), height=3, axis="x")
    app.add(view)
    app.runtime.paint()

    assert (view.x_offset, view.offset) == (0, 0)
    assert app.dispatch(wheel(5, 1, "right")) is True
    assert view.x_offset == 1
    assert view.offset == 0
    assert app.dispatch(wheel(5, 1, "left")) is True
    assert view.x_offset == 0


def test_the_horizontal_wheel_declines_a_vertical_only_panel():
    app = _app(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(Rows(*many(10)), height=3, axis="y")
    app.add(view)
    app.runtime.paint()

    assert app.dispatch(wheel(5, 1, "right")) is False
    assert (view.x_offset, view.offset) == (0, 0)


def test_the_vertical_wheel_leaves_the_horizontal_offset_alone():
    app = _app(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(_Wide(rows=10), height=3, axis="x")
    app.add(view)
    app.runtime.paint()

    assert app.dispatch(wheel(5, 1, "right")) is True
    assert view.x_offset == 1
    # The 1.x route still finds the nearest Scrollable and steps its rows;
    # only the horizontal notch touched x.
    assert app.dispatch(wheel(5, 1, "down")) is True
    assert view.x_offset == 1
    assert view.offset == 3


def test_the_vertical_wheel_still_scrolls_the_pane_outside_a_widget():
    app = _app(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    app.add(Rows(*many(30)))
    app.runtime.paint()
    pane = app.workspace.frame.focused_pane
    before = pane.viewport.offset
    assert before > 0  # the fresh viewport sticks to the tail

    assert app.dispatch(wheel(5, 1, "up")) is True
    assert pane.viewport.offset == before - 3


def test_a_bar_drag_moves_the_scroll_view_without_a_selection():
    app = _app(screen=HeadlessScreen(40, 8), keys=ScriptedEvents(()))
    view = ScrollPanel(Rows(*many(10)), height=3, bar=True)
    app.add(view)
    app.runtime.paint()

    assert app.dispatch(press(39, 0)) is True
    assert app.workspace.selection is None  # the drag took the press, not the gesture
    assert app.dispatch(motion(39, 2)) is True
    assert view.offset == 7
    assert app.workspace.selection is None
    assert app.dispatch(release(39, 2)) is True
    assert app.workspace.selection is None
    assert app.dispatch(motion(39, 1)) is True  # the pointer's hover cue now
    assert view.offset == 7


def test_mounted_controllers_dispatch_before_bindings_and_theme():
    app = _app(screen=HeadlessScreen(40, 6), keys=ScriptedEvents(()))
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
    app = _app(screen=HeadlessScreen(40, 6), keys=ScriptedEvents(()))
    controller = _Controller()
    app.mount(controller, dispatch=False)

    assert app.dispatch(key("x", "x")) is False
    assert controller.keys == []
    assert app.controllers == (controller,)


def test_a_form_owns_its_fields_and_a_click_moves_its_cursor():
    app = _app(screen=HeadlessScreen(40, 12), keys=ScriptedEvents(()))
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
    app.runtime.paint()

    row = next(y for y, line in enumerate(app.runtime.rows) if "Email" in line.text) + 1
    hit = app.workspace.hit(0, row)
    assert hit is not None
    assert app.focus_manager.click(hit) is True
    assert form.index == 1
    assert form.on_key(KeyEvent("b", "b")) is True
    assert email.text == "b"
    assert name.text == ""


# -- terminal options --------------------------------------------------------


def test_the_app_composes_a_runtime_workspace_and_terminal():
    screen = HeadlessScreen(20, 4)
    app = _app(screen=screen, keys=ScriptedEvents(()), auto=False)

    assert isinstance(app.runtime, Runtime)
    assert isinstance(app.workspace, Workspace)
    assert app.workspace is app.runtime.workspace
    assert app.terminal is app.runtime.terminal
    assert app.terminal.screen is screen
    assert not hasattr(app, "tui")  # the 1.x composition name is gone


def test_terminal_options_build_the_screen_and_input_the_driver_uses():
    screen = HeadlessScreen(20, 4)
    source = ScriptedEvents(())
    app = App(terminal=TerminalOptions(screen=screen, input=source), auto=False)

    assert isinstance(app.terminal, Terminal)
    assert app.terminal.screen is screen
    assert app.runtime.screen is screen
    assert app.runtime.keys is source


def test_terminal_options_win_over_the_legacy_arguments():
    legacy = HeadlessScreen(10, 2)
    chosen = HeadlessScreen(20, 5)
    app = App(terminal=TerminalOptions(screen=chosen), auto=False)
    assert app.terminal.screen is chosen
    assert app.runtime.screen is chosen
    with pytest.raises(TypeError):
        App(**{"screen": legacy})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        App(**{"keys": ScriptedEvents(())})  # type: ignore[arg-type]


def test_the_app_builds_its_terminal_from_the_options():
    screen = HeadlessScreen(30, 6)
    source = ScriptedEvents(())
    app = App(terminal=TerminalOptions(screen=screen, input=source), auto=False)

    assert isinstance(app.terminal, Terminal)
    assert app.terminal.screen is screen
    assert app.terminal.input is source
    assert app.runtime.screen is screen
    assert app.runtime.keys is source


def test_the_mouse_mode_flows_from_the_terminal_options_to_the_app():
    screen = HeadlessScreen()
    configured = App(terminal=TerminalOptions(screen=screen), auto=False)
    assert configured.terminal.options.mouse is MouseMode.MOVE
    without_motion = App(
        terminal=TerminalOptions(mouse=MouseMode.DRAG), auto=False
    )
    assert without_motion.terminal.options.mouse is MouseMode.DRAG
    off = App(terminal=TerminalOptions(mouse=MouseMode.OFF), auto=False)
    assert off.terminal.options.mouse is MouseMode.OFF


def test_an_app_with_terminal_options_paints_the_same_rows():
    app = App(
        terminal=TerminalOptions(screen=HeadlessScreen(20, 4)),
        auto=False,
    )
    app.add(Rows("one"))
    app.runtime.paint_now()
    assert rows(app.runtime) == ["one", "", "", ""]


async def test_two_apps_with_equal_terminal_options_paint_the_same_bytes():
    async def rendered(app: App) -> str:
        app.add(Rows("one"))
        app.add(Rows("two"))

        async def body(tui) -> None:
            tui.paint_now()

        await app.runtime.run_session(body)
        return app.runtime.screen.output

    legacy = _app(screen=HeadlessScreen(20, 4), keys=ScriptedEvents(()), auto=False)
    modern = App(
        terminal=TerminalOptions(
            screen=HeadlessScreen(20, 4), input=ScriptedEvents(())
        ),
        auto=False,
    )
    assert await rendered(legacy) == await rendered(modern)



# -- the handler chain -------------------------------------------------------


def test_the_default_chain_is_the_router_handlers():
    from motui.app import DEFAULT_HANDLERS

    app = _app(screen=HeadlessScreen(20, 4), keys=ScriptedEvents(()))
    assert app.handlers is DEFAULT_HANDLERS


def test_auto_false_builds_an_empty_chain():
    app = _app(screen=HeadlessScreen(20, 4), keys=ScriptedEvents(()), auto=False)
    assert app.handlers == ()
    assert app.dispatch(key("a", "a")) is False


def test_a_custom_chain_replaces_the_default_tiers_and_first_claim_wins():
    calls: list[str] = []

    def first(app: App, event) -> bool:
        calls.append("first")
        return False

    def second(app: App, event) -> bool:
        calls.append("second")
        return True

    def third(app: App, event) -> bool:
        calls.append("third")
        return True

    app = _app(
        screen=HeadlessScreen(20, 4),
        keys=ScriptedEvents(()),
        handlers=(first, second, third),
    )
    app.bind("b", lambda: calls.append("binding"))

    assert app.dispatch(key("a", "a")) is True
    assert calls == ["first", "second"]
    # The default tiers are really replaced: the second handler claims the
    # bound key before the App's own binding tier could run.
    calls.clear()
    assert app.dispatch(key("b", "b")) is True
    assert calls == ["first", "second"]


def test_an_explicit_chain_is_used_even_with_auto_false():
    calls: list[str] = []

    def only(app: App, event) -> bool:
        calls.append("only")
        return True

    app = _app(
        screen=HeadlessScreen(20, 4),
        keys=ScriptedEvents(()),
        auto=False,
        handlers=(only,),
    )
    assert app.dispatch(key("a", "a")) is True
    assert calls == ["only"]


def test_a_handler_sees_the_workspace_surface():
    seen: list[str] = []

    def inspect(app: App, event) -> bool:
        seen.append(app.workspace.document.blocks()[0].id)
        return False

    app = _app(
        screen=HeadlessScreen(20, 4),
        keys=ScriptedEvents(()),
        handlers=(inspect,),
    )
    app.add(Rows("one"))
    assert app.dispatch(key("a", "a")) is False
    assert seen == ["b0"]
