"""Strip internals: the clamped cursor and the one-row label strip.

The module is private to the widget package.  :class:`ClampedCursor` is the
selection half of a label strip -- ``index`` / ``select`` / ``move`` over a
label sequence and a disabled-index set.  The public components are
:class:`~motui.widgets.tabs.Tabs` and
:class:`~motui.widgets.menubar.MenuBar`; nothing here is re-exported from
:mod:`motui.widgets`.
"""

from __future__ import annotations

from typing import Sequence

__all__ = ["ClampedCursor"]


class ClampedCursor:
    """A clamped, non-wrapping cursor over a disabled-aware label sequence.

    The mixin owns no storage: subclasses keep the ``_index``,
    ``_disabled_items`` and ``disabled`` slots and implement
    :attr:`_entries`.  :meth:`select` clamps into ``0..len-1`` and refuses a
    disabled index (or a disabled control); :meth:`move` steps over disabled
    indices, clamps at the ends and never wraps.  ``revision()`` stays with
    each component: the value it snapshots is the component's own.
    """

    __slots__ = ()

    _index: int
    _disabled_items: frozenset[int]
    disabled: bool

    @property
    def _entries(self) -> Sequence[str]:
        """The label sequence every cursor verb measures; subclasses implement."""
        raise NotImplementedError

    @property
    def index(self) -> int:
        """The selected index, always inside the entry range.

        Read-only: :meth:`select` and :meth:`move` are the moving doors.
        """
        return self._index

    def select(self, index: int) -> bool:
        """Select ``index``, clamped into range; True when it changed.

        A ``disabled`` index is refused outright -- ``False``, nothing
        moved -- a disabled control refuses every selection, and an empty
        sequence answers ``False`` always.
        """
        if self.disabled or not self._entries:
            return False
        target = min(max(index, 0), len(self._entries) - 1)
        if target in self._disabled_items:
            return False
        changed = target != self._index
        self._index = target
        return changed

    def move(self, delta: int) -> bool:
        """Move the selection ``delta`` labels, clamped and never wrapping.

        Disabled indices are **stepped over**: a positive step from index 1
        with 2 disabled lands on 3, and a step whose direction holds no
        enabled index left stays where it was (``False``).  A disabled
        control moves nowhere.  The answer is whether the selection changed.
        """
        if self.disabled or not self._entries or delta == 0:
            return False
        step = 1 if delta > 0 else -1
        target = self._index
        for _ in range(abs(delta)):
            nxt = target + step
            while 0 <= nxt < len(self._entries) and nxt in self._disabled_items:
                nxt += step
            if not 0 <= nxt < len(self._entries):
                break  # clamped at the edge: the step has no enabled landing
            target = nxt
        return self.select(target)
