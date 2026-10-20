"""Tests for the frozen 1.2 event model in motui.kernel.events.

The five value types are frozen, value-equal, hashable and mutually
exclusive: a mouse report is never a key.  The source protocol is runtime
checkable, and ``motui.testing.ScriptedEvents`` is its in-memory replay.
"""

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
from motui.testing import ScriptedEvents

_EVENT_TYPES = (KeyEvent, MouseEvent, PasteEvent, ResizeEvent, FocusEvent)


def test_every_event_type_is_an_event():
    assert all(issubclass(kind, Event) for kind in _EVENT_TYPES)


def test_only_the_keyboard_is_a_key_event():
    # The five types are siblings: no mouse report, paste, resize or focus
    # report may be mistaken for a key press by an isinstance() test.
    assert isinstance(KeyEvent("a"), Event)
    for event in (
        MouseEvent("left", 1, 2),
        PasteEvent("text"),
        ResizeEvent(80, 24),
        FocusEvent(True),
    ):
        assert isinstance(event, Event)
        assert not isinstance(event, KeyEvent), event


def test_events_are_frozen():
    event = KeyEvent("a", "a")
    with pytest.raises(FrozenInstanceError):
        event.key = "b"  # type: ignore[misc]
    mouse = MouseEvent("left")
    with pytest.raises(FrozenInstanceError):
        mouse.button = "right"  # type: ignore[misc]


def test_events_are_value_equal_and_hashable():
    assert KeyEvent("a", "a") == KeyEvent("a", "a")
    assert KeyEvent("a", "a") != KeyEvent("a", "A")
    assert hash(KeyEvent("a", "a")) == hash(KeyEvent("a", "a"))
    assert MouseEvent("left", 1, 2) == MouseEvent("left", 1, 2)
    assert MouseEvent("left", 1, 2) != MouseEvent("left", 2, 1)
    assert PasteEvent("x") == PasteEvent("x")
    assert ResizeEvent(80, 24) == ResizeEvent(80, 24)
    assert FocusEvent(True) == FocusEvent(True)
    assert FocusEvent(True) != FocusEvent(False)
    assert len({KeyEvent("a"), KeyEvent("a"), KeyEvent("b")}) == 2


def test_key_event_defaults():
    event = KeyEvent("up")
    assert event.char == ""
    assert event.modifiers == frozenset()
    assert event.kind == "press"
    assert KeyEvent("c-s-left", "", frozenset({"ctrl", "shift"})).modifiers == frozenset(
        {"ctrl", "shift"}
    )


def test_mouse_event_defaults_and_fields():
    event = MouseEvent()
    assert (event.button, event.x, event.y, event.kind) == ("none", 0, 0, "press")
    assert event.modifiers == frozenset()
    wheel = MouseEvent("wheel_up", 4, 2, "wheel", frozenset({"ctrl"}))
    assert (wheel.button, wheel.x, wheel.y, wheel.kind) == ("wheel_up", 4, 2, "wheel")
    assert wheel.modifiers == frozenset({"ctrl"})


def test_events_carry_no_timestamp():
    # Time enters through the driver's clock() seam, never through an event.
    for event in (KeyEvent("a"), MouseEvent(), PasteEvent(""), ResizeEvent(0, 0), FocusEvent(False)):
        assert not hasattr(event, "time")
        assert not hasattr(event, "timestamp")
        assert not hasattr(event, "clock")


def test_event_source_is_a_runtime_checkable_protocol():
    source = ScriptedEvents([KeyEvent("a")])
    assert isinstance(source, EventSource)

    class NotASource:
        pass

    assert not isinstance(NotASource(), EventSource)


async def test_scripted_events_replays_then_eofs():
    source = ScriptedEvents([KeyEvent("a", "a"), PasteEvent("x"), None, KeyEvent("z")])
    assert await source.read() == KeyEvent("a", "a")
    assert await source.read() == PasteEvent("x")
    assert await source.read() is None  # a one-shot EOF signal
    assert await source.read() == KeyEvent("z")  # replay resumes after it
    assert await source.read() is None  # exhausted: EOF forever
    assert await source.read() is None


async def test_scripted_events_supports_every_event_type():
    events = [
        KeyEvent("c-c"),
        MouseEvent("left", 1, 2, "press"),
        PasteEvent("literal"),
        ResizeEvent(120, 40),
        FocusEvent(False),
    ]
    source = ScriptedEvents(events)
    assert [await source.read() for _ in events] == events
    assert await source.read() is None
