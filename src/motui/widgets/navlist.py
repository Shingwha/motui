"""NavList: the vertical navigation list -- one row per item, a bar indicator.

:class:`NavList` is the rail a host pins at the edge of its frame: one row
per item, every row the same shape -- a one-cell indicator **seat**, one
space and the label (``"\\u258c overview"``) -- the whole row ``fit`` to the
painting width so a narrow pane truncates with an ellipsis instead of
wrapping.  The active row fills the seat with ``bar`` (``"\\u258c"``, the
left-half block of the VS Code / WinUI activity-bar vocabulary) in
``bar_active_style`` (the theme's ``accent``); every other row leaves the
seat blank (``bar_space``) and wears ``inactive_style`` (the theme's
``dim``) on the label.  The label column therefore never moves between
rows: the bar is the indicator, the blank seat the rows without one.

``groups`` adds the documentation-sidebar shape: an iterable of
``(position, label)`` pairs inserts one **group title row** before the
item at that *item* position -- ``(0, "FOUNDATIONS")`` above the first
item, ``(3, "COMPONENTS")`` above the fourth -- so a long rail reads as a
few named sections instead of one flat ladder.  A group row is chrome, not
an item: its seat is left blank (``bar_space``, the bar column never
moves) and its ``label`` renders verbatim in ``group_style`` (the theme's
``muted``; the caller spells the case -- the demo passes it uppercase --
the component never rewrites a label).  Group rows are **unselectable and
unclickable**, they never take the hover band, and ``active`` /
``select`` / ``move`` keep counting **items** only -- a group row is
transparent to every verb, a rendered row is where the two meet.  A
``position`` below zero clamps above the first item, one past the last
item lays the group row after it; groups at one position keep their given
order.  An empty ``items`` still renders zero rows: there is nothing to
group.

The five style knobs resolve once, at construction, as explicit > theme
field > ``DEFAULT_THEME``: ``active_style`` falls back to the theme's
``accent``, ``inactive_style``/``disabled_style`` to its ``dim``,
``hover_style`` to its ``ground_active``, the non-active bars (``bar_style``) to
its ``muted`` and the active one (``bar_active_style``) to its ``accent``.
``ground_style`` is the family's one new knob: the resting surface every
row rests on.  ``focused`` is the focus flag the focus tier sets
(:class:`~motui.kernel.block.Focusable`): while it is ``False`` the active
bar composes the theme's ``muted`` whole over its style -- the indicator
drops a hue, it is never removed, and the label is never dimmed (the
``Tabs`` rule, verbatim).

**The row-band contract.**  Every row resolves its bands once, at
construction: ``_ground = _pick(ground_style, "ground")`` is the resting
surface and ``_active`` -- the active row's band -- picks
``"ground_active"``, the engaged surface the pointer's hovered row wears as
well (D2).  A row is its text-styled segments -- the seat and the label in
their own styles -- then ``.fit(width).fill(width, band)``: the W1
primitive, the band underneath, the text styles on top, the surface
spanning the painting width.  The active row keeping its accent label and
gaining the band is decision D3; the fill is skipped while the band is
``NONE`` -- the default theme's ground -- so resting rows and group rows
render exactly the bytes they always did, while the active row's band now
spans the width, the registered default change.

``disabled`` names the indices that are visible but not selectable: their
label renders in ``disabled_style`` (the theme's ``dim``) over the
non-active ``bar_style``, :meth:`click` and :meth:`select` refuse them,
and :meth:`move` steps over them (clamped, never wrapping) exactly as
:meth:`Tabs.move` does.  A pointer over a disabled row still marks it --
hover is the pointer's echo, not a selection.

There is deliberately **no** ``handle``: the rail's key routing belongs to
the host, the same division of labour the tab strip keeps.  ``bar = ""``
turns the indicator off (pair it with ``bar_space = ""`` to drop the seat
as well); with the bar off every row renders the same shape and the state
is carried by the foreground alone.  An empty list renders **zero rows**
-- not one blank row: a navigation list is a viewport child, and empty
means nothing to show, unlike a tab strip's one-row chrome.

Pure component: the host routes keys and cells, ``render`` only draws.
Rows are the items -- there is no window and no column arithmetic, so
:meth:`click` takes the row as the index (the column is ignored, and the
docstring says so, as the kernel's ``Clickable`` charter demands) and
:meth:`hover_at` speaks the same row language as :class:`Tabs`.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from ..kernel.lines import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme, Themed

__all__ = ["NavList"]


class NavList(Themed):
    """A vertical navigation list: a bar indicator, a clamped selection.

    ``items`` is a list of labels, one row each; ``active`` is the selected
    index, clamped into ``0..len(items)-1`` on construction (a disabled
    index passed there is kept -- the constructor rewrites no explicit
    request, the verbs are what refuse) and on every later
    :meth:`select`/:meth:`move`.  ``disabled`` is an iterable of indices
    that render but refuse :meth:`click`/:meth:`select` and are stepped
    over by :meth:`move`.  ``groups`` lays group title rows between the
    items (see the module docstring): they render but refuse every verb,
    and ``active`` stays an **item** index.

    Every row renders ``bar`` (the active row) or ``bar_space`` (the
    others), then ``bar_space``, then the label -- ``Line.fit`` to the
    painting width -- so all rows share one shape and the labels line up in
    one column.  The active row keeps its accent label and carries the
    ``ground_active`` band underneath it (D3); the resting rows and the
    group title rows rest on the ground.  An empty list renders ``[]``.
    """

    __slots__ = (
        "_active",
        "_active_band",
        "_active_style",
        "_bar_active_style",
        "_bar_style",
        "_disabled",
        "_disabled_style",
        "_ground",
        "_group_style",
        "_groups",
        "_hover_index",
        "_hover_style",
        "_inactive_style",
        "bar",
        "bar_space",
        "focused",
        "hover",
        "items",
        "theme",
    )

    def __init__(
        self,
        items: list[str],
        *,
        groups: Sequence[tuple[int, str]] = (),
        group_style: Style | None = None,
        active: int = 0,
        disabled: Iterable[int] = (),
        bar: str = "\u258c",
        bar_space: str = " ",
        active_style: Style | None = None,
        inactive_style: Style | None = None,
        hover_style: Style | None = None,
        disabled_style: Style | None = None,
        bar_style: Style | None = None,
        bar_active_style: Style | None = None,
        ground_style: Style | None = None,
        focused: bool = True,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.items = list(items)
        self.bar = bar
        self.bar_space = bar_space
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_index`` (:meth:`hover_at`).
        self.hover = False
        self._active = 0
        # The item row the pointer is on, or ``None``; written by
        # ``hover_at``, read by ``render``.  ``None`` renders byte-for-byte
        # what the list always did, and a group row never marks.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable; a frozenset so
        # ``click``/``select``/``move`` are one membership test apiece.
        self._disabled = frozenset(disabled)
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
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._active_style = self._pick(active_style, "accent")
        self._inactive_style = self._pick(inactive_style, "dim")
        self._hover_style = self._pick(hover_style, "ground_active")
        self._disabled_style = self._pick(disabled_style, "dim")
        self._bar_style = self._pick(bar_style, "muted")
        self._bar_active_style = self._pick(bar_active_style, "accent")
        self._group_style = self._pick(group_style, "muted")
        self._ground = self._pick(ground_style, "ground")
        self._active_band = self._pick(None, "ground_active")
        if self.items:
            # Clamped like every later request; the disabled rule belongs to
            # the verbs, not to this explicit constructor value.
            self._active = min(max(active, 0), len(self.items) - 1)

    @property
    def active(self) -> int:
        """The selected **item** index, always inside the item range.

        Group rows carry no index: a selection never lands on one.
        """
        return self._active

    def select(self, index: int) -> bool:
        """Select item ``index``, clamped into range; True when it changed.

        ``index`` is an item index -- group rows are transparent.  A
        ``disabled`` index is refused outright -- ``False``, nothing moved
        -- and an empty list answers ``False`` always.
        """
        if not self.items:
            return False
        target = min(max(index, 0), len(self.items) - 1)
        if target in self._disabled:
            return False
        changed = target != self._active
        self._active = target
        return changed

    def move(self, delta: int) -> bool:
        """Move the selection ``delta`` items, clamped and never wrapping.

        Disabled indices are **stepped over**: a positive step from index 1
        with 2 disabled lands on 3, and a step whose direction holds no
        enabled index left stays where it was (``False``).  Group rows are
        not indices: a step counts items, so it walks across every group
        row in between.  The answer is whether the selection changed.
        """
        if not self.items or delta == 0:
            return False
        step = 1 if delta > 0 else -1
        target = self._active
        for _ in range(abs(delta)):
            nxt = target + step
            while 0 <= nxt < len(self.items) and nxt in self._disabled:
                nxt += step
            if not 0 <= nxt < len(self.items):
                break  # clamped at the edge: the step has no enabled landing
            target = nxt
        return self.select(target)

    def click(self, row: int, col: int) -> bool:
        """Select the item the **rendered** row ``row`` covers; True on a hit.

        The row is the cell: the list paints its rows itself -- items and
        group rows interleaved -- and never windows, so there is no
        last-render table to walk and ``col`` is ignored (the whole row is
        the cell).  A row outside the list, on a **disabled** item, or on a
        **group title row** answers ``False`` and changes nothing; a hit on
        an enabled item selects it -- even when it already was active -- and
        answers ``True``.
        """
        index = self._item_at(row)
        if index is None or index in self._disabled:
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
        the theme's ``ground_active`` band -- the same engaged surface the
        active row wears (D2).
        """
        target = self._item_at(row)
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def revision(self) -> object:
        """The row cache's snapshot: every input the list's rows read.

        In order: the items (a tuple copy, so an in-place edit of the host's
        list moves it), the latched group rows, the active item index, the
        disabled set, the item under the pointer, ``focused``, the bar and
        seat strings, the nine resolved bands and the theme (read at render
        time for the unfocused bar's ``muted``).  The block-level ``hover``
        flag paints nothing -- the row emphasis lives in ``_hover_index`` --
        so it is deliberately out.

        The snapshot is plain immutable values and costs far less than a
        render; it is what lets a **sealed** rail's hover, focus flip or
        selection reach the screen (D4).
        """
        return (
            tuple(self.items),
            self._groups,
            self._active,
            self._disabled,
            self._hover_index,
            self.focused,
            self.bar,
            self.bar_space,
            self._active_style,
            self._inactive_style,
            self._hover_style,
            self._disabled_style,
            self._bar_style,
            self._bar_active_style,
            self._group_style,
            self._ground,
            self._active_band,
            self._theme,
        )

    def render(self, width: int) -> list[Line]:
        """One row per item **and group row** (``[]`` for an empty list), each on its band.

        An item row is ``bar + bar_space + label`` on the active item -- the
        bar in ``bar_active_style`` (the theme's ``muted`` whole while
        unfocused) -- and ``bar_space + bar_space + label`` on the others,
        so the label column is the same everywhere; the label wears its own
        style (``disabled_style`` for a disabled index: the stricter state
        wins), then the band the row resolved to (D3: the active row's
        ``ground_active`` under its accent label, the pointer's the same
        token -- D2).  A group row is
        ``bar_space + bar_space + label`` in ``group_style`` -- the seat is
        left blank, the label verbatim (the caller spells its case) -- and
        rests on the ground, never the engaged band.  A ``bar`` of ``""``
        leaves the seat to ``bar_space``, so every row renders one shape and
        the state is carried by the foreground alone.  Every row is ``fit``
        to ``width`` with its band resting underneath through the W1
        primitive (:meth:`_rest`).
        """
        if not self.items:
            return []
        # The focus rule, once per render: an unfocused list drops the bar
        # from accent to muted -- the label is never dimmed (D3).
        bar_active = self._bar_active_style
        if not self.focused:
            bar_active = bar_active.merge(self._theme.muted)
        rows: list[Line] = []
        for kind, payload in self._plan():
            if kind == "group":
                rows.append(
                    self._rest(
                        Line((
                            Segment(self.bar_space, self._bar_style),
                            Segment(f"{self.bar_space}{payload}", self._group_style),
                        )),
                        width,
                    )
                )
                continue
            index = payload
            if index in self._disabled:
                label_style, bar_style = self._disabled_style, self._bar_style
            elif index == self._active:
                label_style, bar_style = self._active_style, bar_active
            else:
                label_style, bar_style = self._inactive_style, self._bar_style
            seat = self.bar if index == self._active and self.bar else self.bar_space
            rows.append(
                self._rest(
                    Line((
                        Segment(seat, bar_style),
                        Segment(f"{self.bar_space}{self.items[index]}", label_style),
                    )),
                    width,
                    index == self._active,
                    index == self._hover_index,
                )
            )
        return rows

    def _band(self, current: bool, hovered: bool) -> Style:
        """The surface one row rests on: the ground, or the engaged band.

        The active row carries ``_active_band`` (``ground_active`` -- D3:
        the band under its accent label), the pointer's row ``_hover_style``
        (``ground_active`` as well -- D2: the active row and the hover share
        the one token), stacked where the two meet; every other row -- a
        resting item or a group title -- rests on the ground.  The band is
        never dimmed: the rail's unfocused rule is the bar's hue (the label
        is never dimmed), not a band's weight.
        """
        if not current and not hovered:
            return self._ground
        band = self._active_band if current else self._hover_style
        if hovered:
            band = band.merge(self._hover_style)
        return band

    def _rest(
        self, line: Line, width: int, current: bool = False, hovered: bool = False
    ) -> Line:
        """One row on its band: the text-styled segments, ``fit``, band under.

        The row-band contract's rendering half: ``fit`` trims to ``width``,
        then the band :meth:`_band` resolved rests *underneath* the segments
        through the W1 primitive -- the band the base, the text styles on
        top (the Rich ``Padding(style=...)`` rule) -- and the row grows to
        the full painting width, the surface a grounded row wears.  The fill
        is skipped when the band is ``NONE`` (the default theme's ground):
        a resting row is then exactly the row it always was, byte for byte,
        while an engaged row's band -- and any themed ground -- spans the
        width (the registered default change).
        """
        fitted = line.fit(width)
        band = self._band(current, hovered)
        return fitted if band == NONE else fitted.fill(width, band)

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
        return f"NavList({self.items!r}, active={self._active})"
