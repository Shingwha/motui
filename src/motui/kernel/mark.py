"""MarkSet: the multiple-selection marking of a data view's rows.

A marked view (``Table`` / ``List`` / the multi-select choice family) holds
raw row indices -- the view's own data-row numbering, never rendered rows --
and the mark survives re-sorting or re-filtering because the host owns the
reorder and can re-map the set.  Two glyphs carry the mark: ``[x]`` marked,
``[ ]`` unmarked -- the checkbox pair from :mod:`motui.kernel.glyphs`, which
the views prefix to the row's own text through ``mark_prefix`` as one seat
(:func:`~motui.kernel.glyphs.seat`: the glyph plus its separator).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .glyphs import MARKED, UNMARKED, seat

__all__ = ["MarkSet", "mark_prefix"]


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


def mark_prefix(
    marked: bool,
    *,
    marked_glyph: str = MARKED,
    unmarked_glyph: str = UNMARKED,
) -> str:
    """The marked or unmarked seat: ``"[x] "`` / ``"[ ] "`` by default.

    The glyph pair is the vocabulary's checkbox pair
    (:data:`~motui.kernel.glyphs.MARKED` /
    :data:`~motui.kernel.glyphs.UNMARKED`); a host may pass its own pair,
    and each answer is :func:`~motui.kernel.glyphs.seat` -- the glyph plus
    one separator column, ``""`` for a disabled glyph.  A pair whose
    members differ in width is padded by the component through
    :func:`~motui.kernel.glyphs.pair_seat`, not here: this helper answers
    one glyph's own seat.
    """
    return seat(marked_glyph if marked else unmarked_glyph)
