"""The command value and the ordered registry: lookup, matching and invocation."""

from __future__ import annotations

import pytest

from motui.app.commands import Command, CommandRegistry
from motui.widgets import Option


def test_equal_commands_compare_and_hash_by_value():
    assert Command(name="save", description="Save", keys=("c-s",)) == Command(
        name="save", description="Save", keys=("c-s",)
    )
    assert hash(Command(name="save", keys=["c-s"])) == hash(
        Command(name="save", keys=("c-s",))
    )
    assert Command(name="save") != Command(name="save", group="File")


def test_group_is_a_first_class_field():
    command = Command(name="theme.next", group="Appearance", description="Switch")
    assert (command.name, command.group, command.description) == (
        "theme.next",
        "Appearance",
        "Switch",
    )
    assert Command(name="save").group == ""


def test_commands_are_keyword_only():
    with pytest.raises(TypeError):
        Command("save", "Save", "File")  # type: ignore[misc]


def test_the_legacy_positional_form_still_constructs_a_command():
    """The frozen demo calls ``Command(name, description)``; W5 removes this."""
    assert Command("save", "Save") == Command(name="save", description="Save")


def test_commands_keep_insertion_order():
    first, second = Command(name="first"), Command(name="second")
    registry = CommandRegistry([first, second])
    assert list(registry) == [first, second]
    assert len(registry) == 2


def test_add_get_and_remove_address_by_name():
    first, second = Command(name="first"), Command(name="second")
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
    original = Command(name="save", description="original")
    registry = CommandRegistry([original])
    with pytest.raises(ValueError):
        registry.add(Command(name="save", description="replacement"))
    assert registry.get("save") is original
    with pytest.raises(ValueError):
        CommandRegistry([Command(name="save"), Command(name="save")])


def test_match_is_a_case_insensitive_substring_of_name_or_description():
    registry = CommandRegistry(
        [
            Command(name="Save File", description="Write the document"),
            Command(name="quit", description="Close the app"),
            Command(name="copy", description="SAVE to clipboard"),
        ]
    )
    assert [command.name for command in registry.match("save")] == ["Save File", "copy"]
    assert [command.name for command in registry.match("FILE")] == ["Save File"]
    assert [command.name for command in registry.match("write")] == ["Save File"]
    assert registry.match("zzz") == []


def test_match_filters_disabled_unless_asked():
    registry = CommandRegistry(
        [
            Command(name="on", description="a live action"),
            Command(name="off", description="a dead action", enabled=False),
        ]
    )
    assert [command.name for command in registry.match("action")] == ["on"]
    assert [command.name for command in registry.match("action", include_disabled=True)] == [
        "on",
        "off",
    ]
    assert [command.name for command in registry.match("")] == ["on"]


def test_by_key_answers_the_first_command_bound_to_a_key():
    first = Command(name="first", keys=("c-s", "f2"))
    second = Command(name="second", keys=("c-s",))
    registry = CommandRegistry([first, second])
    assert registry.by_key("c-s") is first
    assert registry.by_key("f2") is first
    assert registry.by_key("f3") is None


def test_by_key_answers_a_disabled_command_but_invoke_refuses_it():
    command = Command(name="off", keys=("f9",), enabled=False)
    registry = CommandRegistry([command])
    assert registry.by_key("f9") is command
    assert registry.invoke("off") is None


def test_invoke_calls_the_handler_with_the_given_arguments():
    calls: list[tuple] = []
    registry = CommandRegistry(
        [Command(name="add", handler=lambda a, b=0: calls.append((a, b)) or a + b)]
    )
    assert registry.invoke("add", 2, b=3) == 5
    assert calls == [(2, 3)]


def test_invoke_returns_none_for_a_disabled_or_handlerless_command():
    disabled_calls: list[object] = []
    registry = CommandRegistry(
        [
            Command(name="off", handler=disabled_calls.append, enabled=False),
            Command(name="declarative"),
        ]
    )
    assert registry.invoke("off", "x") is None
    assert disabled_calls == []
    assert registry.invoke("declarative") is None


def test_invoke_an_unknown_name_raises():
    with pytest.raises(KeyError):
        CommandRegistry().invoke("missing")


class _Host:
    """The smallest object ``bind`` needs: a key -> callback table."""

    def __init__(self) -> None:
        self.bindings: dict[str, object] = {}

    def bind(self, key: str, callback) -> None:
        self.bindings[key] = callback


def test_bind_routes_every_key_to_an_invoke_of_its_command():
    calls: list[str] = []
    registry = CommandRegistry(
        [
            Command(
                name="save",
                handler=lambda: calls.append("save"),
                keys=("c-s", "f2"),
            ),
            Command(
                name="quit",
                handler=lambda: calls.append("quit"),
                keys=("c-q",),
            ),
            Command(name="declarative", keys=("f3",)),
        ]
    )
    host = _Host()

    assert registry.bind(host) is None
    assert set(host.bindings) == {"c-s", "f2", "c-q", "f3"}
    for key in ("c-s", "f2", "c-q", "f3"):
        host.bindings[key]()
    assert calls == ["save", "save", "quit"]


def test_bind_keeps_a_disabled_command_bound_but_invoke_refuses_it():
    calls: list[object] = []
    registry = CommandRegistry(
        [Command(name="off", handler=calls.append, keys=("f9",), enabled=False)]
    )
    host = _Host()
    registry.bind(host)

    host.bindings["f9"]()

    assert calls == []


def test_options_map_every_command_in_order():
    first = Command(name="first", description="First action", keys=("f1",))
    second = Command(name="second", enabled=False, group="File")
    options = CommandRegistry([first, second]).options()
    assert options == [
        Option("first", first, "First action"),
        Option("second", second, ""),
    ]
