"""focus: the focus tier -- who is focused, how it cycles, where events go.

This module is the assembly tier (D3) -- the peer of
:mod:`motui.gesture` and :mod:`motui.app`: it imports core and
app, and it is where every focus *behavior* lands.  Focus is a layer, never
a component's responsibility (the interaction charter's rule 3): a component
declares only that it can be focused -- one read-write ``focused: bool``
(:class:`~motui.kernel.block.Focusable`) -- and renders by it; *who* is
focused, *how* the focus cycles and *where* an event goes live here, in one
place.

A host opts in with one explicit line, the same explicit-mounting rule
:class:`~motui.gesture.SelectionGesture` follows -- ``TUI`` never
attaches a ring itself::

    ring = FocusRing([menu, tree])        # the first target is focused
    event = await tui.read_key()
    if not ring.handle(event):
        ...                               # the host's own dispatch

The ring holds registered targets and flips every target's ``focused`` flag
as the focus moves, so a component never learns a manager exists; an
unregistered component is never touched.  Cycling is the host's key: the
ring binds nothing of its own -- the host routes the ``tab`` key to
:meth:`FocusRing.focus_next` -- and every other key is dispatched to the
focused target by :meth:`FocusRing.handle`.  A click is resolved to a cell
by the host's hit test and handed to :meth:`FocusRing.click`, which first
descends every container to the leaf under the cell
(:func:`~motui.kernel.block.descend`), then dispatches it, focuses the
component it landed on, and activates it on the second click (the standard
desktop semantic).
"""

from __future__ import annotations

from collections.abc import Sequence

from .app import Hit
from .kernel.block import Activable, Clickable, Component, Focusable, descend
from .kernel.events import Key, Paste

__all__ = ["FocusRing"]


class FocusRing:
    """The focus tier: who is focused, how it cycles, where events go.

    ``targets`` are the ring's registered components, in the order the
    focus cycles through them; ``wrap`` makes :meth:`focus_next` step from
    the last target back onto the first.  The constructor validates every
    target against :class:`~motui.kernel.block.Focusable` -- a target
    that cannot be focused is a programming error, and it raises
    ``TypeError`` at construction rather than at the first keypress.  A
    non-empty ring focuses ``targets[0]`` before it returns (a page a host
    mounts is immediately playable, and the flags of all its *other*
    targets are cleared to ``False``); an empty ring holds no focus and
    every method degrades safely (``focused`` is ``None``, ``focus`` and
    ``focus_next`` answer ``False``, ``handle`` and ``click`` pass
    everything through).

    **The routing table** -- :meth:`handle` dispatches ``event`` in this
    order, answering whether the ring consumed it:

    1. the focus is empty -> ``False`` (there is nobody to route to);
    2. the focused target has a ``handle`` method -- it **goes first**,
       before any ring verb (a field or controller consumes its own keys:
       ``TextBuffer.handle`` takes printable characters, the arrows, the
       backspace, and a ``Paste``);
    3. while the target left the event alone, only a
       :class:`~motui.kernel.events.Key` is read: ``up``/``left`` ->
       ``move(-1)``; ``down``/``right`` -> ``move(+1)`` -- with no ``move``
       method the arrow falls back to its own verb -- ``up`` -> ``move_up()``,
       ``left`` -> ``move_left()``, ``down`` -> ``move_down()``, ``right`` ->
       ``move_right()`` -- which is the text fields' shape; ``enter`` ->
       ``activate()`` (a target that is not
       :class:`~motui.kernel.block.Activable` answers ``False``);
    4. everything else -> ``False`` (the host keeps routing its own keys:
       the submit gesture, the palette, quit).

    **The click policy** -- :meth:`click` runs one click through four
    steps, answering whether any component consumed it.  The click first
    **descends**: the hit's cell is walked through every
    :class:`~motui.kernel.block.Container.child_at` to the deepest leaf
    (a ``Padding(Select)`` click lands on the ``Select``), and every step
    below works on that leaf:

    1. a :class:`~motui.kernel.block.Clickable` leaf is dispatched
       its own cell -- ``component.click(row, col)`` -- **any** clickable
       component, not only a ring target (a page may hold mouse-only
       widgets beside the ring);
    2. a leaf that is in the ring and is **not** the current focus is
       focused: the first click only moves the focus;
    3. a leaf that is in the ring and **already** the current focus is
       activated (``activate()``, when it is
       :class:`~motui.kernel.block.Activable`): the second click
       activates -- the standard desktop semantic;
    4. the answer is whether a component consumed the click (the host
       repaints or toasts on it).

    **Out of scope, deliberately**: no hover of its own (the ring reads no
    motion report and flips no hover flag: hover is the
    :mod:`motui.pointer` tier's, with ``TUI(hover=True)`` opening
    DECSET 1003); no hotkey beyond ``tab`` (the ring
    binds nothing; the host routes ``tab`` to :meth:`focus_next`); no mouse
    drag (press-motion-release is :class:`~motui.gesture.SelectionGesture`'s);
    no pane or window focus (that is the frame's -- :class:`~motui.kernel.frame.Frame`
    and ``TUI.focus_at`` own which pane gets input).
    """

    __slots__ = ("_focused", "_targets", "_wrap")

    def __init__(
        self, targets: Sequence[Component] = (), *, wrap: bool = True
    ) -> None:
        self._targets: tuple[Component, ...] = tuple(targets)
        for target in self._targets:
            if not isinstance(target, Focusable):
                raise TypeError(
                    f"focus targets must satisfy Focusable (a writable "
                    f"'focused: bool'), got {target!r}"
                )
        self._wrap = wrap
        self._focused: Component | None = None
        if self._targets:
            self._set_focused(self._targets[0])

    @property
    def targets(self) -> tuple[Component, ...]:
        """The registered targets, in focus-cycle order."""
        return self._targets

    @property
    def focused(self) -> Component | None:
        """The target holding the focus, or ``None`` for an empty ring."""
        return self._focused

    def focus(self, target: Component) -> bool:
        """Focus ``target``; ``True`` when the focus moved there.

        A target that is not registered is left alone and answers
        ``False`` -- the current focus does not move.  A registered target
        that already holds the focus answers ``False`` (nothing changed).
        On a move every registered target's ``focused`` flag is rewritten:
        the new focus reads ``True``, all others ``False``.
        """
        if not self._registered(target) or target is self._focused:
            return False
        self._set_focused(target)
        return True

    def focus_next(self, delta: int = 1) -> bool:
        """Step the focus ``delta`` targets on; ``False`` when it did not move.

        ``wrap`` (the default) cycles off the last target onto the first
        and off the first onto the last; without it the step clamps at the
        ends.  An empty ring answers ``False``; a step that lands on the
        current focus (a single-target ring, a clamped edge) answers
        ``False`` and changes nothing.  The host routes its ``tab`` key
        here -- the ring binds no key itself.
        """
        count = len(self._targets)
        if count == 0 or self._focused is None:
            return False
        index = next(
            i for i, known in enumerate(self._targets) if known is self._focused
        )
        if self._wrap:
            target = self._targets[(index + delta) % count]
        else:
            target = self._targets[min(max(index + delta, 0), count - 1)]
        return self.focus(target)

    def handle(self, event: Key | Paste) -> bool:
        """Route ``event`` to the focused target; ``True`` when consumed.

        The routing table is in the class docstring, in order: an empty
        focus declines; the focused target's own ``handle`` goes first; an
        unconsumed ``Key`` drives the target's cursor (``move``, or
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
        if not isinstance(event, Key):
            return False
        if event.name == "up":
            return self._step(-1, "move_up")
        if event.name == "left":
            return self._step(-1, "move_left")
        if event.name == "down":
            return self._step(1, "move_down")
        if event.name == "right":
            return self._step(1, "move_right")
        if event.name == "enter":
            return self._activate()
        return False

    def click(self, hit: Hit) -> bool:
        """Resolve one click: descend, dispatch, focus, then activate; consumed?

        The click policy is in the class docstring, in order: the hit's
        cell first walks :func:`~motui.kernel.block.descend` through
        every container ``child_at`` to the deepest leaf -- a click through
        a ``Row`` / ``Column`` / ``Padding`` / ``Panel`` reaches the
        wrapped component, and the focus registry is a registry of leaves
        (D4: containers route coordinates, they are not targets) -- then a
        :class:`~motui.kernel.block.Clickable` leaf is dispatched its
        own cell, a ring target that is not yet focused is focused (the
        first click focuses), the focused target is activated (the second
        click activates), and the answer says whether anything consumed the
        click.
        """
        component, row, col = descend(hit.block.component, hit.row, hit.col)
        consumed = isinstance(component, Clickable) and component.click(row, col)
        if not self._registered(component):
            return consumed
        if component is not self._focused:
            self.focus(component)
            return True
        if isinstance(component, Activable):
            return component.activate() or consumed
        return consumed

    def __repr__(self) -> str:
        return (
            f"FocusRing({len(self._targets)} targets, focused={self._focused!r})"
        )

    # -- ring internals ---------------------------------------------------------

    def _registered(self, target: Component) -> bool:
        """Whether ``target`` is one of this ring's own objects (by identity)."""
        return any(target is known for known in self._targets)

    def _set_focused(self, target: Component) -> None:
        """Make ``target`` the focus and rewrite every target's flag."""
        self._focused = target
        for known in self._targets:
            known.focused = known is target

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
