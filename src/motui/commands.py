"""Commands: the named actions a host binds to keys and a palette.

A :class:`Command` is a value: a stable name, a human description, an
optional handler, the key names it answers to and an enabled flag.  The
:class:`CommandRegistry` is the ordered collection a host fills once and
then resolves by name, by key press or by a palette query.  It owns no
screen and no widget: the composition root calls ``invoke`` from its own
dispatch and hands ``options()`` to a :class:`~motui.interaction.command_palette.CommandPalette`.

The registry keeps insertion order throughout -- iteration, matching and
``options()`` -- so a palette's rows are stable and a host controls their
priority.  Matching is a case-insensitive substring over the name and the
description; disabled commands stay registered (a host may still invoke
them explicitly) but are filtered out of ``match`` by default and
``invoke`` refuses them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from .widgets.choice import Option

__all__ = ["Command", "CommandRegistry"]


@dataclass(frozen=True, slots=True)
class Command:
    """One named action: description, handler, key bindings and enabled flag.

    ``keys`` is normalized to a tuple at construction (a list argument is
    copied), so the value is hashable and cannot be mutated behind the
    registry's back.  ``handler`` receives whatever the caller passes to
    :meth:`CommandRegistry.invoke`; ``None`` means the command is
    declarative -- it matches and lists, but invocation is a no-op.
    """

    name: str
    description: str = ""
    handler: Callable[..., object] | None = None
    keys: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "keys", tuple(self.keys))


class CommandRegistry:
    """An ordered, name-addressed command collection.

    Adding a name twice raises :class:`ValueError` (names are the registry's
    identity, like block ids); removing or looking up a missing name raises
    :class:`KeyError`.  A key bound by more than one command resolves to the
    first command added, so a host presses a key and gets one action --
    later duplicates never silently shadow the original.
    """

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
        """Detach and return the command ``name``; a missing one raises ``KeyError``."""
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
        """Commands whose name or description contains ``query``, in order.

        Case-insensitive and substring-based; the empty query matches every
        candidate.  Disabled commands are left out unless
        ``include_disabled`` is true.
        """
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
        """The first command bound to ``key``, enabled or not; ``None`` when unbound.

        The raw command comes back even when disabled so a host can explain
        why the key did nothing; :meth:`invoke` is the enforcement point.
        """
        for command in self._commands.values():
            if key in command.keys:
                return command
        return None

    def invoke(self, name: str, *args, **kwargs) -> object | None:
        """Call the command's handler; ``None`` when disabled or handler-less.

        A missing name raises :class:`KeyError` (the registry's lookup
        contract).  The handler's own return value is passed back unchanged.
        """
        command = self.get(name)
        if not command.enabled or command.handler is None:
            return None
        return command.handler(*args, **kwargs)

    def options(self) -> list[Option]:
        """The registry as palette options: label=name, value=command, description.

        Every registered command is included, in insertion order; filtering
        is :meth:`match`'s job.  The command itself is the option's payload,
        so a palette's pick invokes the value the host already holds.
        """
        return [
            Option(command.name, command, command.description)
            for command in self._commands.values()
        ]

    def __repr__(self) -> str:
        return f"CommandRegistry({len(self._commands)} commands)"
