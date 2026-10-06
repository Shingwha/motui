"""Document model: addressable blocks rendered by components.

The toolkit's unit of content is a :class:`Block`: a stable id, a
:class:`Component` that knows how to render itself at a given width, and a
two-state lifecycle.  There is deliberately no "committed" state: in a
full-screen rewrite there is no terminal history to append into, so a block is
either :class:`BlockState.OPEN` (still being written to) or
:class:`BlockState.SEALED` (frozen content).
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from .lines import Line

__all__ = ["Activable", "Block", "BlockState", "Clickable", "Component", "Document"]


@runtime_checkable
class Component(Protocol):
    """Anything that renders itself into rows: ``render(width) -> list[Line]``.

    The one protocol the document model knows: a component is handed the
    columns available to it (the screen width in full-screen mode) and
    answers with the rows it wants painted there.  Nothing else about its
    host is promised, and nothing about its own state is assumed.
    """

    def render(self, width: int) -> list[Line]:
        ...


@runtime_checkable
class Clickable(Protocol):
    """A component that can consume a click on one of its own cells.

    ``row``/``col`` are a 0-based cell of the component's own ``render``
    output -- exactly what :meth:`~mocode_tui.app.TUI.hit_test` reports as
    ``Hit.row``/``Hit.col`` -- so the component absorbs its own layout
    arithmetic (a title row above the options, a scrolled window, the
    segment widths of a tab strip).  ``col`` deliberately has **no default
    value**: a host always holds both coordinates, and a default would let
    an implementation ignore the column without ever deciding to.  A
    row-shaped component -- a vertical list, a tree -- ignores ``col`` and
    **must say so in its own docstring**; the column is never dropped
    silently.  The answer says whether the click landed on something the
    component consumes (``True``) or fell outside (``False``); a hit moves
    the component's cursor.  Optional: a component without ``click`` simply
    is not clickable, and a host checks ``isinstance(component, Clickable)``
    before dispatching.
    """

    def click(self, row: int, col: int) -> bool:
        ...


@runtime_checkable
class Activable(Protocol):
    """A component that can execute the thing under its cursor.

    ``activate()`` is the one verb for "the cursor is on something and the
    return key takes it": the menu family (``Select``, ``Confirm``,
    ``Autocomplete``) takes the option under its cursor into ``chosen``,
    and a ``Tree`` expands or collapses the node under its cursor.  The
    answer says whether there was something to take (``False`` for an
    empty menu, a leaf, ...).  The protocol is deliberately narrow: a
    component with no cursor item -- a text field, a tab strip, a table
    container -- does not implement it, and *setting* a value is not
    activation (the tab strip selects, it does not activate).  Optional:
    a host checks ``isinstance(component, Activable)`` before dispatching
    the return key, and reads a menu's ``chosen`` once afterwards.
    """

    def activate(self) -> bool:
        ...


class BlockState(Enum):
    """Lifecycle of a block: open (writable) or sealed (frozen). No COMMITTED."""

    OPEN = "open"
    SEALED = "sealed"


class Block:
    """One addressable row-producing unit inside a :class:`Document`."""

    __slots__ = ("_component", "_id", "_pin", "_state")

    def __init__(self, id: str, component: Component, *, pin: str | None = None) -> None:
        if pin not in (None, "top", "bottom"):
            raise ValueError(f"pin must be 'top', 'bottom' or None, got {pin!r}")
        self._id = id
        self._component = component
        self._pin = pin
        self._state = BlockState.OPEN

    @property
    def id(self) -> str:
        return self._id

    @property
    def component(self) -> Component:
        return self._component

    @property
    def state(self) -> BlockState:
        return self._state

    @property
    def pin(self) -> str | None:
        """Fixed region of the block: ``"top"``, ``"bottom"``, or ``None``.

        ``None`` (the default) leaves the block in the scrollable body;
        ``"top"``/``"bottom"`` place it in the matching fixed region of the
        screen, which never scrolls away.
        """
        return self._pin

    @property
    def is_open(self) -> bool:
        return self._state is BlockState.OPEN

    def seal(self) -> None:
        """Freeze the block: OPEN -> SEALED. Sealing twice raises ValueError."""
        if self._state is not BlockState.OPEN:
            raise ValueError(f"block {self._id!r} is already sealed")
        self._state = BlockState.SEALED

    def render(self, width: int) -> list[Line]:
        """Forward rendering to the block's component."""
        return self._component.render(width)

    def __repr__(self) -> str:
        return (
            f"Block(id={self._id!r}, state={self._state.value}, "
            f"pin={self._pin!r})"
        )


class Document:
    """An ordered collection of blocks, addressable by id."""

    def __init__(self) -> None:
        self._blocks: list[Block] = []
        self._by_id: dict[str, Block] = {}
        self._auto_index = -1  # first generated id is "b0"

    def _next_auto_id(self) -> str:
        """The first ``b{n}`` id past the last one handed out that is free.

        The candidate is derived from the cursor and advanced past every id
        the document already holds -- an explicit ``b0`` pushes the first
        auto id to ``b1`` -- so a generated id never collides with one a
        caller claimed; the cursor lands on the id handed out.
        """
        index = self._auto_index + 1
        while f"b{index}" in self._by_id:
            index += 1
        self._auto_index = index
        return f"b{index}"

    def add(
        self,
        component: Component,
        *,
        id: str | None = None,
        pin: str | None = None,
    ) -> Block:
        """Append a block; auto id ``b{n}`` when ``id`` is None. Duplicate ids raise.

        ``pin`` places the block in a fixed region -- ``"top"`` or
        ``"bottom"`` -- or leaves it in the scrollable body (``None``, the
        default).  Anything else raises ``ValueError``.
        """
        if id is None:
            id = self._next_auto_id()
        elif id in self._by_id:
            raise ValueError(f"duplicate block id: {id!r}")
        block = Block(id, component, pin=pin)
        self._blocks.append(block)
        self._by_id[id] = block
        return block

    def get(self, id: str) -> Block:
        """The block with ``id``; missing id raises KeyError with a message."""
        try:
            return self._by_id[id]
        except KeyError:
            raise KeyError(f"no block with id {id!r}") from None

    def remove(self, id: str) -> Block:
        """Detach the block with ``id`` and return it; missing id raises KeyError."""
        block = self.get(id)
        self._blocks.remove(block)
        del self._by_id[id]
        return block

    def blocks(self) -> tuple[Block, ...]:
        """Snapshot of the blocks in document order (immune to later mutation)."""
        return tuple(self._blocks)

    def __len__(self) -> int:
        return len(self._blocks)

    def __repr__(self) -> str:
        return f"Document({len(self._blocks)} blocks)"
