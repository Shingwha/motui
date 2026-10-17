"""Radio: the single-choice group -- one ``(•)`` marker on one row.

A radio group is one selection over a list of labels: the row at
:attr:`Radio.index` carries the filled marker (``(•) label``), every other
row the empty one (``( ) label``), and the selected row renders in
``selected_style`` -- the theme's ``accent`` by default -- while the plain
rows stay unstyled.  The component holds state and answers controller
methods like every primitive (D15): :meth:`Radio.move` steers the selection,
:meth:`Radio.click` and :meth:`Radio.activate` are its two doors, and all
three write the selection into :attr:`Radio.chosen` for the host to read
once and reset -- there is no callback, no event bus.

``labels`` takes plain strings (the label is the value) or
:class:`~motui.widgets.choice.Option` entries (a label with its own
payload), the same option vocabulary the menu family speaks; ``chosen`` is
the selected entry's value, or its label when a plain string was given.
Rows step with :meth:`Radio.move` like a data view -- **clamped** at the
ends, never wrapping -- and ``hover_at`` is the pointer tier's row marking
(the marked row merges the theme's ``hover``), resolved the same way
:meth:`Radio.click` resolves a cell, so the two can never disagree.
``focused`` is the focus flag the focus tier sets
(:class:`~motui.core.block.Focusable`): while it is ``True`` the
selected row additionally merges ``focus_style`` (the theme's ``cursor``) --
the selection stays visible either way, and an unfocused radio renders
byte-for-byte what it always did.
"""

from __future__ import annotations

from typing import Sequence

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import Theme, Themed
from .choice import Option

__all__ = ["Radio"]

#: The empty marker: unselected rows lead with it, four cells wide.
EMPTY_MARK = "( ) "

#: The filled marker: the one row that is the group's selection leads with it.
FILLED_MARK = "(\u2022) "


class Radio(Themed):
    """A vertical single-choice group with one ``(•)`` selection.

    ``index`` is the selected (and cursor) row: reading it is always a row
    of the group, and assigning clamps into range (an empty group keeps
    ``0``).  ``labels`` is the display labels, in order -- the constructor
    accepted strings and :class:`~motui.widgets.choice.Option` entries
    both, and this is the plain-text view of what renders.  :meth:`move`
    steps the selection ``delta`` rows and clamps at the ends; a step that
    moved writes the new selection into :attr:`chosen`, as does a landing
    :meth:`click` and an :meth:`activate` -- the host reads ``chosen`` once
    and resets it to ``None``.

    :meth:`hover_at` is the pointer tier's row-level half: the marked row
    renders its own style merged with the theme's ``hover``.  The marking
    lives in one private row index that starts ``None``, so an un-hovered
    group renders byte-for-byte what it always did; ``hover`` is the
    tier's block-level flag and paints nothing of its own (the row marking
    is the whole emphasis, the ``Select`` precedent).  Styles resolve
    once, at construction, as explicit > theme field > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "_focus_style",
        "_hover_row",
        "_hover_style",
        "_index",
        "_label_style",
        "_selected_style",
        "_values",
        "chosen",
        "focused",
        "hover",
        "labels",
        "theme",
    )

    def __init__(
        self,
        labels: Sequence[str | Option],
        *,
        index: int = 0,
        label_style: Style | None = None,
        selected_style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        #: The display labels, in row order (the constructor's strings and
        #: options normalized to their labels).
        self.labels = [
            item.label if isinstance(item, Option) else str(item) for item in labels
        ]
        # The payload ``chosen`` carries per row: an Option's value (its
        # label when the value is None), or the plain label itself.
        self._values = [
            (item.value if item.value is not None else item.label)
            if isinstance(item, Option)
            else str(item)
            for item in labels
        ]
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`hover_at`).
        self.hover = False
        # The row the pointer is on, or ``None``; written by ``hover_at``,
        # read by ``render``.  ``None`` renders byte-for-byte the same rows.
        self._hover_row: int | None = None
        #: The pending selection: written by ``move`` / ``click`` /
        #: ``activate`` (the selected entry's label or payload), read once by
        #: the host, which resets it to ``None``.
        self.chosen: int | str | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._label_style = label_style if label_style is not None else NONE
        self._selected_style = self._pick(selected_style, "accent")
        self._hover_style = self._pick(hover_style, "hover")
        self._focus_style = self._pick(focus_style, "cursor")
        # The setter reads ``self.labels``, which is armed by now.
        self.index = index

    # -- the selection ---------------------------------------------------------

    @property
    def index(self) -> int:
        """The selected row of :attr:`labels` (``0`` for an empty group)."""
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        count = len(self.labels)
        self._index = min(max(value, 0), count - 1) if count else 0

    @property
    def selected(self) -> str | None:
        """The label of the selected row, or ``None`` for an empty group."""
        return self.labels[self._index] if self.labels else None

    def move(self, delta: int) -> bool:
        """Step the selection ``delta`` rows, clamped; ``True`` when it moved.

        A radio group is a data view, not a menu cycle: the selection stops
        at the ends instead of wrapping.  A step that moved writes the new
        selection into :attr:`chosen` (the group really selected it); an
        empty group moves nowhere.
        """
        if not self.labels:
            return False
        target = min(max(self._index + delta, 0), len(self.labels) - 1)
        moved = target != self._index
        self._index = target
        if moved:
            self.chosen = self._values[target]
        return moved

    def click(self, row: int, col: int) -> bool:
        """Select the row a cell landed on; ``True`` on a hit.

        ``row`` is a 0-based row of this component's own render; ``col`` is
        ignored -- a radio row owns the whole width, like every row-shaped
        component.  A hit selects that row (even when it already was
        selected) and writes it into :attr:`chosen`; a row outside the
        labels answers ``False`` and changes nothing.
        """
        if not 0 <= row < len(self.labels):
            return False
        self._index = row
        self.chosen = self._values[row]
        return True

    def activate(self) -> bool:
        """Take the selected row into :attr:`chosen`; ``True`` on a selection.

        The group's :class:`~motui.core.block.Activable` verb: a host
        routes the return key here, then reads ``chosen`` once.  An empty
        group has nothing to take (``False``, and ``chosen`` stays ``None``).
        """
        if not self.labels:
            return False
        self.chosen = self._values[self._index]
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the row under a cell; ``True`` when the marking changed.

        The pointer tier's row-level half: ``row`` is a 0-based row of this
        component's own render and ``col`` is ignored (a radio row owns the
        whole width).  A negative ``row`` -- or one past the labels -- clears
        the marking (the pointer left); the answer is whether the marked row
        actually changed, so a motion inside one row answers ``False``
        (nothing to repaint).  :meth:`render` merges the theme's ``hover``
        over the marked row's own style.
        """
        target = row if 0 <= row < len(self.labels) else None
        changed = target != self._hover_row
        self._hover_row = target
        return changed

    # -- rendering ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        out: list[Line] = []
        for index, label in enumerate(self.labels):
            style = self._selected_style if index == self._index else self._label_style
            if index == self._hover_row:
                style = style.merge(self._hover_style)
            if index == self._index and self.focused:
                style = style.merge(self._focus_style)
            mark = FILLED_MARK if index == self._index else EMPTY_MARK
            out.append(Line((Segment(mark, style), Segment(label, style))).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Radio({self.labels!r}, index={self._index}, focused={self.focused})"
