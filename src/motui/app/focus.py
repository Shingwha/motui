"""focus: the focus tier -- who is focused, how it cycles, where events go.

This module is the assembly tier (D3) -- the peer of
:mod:`motui.app.gesture` and :mod:`motui.app`: it imports the core and the
driver's value types, and it is where every focus *behavior* lands.  Focus
is a layer, never a component's responsibility (the interaction charter's
rule 3): a component declares only that it can be focused -- one read-write
``focused: bool`` -- and renders by it; *who* is focused, *how* the focus
cycles and *where* an event goes live here, in one place.

The target tuple is the mounted tree's focus ring: the App re-derives it
with :func:`focus_targets` and hands it over through
:meth:`FocusManager.sync` before every focus verb, so mounting or removing
a block needs no registration bookkeeping.  The constructor still takes an
explicit tuple, which is what a trap, a modal and the demo's per-topic ring
use.  A target is a node of the explicit widget tree -- ``focusable``, or a
``focus_scope`` container (a ``Form`` routes its fields itself, so the ring
stops at it).  A target without a ``focused`` attribute is a pure routing
target (a plain ``Component`` handed to a trap); it is focused by identity
and no flag is written.

Cycling is the host's key: the manager binds nothing of its own -- the host
routes ``tab`` to :meth:`FocusManager.focus_next` -- and every other key is
dispatched to the focused target by :meth:`FocusManager.handle`.  A click
is resolved to a cell by the host's hit test and handed to
:meth:`FocusManager.on_click`, which first descends every container to the leaf
under the cell, then dispatches it, focuses the component it landed on, and
activates it on the second click (the standard desktop semantic).

**Traps.**  :meth:`FocusManager.push_trap` saves the current target tuple
and focus, then narrows the manager to the trapped targets (the first one
focused, or none for an empty trap); :meth:`FocusManager.pop_trap` restores
the saved pair.  Traps nest, which is exactly what two stacked modals need:
closing the top one returns focus to the one below.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING

from ..kernel.document import Component, descend_chain
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.geom import Pos
from ..kernel.hit import Hit

if TYPE_CHECKING:
    from .driver import TUI

__all__ = ["FocusManager"]


def _document_roots(tui: "TUI") -> Iterator[Component]:
    """Every block root of every pane and dock, in paint order.

    The focus ring is derived from what is mounted, so it must see the
    whole frame: the content panes in tiling order, then the docks (the
    frame's own paint order).  A dock holds a one-block document like a
    pane, so the same ``blocks()`` walk serves both.
    """
    frame = tui.frame
    panes = (*frame.panes, *frame.docks.values())
    for pane in panes:
        for section in pane.viewport.document.blocks():
            yield section.widget


def iter_widgets(tui: "TUI") -> Iterator[Component]:
    """Every mounted node once, depth first, in frame order.

    The flat tree walk ``App`` uses for broadcasts (a resize reaches every
    widget, a focus scope's subtree included).  A root without ``walk`` is
    yielded alone; a shared node is yielded at its first position only.
    """
    seen: set[int] = set()
    for root in _document_roots(tui):
        walk = getattr(root, "walk", None)
        nodes = walk() if callable(walk) else (root,)
        for node in nodes:
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield node


def focus_targets(tui: "TUI") -> tuple[Component, ...]:
    """The focus ring: the mounted tree's preorder ``focusable``/scope nodes.

    A ``focus_scope`` node (a ``Form`` or a ``ComboBox`` routes its own
    subtree) joins the ring itself and stops the descent -- its subtree never becomes separate
    targets.  Every other node joins when ``focusable`` is set.  Nodes are
    visited in the frame/document order :func:`_document_roots` yields, and
    an object appears once even when the tree shares it.
    """
    targets: list[Component] = []
    seen: set[int] = set()
    for root in _document_roots(tui):
        stack: list[Component] = [root]
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            scope = bool(getattr(node, "focus_scope", False))
            if scope:
                targets.append(node)
                continue
            if bool(getattr(node, "focusable", False)):
                targets.append(node)
            children = getattr(node, "children", None)
            if children:
                stack.extend(reversed(list(children)))
    return tuple(targets)


class FocusManager:
    """The focus tier: who is focused, how it cycles, where events go.

    ``targets`` are the manager's components, in the order the focus cycles
    through them; ``wrap`` makes :meth:`focus_next` step from the last
    target back onto the first.  The constructor does **not** focus
    anything: a freshly built manager holds no focus and no target's flag is
    touched, so mounting a page never plays with the components' own
    defaults.  :meth:`focus_next` from that empty focus selects the first
    target (the last one for a negative ``delta``), and an empty manager
    degrades safely (``focused`` is ``None``, ``focus`` and ``focus_next``
    answer ``False``, ``handle`` and ``click`` pass everything through).
    ``on_change`` is called with the new focus -- a component, or ``None``
    when the focus was cleared -- after every real change.

    A target need not have a ``focused`` attribute; it is then a pure
    routing target (a plain component in a trap), focused by identity
    without a flag write.  Every target that does have the attribute is
    rewritten on a move, so one manager always has at most one focused flag
    set.

    **The routing table** -- :meth:`handle` dispatches ``event`` in this
    order, answering whether the manager consumed it:

    1. the focus is empty -> ``False`` (there is nobody to route to);
    2. a :class:`~motui.kernel.events.KeyEvent` reads the target's
       :attr:`keymap <motui.widgets.base.Widget.keymap>` first: a bound
       action runs through ``on_action(name)``;
    3. an unconsumed key goes to ``on_key(event)``;
    4. an unconsumed ``enter`` on an ``activatable`` target runs
       ``on_action("activate")`` -- the 1.x activation fallback, now opt-in
       through the capability flag instead of a hard-coded key table;
    5. a :class:`~motui.kernel.events.PasteEvent` goes to ``on_paste`` and a
       :class:`~motui.kernel.events.MouseEvent` to ``on_mouse``;
    6. everything else -> ``False`` (the host keeps routing its own keys:
       the submit gesture, the palette, quit).

    The manager binds no arrow itself: a data view declares its arrows in
    its keymap, a text field consumes them in ``on_key``, and a widget with
    neither keeps the key for the host.

    **The click policy** -- :meth:`on_click` runs one click through four
    steps, answering whether any component consumed it.  The click first
    **descends**: the hit's cell is walked through every container's
    ``child_at`` to the deepest leaf (a ``Padding(Select)`` click lands on
    the ``Select``), and every step below works on that leaf:

    1. a leaf whose ``clickable`` flag is set is dispatched its own cell --
       ``on_click(Pos(x=col, y=row))`` -- **any** clickable component, not
       only a manager target (a page may hold mouse-only widgets beside the
       focus list);
    2. every ancestor gets ``focus_at(row, col)``: the focus-routing half of
       a click (a ``Form`` moves its field cursor, a ``Dialog`` its button
       cursor) without repeating the leaf's action;
    3. the nearest target in the chain that is **not** the current focus is
       focused: the first click only moves the focus;
    4. a target that is already the focus and is ``activatable`` is
       activated through ``on_action("activate")``: the second click
       activates -- the standard desktop semantic.

    The answer is whether a component consumed the click (the host repaints
    or toasts on it).

    **Out of scope, deliberately**: no hover of its own (the manager reads no
    motion report and flips no hover flag: hover is the
    :mod:`motui.app.pointer` tier's, with ``TUI(hover=True)`` opening
    DECSET 1003); no hotkey beyond ``tab`` (the manager
    binds nothing; the host routes ``tab`` to :meth:`focus_next`); no mouse
    drag (press-motion-release is :class:`~motui.app.gesture.SelectionGesture`'s);
    no pane or window focus (that is the frame's -- :class:`~motui.kernel.frame.Frame`
    and ``TUI.pane_at`` own which pane gets input).
    """

    __slots__ = ("_focused", "_on_change", "_targets", "_traps", "_wrap")

    def __init__(
        self,
        targets: Iterable[Component] = (),
        *,
        wrap: bool = True,
        on_change: Callable[[Component | None], object] | None = None,
    ) -> None:
        self._targets: tuple[Component, ...] = tuple(targets)
        self._wrap = wrap
        self._on_change = on_change
        self._focused: Component | None = None
        self._traps: list[tuple[tuple[Component, ...], Component | None]] = []

    @property
    def targets(self) -> tuple[Component, ...]:
        """The current targets, in focus-cycle order."""
        return self._targets

    @property
    def focused(self) -> Component | None:
        """The target holding the focus, or ``None`` for an empty focus."""
        return self._focused

    def sync(self, targets: Iterable[Component]) -> None:
        """Replace the target set; keep the focus when it is still a target.

        The App re-derives ``targets`` from the mounted tree before every
        focus verb, so mounting or removing a subtree updates the ring with
        no registration bookkeeping.  A focus that is no longer in the set
        is cleared -- its flag drops and ``on_change(None)`` fires -- while
        a focus that survived the edit stays put (the common per-round
        case: one block was added elsewhere).

        With **no** focus, only the target tuple is replaced: the manager
        touches no component's flag, exactly like the constructor, so a
        widget's own default (a focused field inside a mounted block) is
        never rewritten merely because the App mounted something else.
        """
        held = tuple(targets)
        if self._focused is None:
            self._targets = held
            return
        if any(self._focused is known for known in held):
            self._replace(held, self._focused)
        else:
            self._replace(held, None)

    def focus(self, target: Component) -> bool:
        """Focus ``target``; ``True`` when the focus moved there.

        A target that is not registered is left alone and answers
        ``False`` -- the current focus does not move.  A registered target
        that already holds the focus answers ``False`` (nothing changed).
        On a move every registered target that carries a ``focused`` flag is rewritten:
        the new focus reads ``True``, all others ``False``; a target without the flag
        target is focused by identity with no flag write.
        """
        if not self._registered(target) or target is self._focused:
            return False
        self._set_focused(target)
        return True

    def focus_next(self, delta: int = 1) -> bool:
        """Step the focus ``delta`` targets on; ``False`` when it did not move.

        From no focus (the constructor's state) a positive ``delta`` selects
        the first target and a negative one the last; ``delta == 0`` changes
        nothing.  ``wrap`` (the default) cycles off the last target onto the
        first and off the first onto the last; without it the step clamps at
        the ends.  An empty manager answers ``False``; a step that lands on
        the current focus (a single-target list, a clamped edge) answers
        ``False`` and changes nothing.  The host routes its ``tab`` key
        here -- the manager binds no key itself.
        """
        count = len(self._targets)
        if count == 0:
            return False
        if self._focused is None:
            if delta > 0:
                return self.focus(self._targets[0])
            if delta < 0:
                return self.focus(self._targets[-1])
            return False
        index = next(
            (i for i, known in enumerate(self._targets) if known is self._focused),
            None,
        )
        if index is None:
            # The focus points outside the current set (a manual trap edit):
            # step from the edge the delta points away from.
            if delta > 0:
                return self.focus(self._targets[0])
            if delta < 0:
                return self.focus(self._targets[-1])
            return False
        if self._wrap:
            target = self._targets[(index + delta) % count]
        else:
            target = self._targets[min(max(index + delta, 0), count - 1)]
        return self.focus(target)

    def focus_previous(self) -> bool:
        """Step the focus one target back (``focus_next(-1)``)."""
        return self.focus_next(-1)

    def handle(self, event: Event) -> bool:
        """Route ``event`` to the focused target; ``True`` when consumed.

        The routing table is in the class docstring, in order: an empty
        focus declines; a key reads the target's keymap through
        ``on_action``, then ``on_key``, then the ``enter`` activation
        fallback for an ``activatable`` target; a paste and a mouse report
        go to their typed hooks; everything else declines, so the host
        keeps routing the events it owns.
        """
        target = self._focused
        if target is None:
            return False
        if isinstance(event, KeyEvent):
            action = dict(getattr(target, "keymap", {}) or {}).get(event.key)
            if action is not None:
                on_action = getattr(target, "on_action", None)
                if on_action is not None and on_action(action):
                    return True
            if self._hook(target, "on_key", event):
                return True
            if event.key == "enter" and bool(
                getattr(target, "activatable", False)
            ):
                return self._activate(target)
            return False
        if isinstance(event, PasteEvent):
            return self._hook(target, "on_paste", event)
        if isinstance(event, MouseEvent):
            return self._hook(target, "on_mouse", event)
        return False

    def click(self, hit: Hit) -> bool:
        """Resolve one click: act on the leaf, update the focus owner; consumed?

        The click walks the hit's ancestor chain.  The deepest leaf gets the
        action through its ``clickable`` flag -- a field's caret, a button's
        press, a list row's cursor -- and every ancestor gets its
        ``focus_at``, the focus-routing half (a ``Form`` moves its field
        cursor, a ``Dialog`` its button cursor) without repeating the leaf's
        action.  The **nearest target ancestor** is the focus owner: it
        receives the focus when it was elsewhere.  Activation on a repeat
        click applies to an ``activatable`` leaf target, so a second click
        on a form's background never submits it.
        """
        chain = hit.chain or descend_chain(
            hit.block.component, hit.row, hit.col
        )
        if not chain:
            return False
        leaf, leaf_row, leaf_col = chain[-1]
        consumed = False
        if bool(getattr(leaf, "clickable", False)):
            on_click = getattr(leaf, "on_click", None)
            if on_click is not None:
                consumed = bool(on_click(Pos(x=leaf_col, y=leaf_row))) or consumed
        for owner, owner_row, owner_col in reversed(chain[:-1]):
            focus_at = getattr(owner, "focus_at", None)
            if focus_at is not None and focus_at(owner_row, owner_col):
                consumed = True
        target = next(
            (owner for owner, _row, _col in reversed(chain) if self._registered(owner)),
            None,
        )
        if target is None:
            return consumed
        if target is not self._focused:
            self.focus(target)
            return True
        if target is leaf and bool(getattr(target, "activatable", False)):
            return self._activate(target) or consumed
        return consumed

    def push_trap(self, targets: Iterable[Component]) -> None:
        """Narrow the manager to ``targets``, saving the current focus state.

        The saved pair (target tuple, focused component) is restored whole
        by :meth:`pop_trap`; traps nest, so two stacked modals each restore
        the layer below.  The trapped first target is focused (no target
        stays focused for an empty trap) and ``on_change`` fires if that
        moved the focus.
        """
        self._traps.append((self._targets, self._focused))
        trapped = tuple(targets)
        self._replace(trapped, trapped[0] if trapped else None)

    def pop_trap(self) -> None:
        """Restore the targets and focus saved by the last :meth:`push_trap`.

        Raises ``IndexError`` when no trap is open -- an unbalanced pop is a
        programming error, not a silent no-op.
        """
        if not self._traps:
            raise IndexError("pop_trap() without a matching push_trap()")
        targets, focused = self._traps.pop()
        self._replace(targets, focused)

    def __repr__(self) -> str:
        return (
            f"FocusManager({len(self._targets)} targets, "
            f"focused={self._focused!r})"
        )

    # -- internals ---------------------------------------------------------------

    def _registered(self, target: Component) -> bool:
        """Whether ``target`` is one of this manager's own objects (by identity)."""
        return any(target is known for known in self._targets)

    def _set_focused(self, target: Component | None) -> None:
        """Focus ``target`` within the current targets and rewrite every flag."""
        self._replace(self._targets, target)

    def _replace(
        self, targets: tuple[Component, ...], target: Component | None
    ) -> None:
        """Install ``targets``/``target`` and rewrite the flags in one move."""
        previous = self._focused
        self._targets = tuple(targets)
        self._focused = target
        for known in self._targets:
            if hasattr(known, "focused"):
                known.focused = known is target
        if (
            previous is not None
            and previous is not target
            and hasattr(previous, "focused")
            and not any(previous is known for known in self._targets)
        ):
            previous.focused = False
        if previous is not target and self._on_change is not None:
            self._on_change(target)

    @staticmethod
    def _hook(target: Component, name: str, event: Event) -> bool:
        """Run ``target``'s typed hook; a pure routing object declines."""
        hook = getattr(target, name, None)
        return bool(hook(event)) if hook is not None else False

    @staticmethod
    def _activate(target: Component) -> bool:
        """Run ``on_action("activate")``; a plain object declines."""
        on_action = getattr(target, "on_action", None)
        return bool(on_action("activate")) if on_action is not None else False
