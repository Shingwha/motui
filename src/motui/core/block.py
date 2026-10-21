"""Document model: addressable blocks rendered by components.

The toolkit's unit of content is a :class:`Block`: a stable id, a
:class:`Component` that knows how to render itself at a given width, and a
row cache that follows the component's own revision snapshot.  There is no
lifecycle flag: a block caches exactly when its component can prove the rows
are unchanged (:class:`Revisioned` answering a snapshot), and re-renders
otherwise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .lines import Line

if TYPE_CHECKING:  # the protocol names the event model; no runtime import needed
    from .events import Event

__all__ = [
    "Activable",
    "Block",
    "Clickable",
    "Component",
    "Container",
    "Controller",
    "Document",
    "Focusable",
    "Hoverable",
    "Resultful",
    "Revisioned",
    "descend",
    "descend_chain",
]


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
    output -- exactly what :meth:`~motui.app.TUI.hit` reports as
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


@runtime_checkable
class Focusable(Protocol):
    """The minimum a component declares to be focusable: ``focused: bool``.

    One read-write flag, nothing else.  The focus tier
    (:class:`~motui.app.focus.FocusManager`) owns *who* is focused and flips
    the flag; the component decides what being focused *looks like* -- a
    block cursor (the text fields), an undimmed cursor row (the list
    family) -- and never learns that a manager exists.  The attribute is
    writable by contract: the manager sets it on every target as the focus
    moves.
    """

    focused: bool


@runtime_checkable
class Hoverable(Protocol):
    """A component that can be highlighted while the pointer is over it.

    ``hover`` is the one read-write flag the pointer tier flips, the exact
    peer of ``Focusable.focused``.  A component decides what being hovered
    *looks like* and never learns that a pointer manager exists.  A
    component with finer granularity may also implement ``hover_at(row,
    col) -> bool`` (an optional method, not part of this protocol): it
    records which of its own cells the pointer is on and answers whether
    what it renders changed.  ``row < 0`` means the pointer left.
    """

    hover: bool


@runtime_checkable
class Container(Protocol):
    """A component made of children, translating its own cells to a child's.

    ``child_at(row, col)`` takes a 0-based cell of this component's own
    ``render`` output (exactly ``Hit.row`` / ``Hit.col``) and answers
    ``(component, row, col)`` for the child that owns it, or ``None`` for a
    cell the container itself owns (its border, padding or gap).  The
    geometry comes from this component's **last render** -- the same
    precedent ``TextBuffer.move_up`` follows -- so a container that has not
    rendered yet answers ``None``.  A container never proxies ``handle`` /
    ``move`` / ``activate`` / ``focused``; it only routes coordinates.
    """

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        ...


@runtime_checkable
class Controller(Protocol):
    """A component that consumes events: ``handle(event) -> bool``.

    The one routing contract of the interactive tier: ``True`` means the
    component **consumed** the event, ``False`` means the host's own
    dispatch still gets its turn.  The answer never means "changed" -- a
    component that only needs a repaint asks its host to refresh itself --
    so every controller answers the same question and a host can route a
    chain of candidates without translating each one's private convention.
    Optional: a pure renderer has no ``handle``.
    """

    def handle(self, event: "Event") -> bool:
        ...


@runtime_checkable
class Resultful(Protocol):
    """A component with a one-shot result: ``take_result() -> object | None``.

    Reading the result **clears** it, so a host reads a pick exactly once
    and never needs a second write to reset it.  ``None`` means "nothing
    pending"; a component whose legal result is ``None`` uses the take
    itself as the signal (a cancel).  There is no public ``chosen``
    attribute on components: this method is the only result door.
    """

    def take_result(self) -> object | None:
        ...


@runtime_checkable
class Revisioned(Protocol):
    """A component whose rows are a pure function of a value snapshot.

    ``revision()`` answers *everything the component's rows depend on*, as a
    value: while two calls answer **equal** snapshots the component promises
    that ``render(width)`` answers equal rows at any one width -- so a cache
    keyed on the pair ``(width, revision())`` may hand the older rows back.
    The row cache on :meth:`Block.rows` is exactly that cache, and the
    promise is what makes it safe to keep a block's rows between frames: a
    hover that moves, a streamed assignment, a toggled mark changes the
    snapshot, so the next ``rows()`` misses and re-renders.

    Two rules make the promise hold.

    The snapshot must be **value semantics**: every mutable field the rows
    read goes in copied, not by reference.  ``Table.rows`` is the canonical
    trap -- ``rows == cached`` is trivially true when "cached" holds the very
    same list, so an in-place edit would never be seen -- and a tuple built
    over a snapshot (``tuple(map(tuple, self.rows))``) is the shape that
    catches it.  Reference identity is not value identity, and a component
    that hands its live state out is worse than one without a revision at
    all: it would freeze under a cache instead of merely being re-rendered.

    The snapshot must **cost much less than the render it guards** -- the
    design bound is at most a few percent of one ``render(width)``, because
    every cached frame pays the snapshot again while only a miss pays the
    render; a snapshot that re-wraps the text it guards has moved the cost,
    not removed it.

    ``None`` is the off switch, not a snapshot: :meth:`Block.rows` never
    caches a block whose revision answers ``None`` (no snapshot, no
    invalidation), and ``Text._revision`` returning ``None`` closes that
    component's own row memory the same way.  A block whose component does
    not implement this protocol at all also re-renders every layout.
    Optional: hosts and blocks check ``isinstance(component,
    Revisioned)``.
    """

    def revision(self) -> object:
        ...


#: How many container levels :func:`descend` walks before stopping.
#:
#: A safety rail, not a layout rule: a well-formed tree is a handful of
#: levels deep, and a malformed container that answers ``child_at`` with
#: itself would otherwise loop forever.  Past the limit ``descend`` stops
#: and hands back the layer it is on -- it never raises.
_DESCEND_LIMIT = 64


def descend_chain(
    component: Component, row: int, col: int
) -> "tuple[tuple[Component, int, int], ...]":
    """Every component owning a cell, outermost first, with its own coords.

    Walks ``Container.child_at`` from ``component`` down, recording each
    component it lands on beside the cell in that component's own
    coordinate space.  The first entry is always ``(component, row, col)``;
    the last is the deepest component the cell descends to, which is what
    :func:`descend` answers.  Pure, allocation-light (one tuple per level)
    and depth-guarded like :func:`descend` (``_DESCEND_LIMIT``).

    The chain is the value a host routes with: a wheel finds the nearest
    :class:`~motui.core.scroll.Scrollable` by walking it backwards, and a
    click can address any ancestor without a second hit test.
    """
    chain: list[tuple[Component, int, int]] = [(component, row, col)]
    for _ in range(_DESCEND_LIMIT):
        if not isinstance(component, Container):
            break
        cell = component.child_at(row, col)
        if cell is None:
            break
        component, row, col = cell
        chain.append((component, row, col))
    return tuple(chain)


def descend(component: Component, row: int, col: int) -> "tuple[Component, int, int]":
    """The deepest component owning a cell, with that component's own coords.

    Walks ``Container.child_at`` until a component is not a container or
    declines the cell; then returns it unchanged.  Pure, allocation-light
    and depth-guarded (a malformed container that returns itself cannot
    loop forever).  The kernel's one coordinate-descend primitive, shared by
    the pointer tier and the focus ring's click policy; it is the tail of
    :func:`descend_chain`.
    """
    return descend_chain(component, row, col)[-1]


class Block:
    """One addressable row-producing unit inside a :class:`Document`.

    Besides the id and the component, a block owns its own **row cache**
    (:meth:`rows`): the rows a component answered at one width are the
    block's rows, so the cache belongs with the identity they hang on rather
    than in whatever object happened to lay them out last.  A cache on the
    layout side had to be pruned by id every frame -- a per-frame walk of the
    whole document to catch a removed block or an id reused by a new one; a
    cache on the block dies with the block and nothing reuses it.  The cache
    is keyed ``(width, revision)``, and only a component that implements
    :class:`Revisioned` and answers a non-``None`` snapshot is cached: an
    unrevisioned component re-renders on every call, because the block has no
    way to see that its content changed.
    """

    __slots__ = (
        "_cacheable",
        "_component",
        "_id",
        "_pin",
        "_rows_cache",
        "_rows_revision",
        "_rows_width",
    )

    def __init__(self, id: str, component: Component, *, pin: str | None = None) -> None:
        if pin not in (None, "top", "bottom"):
            raise ValueError(f"pin must be 'top', 'bottom' or None, got {pin!r}")
        self._id = id
        self._component = component
        self._pin = pin
        # The component's protocol membership never changes (it is fixed by
        # the type), so it is decided once here: a per-frame isinstance on
        # every block would cost more than the cache saves.
        self._cacheable = isinstance(component, Revisioned)
        # The cache slot: the last rows rendered at ``_rows_width`` whose
        # component answered ``_rows_revision``.  ``None`` rows mean "nothing
        # cached yet" -- a revision of ``None`` (a component without the
        # protocol, or one with its memory switched off) is a legitimate key,
        # so it cannot double as the empty marker.
        self._rows_cache: list[Line] | None = None
        self._rows_width: int | None = None
        self._rows_revision: object = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def component(self) -> Component:
        return self._component

    @property
    def pin(self) -> str | None:
        """Fixed region of the block: ``"top"``, ``"bottom"``, or ``None``.

        ``None`` (the default) leaves the block in the scrollable body;
        ``"top"``/``"bottom"`` place it in the matching fixed region of the
        screen, which never scrolls away.
        """
        return self._pin

    def revision(self) -> object:
        """The component's snapshot for the rows it renders, or ``None``.

        Forwards to a :class:`Revisioned` component and answers ``None``
        for anything else -- "no snapshot", the answer that leaves the row
        cache off.
        """
        if self._cacheable:
            return self._component.revision()
        return None

    def render(self, width: int) -> list[Line]:
        """Forward rendering to the block's component: the *fresh-rows* door.

        Deliberately uncached: this is "render it again, now".  The cached
        door every layout-side caller wants is :meth:`rows`.
        """
        return self._component.render(width)

    def rows(self, width: int) -> list[Line]:
        """The block's rows at ``width``, cached when the component allows it.

        The one door for "the rows this block has at this width" -- the
        viewport's layout and height walk, ``TUI.reveal``'s address
        arithmetic, the search walk, the selection extraction and the
        gesture walk all read it -- and the cache it answers from is the
        block's own, keyed ``(width, revision())``.  The caching rule is one
        line:

        * a component that implements :class:`Revisioned` **and** answers a
          snapshot is cached until the width or the snapshot moves;
        * anything else -- no protocol, or a ``None`` snapshot ("memory
          off") -- re-renders per call, because the block cannot see a
          change it would have to invalidate on.

        The returned list is a fresh copy the caller owns (the cache keeps
        its own); the :class:`Line` values inside it are immutable and may
        be shared, so a hit is one list copy, not a row rebuild.  Cache
        entries die with the block: nothing is pruned anywhere, and a
        removed block's id reused by a new block starts with a fresh slot.
        """
        if not self._cacheable:
            return list(self._component.render(width))  # no snapshot: never cached
        revision = self._component.revision()
        if revision is None:
            # A component with the protocol switched its memory off (``None``
            # is "no snapshot"): the block must not cache what it cannot
            # invalidate.
            return list(self._component.render(width))
        if (
            self._rows_cache is not None
            and self._rows_width == width
            and self._rows_revision == revision
        ):
            return list(self._rows_cache)
        rows = list(self._component.render(width))
        self._rows_cache = rows
        self._rows_width = width
        self._rows_revision = revision
        return list(rows)

    def __repr__(self) -> str:
        return f"Block(id={self._id!r}, pin={self._pin!r})"


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
