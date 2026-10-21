"""Decor components: :class:`Divider` and :class:`Panel`.

Framing furniture that marks or wraps content rows.  ``Divider`` renders a
horizontal rule capped at ``max_width`` columns when given (full ``width``
otherwise; optionally embedding a label -- the ``── label ───`` inline status
row) and ``Panel`` a boxed border around any child component, padding it back
to the inner width so the grid stays aligned -- or, with ``frame=False``, the
same panel without the box (see :class:`Panel`).  The row-shaped furniture --
the one-row ``Notice`` with it -- lives beside this module, in
:mod:`motui.widgets.rows`.  Only the kernel is imported: layout is computed
here, never drawn.  The divider / panel border color comes from the
:class:`~motui.core.theme.Theme` the component was built with.
"""

from __future__ import annotations

from ..core.block import Component, Revisioned
from ..core.glyphs import GLYPHS, Border, Glyphs
from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import ellipsize_tail, visible_width
from ..core.theme import Theme, Themed

__all__ = ["Divider", "Panel"]


def _child_key(child: object) -> object:
    """The cache key of a child: its identity plus its revision when it has one.

    A swapped child must move the parent's snapshot even when the new child
    renders equal rows; a mutable child's own ``revision`` is what carries
    its in-place changes through a parent that is otherwise unchanged.
    """
    if isinstance(child, Revisioned):
        return (id(child), child.revision())
    return id(child)


def _labelled_rule(
    char: str,
    lead: int,
    label: str,
    label_style: Style,
    style: Style,
    span: int,
) -> list[Segment]:
    """The segments of a labelled rule over ``span`` columns.

    ``char * lead``, a space, the label, a space, then the closing run of
    ``char`` -- ``char * fill``, floored so the row never exceeds ``span``
    columns.  The label is expected to fit already (each caller ellipsizes
    it against the span it has room for); an empty label degrades to the
    pure rule, and ``span <= 0`` -- or a zero-width ``char`` -- yields no
    segments.  :class:`Divider` renders the segments as built;
    :class:`Panel` fuses them into its one-segment border row.
    """
    char_w = visible_width(char)
    if span <= 0 or char_w <= 0:
        return []
    if not label:
        count = span // char_w
        return [Segment(char * count, style)] if count else []
    used = lead * char_w + 2 + visible_width(label)
    fill = max(0, (span - used) // char_w)
    segments = [
        Segment(char * lead, style),
        Segment(" ", style),
        Segment(label, label_style),
        Segment(" ", style),
    ]
    if fill:
        segments.append(Segment(char * fill, style))
    return segments


class Divider(Themed):
    """A horizontal rule built from one repeated character.

    With a ``label`` the rule embeds it: ``char * 2 + " " + label + " " +
    char * fill`` spanning ``max(0, min(width, max_width))`` columns -- the
    shape of an inline working-status line parked on an input box's top
    border.  ``max_width`` caps that span (``None``, the default,
    spans the whole ``width``): the rule comes out left-aligned and the
    shorter row is legal, since a painter clears the tail past it.  The
    label carries ``label_style``; the rules and the two spaces carry
    ``style`` (the theme's ``borders.base`` when none is given).  A label that
    does not fit the capped width minus 4 is truncated with
    :func:`~motui.core.text.ellipsize_tail`; when nothing survives
    the truncation the row degrades to the pure rule, exactly like an empty
    ``label``.  ``label`` / ``label_style`` / ``max_width`` are plain
    mutable attributes, so a host can re-label one divider in place (the
    demo's working spinner does), re-cap it, and invalidate.
    """

    __slots__ = (
        "char",
        "glyphs",
        "label",
        "label_style",
        "max_width",
        "style",
        "theme",
    )

    def __init__(
        self,
        *,
        char: str | None = None,
        style: Style | None = None,
        label: str = "",
        label_style: Style | None = None,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        max_width: int | None = None,
    ) -> None:
        super().__init__(theme)
        self.glyphs = glyphs
        self.char = glyphs.horizontal_rule if char is None else char
        self.style = style
        self.label = label
        self.label_style = label_style
        self.theme = theme
        self.max_width = max_width
        # ``style`` / ``label_style`` are plain (mutable) attributes -- a
        # host re-labels and re-styles one divider in place -- so the theme
        # fallback resolves against the stored theme at render time.

    def revision(self) -> object:
        """The :class:`~motui.core.block.Revisioned` snapshot.

        Every mutable input :meth:`render` reads, as values: the rule glyph,
        the explicit styles (``None`` included -- the render resolves the
        theme fallback itself), the label, the cap and the stored theme.
        """
        return (
            self.char,
            self.style,
            self.label,
            self.label_style,
            self.max_width,
            self._theme,
        )

    def render(self, width: int) -> list[Line]:
        style = self.pick(self.style, self._theme.borders.base)
        label_style = self.pick(self.label_style, self._theme.text.muted)
        if width <= 0 or visible_width(self.char) <= 0:
            return [Line()]
        paint = width if self.max_width is None else max(0, min(width, self.max_width))
        label = ellipsize_tail(self.label, paint - 4) if self.label else ""
        segments = _labelled_rule(self.char, 2, label, label_style, style, paint)
        return [Line(segments).fit(width)]

    def __repr__(self) -> str:
        if self.label:
            return f"Divider(char={self.char!r}, label={self.label!r})"
        return f"Divider(char={self.char!r})"


class Panel(Themed):
    """A child component inside a single-line box border.

    The child renders at ``width - 4`` (two border columns plus one padding
    column per side); its rows are padded back to the inner width so the
    right border stays aligned.  ``title`` is embedded in the top border
    when it fits (``width >= 6``); below ``width < 4`` the frame degrades to
    the bare child, still ``fit`` to ``width``.  ``style`` is the border
    color (the theme's ``borders.base`` when none is given).  The container
    implements ``Container.child_at`` over the geometry of its last render:
    only the content cells map to the child -- the border rows and the
    border/padding columns belong to the ``Panel`` itself.

    **``frame=False`` drops the box and keeps the panel.**  The child
    renders at ``width - 2`` -- the same one padding column per side, with
    the pad cells beside it, every row still exactly ``width`` columns --
    and no title row is drawn: a title has nowhere to sit without the edge
    it was embedded in, so the host composes its own heading (the Rich
    reading of a box-less panel).  ``style`` is then the panel's **ground**
    instead of its frame color: an explicit style paints the panel's own
    cells and merges *under* the child's segments -- the child's colors win,
    the ground shows through wherever it has none, the ``Padding``
    ``fill_style`` rule -- so the block reads as one continuous band
    (geometrically what ``Padding(child, left=1, right=1,
    fill_style=style)`` spells; the switch is for a host that flips its
    chrome on one component instead of swapping two).  No explicit style
    means no ground, and the theme's ``borders.base`` field is never consulted in
    this mode: there is no frame to color, and a themed ground would
    repaint the child's own unstyled runs.  Below ``width < 2`` the padding
    drops too and the bare child keeps the width, the frame's own
    degradation.  ``frame`` is a plain mutable attribute like ``title``,
    and it is part of the wrap memo's key, so flipping it re-wraps instead
    of serving the other mode's rows.

    The frame is a pure function of the child's rows and the frame's own
    parameters, so the framed answer is remembered per **child-row identity**
    (the child's rows, by object, plus the width, the title and the resolved
    border style): a host that repaints the same child frame after frame (a
    long document inside a box) wraps the rows once, and the child's own
    memory is what it keeps re-reading (render-cost W4: the box used to
    re-fit, re-pad and re-splice every child row on every frame).  A hit
    hands back a fresh list of the remembered rows -- the same immutable
    ``Line`` values -- and refreshes the ``child_at`` geometry exactly as a
    miss does, so navigation is unaffected.
    """

    __slots__ = (
        "_border",
        "_child_rows",
        "_glyphs",
        "_inner",
        "_memo",
        "_width",
        "child",
        "frame",
        "style",
        "theme",
        "title",
    )

    def __init__(
        self,
        child,
        *,
        title: str = "",
        style: Style | None = None,
        frame: bool = True,
        border: Border | None = None,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.child = child
        self.title = title
        self.style = style
        self.frame = frame
        self._glyphs = glyphs
        self._border = glyphs.box if border is None else border
        self.theme = theme
        # ``style`` is a plain (mutable) attribute, same in-place restyle
        # affordance as Divider: the theme fallback resolves at render time.
        # No cached geometry before the first render: `child_at` declines
        # every cell until `render` stores the layout it painted.
        self._child_rows = 0
        self._inner = 0
        self._width = 0
        #: The wrap memo: ``(child-row identity tuple, width, title, frame,
        #: style)`` -> ``(wrapped rows, the child rows that key it)`` -- the
        #: child rows are kept precisely so their identities stay pinned, and
        #: a hit hands back copies.  ``None`` until the first render.
        self._memo: tuple[tuple, list[Line], list[Line]] | None = None

    def revision(self) -> object:
        """The :class:`~motui.core.block.Revisioned` snapshot.

        The wrap parameters plus the child's own key: its identity and --
        when it is :class:`~motui.core.block.Revisioned` -- its snapshot,
        so an in-place child change re-wraps a sealed panel.
        """
        return (
            self.title,
            self.style,
            self.frame,
            self._border,
            self._theme,
            _child_key(self.child),
        )

    def render(self, width: int) -> list[Line]:
        if self.frame:
            style = self.pick(self.style, self._theme.borders.base)
            framed = width >= 4
            lead = 2 if framed else 0  # the border and one pad column per side
        else:
            # Borderless: no frame to color, so the theme's border is never
            # consulted -- an explicit ``style`` is the ground instead.
            style = self.style
            framed = False
            lead = 1 if width >= 2 else 0  # one pad column per side
        inner = width - 2 * lead  # never negative: the lead is 0 below the minimum
        self._width = width
        self._inner = inner
        child_rows = list(self.child.render(inner))
        key = (tuple(map(id, child_rows)), width, self.title, self.frame, style, self._border)
        memo = self._memo
        if memo is not None and memo[0] == key:
            self._child_rows = len(memo[2])
            return list(memo[1])
        if not framed:
            rows = [self._bare_row(row, width, lead, style) for row in child_rows]
            self._child_rows = len(rows)
            self._memo = (key, rows, child_rows)
            return list(rows)
        rows = [row.fit(inner).fill(inner) for row in child_rows]
        self._child_rows = len(rows)
        out = [self._top_row(width, style)]
        for row in rows:
            framed_row = (
                Line((Segment(f"{self._border.left} ", style),))
                + row
                + Line((Segment(f" {self._border.right}", style),))
            )
            out.append(framed_row.fit(width))
        out.append(self._bottom_row(width, style))
        self._memo = (key, out, child_rows)
        return list(out)

    def _bare_row(self, row: Line, width: int, lead: int, ground: Style | None) -> Line:
        """One unwrapped row: the lead pad, the child, the fill to ``width``.

        The borderless panel spans the width it is handed exactly as the
        framed one does, its own cells (the pads and the cells the child
        leaves blank) carrying ``ground`` when there is one -- and the
        ground merges *under* the child's segments, so the block reads as
        one continuous band.  Without a ground the pads are plain spaces and
        the child's styles stay untouched.  ``lead == 0`` is the bare-child
        degradation (the frame's below four columns, the borderless panel's
        below two): the row is the child's, fitted, ground or not.

        The composition is ``(lead pad + row).fit(width).fill(width, pad)``:
        ``fill`` grows the row to the full width and merges the ground
        underneath (the Rich ``Padding(style=...)`` rule) when there is one,
        the ``NONE`` fast path when there is not -- and it never truncates,
        which the fit already handled.
        """
        if lead == 0:
            return row.fit(width)
        pad = NONE if ground is None else ground
        return (Line((Segment(" " * lead, pad),)) + row).fit(width).fill(width, pad)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning a content cell of the last render, in its coords.

        The panel's own cells answer ``None`` -- the border rows and the
        border/padding columns when framed, the pad columns when the frame
        is off -- and so does every cell before the first render.  Below the
        minimum width of either mode (four columns framed, two borderless)
        the panel degrades to the bare child, and then the whole block is
        the child's.
        """
        if row < 0 or col < 0:
            return None
        if self.frame:
            top, lead = (1, 2) if self._width >= 4 else (0, 0)
        else:
            top, lead = 0, (1 if self._width >= 2 else 0)
        if top <= row < top + self._child_rows and lead <= col < lead + self._inner:
            return self.child, row - top, col - lead
        return None

    def _top_row(self, width: int, style: Style) -> Line:
        border = self._border
        if self.title and width >= 6:
            label = ellipsize_tail(self.title, width - 5)
            if label:
                # One border segment: the title is embedded between the rule
                # runs and the whole row fuses into one styled run.
                segments = _labelled_rule(
                    border.top, 1, label, style, style, width - 2
                )
                text = "".join(segment.text for segment in segments)
                return Line.from_text(
                    f"{border.top_left}{text}{border.top_right}", style
                )
        return Line.from_text(
            f"{border.top_left}{border.top * (width - 2)}{border.top_right}", style
        )

    def _bottom_row(self, width: int, style: Style) -> Line:
        border = self._border
        return Line.from_text(
            f"{border.bottom_left}{border.bottom * (width - 2)}{border.bottom_right}",
            style,
        )

    def __repr__(self) -> str:
        mode = "" if self.frame else ", frame=False"
        return f"Panel({self.child!r}, title={self.title!r}{mode})"
