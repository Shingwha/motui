"""Collapsible: a titled section that folds its body away.

One control, one row: the title leads with a state marker -- ``\u25be ``
while the section is open, ``\u25b8 `` while it is folded -- and the
:attr:`Collapsible.body` component's rows follow, inset by the marker's
width, only while :attr:`Collapsible.open` is ``True``.  The whole title
row is the control: :meth:`Collapsible.click` and
:meth:`Collapsible.activate` are the same flip, and each writes the new
state into :attr:`Collapsible.chosen` for the host to read once and reset
(D15 -- a state plus controller methods, no callbacks)::

    \u25be options
      Body line one
      Body line two

The body is any component (:class:`~motui.widgets.decor.Panel`'s child
protocol): it renders through the same ``render(width)`` -- at
``width`` minus the marker's columns, the width the inset leaves it -- so a
nested ``Panel``, a field or a layout works unchanged.  A click on a body
row is **not** the section's: the container only owns its title row, and a
row past it answers ``False`` like any cell outside the control.

``hover_at`` is the pointer tier's row marking -- the title row merges the
theme's ``hover`` while the pointer is on it; ``focused`` is the focus flag
the focus tier sets (:class:`~motui.core.block.Focusable`), and a
focused title row additionally merges ``focus_style`` (the theme's
``cursor``).  Both markings start off, so a plain collapsible renders
byte-for-byte what it always did.  Styles resolve once, at construction,
as explicit > theme field > ``DEFAULT_THEME``; the body keeps whatever
styles its own construction resolved.
"""

from __future__ import annotations

from ..core.block import Component
from ..core.lines import Line, Segment
from ..core.style import Style
from ..core.text import visible_width
from ..core.theme import Theme, Themed

__all__ = ["Collapsible"]

#: The open marker: the section's body is showing.
OPEN_MARK = "\u25be "

#: The closed marker: the body is folded away.
CLOSED_MARK = "\u25b8 "


class Collapsible(Themed):
    """A titled section whose body folds away under its title row.

    ``open`` is a read-write attribute: :meth:`click` and :meth:`activate`
    flip it and mirror the new value into :attr:`chosen` -- the host reads
    ``chosen`` once and resets it to ``None`` -- and a host may also set it
    directly (nothing renders stale: the body is re-rendered per call).
    ``body`` is a read-write attribute too, the component whose rows follow
    the title while open.

    The title row renders ``"\u25be title"`` / ``"\u25b8 title"`` in
    ``title_style`` (the theme's ``accent``); the pointer's row marking
    (:meth:`hover_at`) merges the theme's ``hover`` over it and
    ``focused`` merges ``focus_style`` (the theme's ``cursor``), so hover
    and focus are each plainly visible against the title.  ``render``
    answers the title row alone while closed, and the title plus the
    body's rows -- inset by the marker's width and ``fit`` to the painting
    width -- while open.  ``hover`` is the tier's block-level flag and
    paints nothing of its own (the row marking is the whole emphasis).
    """

    __slots__ = (
        "_focus_style",
        "_hover_style",
        "_marked",
        "_title_style",
        "body",
        "chosen",
        "focused",
        "hover",
        "open",
        "theme",
        "title",
    )

    def __init__(
        self,
        title: str,
        body: Component,
        *,
        open: bool = True,
        title_style: Style | None = None,
        hover_style: Style | None = None,
        focus_style: Style | None = None,
        theme: Theme | None = None,
        focused: bool = False,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.title = title
        self.body = body
        self.open = open
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_marked`` (:meth:`hover_at`).
        self.hover = False
        # The title row is marked while the pointer is on it; written by
        # ``hover_at``, read by ``render``.  Unmarked renders byte-for-byte
        # the same rows.
        self._marked = False
        #: The pending toggle: written by ``click`` / ``activate`` (the new
        #: ``open`` state), read once by the host, which resets it.
        self.chosen: bool | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._title_style = self._pick(title_style, "accent")
        self._hover_style = self._pick(hover_style, "hover")
        self._focus_style = self._pick(focus_style, "cursor")

    # -- the toggle --------------------------------------------------------------

    def click(self, row: int, col: int) -> bool:
        """Flip :attr:`open` when the click lands on the title row.

        ``row 0`` is the title row -- the control -- and any other ``row``
        (a body row, a cell past the render) answers ``False``: the body is
        the body's own business.  ``col`` is ignored: the title row owns
        the whole width.  A hit flips the state and mirrors it into
        :attr:`chosen` (even when the state already read that way -- a hit
        is a hit, and the flip is deterministic).
        """
        if row != 0:
            return False
        return self.activate()

    def activate(self) -> bool:
        """Flip :attr:`open`, mirror the new state into :attr:`chosen`; always ``True``."""
        self.open = not self.open
        self.chosen = self.open
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the title row under a cell; ``True`` when the marking changed.

        The pointer tier's row-level half: ``row 0`` is the title row, and
        every other row -- a body row, a negative one (the pointer left) --
        clears the marking.  ``col`` is ignored.  The answer is whether the
        marking changed, so a motion inside the row answers ``False``
        (nothing to repaint); :meth:`render` merges the theme's ``hover``
        over the marked title row.
        """
        target = row == 0
        changed = target != self._marked
        self._marked = target
        return changed

    # -- rendering ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        style = self._title_style
        if self._marked:
            style = style.merge(self._hover_style)
        if self.focused:
            style = style.merge(self._focus_style)
        mark = OPEN_MARK if self.open else CLOSED_MARK
        out = [Line((Segment(mark, style), Segment(self.title, style))).fit(width)]
        if self.open:
            indent = visible_width(mark)
            for row in self.body.render(max(0, width - indent)):
                out.append(Line((Segment(" " * indent), *row.segments)).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Collapsible({self.title!r}, open={self.open}, focused={self.focused})"
