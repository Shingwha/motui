"""MarkSet: the multiple-selection marking of a data view's rows.

A marked view (``Table`` / ``List`` / the multi-select choice family) holds
raw row indices -- the view's own data-row numbering, never rendered rows --
and the mark survives re-sorting or re-filtering because the host owns the
reorder and can re-map the set.  Two glyphs carry the mark: ``[x]`` marked,
``[ ]`` unmarked -- the checkbox pair, three columns wide, which the views
prefix to the row's own text through ``mark_prefix``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

__all__ = ["MarkSet", "mark_prefix"]

#: The two marked-row prefixes (the checkbox glyph pair, three columns).
MARKED = "[x]"
UNMARKED = "[ ]"


class MarkSet:
    """A mutable set of raw row indices; ``toggle`` is the one gesture.

    An index is the view's **data-row** number -- never a rendered row --
    and the set stores exactly what it is given: duplicates collapse (it is
    a set), a negative index is kept as it came, and the view clamps to its
    own rows before it reads or writes.  ``toggle`` answers the *new* state
    (``True`` means the index is marked now) and ``clear`` whether anything
    was dropped, so a caller tells "nothing happened" from "the view must
    repaint" without asking the set twice.  Iteration is a snapshot copy in
    ascending order: rendering reads the marks in that one order, so the
    rows never depend on the order the marks were made in.
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


def mark_prefix(marked: bool) -> str:
    """The three-column glyph plus a separator: ``"[x] "`` / ``"[ ] "``."""
    return (MARKED if marked else UNMARKED) + " "
