"""The runtime surface the controllers read: the clipboard and the layer exports."""

from __future__ import annotations

import motui
from motui.app import Runtime
from motui.terminal import HeadlessScreen
from tests.testing import headless_tui


class ClipboardScreen(HeadlessScreen):
    """A headless screen that records the clipboard texts pushed to it."""

    def __init__(self) -> None:
        super().__init__(10, 3)
        self.copied: list[str] = []

    def copy_to_clipboard(self, text: str) -> bool:
        self.copied.append(text)
        return True


def test_copy_to_clipboard_delegates_to_the_screen():
    screen = ClipboardScreen()
    runtime = Runtime(screen=screen)
    assert runtime.copy_to_clipboard("copied") is True
    assert screen.copied == ["copied"]


def test_headless_tui_answers_a_runtime():
    runtime = headless_tui()
    assert isinstance(runtime, Runtime)


def test_the_root_hands_out_the_app_and_the_app_layer_the_runtime():
    from motui.app import FocusManager, Workspace

    assert not hasattr(motui, "TUI")  # the 1.x root name is gone
    assert motui.App is not None
    assert Runtime.__module__ == "motui.app.runtime"
    assert Workspace.__module__ == "motui.app.workspace"
    assert FocusManager.__module__ == "motui.app.focus"
