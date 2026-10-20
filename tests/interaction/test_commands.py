"""The command value and the ordered registry: lookup, matching and invocation."""

from __future__ import annotations

import pytest

from motui.commands import Command, CommandRegistry
from motui.widgets import Option


def test_equal_commands_compare_and_hash_by_value():
    assert Command("save", "Save", keys=("c-s",)) == Command(
        "save", "Save", keys=("c-s",)
    )
    assert hash(Command("save", keys=["c-s"])) == hash(Command("save", keys=("c-s",)))


def test_commands_keep_insertion_order():
    first, second = Command("first"), Command("second")
    registry = CommandRegistry([first, second])
    assert list(registry) == [first, second]
    assert len(registry) == 2


def test_add_get_and_remove_address_by_name():
    first, second = Command("first"), Command("second")
    registry = CommandRegistry()
    registry.add(first)
    registry.add(second)
    assert registry.get("first") is first
    assert registry.remove("second") is second
    assert list(registry) == [first]
    with pytest.raises(KeyError):
        registry.get("second")
    with pytest.raises(KeyError):
        registry.remove("second")


def test_a_duplicate_name_raises_and_keeps_the_original():
    original = Command("save", description="original")
    registry = CommandRegistry([original])
    with pytest.raises(ValueError):
        registry.add(Command("save", description="replacement"))
    assert registry.get("save") is original
    with pytest.raises(ValueError):
        CommandRegistry([Command("save"), Command("save")])


def test_match_is_a_case_insensitive_substring_of_name_or_description():
    registry = CommandRegistry(
        [
            Command("Save File", "Write the document"),
            Command("quit", "Close the app"),
            Command("copy", "SAVE to clipboard"),
        ]
    )
    assert [command.name for command in registry.match("save")] == ["Save File", "copy"]
    assert [command.name for command in registry.match("FILE")] == ["Save File"]
    assert [command.name for command in registry.match("write")] == ["Save File"]
    assert registry.match("zzz") == []


def test_match_filters_disabled_unless_asked():
    registry = CommandRegistry(
        [Command("on", "a live action"), Command("off", "a dead action", enabled=False)]
    )
    assert [command.name for command in registry.match("action")] == ["on"]
    assert [command.name for command in registry.match("action", include_disabled=True)] == [
        "on",
        "off",
    ]
    assert [command.name for command in registry.match("")] == ["on"]


def test_by_key_answers_the_first_command_bound_to_a_key():
    first = Command("first", keys=("c-s", "f2"))
    second = Command("second", keys=("c-s",))
    registry = CommandRegistry([first, second])
    assert registry.by_key("c-s") is first
    assert registry.by_key("f2") is first
    assert registry.by_key("f3") is None


def test_by_key_answers_a_disabled_command_but_invoke_refuses_it():
    command = Command("off", keys=("f9",), enabled=False)
    registry = CommandRegistry([command])
    assert registry.by_key("f9") is command
    assert registry.invoke("off") is None


def test_invoke_calls_the_handler_with_the_given_arguments():
    calls: list[tuple] = []
    registry = CommandRegistry(
        [Command("add", handler=lambda a, b=0: calls.append((a, b)) or a + b)]
    )
    assert registry.invoke("add", 2, b=3) == 5
    assert calls == [(2, 3)]


def test_invoke_returns_none_for_a_disabled_or_handlerless_command():
    disabled_calls: list[object] = []
    registry = CommandRegistry(
        [
            Command("off", handler=disabled_calls.append, enabled=False),
            Command("declarative"),
        ]
    )
    assert registry.invoke("off", "x") is None
    assert disabled_calls == []
    assert registry.invoke("declarative") is None


def test_invoke_an_unknown_name_raises():
    with pytest.raises(KeyError):
        CommandRegistry().invoke("missing")


def test_options_map_every_command_in_order():
    first = Command("first", "First action", keys=("f1",))
    second = Command("second", enabled=False)
    options = CommandRegistry([first, second]).options()
    assert options == [
        Option("first", first, "First action"),
        Option("second", second, ""),
    ]
