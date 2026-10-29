"""MarkSet: the multiple-selection marking of a data view's rows.

Holds raw data-row indices; the host owns any reorder and can re-map the
set.  The vocabulary's ``check_on``/``check_off`` pair renders the mark.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from ..kernel.glyphs import GLYPHS, seat

__all__ = ["MarkSet", "mark_prefix"]


class MarkSet:
    """A mutable set of raw row indices; ``toggle`` is the one gesture.

    Indices are data-row numbers, stored as given; the view clamps.  Toggle
    answers the new state and ``clear`` whether anything dropped.  Iteration
    is a sorted snapshot.
    """

    __slots__ = ("_index",)

    def __init__(self, marked: Iterable[int] = ()) -> None:
        self._index: set[int] = set(marked)

    def __contains__(self, index: int) -> bool:
        return index in self._index

    def __iter__(self) -> Iterator[int]:
        """The marked indices in ascending order, as a snapshot copy."""
        return iter(sorted(self._index))

    def __len__(self) -> int:
        """How many rows are marked."""
        return len(self._index)

    def toggle(self, index: int) -> bool:
        """Flip ``index``'s mark; answer the new state (``True`` = now marked)."""
        if index in self._index:
            self._index.remove(index)
            return False
        self._index.add(index)
        return True

    def clear(self) -> bool:
        """Drop every mark; answer whether anything was dropped."""
        changed = bool(self._index)
        self._index.clear()
        return changed

    def __repr__(self) -> str:
        return f"MarkSet({sorted(self._index)!r})"


def mark_prefix(
    marked: bool,
    *,
    marked_glyph: str = GLYPHS.check_on,
    unmarked_glyph: str = GLYPHS.check_off,
) -> str:
    """The marked or unmarked seat: ``"[x] "`` / ``"[ ] "`` by default.

    Each answer is one glyph's seat; pair padding is the component's job.
    """
    return seat(marked_glyph if marked else unmarked_glyph)
