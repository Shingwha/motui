"""Tabs: the single-row tab strip component.

:class:`Tabs` renders ``" name \\u2502 name \\u2502 name "`` on exactly one row --
a leading and trailing space, the names separated by ``" \\u2502 "``.  The
active tab carries ``active_style`` (the theme's ``selection`` by default),
the rest ``inactive_style`` (plain by default); the divider is never styled.
``focused`` is the focus flag the focus tier sets: an unfocused strip
renders its active label in ``active_style.merge(theme.dim)`` (the hue
stays, the weight drops).  ``move``/``select`` drive the selection, clamped
into range and never wrapping, and the row is ``fit`` to the painting width
so a narrow screen truncates with a ``\\u2026`` instead of wrapping.  Pure
component: the host routes keys and cells, ``render`` only draws;
:meth:`Tabs.click` resolves the cell's column against this component's own
last render, so the host never resolves a tab itself.
"""

from __future__ import annotations

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import visible_width
from ..core.theme import Theme, Themed

__all__ = ["Tabs"]


class Tabs(Themed):
    """A horizontal tab strip with a clamped, non-wrapping selection.

    ``tabs`` is a list of names; ``active`` is the selected index (clamped
    into ``0..len(tabs)-1`` on construction and on every later
    ``select``/``move``).  Rendering always yields exactly one row -- an
    empty strip renders one empty row -- with one space of breathing room
    at both ends and the names joined by ``" " + divider + " "``.
    ``active_style`` defaults to the theme's ``selection``,
    ``inactive_style`` to plain (``NONE``).  Styles resolve once, at
    construction, as explicit > theme > ``DEFAULT_THEME``.

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.core.block.Focusable`): while it is ``True`` the
    active label renders in ``active_style``; while it is ``False`` that
    style is merged with the theme's ``dim`` -- the selection stays
    legible but loses weight, and the inactive labels and the divider
    render unchanged.

    ``_last_width`` is the width the last :meth:`render` painted at -- the
    geometry :meth:`click` maps a column against; until the first paint it
    is 80, the same convention as ``TextBuffer.last_width``.  The pointer
    tier's :meth:`hover_at` resolves a cell through the same arithmetic
    (:meth:`_tab_at`) and the marked label merges the theme's ``hover`` --
    the marking starts ``None``, so an un-hovered strip renders exactly the
    bytes it always did.
    """

    __slots__ = (
        "_active",
        "_active_style",
        "_dim",
        "_hover_index",
        "_hover_style",
        "_inactive_style",
        "_last_width",
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
        active: int = 0,
        active_style: Style | None = None,
        inactive_style: Style | None = None,
        divider: str = "\u2502",
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
        self._active = 0
        # The label the pointer is on, or ``None``; written by ``hover_at``,
        # read by ``render``.  ``None`` renders byte-for-byte what the strip
        # always did.
        self._hover_index: int | None = None
        # The width ``click`` maps against before the first paint (same 80 as
        # ``TextBuffer.last_width``); every render refreshes it.
        self._last_width = 80
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._active_style = self._pick(active_style, "selection")
        self._inactive_style = inactive_style if inactive_style is not None else NONE
        self._dim = self._pick(None, "dim")
        self._hover_style = self._pick(None, "hover")
        self.select(active)

    @property
    def active(self) -> int:
        """The selected tab index, always inside the tab range."""
        return self._active

    def select(self, index: int) -> bool:
        """Select tab ``index``, clamped into range; True when it changed."""
        if not self.tabs:
            return False
        target = min(max(index, 0), len(self.tabs) - 1)
        changed = target != self._active
        self._active = target
        return changed

    def move(self, delta: int) -> bool:
        """Move the selection by ``delta`` tabs, clamped (never wraps)."""
        return self.select(self._active + delta)

    def click(self, row: int, col: int) -> bool:
        """Select the tab whose label covers cell ``(row, col)``; True on a hit.

        The strip paints exactly one row, so any other ``row`` -- and every
        cell of an empty strip -- answers ``False``.  ``col`` resolves
        through :meth:`_tab_at`, the walk over this component's own last
        render: a cell on the leading or trailing padding, on a
        ``" divider "`` gap, past the last label, or on a truncating ``fit``
        answers no tab and ``False``.  A hit selects that tab -- even when
        it already was active -- and answers ``True``.
        """
        if row != 0:
            return False
        index = self._tab_at(col)
        if index is None:
            return False
        self.select(index)
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the label under a cell; ``True`` when the marking changed.

        The pointer tier's label-level half (D3): the strip paints one row,
        so any other ``row`` -- and every cell no label covers -- answers
        "no tab" and clears the marking; a negative ``row`` clears it too
        (the pointer left).  ``col`` resolves through :meth:`_tab_at`, the
        same arithmetic :meth:`click` consumes, so the two can never
        disagree about which label a cell covers.  The answer is whether
        the marked label changed; :meth:`render` merges the theme's
        ``hover`` over it.
        """
        target = None if row < 0 else (self._tab_at(col) if row == 0 else None)
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def _tab_at(self, col: int) -> int | None:
        """The tab index a column of the last render's row covers, or ``None``.

        The walk :meth:`click` and :meth:`hover_at` share: the row is
        re-resolved from this component's own last render
        (``self.render(self._last_width)``), its segments are walked in
        paint order and their ``visible_width`` accumulated until the cell
        falls inside one.  A label segment is recognized by its text
        matching the tab's name, so the leading and trailing padding, every
        ``" divider "`` gap and a truncating ``fit`` marker pass by -- and a
        cell on any of them answers ``None``.
        """
        if not self.tabs:
            return None
        names = self.tabs
        x, seen = 0, 0
        for segment in self.render(self._last_width)[0].segments:
            span = visible_width(segment.text)
            if seen < len(names) and segment.text == names[seen]:
                if x <= col < x + span:
                    return seen
                seen += 1
            x += span
        return None

    def render(self, width: int) -> list[Line]:
        self._last_width = width  # the geometry ``click`` maps a column against
        if not self.tabs:
            return [Line()]
        # The focus rule, once per render: an unfocused strip dims its active
        # label (the inactive labels and the divider are untouched).
        active_style = self._active_style
        if not self.focused:
            active_style = active_style.merge(self._dim)
        segments: list[Segment] = [Segment(" ")]
        for i, name in enumerate(self.tabs):
            if i:
                segments.append(Segment(f" {self.divider} "))
            style = active_style if i == self._active else self._inactive_style
            if i == self._hover_index:
                style = style.merge(self._hover_style)
            segments.append(Segment(name, style))
        segments.append(Segment(" "))
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        return f"Tabs({self.tabs!r}, active={self._active})"
