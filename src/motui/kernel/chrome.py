"""chrome: the kernel's pane chrome renderers -- the split's separator.

The frame budgets chrome; this module supplies the one reference chrome the
driver composes itself: the 1-cell divider between two split panes.  It is
kernel-side because both the driver (which registers it on a split) and the
kernel frame (which owns the mark it registers under and the geometry that
budgets it) must agree on it without the kernel importing the interaction
layer or the driver.

The separator reads two live values at paint time -- the frame's focus and
the host's theme -- so one chrome object serves every focus change and a
re-themed host, and it rides a retile without re-registration.
"""

from __future__ import annotations

from typing import Protocol

from .frame import Chrome, Frame, SEPARATOR_CHROME_NAME
from .lines import Line
from .style import Style
from .theme import Theme
from .viewport import ScreenLayout

__all__ = ["Separator"]


class _ChromeHost(Protocol):
    """The two live values the separator reads (the driver satisfies this)."""

    @property
    def frame(self) -> Frame: ...

    @property
    def theme(self) -> Theme: ...


class Separator:
    """The 1-cell divider between two split panes: chrome, themed by focus.

    The tmux convention (D4): the divider cell belongs to the pane before
    it -- registered as that pane's right-edge (vertical split) or
    bottom-edge (horizontal) chrome, so it is budgeted, never a gap -- and
    it reads in the host's theme: ``accent`` while either pane it divides
    is the focused one, ``border`` otherwise.  The style is read at paint
    time from the frame's focus and the host's theme, so one chrome object
    serves every focus change and follows a re-themed host, and it rides a
    retile without re-registration.  The chrome registers under
    :data:`~motui.kernel.frame.SEPARATOR_CHROME_NAME`, the mark a
    :meth:`~motui.kernel.frame.Pane.close` strips it by when the
    adjacency it divides goes.  ``TUI.split`` is the one registration path;
    a host wanting a different look registers its own chrome on the pane
    instead (``split(separator=False)``, then ``pane.add_chrome(...)``).
    """

    __slots__ = ("_after_id", "_before_id", "chrome", "_strip_cache", "_host")

    def __init__(
        self, host: _ChromeHost, before_id: str, after_id: str, edge: str
    ) -> None:
        self._host = host
        self._before_id = before_id
        self._after_id = after_id
        self.chrome = Chrome(edge, 1, self._paint, name=SEPARATOR_CHROME_NAME)
        # The last strip painted and the state it was painted from: the memo
        # of :meth:`_paint`, keyed by the edge, the length and the style.
        self._strip_cache: tuple[tuple, tuple[Line, ...]] | None = None

    def _accent(self) -> bool:
        """Whether either pane this divider separates is the focused one."""
        focused = self._host.frame.focused_pane
        return focused is not None and focused.id in (self._before_id, self._after_id)

    def _paint(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The strip: one accent or border cell per cell of the pane's edge.

        Edge-aware the way the paint protocol needs: a left/right divider is
        the pane's height in one-column rows, a bottom one one row of the
        pane's width -- either way the strip fills its band's own cells, so a
        horizontal split's divider never paints a one-column row over the
        content it was budgeted beside.

        The strip is the resolved style repeated, and the style is read
        here, every paint -- focus and the host's theme are live -- so
        the memo is keyed on where it landed besides the edge and the
        length: a focus change or a re-skin resolves a different style and
        rebuilds, and the frame invalidation that follows focus needs no
        separate signal.  A fresh list comes back every call, as it always
        has.
        """
        style = self._resolve()
        key = (self.chrome.edge, length, style)
        cached = self._strip_cache
        if cached is not None and cached[0] == key:
            return list(cached[1])
        if self.chrome.edge in ("left", "right"):
            strip = tuple(Line.filled(1, style) for _ in range(length))
        else:
            strip = (Line.filled(length, style),)
        self._strip_cache = (key, strip)
        return list(strip)

    def _resolve(self) -> Style:
        """The cell's style: the host theme's accent beside focus, else its border."""
        theme = self._host.theme
        return theme.accent if self._accent() else theme.border

    def __repr__(self) -> str:
        return f"Separator({self._before_id!r}|{self._after_id!r})"
