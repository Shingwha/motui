"""The driver surface the controllers read: the clipboard and the root exports."""

from __future__ import annotations

import motui
from motui import TUI
from motui.core import HeadlessScreen
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
    tui = TUI(screen=screen)
    assert tui.copy_to_clipboard("copied") is True
    assert screen.copied == ["copied"]


def test_the_root_hands_out_the_driver_and_the_focus_manager():
    from motui.app import FocusManager

    assert motui.TUI is TUI
    assert motui.FocusManager is FocusManager
