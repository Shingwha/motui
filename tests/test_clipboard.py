"""Tests for motui.kernel.clipboard: the copy capability.

``Clipboard`` is one runtime-checkable protocol; ``ScreenClipboard``
forwards to the screen's OSC 52 door; ``MemoryClipboard`` records the last
text and answers ``True``.
"""

from __future__ import annotations

import base64

from motui.kernel import Clipboard, MemoryClipboard, ScreenClipboard
from motui.kernel.screen import HeadlessScreen


class _RecordingScreen:
    """Screen double: records copies, answers a scripted result."""

    def __init__(self, accepted: bool = True) -> None:
        self.accepted = accepted
        self.copied: list[str] = []

    def copy_to_clipboard(self, text: str) -> bool:
        self.copied.append(text)
        return self.accepted


def test_the_protocol_is_runtime_checkable_for_both_backends():
    assert isinstance(MemoryClipboard(), Clipboard)
    assert isinstance(ScreenClipboard(_RecordingScreen()), Clipboard)


def test_an_object_without_copy_is_not_a_clipboard():
    assert not isinstance(object(), Clipboard)


def test_screen_clipboard_forwards_the_text_and_the_answer():
    screen = _RecordingScreen()
    clipboard = ScreenClipboard(screen)
    assert clipboard.copy("hello") is True
    assert screen.copied == ["hello"]
    assert clipboard.copy("again") is True
    assert screen.copied == ["hello", "again"]


def test_screen_clipboard_reports_a_refused_write():
    screen = _RecordingScreen(accepted=False)
    assert ScreenClipboard(screen).copy("hello") is False
    assert screen.copied == ["hello"]


def test_screen_clipboard_writes_through_a_headless_screen():
    screen = HeadlessScreen(20, 4)
    clipboard = ScreenClipboard(screen)
    assert clipboard.copy("clip") is True
    encoded = base64.b64encode(b"clip").decode("ascii")
    assert f"]52;c;{encoded}" in screen.output  # the OSC 52 payload is recorded


def test_memory_clipboard_records_the_last_text():
    clipboard = MemoryClipboard()
    assert clipboard.text is None
    assert clipboard.copy("first") is True
    assert clipboard.text == "first"
    assert clipboard.copy("second") is True
    assert clipboard.text == "second"
    # The empty string is a value, not "nothing copied".
    assert clipboard.copy("") is True
    assert clipboard.text == ""


def test_the_memory_clipboard_keeps_the_text_verbatim():
    clipboard = MemoryClipboard()
    text = "line one\nline two\t中"
    clipboard.copy(text)
    assert clipboard.text == text
