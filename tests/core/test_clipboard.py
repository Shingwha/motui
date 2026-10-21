"""The clipboard capability: the protocol, the memory backend and forwarding
through a screen."""

from __future__ import annotations

import base64

from motui.core import Clipboard, MemoryClipboard, ScreenClipboard
from motui.core.screen import HeadlessScreen


class _RecordingScreen:
    def __init__(self, accepted: bool = True) -> None:
        self.accepted = accepted
        self.copied: list[str] = []

    def copy_to_clipboard(self, text: str) -> bool:
        self.copied.append(text)
        return self.accepted


def test_the_protocol_is_runtime_checkable_and_requires_copy():
    assert isinstance(MemoryClipboard(), Clipboard)
    assert isinstance(ScreenClipboard(_RecordingScreen()), Clipboard)
    assert not isinstance(object(), Clipboard)


def test_screen_clipboard_forwards_the_text_and_the_answer():
    screen = _RecordingScreen()
    clipboard = ScreenClipboard(screen)
    assert clipboard.copy("hello") is True
    assert clipboard.copy("again") is True
    assert screen.copied == ["hello", "again"]
    assert ScreenClipboard(_RecordingScreen(accepted=False)).copy("hello") is False


def test_screen_clipboard_writes_through_a_headless_screen():
    screen = HeadlessScreen(20, 4)
    assert ScreenClipboard(screen).copy("clip") is True
    encoded = base64.b64encode(b"clip").decode("ascii")
    assert f"]52;c;{encoded}" in screen.output


def test_memory_clipboard_records_the_last_text_verbatim():
    clipboard = MemoryClipboard()
    assert clipboard.text is None
    assert clipboard.copy("first") is True
    assert clipboard.text == "first"
    text = "line one\nline two\t\u4e2d"
    assert clipboard.copy(text) is True
    assert clipboard.text == text
    assert clipboard.copy("") is True
    assert clipboard.text == ""
