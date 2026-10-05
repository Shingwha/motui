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

__all__ = ["Block", "BlockState", "Component", "Document"]


@runtime_checkable
class Component(Protocol):
    """Anything that renders itself into rows: ``render(width) -> list[Line]``.

    This protocol is frozen from W1 onward: every later wave keeps this exact
    signature, with ``width`` being the available columns (the screen width in
    full-screen mode).
    """

    def render(self, width: int) -> list[Line]:
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
    def pinned(self) -> bool:
        """Derived query: whether the block sits in the bottom fixed region."""
        return self._pin == "bottom"

    @property
    def is_open(self) -> bool:
        return self._state is BlockState.OPEN

    def set_component(self, component: Component) -> None:
        """Swap the component; allowed in any state."""
        self._component = component

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
        self._auto_index += 1
        candidate = f"b{self._auto_index}"
        while candidate in self._by_id:  # keep auto ids clear of explicit ones
            self._auto_index += 1
            candidate = f"b{self._auto_index}"
        return candidate

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
