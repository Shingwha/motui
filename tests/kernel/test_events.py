"""The frozen event model: value types, defaults, equality, type exclusivity
and the EventSource protocol."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from motui.kernel.events import (
    Event,
    EventSource,
    FocusEvent,
    KeyEvent,
    MouseEvent,
    PasteEvent,
    ResizeEvent,
)

EVENT_TYPES = (KeyEvent, MouseEvent, PasteEvent, ResizeEvent, FocusEvent)


def test_every_event_type_is_an_event():
    assert all(issubclass(kind, Event) for kind in EVENT_TYPES)


def test_only_the_keyboard_is_a_key_event():
    assert isinstance(KeyEvent("a"), Event)
    for event in (MouseEvent("left", 1, 2), PasteEvent("text"), ResizeEvent(80, 24), FocusEvent(True)):
        assert isinstance(event, Event)
        assert not isinstance(event, KeyEvent)


def test_events_are_frozen():
    with pytest.raises(FrozenInstanceError):
        KeyEvent("a", "a").key = "b"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        MouseEvent("left").button = "right"  # type: ignore[misc]


def test_events_are_value_equal_and_hashable():
    assert KeyEvent("a", "a") == KeyEvent("a", "a")
    assert KeyEvent("a", "a") != KeyEvent("a", "A")
    assert hash(KeyEvent("a", "a")) == hash(KeyEvent("a", "a"))
    assert MouseEvent("left", 1, 2) != MouseEvent("left", 2, 1)
    assert FocusEvent(True) != FocusEvent(False)
    assert len({KeyEvent("a"), KeyEvent("a"), KeyEvent("b")}) == 2


def test_key_and_mouse_event_defaults():
    event = KeyEvent("up")
    assert (event.char, event.modifiers, event.kind) == ("", frozenset(), "press")
    assert KeyEvent("c-s-left", "", frozenset({"ctrl", "shift"})).modifiers == frozenset(
        {"ctrl", "shift"}
    )
    mouse = MouseEvent()
    assert (mouse.button, mouse.x, mouse.y, mouse.kind) == ("none", 0, 0, "press")
    wheel = MouseEvent("wheel_up", 4, 2, "wheel", frozenset({"ctrl"}))
    assert (wheel.button, wheel.x, wheel.y, wheel.kind) == ("wheel_up", 4, 2, "wheel")
    assert wheel.modifiers == frozenset({"ctrl"})


def test_events_carry_no_timestamp():
    for event in (KeyEvent("a"), MouseEvent(), PasteEvent(""), ResizeEvent(0, 0), FocusEvent(False)):
        assert not hasattr(event, "time")
        assert not hasattr(event, "timestamp")


def test_event_source_is_a_runtime_checkable_protocol():
    class Source:
        async def read(self):
            return None

    class NotASource:
        pass

    assert isinstance(Source(), EventSource)
    assert not isinstance(NotASource(), EventSource)
