"""Tabs: the tab strip component -- one row, or one row per label.

:class:`Tabs` renders in one of two axes.  The default ``"horizontal"``
strip paints ``" name \\u2502 name \\u2502 name "`` on exactly one row -- a
leading and trailing space, the names separated by ``" \\u2502 "``.  The
``"vertical"`` strip paints one label per row, left-aligned, no divider at
all (a rail: the row is the label).  The active tab carries
``active_style`` (the theme's ``selection`` by default), the rest
``inactive_style`` (plain by default); the horizontal divider is never
styled.  ``focused`` is the focus flag the focus tier sets: an unfocused
strip renders its active label in ``active_style.merge(theme.dim)`` (the
hue stays, the weight drops).  ``move``/``select`` drive the selection,
clamped into range and never wrapping, and every row is ``fit`` to the
painting width so a narrow screen truncates with a ``\\u2026`` instead of
wrapping.  Pure component: the host routes keys and cells, ``render`` only
draws; :meth:`Tabs.click` resolves the cell's own axis -- the column of the
one horizontal row, or the row of the vertical stack -- against this
component's own last render, so the host never resolves a tab itself.
"""

from __future__ import annotations

from ..kernel.lines import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed

__all__ = ["Tabs"]


class Tabs(Themed):
    """A tab strip with a clamped, non-wrapping selection, on either axis.

    ``tabs`` is a list of names; ``active`` is the selected index (clamped
    into ``0..len(tabs)-1`` on construction and on every later
    ``select``/``move``).  ``orientation`` is ``"horizontal"`` (the
    default: exactly one row with one space of breathing room at both ends
    and the names joined by ``" " + divider + " "``) or ``"vertical"``
    (one label per row, left-aligned, the row fitted to the width); any
    other value raises ``ValueError`` at construction.  An empty strip
    renders one empty row on either axis.
    ``active_style`` defaults to the theme's ``selection``,
    ``inactive_style`` to plain (``NONE``).  Styles resolve once, at
    construction, as explicit > theme > ``DEFAULT_THEME``, and the rules
    are the same on both axes: the active label in ``active_style``, the
    rest in ``inactive_style``, the label under the pointer merging the
    theme's ``hover``.

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.block.Focusable`): while it is ``True`` the
    active label renders in ``active_style``; while it is ``False`` that
    style is merged with the theme's ``dim`` -- the selection stays
    legible but loses weight, and the inactive labels and the divider
    render unchanged.

    ``_last_width`` is the width the last :meth:`render` painted at -- the
    geometry the horizontal :meth:`click` maps a column against; until the
    first paint it is 80, the same convention as ``TextBuffer.last_width``.
    :meth:`click` and the pointer tier's :meth:`hover_at` resolve a cell
    through the one walk :meth:`_hit` runs: a column of the horizontal
    strip's single row, or a row of the vertical stack (where the row is
    the label's whole cell and the column is ignored).  The marking starts
    ``None``, so an un-hovered strip renders exactly the bytes it always
    did.
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
        "orientation",
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
        orientation: str = "horizontal",
    ) -> None:
        super().__init__(theme)
        if orientation not in ("horizontal", "vertical"):
            raise ValueError(
                f"orientation must be 'horizontal' or 'vertical', got {orientation!r}"
            )
        self.theme = theme
        self.tabs = list(tabs)
        self.divider = divider
        self.orientation = orientation
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
        """Select the tab cell ``(row, col)`` covers; True on a hit.

        The cell resolves through :meth:`_hit`, the walk over this
        component's own last render: the column of the one horizontal row
        -- where the leading and trailing padding, every ``" divider "``
        gap, a cell past the last label and a truncating ``fit`` answer no
        tab -- or the row of the vertical stack, where the row *is* the
        label's cell (its column is ignored).  A cell outside the strip --
        an empty strip, a row the vertical stack does not hold, any row but
        the first on the horizontal axis -- answers ``False``.  A hit
        selects that tab -- even when it already was active -- and answers
        ``True``.
        """
        index = self._hit(row, col)
        if index is None:
            return False
        self.select(index)
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the label under a cell; ``True`` when the marking changed.

        The pointer tier's label-level half (D3): the cell resolves through
        :meth:`_hit`, the same walk :meth:`click` consumes, so the two can
        never disagree about which label a cell covers -- a cell no label
        covers, and a negative ``row`` (the pointer left), answer "no tab"
        and clear the marking.  The answer is whether the marked label
        changed; :meth:`render` merges the theme's ``hover`` over it.
        """
        target = None if row < 0 else self._hit(row, col)
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def _hit(self, row: int, col: int) -> int | None:
        """The tab index a cell covers on this strip's own axis, or ``None``.

        The axis halves: the vertical stack resolves the *row* (a row
        inside the stack is that label's cell whatever the column), and the
        horizontal row resolves the *column* through :meth:`_tab_at`.
        """
        if self.orientation == "vertical":
            return row if 0 <= row < len(self.tabs) else None
        if row != 0:
            return None
        return self._tab_at(col)

    def _tab_at(self, col: int) -> int | None:
        """The tab index a column of the last horizontal render covers, or ``None``.

        The walk the horizontal :meth:`_hit` runs: the row is re-resolved
        from this component's own last render
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

        def style_of(index: int) -> Style:
            style = active_style if index == self._active else self._inactive_style
            return style.merge(self._hover_style) if index == self._hover_index else style

        if self.orientation == "vertical":
            # One label per row, left-aligned; the row is the label's cell.
            return [Line([Segment(name, style_of(i))]).fit(width) for i, name in enumerate(self.tabs)]
        segments: list[Segment] = [Segment(" ")]
        for i, name in enumerate(self.tabs):
            if i:
                segments.append(Segment(f" {self.divider} "))
            segments.append(Segment(name, style_of(i)))
        segments.append(Segment(" "))
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        return f"Tabs({self.tabs!r}, active={self._active})"
