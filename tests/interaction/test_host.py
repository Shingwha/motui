"""The Host seam: the driver satisfies it, its factories build real widgets."""

from __future__ import annotations

import motui
from motui import TUI
from motui.core import HeadlessScreen
from motui.core.host import Host
from tests.testing import headless_tui, key


class ClipboardScreen(HeadlessScreen):
    """A headless screen that records the clipboard texts pushed to it."""

    def __init__(self) -> None:
        super().__init__(10, 3)
        self.copied: list[str] = []

    def copy_to_clipboard(self, text: str) -> bool:
        self.copied.append(text)
        return True


def test_tui_structurally_satisfies_the_host_protocol():
    tui = headless_tui(20, 5)
    assert isinstance(tui, Host)
    assert isinstance(tui.screen, HeadlessScreen)
    assert tui.frame is not None


def test_the_host_protocol_rejects_a_partial_object():
    class Partial:
        screen = None
        frame = None

    assert not isinstance(Partial(), Host)


def test_make_input_builds_a_real_handleable_field():
    tui = headless_tui(20, 5)
    field = tui.make_input(prompt="? ")
    assert field.render(10)
    assert field.handle(key("a", "a")) is True
    assert field.text == "a"


def test_make_autocomplete_builds_a_filterable_list():
    from motui.widgets.choice import Option

    tui = headless_tui(20, 5)
    options = [Option("alpha", value=1), Option("beta", value=2)]
    auto = tui.make_autocomplete(options, max_rows=2)
    auto.set_query("be")
    assert auto.take_result() is None
    auto.activate()
    assert auto.take_result() == options[1]


def test_copy_to_clipboard_delegates_to_the_screen():
    screen = ClipboardScreen()
    tui = TUI(screen=screen)
    assert tui.copy_to_clipboard("copied") is True
    assert screen.copied == ["copied"]


def test_the_root_hands_out_the_driver_and_the_focus_manager():
    from motui.app import FocusManager

    assert motui.TUI is TUI
    assert motui.FocusManager is FocusManager
