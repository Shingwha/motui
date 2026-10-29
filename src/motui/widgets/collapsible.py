"""Collapsible: a titled section that folds its body away.

The title row leads with a fold marker; while ``open`` the body renders
inset under it.  Clicking or activating the title flips ``open`` and leaves
it pending.  ``child_at`` descends into an open body.
"""

from __future__ import annotations

from ..kernel.cell import Line, Segment, Surface
from ..kernel.document import Component
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, seat
from ..kernel.layout import Constraints
from ..kernel.text import WrapMode, visible_width
from ..kernel.theme import Styles, Theme
from .base import ActionWidget

__all__ = ["Collapsible"]


class Collapsible(ActionWidget):
    """A titled section whose body folds away under its title row.

    ``open`` is assignable; ``activate``/``toggle`` flip it and emit the new
    value, while a direct assignment just repaints.  The title draws the
    marker and title in ``content.accent`` with hover/focus overlays; the
    body renders inset by the marker while open.  Open body rows are
    memoized on identity; the title row re-renders every call.
    """

    __slots__ = (
        "_body_count",
        "_body_memo",
        "_marked",
        "body",
        "glyphs",
        "open",
        "title",
    )

    #: The title row is a focus target, the pointer marks it, a click or the
    #: activation verb folds it.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    def __init__(
        self,
        body: Component,
        *,
        title: str = "",
        open: bool = True,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(disabled=disabled, theme=theme, styles=styles)
        self.title = title
        self.body = body
        # The explicit tree: the folded content is this section's child, and
        # a widget body gets its ``parent`` pointed back here.
        self.children = [body]
        self.open = open
        self.glyphs = glyphs
        # The title row is marked while the pointer is on it; written by
        # ``on_hover``, read by ``render``.  Unmarked renders byte-for-byte
        # the same rows.
        self._marked = False
        #: The body memo: ``(body-row identity tuple, width, marker indent)``
        #: -> ``(inset rows, the body rows that key it)`` -- ``None`` until
        #: the first open render.
        self._body_memo: tuple[tuple, list[Line], list[Line]] | None = None
        #: The number of body rows the last render produced (the geometry
        #: :meth:`child_at` maps through; 0 while closed).
        self._body_count = 0

    # -- the toggle --------------------------------------------------------------

    def on_click(self, pos: Pos) -> bool:
        """Flip ``open`` when the click lands on the title row (row 0); ``pos.x`` is ignored."""
        if pos.y != 0:
            return False
        return self.activate()

    def activate(self) -> bool:
        """Fold or unfold the section; the same flip as :meth:`toggle`."""
        return self.toggle()

    def toggle(self) -> bool:
        """Flip :attr:`open` and leave the new state pending; disabled refuses."""
        if self.disabled:
            return False
        self.open = not self.open
        self._emit(self.open)
        return True

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a cell to the open body; the title row belongs to the wrapper.

        Body cells are inset by the marker width; a closed section maps
        nothing.
        """
        if not self.open or row <= 0:
            return None
        local = row - 1
        if local >= self._body_count:
            return None
        indent = visible_width(seat(self.glyphs.fold_open))
        return self.body, local, max(0, col - indent)

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the title row under the pointer; True when that changed."""
        target = pos is not None and pos.y == 0
        changed = target != self._marked
        if changed:
            self._marked = target
            self.touch()
        return changed

    # -- rendering ---------------------------------------------------------------

    def render(self, c: Constraints) -> Surface:
        """The title row and, while open, the body's inset rows."""
        width = c.width
        style = self.group("content").accent
        if self.disabled:
            style = style.merge(self.group("text").faint).merge(
                self.group("controls").overlay(disabled=True)
            )
        else:
            if self._marked:
                style = style.merge(self.group("surfaces").hover)
            style = style.merge(self.group("controls").overlay(focused=self.focused))
        mark = seat(
            self.glyphs.fold_open if self.open else self.glyphs.fold_closed
        )
        out = [
            Line((Segment(mark, style), Segment(self.title, style))).clip(
                WrapMode.ELLIPSIS, width
            )
        ]
        if self.open:
            indent = visible_width(mark)
            body_rows = list(self.body.render(Constraints(width=max(0, width - indent))))
            self._body_count = len(body_rows)
            key = (tuple(map(id, body_rows)), width, indent)
            memo = self._body_memo
            if memo is not None and memo[0] == key:
                out.extend(memo[1])
            else:
                rows = [
                    Line((Segment(" " * indent), *row.segments)).clip(WrapMode.ELLIPSIS, width)
                    for row in body_rows
                ]
                self._body_memo = (key, rows, body_rows)
                out.extend(rows)
        else:
            self._body_count = 0
        if c.max_height is not None:
            out = out[: c.max_height]
        return Surface.clipped(out, c.width)

    def __repr__(self) -> str:
        return f"Collapsible({self.title!r}, open={self.open}, focused={self.focused})"
