"""Tabs: the horizontal content strip -- one row, one underline indicator.

:class:`Tabs` is the strip a content view switch wears: exactly one row of
``" a \\u2502 b \\u2502 c "`` -- one space of breathing room at both ends,
the labels joined by ``" " + divider + " "``, the whole row ``fit`` to the
painting width so a narrow screen truncates with an ellipsis instead of
wrapping.  The active label is the strip's **indicator**: it carries
``active_style`` (the theme's ``accent``) merged with ``indicator_style``
(the theme's ``accent`` too, so the default is one hue) **and the underline
mark** -- the indicator's shape, which survives every color mode as an SGR
attribute, so an active label reads as active even with the colors off.
The other labels wear ``inactive_style`` (the theme's ``dim``), the
dividers ``divider_style`` (the theme's ``muted`` -- a separator is never
accent), and the label under the pointer merges the theme's ``hover`` band.

``focused`` is the focus flag the focus tier sets
(:class:`~motui.kernel.block.Focusable`).  While it is ``False`` the
indicator **drops from accent to muted** -- the label is *not* dimmed (the
old reverse-video recipe dimmed it; that behaviour is gone).  The color
rule is worth spelling out because :meth:`~motui.kernel.style.Style.merge`
cannot take "just the foreground": the default indicator is the theme's
``accent`` whole (its ``fg`` *and* its bold flag), so an unfocused strip
composes ``active_style.merge(theme.muted)`` -- ``muted`` whole, the same
rule the ``NavList`` bar follows -- rather than merging something onto
``accent`` and hoping to lower its weight.  The underline mark stays: an
unfocused strip loses the indicator's hue, never the indicator.

``disabled_items`` names the indices that are visible but not selectable:
their label renders in ``disabled_style`` (the theme's ``dim``, so a
disabled label is quiet by default), :meth:`click` answers ``False``
without touching the selection, and :meth:`move` **steps over** them --
a step towards a disabled index lands on the next enabled one, and a step
with no enabled index left in that direction stays put.  :meth:`select`
onto a disabled index answers ``False`` and changes nothing.  A pointer
over a disabled label still marks it (the hover band is the pointer's
echo, not a selection), and a disabled index passed as the constructor's
``index`` is kept -- the constructor rewrites no explicit request, the
four verbs above are what refuse.  The ``disabled`` flag is the whole-strip
switch: every selection gesture is refused.

Inactive and disabled labels share the theme's ``dim`` by default: the
state difference is carried by what the label *can do*, and a host that
wants a visible difference passes a distinct ``disabled_style``.

The strip is horizontal, period: the second axis this class used to take
(a one-label-per-row rail) is gone, not aliased -- the vertical navigation
rail is :class:`~motui.widgets.navlist.NavList`.  Pure component: the
host routes keys and cells, ``render`` only draws.  ``_last_width`` is
the width the last :meth:`render` painted at -- the geometry
:meth:`click` maps a column against; until the first paint it is 80, the
same convention as ``TextBuffer.last_width``.  :meth:`click` and the
pointer tier's :meth:`hover_at` resolve a cell through the one walk
:meth:`_hit` runs over this component's own last render, so the host
never resolves a tab itself: the leading and trailing padding, every
``" divider "`` gap, a cell past the last label and a truncating ``fit``
answer no tab.  The marking starts ``None``, so an un-hovered strip
renders exactly the bytes it always did.
"""

from __future__ import annotations

from typing import Iterable

from ..kernel.lines import Line, Segment
from ..kernel.style import Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed

__all__ = ["Tabs"]

#: The horizontal indicator's shape: the active label underlines its own
#: cells (D2).  It is composed onto the label whatever the colors say, so
#: "active" reads with the terminal's colors off.
UNDERLINE = Style(underline=True)


class Tabs(Themed):
    """A horizontal content strip: one row, a clamped, non-wrapping selection.

    ``tabs`` is a list of labels; ``index`` is the selected index (read-only
    property), clamped
    into ``0..len(tabs)-1`` on construction (a disabled index passed there
    is kept: see the module docstring) and on every later
    :meth:`select`/:meth:`move`.  ``disabled_items`` is an iterable of indices
    that render but refuse :meth:`click`/:meth:`select` and are stepped
    over by :meth:`move`; the ``disabled`` flag refuses every gesture.

    Styles resolve once, at construction, as explicit > theme field >
    ``DEFAULT_THEME``: ``active_style`` falls back to the theme's
    ``accent``, ``inactive_style``/``disabled_style`` to its ``dim``,
    ``hover_style`` to its ``hover``, ``divider_style`` to its ``muted``
    and ``indicator_style`` (the indicator's color) to its ``accent`` as
    well -- so the default active label is one hue, marked by the
    underline.  While ``focused`` is ``False`` the indicator composes the
    theme's ``muted`` (whole) instead of ``indicator_style``; the label's
    own style is untouched.

    ``_last_width`` is the width the last :meth:`render` painted at -- the
    geometry :meth:`click` maps a column against; until the first paint it
    is 80, the same convention as ``TextBuffer.last_width``.  The marking
    starts ``None``, so an un-hovered strip renders exactly the bytes it
    always did.
    """

    __slots__ = (
        "_active_style",
        "_disabled_items",
        "_disabled_style",
        "_divider_style",
        "_hover_index",
        "_hover_style",
        "_inactive_style",
        "_index",
        "_indicator_style",
        "_last_width",
        "_spans",
        "disabled",
        "divider",
        "focused",
        "hover",
        "tabs",
        "theme",
    )

    def __init__(
        self,
        tabs: list[str],
        *,
        index: int = 0,
        active_style: Style | None = None,
        inactive_style: Style | None = None,
        hover_style: Style | None = None,
        disabled_style: Style | None = None,
        divider: str = "\u2502",
        divider_style: Style | None = None,
        indicator_style: Style | None = None,
        disabled_items: Iterable[int] = (),
        disabled: bool = False,
        focused: bool = True,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.tabs = list(tabs)
        self.divider = divider
        self.focused = focused
        #: The pointer tier's flag; the label-level emphasis lives in
        #: ``_hover_index`` (:meth:`hover_at`).
        self.hover = False
        #: The whole strip refuses every selection gesture when disabled.
        self.disabled = disabled
        self._index = 0
        # The label the pointer is on, or ``None``; written by ``hover_at``,
        # read by ``render``.  ``None`` renders byte-for-byte what the strip
        # always did.
        self._hover_index: int | None = None
        # The indices that are visible but not selectable; a frozenset so
        # ``click``/``select``/``move`` are one membership test apiece.
        self._disabled_items = frozenset(disabled_items)
        # The width ``click`` maps against before the first paint (same 80 as
        # ``TextBuffer.last_width``); every render refreshes it.
        self._last_width = 80
        # The label spans of the last render -- ``(start, stop, index)`` per
        # label, in paint order -- so a hit reads the table instead of
        # re-rendering the strip (the P0).  ``None`` until the first paint:
        # the fallback builds the geometry once, without calling ``render``.
        self._spans: tuple[tuple[int, int, int], ...] | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._active_style = self._pick(active_style, "accent")
        self._inactive_style = self._pick(inactive_style, "dim")
        self._hover_style = self._pick(hover_style, "hover")
        self._disabled_style = self._pick(disabled_style, "dim")
        self._divider_style = self._pick(divider_style, "muted")
        self._indicator_style = self._pick(indicator_style, "accent")
        if self.tabs:
            # Clamped like every later request; the disabled rule belongs to
            # the verbs, not to this explicit constructor value.
            self._index = min(max(index, 0), len(self.tabs) - 1)

    @property
    def index(self) -> int:
        """The selected tab index, always inside the tab range.

        Read-only: :meth:`select` and :meth:`move` are the moving doors.
        """
        return self._index

    def select(self, index: int) -> bool:
        """Select tab ``index``, clamped into range; True when it changed.

        A ``disabled`` index is refused outright -- ``False``, nothing
        moved -- a disabled strip refuses every selection, and an empty
        strip answers ``False`` always.
        """
        if self.disabled or not self.tabs:
            return False
        target = min(max(index, 0), len(self.tabs) - 1)
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
        strip moves nowhere.  The answer is whether the selection changed.
        """
        if self.disabled or not self.tabs or delta == 0:
            return False
        step = 1 if delta > 0 else -1
        target = self._index
        for _ in range(abs(delta)):
            nxt = target + step
            while 0 <= nxt < len(self.tabs) and nxt in self._disabled_items:
                nxt += step
            if not 0 <= nxt < len(self.tabs):
                break  # clamped at the edge: the step has no enabled landing
            target = nxt
        return self.select(target)

    def click(self, row: int, col: int) -> bool:
        """Select the tab cell ``(row, col)`` covers; True on a hit.

        The cell resolves through :meth:`_hit`, the walk over this
        component's own last render: the column of the strip's one row, or
        no tab -- the leading and trailing padding, every ``" divider "``
        gap, a cell past the last label and a truncating ``fit`` all answer
        no tab, and so does any row but the first.  A hit on a **disabled**
        label (or on a disabled strip) answers ``False`` and changes
        nothing; a hit on an enabled one selects it -- even when it already
        was active -- and answers ``True``.
        """
        if self.disabled:
            return False
        index = self._hit(row, col)
        if index is None or index in self._disabled_items:
            return False
        self.select(index)
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the label under a cell; ``True`` when the marking changed.

        The pointer tier's label-level half: the cell resolves through
        :meth:`_hit`, the same walk :meth:`click` consumes, so the two can
        never disagree about which label a cell covers -- a cell no label
        covers, and a negative ``row`` (the pointer left), answer "no tab"
        and clear the marking.  Disabled labels are marked like any other
        (the band is the pointer's echo, not a selection).  The answer is
        whether the marked label changed; :meth:`render` merges the theme's
        ``hover`` over it.
        """
        target = None if row < 0 else self._hit(row, col)
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def _hit(self, row: int, col: int) -> int | None:
        """The tab index a cell covers on the strip's one row, or ``None``."""
        if row != 0:
            return None
        return self._tab_at(col)

    def _tab_at(self, col: int) -> int | None:
        """The tab index a column of the last render covers, or ``None``.

        The hit reads the **span table** the last :meth:`render` recorded --
        ``(start, stop, index)`` tuples in paint order, measured on the
        fitted row, so the leading and trailing padding, every
        ``" divider "`` gap and a truncating ``fit`` marker pass by exactly
        as they did when the table was walked per hit.  Before the first
        paint the table is built once at the default width (the old
        ``_last_width`` convention); after it, no render runs from a hit
        (the P0).
        """
        if not self.tabs:
            return None
        spans = self._spans
        if spans is None:
            _, spans = self._layout(self._last_width)
            self._spans = spans
        for start, stop, index in spans:
            if start <= col < stop:
                return index
        return None

    def revision(self) -> object:
        """The row cache's snapshot: every input the strip's row reads.

        In order: the labels (a tuple copy, so an in-place edit of the
        host's list moves it), the index, the disabled item set, the
        whole-control disabled flag, the index under the pointer,
        ``focused``, the divider string, the six resolved bands and the
        theme (read at render time for the unfocused indicator's ``muted``).
        The block-level ``hover`` flag paints nothing -- the row emphasis
        lives in ``_hover_index`` -- so it is deliberately out, and
        ``_last_width``/``_spans`` are outputs of ``render``, not inputs.

        The snapshot is plain immutable values and costs far less than a
        render; it is what lets a **sealed** strip's hover, focus flip or
        selection reach the screen (D4).
        """
        return (
            tuple(self.tabs),
            self._index,
            self._disabled_items,
            self.disabled,
            self._hover_index,
            self.focused,
            self.divider,
            self._active_style,
            self._inactive_style,
            self._hover_style,
            self._disabled_style,
            self._divider_style,
            self._indicator_style,
            self._theme,
        )

    def _layout(self, width: int) -> tuple[Line, tuple[tuple[int, int, int], ...]]:
        """The strip's fitted row and the label span table, in one build."""
        if not self.tabs:
            return Line(), ()
        # The focus rule, once per build: an unfocused strip drops the
        # indicator from accent to muted -- the label is never dimmed (D3).
        indicator = self._indicator_style if self.focused else self._theme.muted
        active_style = self._active_style.merge(indicator).merge(UNDERLINE)

        def style_of(index: int) -> Style:
            if index in self._disabled_items:
                style = self._disabled_style
            else:
                style = active_style if index == self._index else self._inactive_style
            return style.merge(self._hover_style) if index == self._hover_index else style

        segments: list[Segment] = [Segment(" ")]
        for i, name in enumerate(self.tabs):
            if i:
                segments.append(Segment(f" {self.divider} ", self._divider_style))
            segments.append(Segment(name, style_of(i)))
        segments.append(Segment(" "))
        line = Line(segments).fit(width)
        return line, self._spans_of(line)

    def _spans_of(self, line: Line) -> tuple[tuple[int, int, int], ...]:
        """The label spans of a fitted row, by the render's own segment walk.

        A label segment is recognized by its text matching the tab's name,
        so padding, dividers and a truncating ellipsis (which changes the
        segment's text) carry no span -- the walk the old per-hit
        ``_tab_at`` ran, now recorded once per render.
        """
        spans: list[tuple[int, int, int]] = []
        names = self.tabs
        x, seen = 0, 0
        for segment in line.segments:
            span = visible_width(segment.text)
            if seen < len(names) and segment.text == names[seen]:
                spans.append((x, x + span, seen))
                seen += 1
            x += span
        return tuple(spans)

    def render(self, width: int) -> list[Line]:
        """The strip's one row (or one empty row for an empty strip), ``fit``.

        The active label wears ``active_style`` merged with the indicator
        color -- ``indicator_style`` while focused, the theme's ``muted``
        whole while not -- plus the underline mark; every other label its
        own style (``disabled_style`` for a disabled index: the stricter
        state wins), then the hover band over the label under the pointer.
        The render records the branch's span table and width for the hits.
        """
        self._last_width = width  # the geometry ``click`` maps a column against
        line, spans = self._layout(width)
        self._spans = spans
        return [line]

    def __repr__(self) -> str:
        return f"Tabs({self.tabs!r}, index={self._index})"
