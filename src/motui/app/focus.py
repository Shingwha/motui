"""focus: the focus tier -- who is focused, how it cycles, where events go.

This module is the assembly tier (D3) -- the peer of
:mod:`motui.app.gesture` and :mod:`motui.app`: it imports the core and the
driver's value types, and it is where every focus *behavior* lands.  Focus
is a layer, never a component's responsibility (the interaction charter's
rule 3): a component declares only that it can be focused -- one read-write
``focused: bool`` (:class:`~motui.kernel.document.Focusable`) -- and renders by
it; *who* is focused, *how* the focus cycles and *where* an event goes live
here, in one place.

A host opts in with two explicit lines, the same explicit-mounting rule
:class:`~motui.app.gesture.SelectionGesture` follows -- ``TUI`` never
attaches a manager itself::

    focus = FocusManager([menu, tree])
    focus.focus_next()                    # the first target is not focused until asked
    event = await tui.read_event()
    if not focus.handle(event):
        ...                               # the host's own dispatch

The manager holds registered targets and flips every ``Focusable`` target's
``focused`` flag as the focus moves, so a component never learns a manager
exists; an unregistered component is never touched.  A non-``Focusable``
target is still a legal route target (a ``Dialog`` is the shipped example):
the manager focuses it by identity without writing a flag.  Cycling is the
host's key: the manager binds nothing of its own -- the host routes the
``tab`` key to :meth:`FocusManager.focus_next` -- and every other key is
dispatched to the focused target by :meth:`FocusManager.handle`.  A click is
resolved to a cell by the host's hit test and handed to
:meth:`FocusManager.click`, which first descends every container to the leaf
under the cell (:func:`~motui.kernel.document.descend`), then dispatches it,
focuses the component it landed on, and activates it on the second click (the
standard desktop semantic).

**Traps.**  :meth:`FocusManager.push_trap` saves the current target tuple
and focus, then narrows the manager to the trapped targets (the first one
focused, or none for an empty trap); :meth:`FocusManager.pop_trap` restores
the saved pair.  Traps nest, which is exactly what two stacked modals need:
closing the top one returns focus to the one below.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..kernel.document import Activable, Component, Container, Focusable, descend_chain
from ..kernel.events import Event, KeyEvent
from ..kernel.hit import Hit

__all__ = ["FocusManager"]


class FocusManager:
    """The focus tier: who is focused, how it cycles, where events go.

    ``targets`` are the manager's registered components, in the order the
    focus cycles through them; ``wrap`` makes :meth:`focus_next` step from
    the last target back onto the first.  The constructor does **not** focus
    anything: a freshly built manager holds no focus and no target's flag is
    touched, so mounting a page never plays with the components' own
    defaults.  :meth:`focus_next` from that empty focus selects the first
    target (the last one for a negative ``delta``), and an empty manager
    degrades safely (``focused`` is ``None``, ``focus`` and ``focus_next``
    answer ``False``, ``handle`` and ``click`` pass everything through).
    ``on_change`` is called with the new focus -- a component, or ``None``
    when the focus was cleared -- after every real change.

    A target need not be :class:`~motui.kernel.document.Focusable`; it is then a
    pure routing target (the modal's dialog), focused by identity without a
    flag write.  Every currently registered ``Focusable`` target's flag is
    still rewritten on a move, so one manager always has at most one focused
    flag set.

    **The routing table** -- :meth:`handle` dispatches ``event`` in this
    order, answering whether the manager consumed it:

    1. the focus is empty -> ``False`` (there is nobody to route to);
    2. the focused target has a ``handle`` method -- it **goes first**,
       before any manager verb (a field or controller consumes its own keys:
       ``TextBuffer.handle`` takes printable characters, the arrows, the
       backspace, and a :class:`~motui.kernel.events.PasteEvent`);
    3. while the target left the event alone, only a
       :class:`~motui.kernel.events.KeyEvent` is read: ``up``/``left`` ->
       ``move(-1)``; ``down``/``right`` -> ``move(+1)`` -- with no ``move``
       method the arrow falls back to its own verb -- ``up`` -> ``move_up()``,
       ``left`` -> ``move_left()``, ``down`` -> ``move_down()``, ``right`` ->
       ``move_right()`` -- which is the text fields' shape; ``enter`` ->
       ``activate()`` (a target that is not
       :class:`~motui.kernel.document.Activable` answers ``False``);
    4. everything else -> ``False`` (the host keeps routing its own keys:
       the submit gesture, the palette, quit).

    **The click policy** -- :meth:`click` runs one click through four
    steps, answering whether any component consumed it.  The click first
    **descends**: the hit's cell is walked through every
    :class:`~motui.kernel.document.Container.child_at` to the deepest leaf
    (a ``Padding(Select)`` click lands on the ``Select``), and every step
    below works on that leaf:

    1. a :class:`~motui.kernel.document.Clickable` leaf is dispatched
       its own cell -- ``component.click(row, col)`` -- **any** clickable
       component, not only a manager target (a page may hold mouse-only
       widgets beside the focus list);
    2. a leaf that is registered and is **not** the current focus is
       focused: the first click only moves the focus;
    3. a leaf that is registered and **already** the current focus is
       activated (``activate()``, when it is
       :class:`~motui.kernel.document.Activable`): the second click
       activates -- the standard desktop semantic;
    4. the answer is whether a component consumed the click (the host
       repaints or toasts on it).

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
        """The registered targets, in focus-cycle order."""
        return self._targets

    @property
    def focused(self) -> Component | None:
        """The target holding the focus, or ``None`` for an empty focus."""
        return self._focused

    def add(self, target: Component) -> bool:
        """Register ``target`` at the end of the cycle; ``True`` when added.

        An object already registered (identity) is left alone and answers
        ``False``.  Registration never moves the focus: adding to an empty
        manager leaves it empty until :meth:`focus_next` or :meth:`focus`.
        """
        if self._registered(target):
            return False
        self._targets = (*self._targets, target)
        return True

    def remove(self, target: Component) -> bool:
        """Unregister ``target``; ``True`` when it was registered.

        Removing the current focus clears it -- the target's ``focused``
        flag is dropped to ``False`` when it is ``Focusable``, and
        ``on_change(None)`` fires -- so no manager ever points at a target
        it no longer holds.
        """
        if not self._registered(target):
            return False
        self._targets = tuple(known for known in self._targets if known is not target)
        if target is self._focused:
            self._set_focused(None)
        return True

    def focus(self, target: Component) -> bool:
        """Focus ``target``; ``True`` when the focus moved there.

        A target that is not registered is left alone and answers
        ``False`` -- the current focus does not move.  A registered target
        that already holds the focus answers ``False`` (nothing changed).
        On a move every registered ``Focusable`` target's flag is rewritten:
        the new focus reads ``True``, all others ``False``; a non-Focusable
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
        focus declines; the focused target's own ``handle`` goes first; an
        unconsumed ``KeyEvent`` drives the target's cursor (``move``, or
        ``move_up``/``move_left``/``move_down``/``move_right``) or its
        ``activate()``; everything else declines, so the host keeps
        routing the keys it owns.
        """
        target = self._focused
        if target is None:
            return False
        handler = getattr(target, "handle", None)
        if handler is not None and handler(event):
            return True
        if not isinstance(event, KeyEvent):
            return False
        if event.key == "up":
            return self._step(-1, "move_up")
        if event.key == "left":
            return self._step(-1, "move_left")
        if event.key == "down":
            return self._step(1, "move_down")
        if event.key == "right":
            return self._step(1, "move_right")
        if event.key == "enter":
            return self._activate()
        return False

    def click(self, hit: Hit) -> bool:
        """Resolve one click: act on the leaf, update the focus owner; consumed?

        The click walks the hit's ancestor chain.  The deepest leaf gets the
        action -- a field's caret, a button's press, a list row's cursor --
        and every ancestor gets :meth:`~motui.widgets.base.Widget.focus_at`,
        the focus-routing half (a ``Form`` moves its field cursor, a
        ``Dialog`` its button cursor) without repeating the leaf's action.
        The **nearest registered ancestor** is the focus owner: it receives
        the focus when it was elsewhere.  Activation on a repeat click only
        applies to a leaf target that is not a container, so a second click
        on a form's background never submits it.
        """
        chain = hit.chain or descend_chain(
            hit.block.component, hit.row, hit.col
        )
        leaf, leaf_row, leaf_col = chain[-1]
        consumed = False
        click = getattr(leaf, "click", None)
        if click is not None and click(leaf_row, leaf_col):
            consumed = True
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
        if (
            target is leaf
            and isinstance(target, Activable)
            and not isinstance(target, Container)
        ):
            return target.activate() or consumed
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
            if isinstance(known, Focusable):
                known.focused = known is target
        if (
            previous is not None
            and previous is not target
            and isinstance(previous, Focusable)
            and not any(previous is known for known in self._targets)
        ):
            previous.focused = False
        if previous is not target and self._on_change is not None:
            self._on_change(target)

    def _step(self, delta: int, fallback: str) -> bool:
        """Drive the focused target's cursor: ``move(delta)``, else ``fallback``.

        The fallback is the arrow's own verb on the fields' shape
        (``move_up``/``move_down``/``move_left``/``move_right``); a target
        with neither answers ``False``.
        """
        target = self._focused
        if target is None:
            return False
        move = getattr(target, "move", None)
        if move is not None:
            return bool(move(delta))
        step = getattr(target, fallback, None)
        return bool(step()) if step is not None else False

    def _activate(self) -> bool:
        """Run the focused target's ``activate()``; a non-Activable answers False."""
        target = self._focused
        if not isinstance(target, Activable):
            return False
        return target.activate()
