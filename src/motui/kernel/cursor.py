"""Cursor: the one cursor-and-window arithmetic the widgets share.

One component family -- the data views, the menus, the label strips -- walks
a cursor over a sequence and renders a window of it.  The walking rules
(disabled rows are stepped over, a data view clamps at its ends and a menu
cycles), the edge jumps, and the window policies live here once, so the
components fold this value into their own state instead of carrying a loop
of their own.

``count`` is the sequence length and ``index`` the raw cursor; a cursor the
current sequence no longer answers is clamped by the operations that need a
legal row (:meth:`Cursor.window`, :meth:`Cursor.select`, :meth:`Cursor.move`)
rather than by construction, so a host that shrank its list keeps reading
"no cursor" until a gesture lands.  ``disabled`` names the rows a step walks
over and :meth:`Cursor.select` refuses; a whole-control ``disabled`` flag is
the component's own policy and stays outside this value.

:meth:`Cursor.window` names three policies: ``"top"`` -- the menu's
top-stick window, hanging at the top while the cursor sits inside the first
``size`` rows and then scrolling one row per step with the cursor as its
last row; ``"center"`` -- the data view's window, half a page above the
cursor where the ends allow; ``"bottom"`` -- the tail-pinned window.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["Cursor"]

#: The window policies :meth:`Cursor.window` understands.
_ANCHORS = ("top", "center", "bottom")


class Cursor:
    """A cursor over ``count`` rows plus its disabled set and wrap rule.

    ``wrap=True`` -- a menu -- steps off the last row onto the first and off
    the first onto the last; ``wrap=False`` -- a data view -- clamps at the
    ends instead.  ``disabled`` holds raw row indices: :meth:`move` steps
    over them and :meth:`select` refuses to land on one.  The value is
    mutable on purpose -- a component owns one and folds it into its own
    state -- and every verb is the whole rule, so no caller re-implements
    "skip disabled" or "clamp at the edge".
    """

    __slots__ = ("count", "disabled", "index", "wrap")

    def __init__(
        self,
        count: int = 0,
        *,
        index: int = 0,
        disabled: Iterable[int] = (),
        wrap: bool = False,
    ) -> None:
        self.count = max(0, int(count))
        #: The raw cursor; a stale value is clamped by the verbs, not here
        #: (see the module docstring).
        self.index = int(index)
        self.disabled = frozenset(disabled)
        self.wrap = bool(wrap)

    def clamp(self, index: int) -> int:
        """The nearest legal cursor for ``index`` (``0`` for an empty set)."""
        if self.count <= 0:
            return 0
        return min(max(int(index), 0), self.count - 1)

    def select(self, index: int) -> bool:
        """Land on ``index`` (clamped); ``True`` when the cursor moved.

        A disabled target is refused outright -- ``False``, nothing moved --
        and an empty sequence answers ``False`` always.
        """
        if self.count <= 0:
            return False
        target = self.clamp(index)
        if target in self.disabled:
            return False
        changed = target != self.index
        self.index = target
        return changed

    def move(self, delta: int) -> bool:
        """Move ``delta`` enabled rows; ``True`` when the cursor moved.

        Disabled rows are stepped over: a positive step from row 1 with 2
        disabled lands on 3, and a step whose direction holds no enabled row
        left stays where it was.  A wrapping cursor cycles and a clamping
        one stops at the ends; an empty sequence moves nowhere.
        """
        if self.count <= 0 or delta == 0:
            return False
        step = 1 if delta > 0 else -1
        target = self.index
        moved = False
        for _ in range(abs(delta)):
            candidate = self._next_enabled(target, step)
            if candidate is None or candidate == target:
                break
            target = candidate
            moved = True
        if not moved:
            return False
        self.index = target
        return True

    def _next_enabled(self, start: int, step: int) -> int | None:
        """The next enabled row in ``step``'s direction, or ``None``.

        A wrapping walk checks every row once (and therefore answers
        ``None`` when they are all disabled); a clamping walk answers
        ``None`` at the boundary.
        """
        position = start
        for _ in range(self.count):
            if self.wrap:
                position = (position + step) % self.count
            else:
                position += step
                if position < 0 or position >= self.count:
                    return None
            if position not in self.disabled:
                return position
        return None

    def home(self) -> bool:
        """Jump to the first enabled row; ``True`` when the cursor moved."""
        for position in range(self.count):
            if position not in self.disabled:
                changed = position != self.index
                self.index = position
                return changed
        return False

    def end(self) -> bool:
        """Jump to the last enabled row; ``True`` when the cursor moved."""
        for position in range(self.count - 1, -1, -1):
            if position not in self.disabled:
                changed = position != self.index
                self.index = position
                return changed
        return False

    def window(self, size: int, *, anchor: str = "center") -> tuple[int, int]:
        """The ``[start, stop)`` rows to render (``(0, 0)`` for no window).

        ``size`` is the row budget and ``anchor`` one of :data:`_ANCHORS`:

        * the whole sequence fits (or ``size`` is not positive beyond it) --
          ``(0, count)``, whatever the anchor says: there is nothing to
          scroll;
        * ``"top"`` -- the menu's top-stick policy: ``(0, size)`` while the
          cursor sits inside the first ``size`` rows, then
          ``(index - size + 1, index + 1)``, the cursor row last;
        * ``"center"`` -- ``start = min(max(index - size // 2, 0),
          count - size)`` and ``stop = start + size``: the cursor half a
          window down, both ends clamped;
        * ``"bottom"`` -- ``(count - size, count)``: the tail pinned.

        The stored cursor is clamped first, so a stale ``index`` cannot
        produce a window off the rows.
        """
        if anchor not in _ANCHORS:
            raise ValueError(f"cursor anchor must be one of {_ANCHORS}, got {anchor!r}")
        if self.count <= 0 or size <= 0:
            return 0, 0
        if self.count <= size:
            return 0, self.count
        index = self.clamp(self.index)
        if anchor == "center":
            start = min(max(index - size // 2, 0), self.count - size)
            return start, start + size
        if anchor == "bottom":
            return self.count - size, self.count
        if index < size:
            return 0, size
        return index - size + 1, index + 1
