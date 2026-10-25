"""NavList: the vertical navigation list -- one row per item, a bar indicator.

:class:`NavList` is the rail a host pins at the edge of its frame: one row
per item, every row the same shape -- a one-cell indicator **seat**, one
space and the label (``"\\u258c overview"``) -- the whole row ``fit`` to the
painting width so a narrow pane truncates with an ellipsis instead of
wrapping.  The active row fills the seat with ``glyphs.rail`` (``"\\u258c"``, the
left-half block of the VS Code / WinUI activity-bar vocabulary) in
``content.accent``; every other row leaves the
seat blank (``bar_space``) and wears ``text.faint`` on
the label.  The label column therefore never moves between
rows: the bar is the indicator, the blank seat the rows without one.

``groups`` adds the documentation-sidebar shape: an iterable of
``(position, label)`` pairs inserts one **group title row** before the
item at that *item* position -- ``(0, "FOUNDATIONS")`` above the first
item, ``(3, "COMPONENTS")`` above the fourth -- so a long rail reads as a
few named sections instead of one flat ladder.  A group row is chrome, not
an item: its seat is left blank (``bar_space``, the bar column never
moves) and its ``label`` renders verbatim in ``text.muted`` (the caller spells the case -- the demo passes it uppercase --
the component never rewrites a label).  Group rows are **unselectable and
unclickable**, they never take the hover band, and ``index`` /
``select`` / ``move`` keep counting **items** only -- a group row is
transparent to every verb, a rendered row is where the two meet.  A
``position`` below zero clamps above the first item, one past the last
item lays the group row after it; groups at one position keep their given
order.  An empty ``items`` still renders zero rows: there is nothing to
group.

The style roles resolve at render time from the theme (or a ``styles=``
group override): ``content.accent`` paints the active label,
``text.faint`` the inactive and disabled ones,
``surfaces.hover`` the row under the pointer, ``text.muted`` the
non-active bars and the group rows, and ``content.accent`` the active bar.
``rows.base`` is the resting surface every row rests on.
``focused`` is the focus flag the focus tier sets
(:class:`~motui.kernel.document.Focusable`): while it is ``False`` the active
bar composes ``text.muted`` whole over its style -- the indicator
drops a hue, it is never removed, and the label is never dimmed (the
``Tabs`` rule, verbatim).  It starts ``True``, the old default.

**The row-band contract.**  Every row resolves its band from the theme's
row roles: ``rows.base`` is the resting surface, ``rows.active`` the
selected row's band (the rail never dims it, focused or not) and
``rows.hover`` the pointer's (D3: one token per signal).  A row is
its text-styled
segments -- the seat and the label in their own styles -- then
``.clip(WrapMode.ELLIPSIS, width).fill(fitted.width, band)``: the W1 primitive, the band
underneath, the text styles on top.  The band merges under the row's own
cells -- a pill behind the text, never a ribbon across the pane; a
full-surface band is the host's container's job
(``Padding(fill_style=...)`` / ``Panel(frame=False, style=...)``, which
fill every row to the width they are handed).  The active row keeping its
accent label and gaining the band is decision D3; the fill is skipped
while the band is ``NONE`` -- the default theme's ground and both its
engaged bands -- so resting rows and group rows render exactly the bytes
they always did, and so do the active row and the hovered row until a
host themes them.

``disabled`` names the indices that are visible but not selectable: their
label renders in ``text.faint`` over the
non-active ``text.muted`` bar seat, :meth:`click` and :meth:`select` refuse them,
and :meth:`move` steps over them (clamped, never wrapping) exactly as
:meth:`Tabs.move` does.  A pointer over a disabled row still marks it --
hover is the pointer's echo, not a selection.

There is deliberately **no** ``handle``: the rail's key routing belongs to
the host, the same division of labour the tab strip keeps.  An empty
``glyphs.rail`` turns the indicator off and collapses its seat: the bar
column is the glyph's own width (``visible_width``, so a wide bar takes its
columns) and ``bar_space`` -- the separator after that column -- defaults to
one space while the bar is on and to ``""`` when it is off.  The blank rows' gutter
is therefore ``" " * seat_width(bar)`` (the bar column plus the default
separator), and an empty bar renders each label at column 0 -- no dangling
gutter -- with the state carried by the foreground alone.  An explicit
``bar_space`` sets the separator's width; the demo's one-cell gutter is
exactly the default.  An empty list renders **zero rows** -- not one blank
row: a navigation list is a viewport child, and empty means nothing to
show, unlike a tab strip's one-row chrome.

Pure component: the host routes keys and cells, ``render`` only draws.
Rows are the items -- there is no window and no column arithmetic, so
:meth:`click` takes the row as the index (the column is ignored, and the
docstring says so, as the kernel's ``Clickable`` charter demands) and
:meth:`hover_at` speaks the same row language as :class:`Tabs`.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from ..widgets.cursor import Cursor
from ..kernel.glyphs import GLYPHS, Glyphs, seat_width
from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget
from .strip import ClampedCursor

__all__ = ["NavList"]


class NavList(ClampedCursor, Widget):
    """A vertical navigation list: a bar indicator, a clamped selection.

    ``items`` is a list of labels, one row each; ``index`` is the selected
    index (read-only property), clamped into ``0..len(items)-1`` on
    construction (a disabled
    index passed there is kept -- the constructor rewrites no explicit
    request, the verbs are what refuse) and on every later
    :meth:`select`/:meth:`move`.  ``disabled_items`` is an iterable of indices
    that render but refuse :meth:`click`/:meth:`select` and are stepped
    over by :meth:`move`; the ``disabled`` flag refuses every gesture.  ``groups`` lays group title rows between the
    items (see the module docstring): they render but refuse every verb,
    and ``index`` stays an **item** index.

    Every row renders the bar column -- ``glyphs.rail`` (the active row) or
    the blank ``_bar_seat`` (the others) -- then the ``_separator``, then the
    label -- ``Line.fit`` to the painting width -- so all rows share one
    shape and the labels line up in one column.  ``glyphs.rail`` comes from
    the vocabulary; its column is the glyph's own display width, the blank
    rows leave that column empty, and
    ``bar_space`` is the separator after it (one space by default while the
    bar is on, ``""`` when it is off).  Both states therefore put the label
    at one column, and an empty bar collapses the whole gutter to zero
    columns.  The active row keeps its accent label and carries the
    ``rows.active`` band underneath it (D3); the resting rows and the
    group title rows rest on the ground.  An empty list renders ``[]``.
    """

    __slots__ = (
        "_bar_seat",
        "_bar_space",
        "_disabled_items",
        "_groups",
        "_hover_index",
        "_index",
        "_separator",
        "disabled",
        "glyphs",
        "items",
    )

    def __init__(
        self,
        items: list[str],
        *,
        groups: Sequence[tuple[int, str]] = (),
        index: int = 0,
        disabled_items: Iterable[int] = (),
        disabled: bool = False,
        glyphs: Glyphs = GLYPHS,
        bar_space: str | None = None,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.items = list(items)
        self.glyphs = glyphs
        bar = glyphs.rail
        # The bar column is as wide as the glyph; the blank rows leave that
        # column empty.  ``bar_space`` is the separator after it -- one space
        # by default while the bar is on, none when it is off -- and the
        # seat the blank rows wear (``_bar_seat``) plus that separator is the
        # full gutter stored as ``_bar_space``: ``" " * seat_width(bar)`` for
        # the default bar, and ``""`` when the bar is off.  A wide bar widens
        # its own column, so both states put the label at one column; an
        # explicit ``bar_space`` sets the separator's width.  Read-only: the
        # gutter is derived state (the P0 -- a host edit used to desync the
        # rendered seat from the snapshot).
        self._bar_seat = " " * (seat_width(bar) - (1 if bar else 0))
        separator_width = (
            visible_width(bar_space) if bar_space is not None else (1 if bar else 0)
        )
        self._separator = " " * separator_width
        self._bar_space = self._bar_seat + self._separator
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_index`` (:meth:`hover_at`).
        self.hover = False
        #: The whole rail refuses every selection gesture when disabled.
        self.disabled = disabled
        self._index = 0
        # The item row the pointer is on, or ``None``; written by
        # ``hover_at``, read by ``render``.  ``None`` renders byte-for-byte
        # what the list always did, and a group row never marks.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable; a frozenset so
        # ``click``/``select``/``move`` are one membership test apiece.
        self._disabled_items = frozenset(disabled_items)
        # The group title rows, latched at construction: each ``(position,
        # label)`` sits before that **item** index (clamped into
        # ``0..len(items)``, sorted stably so one position keeps its order).
        self._groups: tuple[tuple[int, str], ...] = tuple(
            sorted(
                ((min(max(position, 0), len(self.items)), label)
                 for position, label in groups),
                key=lambda pair: pair[0],
            )
        )
        # Styles resolve at render time from the theme (or ``styles=``);
        # only the derived gutter is latched here.
        if self.items:
            # Clamped like every later request; the disabled rule belongs to
            # the verbs, not to this explicit constructor value.
            self._index = Cursor(len(self.items)).clamp(index)

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        """The surface one rail row rests on: the theme's row roles.

        The rail never dims its engaged row: it reads ``rows.active``
        whether or not the rail is focused (D3), the pointer's row
        ``rows.hover`` and a resting row ``rows.base``.  The ``rows`` group
        comes from ``styles`` when overridden, else the theme.
        """
        rows = self.group("rows")
        if disabled:
            return rows.disabled
        if hovered:
            return rows.hover
        if current:
            return rows.active
        return rows.base

    @property
    def _entries(self) -> list[str]:
        """The item labels every cursor verb measures (group rows are chrome)."""
        return self.items

    @property
    def bar_space(self) -> str:
        """The derived gutter (blank bar column plus separator); read-only."""
        return self._bar_space

    def click(self, row: int, col: int) -> bool:
        """Select the item the **rendered** row ``row`` covers; True on a hit.

        The row is the cell: the list paints its rows itself -- items and
        group rows interleaved -- and never windows, so there is no
        last-render table to walk and ``col`` is ignored (the whole row is
        the cell).  A row outside the list, on a **disabled** item, on a
        **group title row**, or on a disabled rail answers ``False`` and
        changes nothing; a hit on an enabled item selects it -- even when it
        already was active -- and answers ``True``.
        """
        if self.disabled:
            return False
        index = self._item_at(row)
        if index is None or index in self._disabled_items:
            return False
        self.select(index)
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the item the **rendered** row ``row`` covers; True on a change.

        The row is the cell, ``col`` is ignored, and every row that covers
        no item -- a group title row, a negative row (the pointer left),
        anything past the last row -- answers "no row" and clears the
        marking, exactly as :meth:`Tabs.hover_at` does; a group row is
        therefore never marked.  Disabled items are marked like any other
        (the band is the pointer's echo, not a selection).  The answer
        is whether the marked row changed; :meth:`render` rests that row on
        ``rows.hover`` -- the pointer's own token, whatever row
        it is on (D3).
        """
        target = self._item_at(row)
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def revision(self) -> object:
        """The row cache's snapshot: every input the list's rows read.

        In order: the items (a tuple copy, so an in-place edit of the host's
        list moves it), the latched group rows, the index, the disabled item
        set, the whole-control disabled flag, the item under the pointer,
        ``focused``, the bar and the derived gutter string, the theme and
        the ``styles`` overrides (the label, bar and band roles resolve from
        them at render time).  The block-level ``hover`` flag
        paints nothing -- the row emphasis lives in ``_hover_index`` -- so it
        is deliberately out.

        The snapshot is plain immutable values and costs far less than a
        render; it is what lets a **sealed** rail's hover, focus flip or
        selection reach the screen (D4).
        """
        return (
            tuple(self.items),
            self._groups,
            self._index,
            self._disabled_items,
            self.disabled,
            self._hover_index,
            self.focused,
            self.glyphs,
            self._bar_space,
            self.theme,
            self.styles,
        )

    def render(self, c: Constraints) -> Surface:
        """One row per item **and group row** (``[]`` for an empty list), each on its band.

        An item row is ``bar + separator + label`` on the selected item --
        the bar in ``content.accent`` (``text.muted`` whole while
        unfocused) -- and ``blank bar column + separator + label`` on the
        others, so the label column is the same everywhere (the blank column
        is the bar glyph's display width); the label wears its own
        style (``text.faint`` for a disabled index: the stricter state
        wins), then the band the row resolved to (D3: the selected row's
        ``rows.active`` under its accent label, the pointer's row
        ``rows.hover`` -- and the hover wins wherever the two meet).  A group row is
        ``blank column + separator + label`` in ``text.muted`` -- the seat is
        left blank, the label verbatim (the caller spells its case) -- and
        rests on the ground, never the engaged band.  An empty ``glyphs.rail``
        collapses the seat with it (the blank column is zero wide and the
        separator defaults to ``""``), so every row renders the label alone
        and the state is carried by the foreground alone.  Every row is
        ``fit`` to ``c.width`` with its band resting underneath
        (:func:`~motui.kernel.cell.rest`); the surface is
        :meth:`Surface.clipped` and a ``max_height`` budget truncates the
        leading rows.
        """
        if not self.items:
            return Surface.clipped([], c.width)
        # The roles resolve once per render; the focus rule drops the active
        # bar from accent to muted -- the label is never dimmed (D3).
        text = self.group("text")
        active_label = self.group("content").accent
        bar_active = active_label
        if not self.focused:
            bar_active = bar_active.merge(text.muted)
        rows: list[Line] = []
        for kind, payload in self._plan():
            if kind == "group":
                rows.append(
                    rest(
                        Line((
                            Segment(self._bar_seat, text.muted),
                            Segment(f"{self._separator}{payload}", text.muted),
                        )),
                        c.width,
                        self._band(False, False),
                    )
                )
                continue
            index = payload
            if index in self._disabled_items:
                label_style, bar_style = text.faint, text.muted
            elif index == self._index:
                label_style, bar_style = active_label, bar_active
            else:
                label_style, bar_style = text.faint, text.muted
            seat = (
                self.glyphs.rail
                if index == self._index and self.glyphs.rail
                else self._bar_seat
            )
            rows.append(
                rest(
                    Line((
                        Segment(seat, bar_style),
                        Segment(
                            f"{self._separator}{self.items[index]}", label_style
                        ),
                    )),
                    c.width,
                    self._band(index == self._index, index == self._hover_index),
                )
            )
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    # -- the row plan ------------------------------------------------------------

    def _plan(self) -> list[tuple[str, object]]:
        """The rendered rows, top to bottom: ``("group", label)`` or ``("item", index)``.

        Derived from ``items`` and the group positions on every call, so
        replacing ``items`` never leaves a stale plan behind; the positions
        themselves were clamped to the item range at construction.
        """
        plan: list[tuple[str, object]] = []
        remaining = list(self._groups)
        for position in range(len(self.items) + 1):
            while remaining and remaining[0][0] == position:
                plan.append(("group", remaining.pop(0)[1]))
            if position < len(self.items):
                plan.append(("item", position))
        return plan

    def _item_at(self, row: int) -> int | None:
        """The item index the rendered ``row`` covers, or ``None`` (a group row).

        ``None`` for every row outside the plan as well: one answer for
        "this row is no item", whether it is chrome or nothing at all.
        """
        plan = self._plan()
        if 0 <= row < len(plan) and plan[row][0] == "item":
            return plan[row][1]  # type: ignore[return-value]
        return None

    def __repr__(self) -> str:
        return f"NavList({self.items!r}, index={self._index})"
