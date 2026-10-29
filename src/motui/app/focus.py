"""The focus tier: who is focused, how it cycles, where events go.

Focus is a layer, never a component's responsibility: a component
declares ``focused`` and renders by it. Traps nest, so two stacked modals
restore the layer below."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING

from ..kernel.document import Component, descend_chain
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.geom import Pos
from ..kernel.hit import Hit

if TYPE_CHECKING:
    from .workspace import Workspace

__all__ = ["FocusManager"]


def _document_roots(workspace: Workspace) -> Iterator[Component]:
    """Every block root of every pane and dock, in frame paint order."""
    frame = workspace.frame
    panes = (*frame.panes, *frame.docks.values())
    for pane in panes:
        for section in pane.viewport.document.blocks():
            yield section.widget


def iter_widgets(workspace: Workspace) -> Iterator[Component]:
    """Every mounted node once, depth first, in frame order; a shared node is
    yielded at its first position only."""
    seen: set[int] = set()
    for root in _document_roots(workspace):
        walk = getattr(root, "walk", None)
        nodes = walk() if callable(walk) else (root,)
        for node in nodes:
            if id(node) in seen:
                continue
            seen.add(id(node))
            yield node


def focus_targets(workspace: Workspace) -> tuple[Component, ...]:
    """The focus ring: the mounted tree's preorder ``focusable`` or
    ``focus_scope`` nodes; a scope stops the descent."""
    targets: list[Component] = []
    seen: set[int] = set()
    for root in _document_roots(workspace):
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

    The constructor focuses nothing. Routing reads the keymap through
    ``on_action``, then ``on_key``, then enter/space activation for an
    ``activatable`` target. A click descends to the leaf, dispatches it,
    focuses the nearest target and activates it on a repeat click. Traps save
    and restore targets and focus."""

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
        """Replace the target set, keeping the focus while it is still a target;
        with no focus, no component's flag is touched."""
        held = tuple(targets)
        if self._focused is None:
            self._targets = held
            return
        if any(self._focused is known for known in held):
            self._replace(held, self._focused)
        else:
            self._replace(held, None)

    def focus(self, target: Component) -> bool:
        """Focus ``target``; ``True`` when the focus moved there. An unregistered
        target is left alone."""
        if not self._registered(target) or target is self._focused:
            return False
        self._set_focused(target)
        return True

    def focus_next(self, delta: int = 1) -> bool:
        """Step the focus ``delta`` targets with wrapping or clamping; from no
        focus, selects the first (or the last for a negative delta)."""
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
        """Route ``event`` to the focused target; the routing table is in the class
        docstring."""
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
            if event.key in ("enter", "space") and bool(
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
        """Resolve one click: act on the leaf and dispatch every ancestor's
        ``focus_at``, then focus the nearest target; a second click on an
        activatable leaf target activates it."""
        chain = hit.chain or descend_chain(
            hit.block.widget, hit.row, hit.col
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
        """Narrow the manager to ``targets``, saving targets and focus; traps nest."""
        self._traps.append((self._targets, self._focused))
        trapped = tuple(targets)
        self._replace(trapped, trapped[0] if trapped else None)

    def pop_trap(self) -> None:
        """Restore the pair saved by the last :meth:`push_trap`; an unbalanced pop
        raises ``IndexError``."""
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
