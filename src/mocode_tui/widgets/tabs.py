"""Tabs: the single-row tab strip component.

:class:`Tabs` renders ``" name \\u2502 name \\u2502 name "`` on exactly one row --
a leading and trailing space, the names separated by ``" \\u2502 "``.  The
active tab carries ``active_style`` (the theme's ``selection`` by default),
the rest ``inactive_style`` (plain by default); the divider is never styled.
``move``/``activate`` drive the selection, clamped into range and never
wrapping, and the row is ``fit`` to the painting width so a narrow screen
truncates with a ``\\u2026`` instead of wrapping.  Pure component: the host
routes keys, ``render`` only draws.
"""

from __future__ import annotations

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import DEFAULT_THEME, Theme

__all__ = ["Tabs"]


class Tabs:
    """A horizontal tab strip with a clamped, non-wrapping selection.

    ``tabs`` is a list of names; ``active`` is the selected index (clamped
    into ``0..len(tabs)-1`` on construction and on every later
    ``activate``/``move``).  Rendering always yields exactly one row -- an
    empty strip renders one empty row -- with one space of breathing room
    at both ends and the names joined by ``" " + divider + " "``.
    ``active_style`` defaults to the theme's ``selection``,
    ``inactive_style`` to plain (``NONE``).  Styles resolve once, at
    construction, as explicit > theme > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "_active",
        "_active_style",
        "_inactive_style",
        "active_style",
        "divider",
        "inactive_style",
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
        theme: Theme | None = None,
    ) -> None:
        self.tabs = list(tabs)
        self.active_style = active_style
        self.inactive_style = inactive_style
        self.divider = divider
        self.theme = theme
        self._active = 0
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        base = theme or DEFAULT_THEME
        self._active_style = active_style if active_style is not None else base.selection
        self._inactive_style = inactive_style if inactive_style is not None else NONE
        self.activate(active)

    @property
    def active(self) -> int:
        """The selected tab index, always inside the tab range."""
        return self._active

    def activate(self, index: int) -> bool:
        """Select tab ``index``, clamped into range; True when it changed."""
        if not self.tabs:
            return False
        target = min(max(index, 0), len(self.tabs) - 1)
        changed = target != self._active
        self._active = target
        return changed

    def move(self, delta: int) -> bool:
        """Move the selection by ``delta`` tabs, clamped (never wraps)."""
        return self.activate(self._active + delta)

    def render(self, width: int) -> list[Line]:
        if not self.tabs:
            return [Line()]
        segments: list[Segment] = [Segment(" ")]
        for i, name in enumerate(self.tabs):
            if i:
                segments.append(Segment(f" {self.divider} "))
            style = self._active_style if i == self._active else self._inactive_style
            segments.append(Segment(name, style))
        segments.append(Segment(" "))
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        return f"Tabs({self.tabs!r}, active={self._active})"
