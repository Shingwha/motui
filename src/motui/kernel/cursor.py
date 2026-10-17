"""CursorWindow: the pure arithmetic of a cursor and its render window.

One component family -- the menus, the data views -- walks a cursor over a
sequence and renders a window of it.  The two window policies live here
so ``Select`` and ``List`` share one implementation of the arithmetic and
no policy of their own beyond the numbers they pass in.

``cap`` is the window's row budget (``None`` renders every row).  ``center``
picks the policy: the default top-stick window hangs at the top while the
cursor sits inside the first ``cap`` rows, then scrolls one row per step
with the cursor as its last row; a centring window keeps the cursor at
``index - cap // 2`` (clamped at both ends).  Either policy keeps the
cursor row on screen whenever the sequence has one.

The dataclass is a value: every method returns new positions or ranges and
mutates nothing, so a caller can hold one and a component can fold it into
its own state -- ``Select`` renders at most its ``max_rows`` rows through
the top-stick default, ``List`` at most its ``window`` rows through the
centring one.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CursorWindow"]


@dataclass(frozen=True)
class CursorWindow:
    """A cursor over ``count`` rows and the window policy that follows it.

    ``index`` is the cursor, ``count`` the rows it walks, ``cap`` the
    window's row budget and ``center`` the policy switch; the exact
    boundaries of either policy are :meth:`range`'s table.  The value is
    frozen and every method is pure: a caller assigns :meth:`move`'s answer
    back to its own cursor and renders the slice :meth:`range` names.
    """

    index: int = 0          # the cursor, expected already clamped by the caller-visible setter
    count: int = 0          # the rows the cursor walks
    cap: int | None = None  # the window's row budget; None renders everything
    center: bool = False    # False: the top-stick menu window; True: the centring view window

    def clamp(self, index: int) -> int:
        """The nearest legal cursor for ``index`` (``0`` for an empty set)."""
        if self.count <= 0:
            return 0
        return min(max(index, 0), self.count - 1)

    def range(self) -> tuple[int, int]:
        """The ``[start, stop)`` slice of rows to render (``(0, 0)`` when empty).

        The boundaries, in the order they decide:

        * an empty set (or a negative ``count``) -- ``(0, 0)``;
        * ``cap is None`` or ``count <= cap`` -- the whole sequence,
          ``(0, count)``, whatever ``center`` says: there is nothing to
          scroll;
        * ``cap <= 0`` -- ``(0, 0)``: no row fits;
        * the top-stick policy -- ``(0, cap)`` while the cursor sits inside
          the first ``cap`` rows, then ``(index - cap + 1, index + 1)``: one
          row per step with the cursor row last;
        * the centring policy -- ``start = min(max(index - cap // 2, 0),
          count - cap)`` and ``stop = start + cap``: the cursor half a
          window down, both ends clamped.

        The stored cursor is clamped first, so a stale ``index`` cannot
        produce a window off the rows.
        """
        if self.count <= 0:
            return 0, 0
        if self.cap is None or self.count <= self.cap:
            return 0, self.count
        if self.cap <= 0:
            return 0, 0
        index = self.clamp(self.index)
        if not self.center:
            if index < self.cap:
                return 0, self.cap
            return index - self.cap + 1, index + 1
        start = min(max(index - self.cap // 2, 0), self.count - self.cap)
        return start, start + self.cap

    def move(self, delta: int, wrap: bool = True) -> int:
        """The cursor after stepping ``delta``; wrapping or clamping at the ends.

        ``wrap=True`` -- the menu cycle -- steps off the last row onto the
        first and off the first onto the last (``(index + delta) % count``);
        ``wrap=False`` -- the data view -- clamps at the ends instead.
        Either way the answer is a legal cursor and this value is untouched;
        an empty sequence answers ``0`` -- there is nowhere to step.
        """
        if self.count <= 0:
            return 0
        if wrap:
            return (self.index + delta) % self.count
        return self.clamp(self.index + delta)
