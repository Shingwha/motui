"""Collapsible: a titled section that folds its body away.

One control, one row: the title leads with a state marker -- ``\u25be ``
while the section is open, ``\u25b8 `` while it is folded -- and the
:attr:`Collapsible.body` component's rows follow, inset by the marker's
width, only while :attr:`Collapsible.open` is ``True``.  The whole title
row is the control: :meth:`Collapsible.click` and
:meth:`Collapsible.activate` are the same flip, and each leaves the new
state pending for :meth:`Collapsible.take_result` (D15 -- a state plus
controller methods, no callbacks)::

    \u25be options
      Body line one
      Body line two

The body is any component (:class:`~motui.widgets.decor.Panel`'s child
protocol): it renders through the same ``render(c)`` -- at
``width`` minus the marker's columns, the width the inset leaves it -- so a
nested ``Panel``, a field or a layout works unchanged.  The component is a
:class:`~motui.kernel.document.Container`: a title-row cell answers ``None``
(the wrapper owns it) and an open body cell maps to
``(body, local_row, local_col)``, so a pointer tier can descend into the
folded content.  A click on a body row is **not** the section's control: it
answers ``False`` like any cell outside the title.

``hover_at`` is the pointer tier's row marking -- the title row merges
``surfaces.hover`` while the pointer is on it; ``focused`` is the focus flag
the focus tier sets (:class:`~motui.kernel.document.Focusable`), and a
focused title row additionally merges ``controls.focus``.
Both markings start off, so a plain collapsible renders
byte-for-byte what it always did.  The title band is ``content.accent``;
all three bands resolve at render time from ``styles`` (when given) or the
theme, and the body keeps whatever
styles its own construction resolved.  A disabled section refuses both
flip doors and renders its title in ``text.faint``.
"""

from __future__ import annotations

from ..kernel.document import Component, Revisioned
from ..kernel.glyphs import GLYPHS, Glyphs, seat
from ..kernel.cell import Line, Segment, Surface
from ..kernel.layout import Constraints
from ..kernel.text import visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["Collapsible"]


class Collapsible(Widget):
    """A titled section whose body folds away under its title row.

    ``open`` is a read-write attribute: :meth:`click` and :meth:`activate`
    flip it and leave the new value pending -- the host reads it once
    through :meth:`take_result` -- and a host may also set it
    directly (nothing renders stale: the body is re-rendered per call).
    ``body`` is a read-write attribute too, the component whose rows follow
    the title while open.

    The title row renders ``"\u25be title"`` / ``"\u25b8 title"`` in
    ``content.accent``; the pointer's row marking
    (:meth:`hover_at`) merges ``surfaces.hover`` over it and
    ``focused`` merges ``controls.focus``, so hover
    and focus are each plainly visible against the title.  ``render``
    answers the title row alone while closed, and the title plus the
    body's rows -- inset by the marker's width and ``fit`` to the painting
    width -- while open.  ``hover`` is the tier's block-level flag and
    paints nothing of its own (the row marking is the whole emphasis).

    The open body's inset rows are remembered per **body-row identity**
    (the body's rows by object, plus the width and the marker): a host that
    repaints an open section re-indents nothing, and a hit hands back the
    very same rows by copy (render-cost W4).  The title row is one row --
    it re-renders every call, so hover and focus markings never go stale,
    and the body is left to its own memory.
    """

    __slots__ = (
        "_body_count",
        "_body_memo",
        "_marked",
        "_pending",
        "body",
        "disabled",
        "glyphs",
        "open",
        "title",
    )

    def __init__(
        self,
        title: str,
        body: Component,
        *,
        open: bool = True,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.title = title
        self.body = body
        self.open = open
        self.glyphs = glyphs
        #: Refuse both flip doors and paint the disabled title band.
        self.disabled = disabled
        # The title row is marked while the pointer is on it; written by
        # ``hover_at``, read by ``render``.  Unmarked renders byte-for-byte
        # the same rows.
        self._marked = False
        #: The pending toggle: written by ``click`` / ``activate`` (the new
        #: ``open`` state), read once through :meth:`take_result`.
        self._pending: bool | None = None
        #: The body memo: ``(body-row identity tuple, width, marker indent)``
        #: -> ``(inset rows, the body rows that key it)`` -- ``None`` until
        #: the first open render.
        self._body_memo: tuple[tuple, list[Line], list[Line]] | None = None
        #: The number of body rows the last render produced (the geometry
        #: :meth:`child_at` maps through; 0 while closed).
        self._body_count = 0

    # -- the toggle --------------------------------------------------------------

    def click(self, row: int, col: int) -> bool:
        """Flip :attr:`open` when the click lands on the title row.

        ``row 0`` is the title row -- the control -- and any other ``row``
        (a body row, a cell past the render) answers ``False``: the body is
        the body's own business.  ``col`` is ignored: the title row owns
        the whole width.  A hit flips the state and leaves it pending (even
        when the state already read that way -- a hit is a hit, and the
        flip is deterministic).  A disabled section refuses the click.
        """
        if row != 0:
            return False
        return self.activate()

    def activate(self) -> bool:
        """Flip :attr:`open` and leave the new state pending; ``False`` when disabled."""
        if self.disabled:
            return False
        self.open = not self.open
        self._pending = self.open
        return True

    def take_result(self) -> bool | None:
        """Read the pending flip (the new ``open`` state) once and clear it."""
        value = self._pending
        self._pending = None
        return value

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """Map a cell to the body while open; the title belongs to the wrapper.

        The geometry is the last :meth:`render`'s: row 0 is the title row
        (the wrapper owns every cell of it) and the following
        :attr:`_body_count` rows are the body's own rows, inset by the
        marker's width.  A closed section maps nothing; a cell past the
        body maps nothing.
        """
        if not self.open or row <= 0:
            return None
        local = row - 1
        if local >= self._body_count:
            return None
        indent = visible_width(seat(self.glyphs.fold_open))
        return self.body, local, max(0, col - indent)

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the title row under a cell; ``True`` when the marking changed.

        The pointer tier's row-level half: ``row 0`` is the title row, and
        every other row -- a body row, a negative one (the pointer left) --
        clears the marking.  ``col`` is ignored.  The answer is whether the
        marking changed, so a motion inside the row answers ``False``
        (nothing to repaint); :meth:`render` merges ``surfaces.hover``
        over the marked title row.
        """
        target = row == 0
        changed = target != self._marked
        self._marked = target
        return changed

    # -- rendering ---------------------------------------------------------------

    def revision(self) -> object:
        """The row cache's snapshot: every input ``render`` reads.

        The ``open`` state (which rows exist), the row mark (``_marked``),
        ``focused``, ``title``, the theme/styles pair the three bands
        resolve from and the body's own snapshot are the title
        row's whole input set.  The body's rows are the other row input:

        * when ``body`` is :class:`~motui.kernel.document.Revisioned` and
          answers a snapshot, that ``revision()`` is used directly -- the
          same value the body would hand its own block, so a streamed
          assignment inside the body moves the key before any render;
        * otherwise (a body outside the protocol, or one whose snapshot is
          ``None``) the fallback is the identity tuple of the body rows the
          last *open* render remembered -- the memo the component already
          keeps.  Such a body either answers the same row objects (stable
          identity, safe hit) or rebuilds them every call (a miss per
          frame, never a stale row).

        While closed the body contributes its last memo unchanged; the
        ``open`` flag already moves the snapshot, so the title-only row is
        what renders.  The pending result is a one-shot value, not a row
        input, and the block-level ``hover`` flag paints nothing
        (``_marked`` does); ``disabled`` and its band are row inputs.
        """
        body = self.body
        body_snapshot: object = None
        if isinstance(body, Revisioned):
            snapshot = body.revision()
            if snapshot is not None:
                body_snapshot = ("revision", snapshot)
        if body_snapshot is None:
            rows = self._body_memo[2] if self._body_memo is not None else []
            body_snapshot = ("rows", tuple(map(id, rows)))
        return (
            self.open,
            self._marked,
            self.focused,
            self.disabled,
            self.title,
            self.glyphs,
            self.theme,
            self.styles,
            body_snapshot,
        )

    def render(self, c: Constraints) -> Surface:
        """The title row and, while open, the body's inset rows.

        The body renders at the inner width (``width`` minus the marker's
        columns) and the memo
        key stays the width alone -- a smaller ``max_height`` truncates the
        assembled rows after the memo is consulted, never repaints the body.
        ``_body_count`` keeps the untruncated body geometry :meth:`child_at`
        maps through (the W2a container precedent).  The answer is
        :meth:`~motui.kernel.cell.Surface.clipped`, not padded: short rows
        keep their natural width, so the painted bytes are unchanged.
        """
        width = c.width
        if self.disabled:
            style = self.group("text").faint
        else:
            style = self.group("content").accent
            if self._marked:
                style = style.merge(self.group("surfaces").hover)
            if self.focused:
                style = style.merge(self.group("controls").focus)
        mark = seat(
            self.glyphs.fold_open if self.open else self.glyphs.fold_closed
        )
        out = [Line((Segment(mark, style), Segment(self.title, style))).fit(width)]
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
                    Line((Segment(" " * indent), *row.segments)).fit(width)
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
