"""SelectionGesture: the policy tier of document-space mouse selection.

This module is the assembly tier (D3) -- the peer of :mod:`mocode_tui.app`
and :mod:`mocode_tui.testing`: it imports core and app, and it is where every
selection *behavior* lands.  Above it sit the mechanisms it drives, none of
which it may extend downward: the kernel
(:mod:`mocode_tui.core.selection`) stays pure, timeless and side-effect-free
(the :class:`~mocode_tui.core.selection.Selection` model, the
:func:`~mocode_tui.core.selection.highlight` overlay, the
:func:`~mocode_tui.core.selection.extract` text), and the driver
(:class:`~mocode_tui.app.TUI`) exposes the minimal imperative surface the
gesture needs: :attr:`~mocode_tui.app.TUI.selection` (read),
:meth:`~mocode_tui.app.TUI.set_selection` (write + invalidate), the
:meth:`~mocode_tui.app.TUI.hit_test` cell resolution, the scroll facades and
the pump's :meth:`~mocode_tui.app.TUI.every` handles.

:class:`SelectionGesture` turns mouse reports into that state.  A host opts
in with one explicit line -- ``TUI`` never attaches a gesture itself, the
``Composer.attach`` philosophy -- and dispatches every event through it::

    gesture = SelectionGesture(tui)       # copy_on_select is the default
    event = await tui.read_key()
    if not gesture.handle(event):
        ...                               # the host's own dispatch

``handle`` follows the established consume-a-key contract
(``Input.handle_key`` / ``Editor.handle_key``): it returns ``True`` when the
event advanced the gesture, ``False`` when the host should see it.  The
gesture consumes the left button -- a press anchors the cell the hit test
resolves, motion while dragging extends the head, a release finalizes -- and
passes every other event (and every non-left button) straight through.

The lifecycle rules are policy, and they live here (D8): a zero-width
press-release at one cell *clears* the selection and never fires ``on_end``
(never clobber the clipboard with a click); a completed drag fires
``on_end`` exactly once and the highlight stays until the next press, so the
user can verify what was copied.  ``on_end=None`` selects without any
effect; :func:`copy_on_select` is the shipped default, and its whole body is
``extract`` + :meth:`Screen.copy <mocode_tui.core.screen.Screen.copy>` -- the
smallness is the proof that the mechanism/policy split held (D3/D6).
"""

from __future__ import annotations

from collections.abc import Callable

from .app import TUI
from .core.events import Key, MouseEvent, Paste
from .core.selection import Selection, SelectionAnchor, extract

__all__ = ["SelectionGesture", "copy_on_select"]

#: The ``on_end`` hook: the gesture's selection-end action.  It receives the
#: driver and the finished :class:`~mocode_tui.core.selection.Selection`; its
#: return value is ignored.  ``None`` disables the effect.
_OnEnd = Callable[[TUI, Selection], object] | None


def copy_on_select(tui: TUI, selection: Selection) -> None:
    """The shipped ``on_end`` default: extract the range and OSC 52 it (D6).

    Two lines -- that is the point: every mechanism (the range walk of
    :func:`~mocode_tui.core.selection.extract`, the clipboard primitive
    :meth:`Screen.copy <mocode_tui.core.screen.Screen.copy>`) lives in the
    kernel already, and the whole policy is "which text, which screen, once".
    The write is best-effort (a non-live screen returns ``False`` without
    touching the stream); a host with stronger needs passes its own
    ``on_end``.
    """
    tui.screen.copy(extract(tui.document, selection, width=tui.screen.width))


class SelectionGesture:
    """Mouse selection policy over the block document: anchor, drag, end.

    ``tui`` is the driver whose selection surface, hit test, scroll facades
    and pump the gesture drives.  ``on_end`` is the selection-end action
    (:func:`copy_on_select` by default, ``None`` for selection without any
    effect) -- a default *function argument*, never a kernel ``if`` (D3).

    The gesture owns its own anchor and head addresses (document space, D1)
    and mirrors the drag into the driver through
    :meth:`~mocode_tui.app.TUI.set_selection`; it keeps no copy of the text,
    the rows, or the layout.  It is single-pointer by construction: the left
    button anchors and extends, and a second press while a drag is in flight
    re-anchors from the new cell.
    """

    __slots__ = ("_anchor", "_head", "_on_end", "_tui")

    def __init__(self, tui: TUI, *, on_end: _OnEnd = copy_on_select) -> None:
        self._tui = tui
        self._on_end = on_end
        self._anchor: SelectionAnchor | None = None
        self._head: SelectionAnchor | None = None

    # -- the event contract -------------------------------------------------

    def handle(self, event: Key | Paste | MouseEvent) -> bool:
        """Advance the gesture with ``event``; ``True`` when it was consumed.

        The consume-a-key contract (``Input.handle_key`` /
        ``Editor.handle_key``): the host's dispatch is
        ``if not gesture.handle(event): ...``.  The left button -- press,
        motion while dragging, release -- is consumed; every other key,
        paste, button and lone motion is passed through untouched.
        """
        if not isinstance(event, MouseEvent):
            return False
        if event.kind == "press":
            if event.name != "left":
                return False
            self._press(event)
            return True
        if event.kind == "release":
            if event.name != "left":
                return False
            self._release()
            return True
        if event.kind == "motion":
            if self._anchor is None:
                return False  # no drag in flight: the pointer belongs to the host
            self._motion(event)
            return True
        return False

    def detach(self) -> None:
        """End the gesture cleanly (the ``EveryHandle``/Composer convention).

        Drops the in-flight drag so a later release cannot finalize it; the
        stored selection is the driver's overlay, not the gesture's state,
        and stays as the last frame painted it.
        """
        self._anchor = None
        self._head = None

    def __repr__(self) -> str:
        return f"SelectionGesture(dragging={self._anchor is not None})"

    # -- gesture internals -----------------------------------------------------

    def _press(self, event: MouseEvent) -> None:
        """Anchor at the pressed cell; a press ends the previous highlight."""
        hit = self._tui.hit_test(event.x, event.y)
        if hit is None:
            # No block owns the cell (blank fill, out of range, removed since
            # the last layout): there is nothing to anchor, and the click
            # still retires the previous highlight.
            self._anchor = None
            self._head = None
            self._tui.set_selection(None)
            return
        self._anchor = (hit.block.id, hit.row, hit.col)
        self._head = self._anchor
        # A zero-width range paints nothing (the kernel's lazy clamp), so the
        # previous highlight yields to this press (D8 lifecycle) while the
        # drag is still a single address.
        self._tui.set_selection(Selection.between(self._anchor, self._head))

    def _motion(self, event: MouseEvent) -> None:
        """Extend the head to the cell under the pointer, or end the drag.

        Called only while dragging.  A cleared overlay underneath the drag
        (a reflow, D8, or a host write) ends the drag cleanly rather than
        dragging addresses that no longer point at the same glyphs.
        """
        anchor, head = self._anchor, self._head
        if self._tui.selection is None:
            self._anchor = None
            self._head = None
            return
        hit = self._tui.hit_test(event.x, event.y)
        if hit is None:
            return  # off the content: the head stays where it is
        head = (hit.block.id, hit.row, hit.col)
        self._head = head
        self._tui.set_selection(Selection.between(anchor, head))

    def _release(self) -> None:
        """Finalize: clear a click (no ``on_end``), end a drag (one ``on_end``)."""
        anchor, head = self._anchor, self._head
        self._anchor = None
        self._head = None
        if anchor is None:
            return  # a press that hit nothing: already retired the highlight
        if anchor == head:
            self._tui.set_selection(None)  # a click clears; the clipboard is never touched
            return
        selection = Selection.between(anchor, head)
        self._tui.set_selection(selection)
        if self._on_end is not None:
            self._on_end(self._tui, selection)
