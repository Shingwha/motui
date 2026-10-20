"""Tests for the Host seam: the protocol, the driver's factories and values.

``Host`` is the narrow driver surface the interaction tiers see.  ``TUI``
structurally satisfies it; the value types (``Hit``/``RowRange``/
``EveryHandle``) live in ``kernel.host`` and are re-exported by the kernel
facade, not by ``motui.app``.  The driver's composition-root factories build
the widgets a self-contained tier needs, and its clipboard write delegates
to the screen.
"""

from __future__ import annotations

import motui
import motui.app
import motui.kernel as kernel
from motui import KeyEvent, TUI
from motui.kernel import HeadlessScreen
from motui.kernel.host import EveryHandle, Hit, Host, RowRange
from motui.testing import headless_tui


class _RecordingScreen(HeadlessScreen):
    """A headless screen that records the clipboard texts the driver pushes."""

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


def test_the_host_protocol_is_runtime_checkable_and_rejects_a_partial_object():
    class Partial:
        screen = None
        frame = None

    assert not isinstance(Partial(), Host)


def test_hit_rowrange_and_everyhandle_live_at_kernel_host_and_the_kernel_facade():
    assert kernel.Hit is Hit
    assert kernel.RowRange is RowRange
    assert kernel.EveryHandle is EveryHandle
    assert kernel.Host is Host
    # The driver facade no longer republishes the value types.
    assert motui.app.__all__ == ["TUI"]
    for name in ("Hit", "RowRange", "EveryHandle"):
        assert name not in motui.app.__all__
    assert isinstance(RowRange(0, 3), RowRange)
    handle = EveryHandle()
    assert handle.cancelled is False
    handle.cancel()
    assert handle.cancelled is True


def test_make_input_builds_a_real_handleable_field():
    tui = headless_tui(20, 5)
    field = tui.make_input(prompt="? ")
    assert field.render(10)
    assert field.handle(KeyEvent("a", "a")) is True
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
    screen = _RecordingScreen()
    tui = TUI(screen=screen)
    assert tui.copy_to_clipboard("copied") is True
    assert screen.copied == ["copied"]


def test_the_root_still_hands_out_the_driver_and_the_focus_manager():
    assert motui.TUI is TUI
    assert motui.FocusManager is not None
