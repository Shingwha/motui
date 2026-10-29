"""Cursor: the one cursor-and-window arithmetic the widgets share.

Walking (skip disabled, clamp or wrap), edge jumps and the three window
policies (top/center/bottom) live here once.  ``count`` is the row count and
``index`` the raw cursor, clamped by the verbs rather than construction.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["Cursor"]

#: The window policies :meth:`Cursor.window` understands.
_ANCHORS = ("top", "center", "bottom")


class Cursor:
    """A cursor over ``count`` rows plus its disabled set and wrap rule.

    ``wrap=True`` cycles the ends; ``False`` clamps.  Disabled rows are
    stepped over and refused by ``select``.  The value is mutable and each
    verb is the whole rule.
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
        """Land on ``index`` (clamped); disabled targets and empty sets answer ``False``."""
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

        Disabled rows are stepped over; wrapping cycles, clamping stops at
        the ends, and an empty sequence moves nowhere.
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

        A wrapping walk checks every row once; a clamping walk stops at the
        boundary.
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

        ``anchor`` is ``"top"`` (cursor row last after the first page),
        ``"center"`` (half a page above, clamped) or ``"bottom"`` (tail
        pinned); a sequence fitting ``size`` answers all rows.  The stored
        cursor is clamped first.
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
