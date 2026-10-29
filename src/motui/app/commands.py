"""Commands: the named actions a host binds to keys and a palette.

Insertion order is stable throughout; matching is a case-insensitive
substring. Disabled commands stay registered but are filtered and
refused."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..widgets.choice import Option

if TYPE_CHECKING:
    from .application import App

__all__ = ["Command", "CommandRegistry"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Command:
    """One named action: name, description, group, handler, keys and enabled
    flag; ``keys`` is normalized to a tuple at construction."""

    name: str
    description: str = ""
    group: str = ""
    handler: Callable[..., object] | None = None
    keys: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "keys", tuple(self.keys))


class CommandRegistry:
    """An ordered, name-addressed command collection.

    Duplicate names raise ``ValueError``; a key bound twice resolves to the
    first command added."""

    __slots__ = ("_commands",)

    def __init__(self, commands: Iterable[Command] = ()) -> None:
        self._commands: dict[str, Command] = {}
        for command in commands:
            self.add(command)

    # -- collection -------------------------------------------------------------

    def __iter__(self) -> Iterator[Command]:
        return iter(self._commands.values())

    def __len__(self) -> int:
        return len(self._commands)

    def add(self, command: Command) -> None:
        """Register ``command``; a duplicate name raises :class:`ValueError`."""
        if command.name in self._commands:
            raise ValueError(f"duplicate command name: {command.name!r}")
        self._commands[command.name] = command

    def remove(self, name: str) -> Command:
        """Detach and return the command ``name``; a missing one raises
        :class:`KeyError`."""
        try:
            return self._commands.pop(name)
        except KeyError:
            raise KeyError(f"no command named {name!r}") from None

    def get(self, name: str) -> Command:
        """The command ``name``; a missing one raises :class:`KeyError`."""
        try:
            return self._commands[name]
        except KeyError:
            raise KeyError(f"no command named {name!r}") from None

    # -- resolution -------------------------------------------------------------

    def match(self, query: str, *, include_disabled: bool = False) -> list[Command]:
        """Commands whose name or description contains ``query``, in order;
        case-insensitive and substring-based."""
        needle = query.lower()
        return [
            command
            for command in self._commands.values()
            if (include_disabled or command.enabled)
            and (
                needle in command.name.lower()
                or needle in command.description.lower()
            )
        ]

    def by_key(self, key: str) -> Command | None:
        """The first command bound to ``key``, enabled or not; ``None`` when
        unbound."""
        for command in self._commands.values():
            if key in command.keys:
                return command
        return None

    def invoke(self, name: str, *args, **kwargs) -> object | None:
        """Call the command's handler; ``None`` when disabled or handler-less, and
        a missing name raises :class:`KeyError`."""
        command = self.get(name)
        if not command.enabled or command.handler is None:
            return None
        return command.handler(*args, **kwargs)

    def bind(self, app: App) -> None:
        """Route every command key to an invoke of that command on ``app``, closing
        over the name so later edits are seen."""
        for command in self._commands.values():
            for key in command.keys:
                app.bind(key, lambda name=command.name: self.invoke(name))

    def options(self) -> list[Option]:
        """The registry as palette options: label=name, value=command,
        description."""
        return [
            Option(command.name, command, command.description)
            for command in self._commands.values()
        ]

    def __repr__(self) -> str:
        return f"CommandRegistry({len(self._commands)} commands)"
