"""Immutable row model: :class:`Segment`, :class:`Line` and the plain-text component.

A :class:`Line` is exactly one visual row: an ordered tuple of styled
:class:`Segment` values.  :func:`wrap_line` shares
:func:`motui.core.text.wrap_spans` with :func:`motui.core.text.wrap_text`, so
both wrap with the same break rule.  All width logic comes from
:func:`motui.core.text.visible_width` -- directly, or through
:func:`motui.core.text.fit_text` for per-segment truncation and
:func:`motui.core.text.index_pair_at_columns` for the column-space cut,
whose scanner lives beside the measure it shares its cluster rules with;
nothing here re-measures text.

:class:`Text` -- the simplest component, verbatim text wrapped into rows --
lives here beside the row it renders through: its wrap is
:func:`motui.core.text.wrap_text` and each wrapped row becomes a
:class:`Line`.  Measurement alone stays in :mod:`motui.core.text`, so
this module may import from there and never the other way around.

Two module-level segment utilities round the model out: :func:`fuse`
coalesces runs that share a style, and :func:`overlay` applies one base style
underneath a segment list following the colored-vs-attribute rule.  Both
carry the segments' inline payloads (``link`` / ``action``) along, as every
rebuild in this module does -- a payload survives a cut, a re-style or a
coalesce.

An inline payload rides on the segment: ``link`` is the target of a real
terminal hyperlink (OSC 8, wrapped around the segment's text by
:meth:`Line.styled`) and ``action`` is the application-side name of what a
click on the segment means.  :func:`action_at` resolves the payload of the
column a click landed on; the components that answer clicks (``Text``,
``Markdown``) read their own last render's row table through it, never the
host's coordinates.

Cutting lives here too, in two offset spaces: :func:`slice_line` cuts by
character offsets into ``line.text`` (what word wrapping needs) and
:func:`cut_line` cuts by display columns (what column-addressed overlays such
as text selection need).  ``cut_line`` is built on ``slice_line`` -- one
per-segment cut, one set of width rules, never a second copy of either.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..terminal.ansi import hyperlink_close, hyperlink_open
from .style import NONE, RESET, ColorMode, Style, sgr_prefix
from .theme import Theme, Themed
from .text import (
    ELLIPSIS,
    _normalize_tabs,
    fit_text,
    index_pair_at_columns,
    visible_width,
    wrap_spans,
    wrap_text,
)

__all__ = [
    "ELLIPSIS",
    "Line",
    "Segment",
    "Text",
    "action_at",
    "cut_line",
    "fuse",
    "overlay",
    "rest",
    "slice_line",
    "styled_with",
    "wrap_line",
]


#: Control characters a rendered cell may never carry: C0 with the tab set
#: aside (it has its own rule), DEL, and the C1 range as defense in depth.
#: The set is explicit on purpose -- ``str.isprintable()`` would also condemn
#: the zero-width formatting characters (ZWJ, variation selectors, combining
#: marks) that emoji and accented runs are built from, and those are cells.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")


def _cells_only(text: str) -> str:
    """The Segment door: ``text`` as display cells, never terminal commands.

    Content and instructions part here, at the one point every rendered run
    passes through: a control character (C0, DEL, C1) arriving inside content
    would drive the terminal instead of painting cells -- dropping mouse
    tracking, writing the clipboard, retitling the window -- so the door
    deletes it.  Every escape byte the toolkit emits is constructed in
    :mod:`motui.terminal.ansi`; this door is what keeps that constitution true
    for the content channel.  A tab is not deleted but normalized to one
    space -- the repo's only tab rule (:func:`motui.core.text._normalize_tabs`,
    ``TAB_WIDTH == 1``), applied here so a segment built directly, off the
    wrap path, follows it too.

    The transform preserves width and therefore layout: ``visible_width``
    counts every deleted character as zero columns, and a tab counts one
    column -- exactly what the space replacing it occupies.  Clean text (no
    tab, no control character -- nearly every segment) comes back as the
    very same string, zero allocations: one membership test and one
    regex scan, both C-speed.  The transform is idempotent.
    """
    if "\t" in text:
        text = text.replace("\t", " ")  # the repo's tab rule: one tab, one space
    if _CONTROL_RE.search(text) is None:
        return text  # the fast path: the same string, nothing allocated
    return _CONTROL_RE.sub("", text)


@dataclass(frozen=True, slots=True)
class Segment:
    """A styled run of text.  Segments are frozen and hashable.

    **Cells only.**  Construction is the one door between content and
    terminal commands: ``text`` -- and ``link``, whose bytes reach the
    terminal inside the OSC 8 pair -- pass through :func:`_cells_only` in
    ``__post_init__``, so control characters are deleted and a tab becomes
    one space before anything is measured or painted.  A run of text can
    therefore never carry an escape sequence into the byte stream; only
    :mod:`motui.terminal.ansi` builds escapes.  The transform preserves width
    (deleted characters occupy no columns, a tab counts one column like the
    space that replaces it), so layout and the rendering of clean text are
    untouched, and it is idempotent: a rebuild through :meth:`with_style`
    passes the door again and changes nothing.

    The two payload slots beside ``text``/``style`` are the row model's only
    inline addresses (the kernel constitution): ``link`` is an url the
    terminal should treat as a real hyperlink -- :meth:`Line.styled` wraps
    the segment's text in the OSC 8 pair -- and ``action`` is the name the
    *application* gives to a click on that run (``"open:<url>"``, a task
    list's ``"todo:3"``, ...), which :func:`action_at` hands back for the
    column a click landed on.  ``link`` participates in equality (a changed
    link must repaint the row); ``action`` does not (it never reaches a
    byte, so it must not make two visibly equal rows compare different).
    """

    text: str
    style: Style = Style()
    #: OSC 8 hyperlink target, or ``None`` for plain text.
    link: str | None = None
    #: Application-side action name for a click on this run; metadata only.
    action: str | None = field(default=None, compare=False)
    #: Derived cache: the segment's display width in columns, computed at
    #: most once per instance (the ``Style._prefix`` pattern) and invisible
    #: to eq/hash/repr.  A row is re-measured frame after frame -- by the
    #: painter, the padding, the splice -- through the very same Segment
    #: values, so the one walk lands on the value, not on every reader.
    _width: int = field(init=False, compare=False, repr=False, default=-1)

    def __post_init__(self) -> None:
        """The content door: ``text`` and ``link`` are cells only.

        Runs before any measurement, so the lazy ``_width`` cache and every
        width a reader sees are computed from the sanitized run -- the door
        and the measure can never disagree.  A link that sanitizes to the
        empty string becomes ``None``: an empty OSC 8 target has no meaning,
        and plain text is what it would paint anyway.
        """
        object.__setattr__(self, "text", _cells_only(self.text))
        if self.link is not None:
            object.__setattr__(self, "link", _cells_only(self.link) or None)

    @property
    def width(self) -> int:
        """Display width in columns, via :func:`motui.core.text.visible_width`."""
        if self._width < 0:
            object.__setattr__(self, "_width", visible_width(self.text))
        return self._width

    def with_style(self, style: Style) -> "Segment":
        """A copy of this run in ``style``: text and payloads ride along.

        The one rebuild a restyling site uses (a selection highlight, a
        hover band, a fill underneath), so the ``link``/``action`` a run
        carries survive it -- and, with them, the OSC 8 pairing a later
        repaint emits and the span :func:`action_at` resolves.
        """
        return Segment(self.text, style, link=self.link, action=self.action)


def _segment_bytes(seg: Segment, prefix: str) -> str:
    """One segment's rendered bytes: its style prefix, its text and its link.

    A segment with a ``link`` has its text wrapped in the OSC 8 pair --
    ``prefix open text close`` -- so the terminal paints a real hyperlink
    over exactly the run the segment owns; the pair sits inside the SGR
    prefix's scope and is closed before the next segment's RESET, never
    leaking the link over a neighbour.  A segment without one renders
    ``prefix + text``, byte-for-byte what it always did: the one byte path
    the painter's truecolor mode takes is unchanged for every row that does
    not carry a link.
    """
    if seg.link is None:
        return prefix + seg.text
    return prefix + hyperlink_open(seg.link) + seg.text + hyperlink_close()


class Line:
    """One immutable visual row made of styled :class:`Segment` values."""

    __slots__ = ("_segments", "_text", "_width", "_styled")

    def __init__(self, segments: Iterable[Segment] = ()) -> None:
        object.__setattr__(self, "_segments", tuple(segments))
        # Derived caches: a line is a value, so its plain text, its width and
        # its SGR rendering are pure functions of the segments -- computed at
        # most once each (the Style._prefix pattern), invisible to eq/hash.
        object.__setattr__(self, "_text", None)
        object.__setattr__(self, "_width", None)
        object.__setattr__(self, "_styled", None)

    # -- immutability ------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    # -- construction ------------------------------------------------------

    @classmethod
    def from_text(cls, text: str, style: Style | None = None) -> "Line":
        """A line holding ``text`` in a single segment (``""`` -> empty line)."""
        if text == "":
            return cls()
        return cls((Segment(text, style if style is not None else Style()),))

    # -- views -------------------------------------------------------------

    @property
    def segments(self) -> tuple[Segment, ...]:
        return self._segments

    @property
    def text(self) -> str:
        """Plain-text view (styles dropped)."""
        if self._text is None:
            object.__setattr__(
                self, "_text", "".join(seg.text for seg in self._segments)
            )
        return self._text

    @property
    def width(self) -> int:
        """Display width in columns, via :class:`Segment.width` (which measures
        through :func:`motui.core.text.visible_width`)."""
        if self._width is None:
            object.__setattr__(
                self, "_width", sum(seg.width for seg in self._segments)
            )
        return self._width

    def styled(self) -> str:
        """SGR-escaped rendering: prefix+text per segment, one trailing RESET.

        Every segment after the first non-empty one is preceded by a RESET,
        because SGR is a state machine: a prefix only *adds* attributes, so
        without the reset the first segment's color and attributes would
        persist into the second -- a scrollbar's ``dim`` reaching the pane
        beside it, a band's background reaching the text painted over it.
        A segment is therefore a clean slate: its rendering is a pure
        function of its own style, which is what this docstring has always
        claimed.  A zero-width segment paints nothing and opens no reset.
        A segment carrying a ``link`` additionally wraps its own text in the
        OSC 8 pair (see :func:`action_at`'s sibling payloads); the pair is
        closed inside the segment, so no hyperlink crosses a boundary.  The
        rendering is cached: a line is a value, and the painter re-styles
        the same row frame after frame.
        """
        if self._styled is None:
            parts: list[str] = []
            for seg in self._segments:
                if not seg.text:
                    continue  # a zero-width segment paints nothing at all
                if parts:
                    parts.append(RESET)  # a clean slate: no attribute crosses a boundary
                parts.append(_segment_bytes(seg, seg.style.prefix()))
            object.__setattr__(
                self, "_styled", "".join(parts) + RESET if parts else ""
            )
        return self._styled

    # -- sizing ------------------------------------------------------------

    def fit(self, width: int) -> "Line":
        """Truncate *this* row to ``width`` columns, marking the cut with ``…``.

        Over-wide lines lose their tail; the marker takes one column and
        inherits the style of the last kept segment -- fused onto that
        segment when something survived, a plain unstyled marker when
        nothing did.  ``width <= 0`` yields an empty line, and a line that
        already fits is returned unchanged (the same object).
        """
        if width <= 0:
            return Line()
        if self.width <= width:
            return self
        budget = width - 1  # columns left for text, the marker takes one
        kept: list[Segment] = []
        used = 0
        for seg in self._segments:
            if used >= budget:
                break
            seg_w = seg.width
            if used + seg_w <= budget:
                kept.append(seg)
                used += seg_w
                continue
            # Same measurement root as kernel.text.ellipsize_tail: cut the
            # segment through fit_text so clusters that measure wider (or
            # narrower) than their characters cannot overflow the budget.
            piece = fit_text(seg.text, budget - used)
            if piece:
                kept.append(Segment(piece, seg.style, link=seg.link, action=seg.action))
                used += visible_width(piece)
            break
        marker_style = kept[-1].style if kept else Style()
        if kept and kept[-1].text:
            # Marker shares the truncated run's style and payloads: the same
            # run, one character longer -- so a truncated link's cells stay
            # one hyperlink/action span.
            kept[-1] = Segment(
                kept[-1].text + ELLIPSIS,
                marker_style,
                link=kept[-1].link,
                action=kept[-1].action,
            )
        else:
            kept.append(Segment(ELLIPSIS, marker_style))
        return Line(kept)

    def fill(self, width: int, style: Style = NONE) -> "Line":
        """Grow *this* row to ``width`` columns, ``style`` laid underneath.

        The sizing family's growing member -- ``fit`` trims, ``fill``
        extends, ``filled`` builds a blank row from scratch.  It is where
        the removed ``pad_to`` was absorbed: the ``NONE`` fast path is
        byte-identical to what ``pad_to`` answered.

        ``style`` is the band *underneath* the content (the Rich
        ``Padding(style=...)`` rule, ``ref/industry.md`` §2): every content
        segment comes back through :meth:`Segment.with_style` as
        ``style.merge(seg.style)`` -- ``style`` is the base, the segment's
        own colors win where it has them -- and a gap becomes one
        ``Segment(" " * gap, style)``.  ``fill`` never truncates; ``fit`` is
        the trim, so the canonical band pipeline is ``row.fit(w).fill(w,
        band)``.

        The ``NONE`` fast path (``style == NONE``; ``NONE`` is ``Style()``,
        so ``==`` catches both the constant and any equal style): no gap
        returns the row itself, a gap appends one plain unstyled space
        segment.  ``width <= 0`` yields an empty line.
        """
        if width <= 0:
            return Line()
        if style == NONE:
            gap = width - self.width
            if gap <= 0:
                return self
            return self + Line.from_text(" " * gap)
        segments = [seg.with_style(style.merge(seg.style)) for seg in self._segments]
        gap = width - self.width
        if gap > 0:
            segments.append(Segment(" " * gap, style))
        return Line(segments)

    @classmethod
    def filled(cls, width: int, style: Style = NONE) -> "Line":
        """A fresh row of ``width`` spaces in one segment: the band primitive.

        The blank-row constructor a component that renders solid
        background rows builds on, and what the kernel's chrome strips fill
        with: one segment, ``style``, exactly ``width`` columns.  A row that
        already exists and needs filling is :meth:`fill` instead.
        ``width <= 0`` yields an empty line.
        """
        if width <= 0:
            return cls()
        return cls((Segment(" " * width, style),))

    # -- combination -------------------------------------------------------

    def __add__(self, other: object) -> "Line":
        if not isinstance(other, Line):
            return NotImplemented
        return Line(self._segments + other._segments)

    def merge_span(self, start: int, end: int, style: Style) -> "Line":
        """``style`` merged over the cells ``[start, end)``: a new row.

        The inline-hover post-transform: a component keeps a hover-free base
        row and, while the pointer sits on a span, renders the base with the
        span's segments restyled -- each segment the column range intersects
        (display columns, the :attr:`Segment.width` walk, left-closed and
        right-open as :func:`action_at` reports it) comes back through
        :meth:`Segment.with_style`, so its ``link``/``action`` ride along;
        every other segment is the very same object.  A range that meets no
        non-empty segment answers ``self`` -- the row already renders
        byte-for-byte as asked, and the caller's cache keeps one value.
        """
        if start >= end:
            return self
        segments: list[Segment] = []
        spanned = False
        pos = 0
        for seg in self._segments:
            seg_end = pos + seg.width
            if seg.text and pos < end and seg_end > start:
                segments.append(seg.with_style(seg.style.merge(style)))
                spanned = True
            else:
                segments.append(seg)
            pos = seg_end
        return Line(segments) if spanned else self

    # -- protocol ----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Line):
            return NotImplemented
        return self._segments == other._segments

    def __hash__(self) -> int:
        return hash(self._segments)

    def __repr__(self) -> str:
        return f"Line({self._segments!r})"


def rest(row: Line, width: int, band: Style) -> Line:
    """One row on its band: ``fit`` then ``fill`` at the fitted row's width.

    The band rests under the row's own segments (the Rich
    ``Padding(style=...)`` rule); the ``NONE`` fast path leaves a resting
    row byte-for-byte unchanged.  The row widgets share this one lay-down
    beside :meth:`Line.fit` / :meth:`Line.fill`, the two primitives it
    composes.
    """
    fitted = row.fit(width)
    return fitted if band == NONE else fitted.fill(fitted.width, band)


def styled_with(line: Line, mode: ColorMode) -> str:
    """SGR-escaped rendering of ``line`` for a terminal of capability ``mode``.

    The very assembly :meth:`Line.styled` performs -- a RESET before every
    segment after the first non-empty one, one trailing RESET, a zero-width
    segment painting nothing, an OSC 8 pair around a segment that carries a
    link (a hyperlink is not a color: it survives every mode) -- with each
    segment's prefix resolved through
    :func:`~motui.core.style.sgr_prefix` instead of the segment's own
    cached one.  Because the answer depends on the terminal, it is
    deliberately **not** cached: :meth:`Line.styled`'s cache stays
    capability-free (the kernel constitution), and the painter takes this
    path only for the non-truecolor modes.
    """
    parts: list[str] = []
    for seg in line.segments:
        if not seg.text:
            continue  # a zero-width segment paints nothing at all
        if parts:
            parts.append(RESET)  # a clean slate: no attribute crosses a boundary
        parts.append(_segment_bytes(seg, sgr_prefix(seg.style, mode)))
    return "".join(parts) + RESET if parts else ""


def action_at(line: Line, col: int) -> tuple[str, int, int] | None:
    """The inline action under column ``col``: ``(action, start, end)`` or ``None``.

    Walks ``line``'s segments accumulating display width -- the same
    :class:`Segment` measure every other reader uses, so a wide cluster owns
    both of its columns and the answer never disagrees with what was painted
    -- and answers the payload of the segment ``col`` falls in, with that
    segment's column interval, **left-closed and right-open** (``[start,
    end)``, exactly the cells a click span owns).  ``None`` for a column
    before the line, at or past its end, or inside a segment that carries no
    action: the caller keeps its own policy, this is the lookup only.  Pure:
    no state, no cache, no side effect.
    """
    if col < 0:
        return None
    pos = 0
    for seg in line.segments:
        end = pos + seg.width
        if pos <= col < end:
            return (seg.action, pos, end) if seg.action is not None else None
        pos = end
    return None


class Text(Themed):
    """A block of plain text rendered verbatim, line by line.

    ``text`` is a mutable attribute (streaming text assigns to it).  Each
    logical line (``split("\\n")``) is word-wrapped with
    :func:`motui.core.text.wrap_text` into rows of at most ``width``
    columns, so blank lines survive as blank rows.  Every row carries
    ``style`` and is ``fit`` to ``width`` as a final guard.

    ``style`` defaults to ``None``, which renders as the unstyled default
    (``NONE``).  ``theme`` is read for exactly one thing: the ``hover`` band
    a hovered inline span merges (:meth:`hover_at`); verbatim text has no
    other theme-able style of its own.

    **Caching.**  Wrapping a long text is the most expensive render the
    toolkit has, and a host re-renders the same component frame after frame
    (every mouse move repaints).  The cache lives in **one** place:
    :meth:`~motui.core.block.Block.rows`, which remembers a sealed (or
    revisioned) block's rows by width and :meth:`revision`.  ``render``
    itself is pure -- every standalone call re-wraps -- so a component
    handed straight to a caller never serves a stale row; behind a block,
    the block's cache answers the repeats.  The hit table :attr:`_rows`
    keeps its "last render" meaning and is geometry, not a cache.

    **Inline actions.**  ``Text`` is :class:`Hoverable` and
    :class:`Clickable`: the row table of its last render lives in
    ``self._rows``, and a click or a hover resolves the cell against it
    through :func:`action_at`.  ``click(row, col)`` leaves the segment's
    ``action`` payload pending -- the host reads it once through
    :meth:`take_result`, which clears it -- and answers ``True`` only when
    a payload was hit; a miss declines, so the host's own policies still
    get their turn.  ``hover_at(row, col)``
    remembers the span under the pointer and answers whether the render
    changed; the span merges the theme's ``hover`` band over that segment
    **on a copy**, so the row's own text and payloads are never rewritten.
    The component-level :attr:`hover` flag is the protocol's peer of
    ``focused`` and changes nothing by itself: this component's visual is
    the span, so a whole-row band would be wrong (``Pointer`` sets the flag
    and calls ``hover_at`` on the same move).

    The default rows carry no payloads -- a plain row is verbatim text --
    so a subclass that wants spans renders its own ``Line`` values through
    :meth:`_rows_for` and inherits the hit testing, the hover transform and
    the one-shot result unchanged.
    """

    __slots__ = (
        "_hover_span",
        "_hover_style",
        "_pending",
        "_rows",
        "hover",
        "style",
        "text",
    )

    def __init__(
        self,
        text: str = "",
        *,
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.text = text
        self.style = style
        #: The pointer tier's flag: written by ``Pointer``, never read here
        #: (see the class docstring: this component's visual is the span).
        self.hover = False
        #: The pending pick: ``click`` lands a hit segment's action here and
        #: the host reads it once through :meth:`take_result`.
        self._pending: str | None = None
        # The one themed style: the pointer-hover band, resolved once (there
        # is no explicit hover_style= parameter to win over it).
        self._hover_style = self.pick(None, self._theme.surfaces.hover)
        #: The row table of the last render; geometry for click/hover_at.
        self._rows: list[Line] = []
        #: The span under the pointer: ``(row, start, end)`` or ``None``.
        self._hover_span: tuple[int, int, int] | None = None

    def _rows_for(self, width: int) -> list[Line]:
        """The rows ``text`` renders to: the subclass seam for inline spans.

        The default is verbatim text: one ``Line`` per wrapped piece.  A
        subclass that wants clickable/hoverable spans returns ``Line`` values
        whose segments carry ``link`` / ``action`` payloads instead -- the
        inherited ``render`` keeps the table it returns for ``click`` and
        ``hover_at``, with no further wiring.
        """
        out: list[Line] = []
        for row in self.text.split("\n"):
            for piece in wrap_text(row, width):
                out.append(Line.from_text(piece, self.style).fit(width))
        return out

    def _revision(self) -> object:
        """The value snapshot of everything the rows are made of.

        The default answers ``(text, style, hover span, hover style)`` --
        all four are row inputs: the text wraps, the style lands on every
        segment, and the span (with the band it merges) is what a hovered
        render answers.  This is the **overridable seam** for subclasses
        (the same tier as :meth:`_rows_for`): a subclass whose rows depend
        on more state adds that state to the tuple, and one whose state
        cannot be snapshotted cheaply returns ``None``, which switches block
        caching off rather than risking a stale hit.  The snapshot must be a
        value (no live mutable fields) and must cost far less than the
        wrap it guards.
        """
        return (self.text, self.style, self._hover_span, self._hover_style)

    def revision(self) -> object:
        """The :class:`~motui.core.block.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a block holding this
        component keys its own row cache on the same value, so a streamed
        ``text =`` assignment or a moved hover span invalidates the block's
        copy in one move.  The component keeps no row cache of its own.
        """
        return self._revision()

    def render(self, width: int) -> list[Line]:
        """Wrap ``text`` to ``width`` and return the rows (always a fresh list).

        The render is pure: every call runs :meth:`_rows_for`, and the one
        row cache in the stack is :meth:`~motui.core.block.Block.rows`
        (which keys on this component's :meth:`revision`).  The hover
        transform follows on a copy, so the last-render table never carries
        the band.

        The row table is also kept on ``self`` (``_rows``), because the
        hit testing of ``click`` / ``hover_at`` reads the geometry of the
        **last render**: with no hovered span that table is the hover-free
        rows, byte-for-byte what this component always rendered, and a
        hovered span answers that row rebuilt with the theme's ``hover``
        merged onto the span -- a copy, so the last-render row itself stays
        hover-free.
        """
        rows = self._rows_for(width)
        self._rows = rows
        span = self._hover_span
        if span is None:
            return list(rows)
        index, start, end = span
        out = list(rows)
        if 0 <= index < len(out):
            out[index] = out[index].merge_span(start, end, self._hover_style)
        return out

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the cell under the pointer; answer whether the render changed.

        ``row < 0`` (the pointer left) clears the mark.  The cell resolves
        against the last render's row table through :func:`action_at`: a
        column inside a segment with an ``action`` remembers
        ``(row, start, end)``, anything else -- a plain run, a column past
        the row -- clears it.  The answer is whether that span differs from
        the one remembered, which is exactly whether the frame repaints.
        """
        span: tuple[int, int, int] | None = None
        if row >= 0 and row < len(self._rows):
            hit = action_at(self._rows[row], col)
            if hit is not None:
                span = (row, hit[1], hit[2])
        changed = span != self._hover_span
        self._hover_span = span
        return changed

    def click(self, row: int, col: int) -> bool:
        """Take the action under ``(row, col)`` as the pending result; hit?

        The hit is :func:`action_at` against the last render's row table, so
        the column must land inside a segment that carries an ``action``.
        A hit leaves that payload pending -- read once through
        :meth:`take_result`, which clears it -- and answers ``True``; a miss
        -- a plain run, a column outside the row -- answers ``False`` and
        consumes nothing, leaving the cell to whatever the host does next.
        """
        if 0 <= row < len(self._rows):
            hit = action_at(self._rows[row], col)
            if hit is not None:
                self._pending = hit[0]
                return True
        return False

    def take_result(self) -> str | None:
        """Read the pending action payload once and clear it."""
        value = self._pending
        self._pending = None
        return value

    def __repr__(self) -> str:
        return f"Text({self.text!r})"


def slice_line(line: Line, start: int, end: int) -> Line:
    """The sub-line covering ``line.text[start:end]``, keeping per-segment styles.

    Offsets are character offsets into ``line.text`` (the concatenation of the
    segments, so a slice may start or end mid-segment); tabs inside a kept
    slice become single spaces (the module's documented tab rule) so widths
    stay consistent.  An empty range yields an empty line.  A segment's
    payloads (``link`` / ``action``) ride along, so a wrapped link is still a
    link on the row it landed on.  This is the cut
    :func:`wrap_line` wraps through, promoted from a private helper so the
    column-space cut below can share it instead of re-walking segments.
    """
    if start >= end:
        return Line()
    out: list[Segment] = []
    pos = 0
    for seg in line.segments:
        seg_start = pos
        pos += len(seg.text)
        seg_end = pos
        if seg_end <= start or seg_start >= end:
            continue
        piece = seg.text[max(start, seg_start) - seg_start : min(end, seg_end) - seg_start]
        if piece:
            out.append(
                Segment(
                    _normalize_tabs(piece),
                    seg.style,
                    link=seg.link,
                    action=seg.action,
                )
            )
    return Line(out)


def cut_line(line: Line, start: int, end: int) -> Line:
    """The sub-line covering display columns ``[start, end)``.

    The column-space counterpart of :func:`slice_line`: offsets are terminal
    columns measured with :func:`motui.core.text.visible_width`, not
    character counts.  The range clamps into the line's width -- a selection
    column past a short row simply reaches the row's end -- and a boundary
    landing inside a multi-column cluster snaps **down** to that cluster's
    start through :func:`motui.core.text.index_pair_at_columns`, which runs
    the same cluster rules the measure does: the floor rule that has always
    held for a plain wide character is finally true for every cluster, so a
    cut never halves one.  A cut at (or past) the end, or an empty range,
    yields an empty line.  Per-segment styles survive exactly as they do in
    :func:`slice_line`, which does the cutting.
    """
    if start >= end:
        return Line()
    text = line.text
    return slice_line(line, *index_pair_at_columns(text, start, end))


def wrap_line(line: Line, width: int) -> list[Line]:
    """Word-aware wrap of ``line`` into rows of at most ``width`` columns.

    Same break rule as :func:`motui.core.text.wrap_text`: spaces preferred,
    over-long words and CJK runs hard-broken, wide characters owning a row of
    their own when ``width`` is smaller than the character.  Styles survive
    across breaks; whitespace at a break is dropped.  An empty line (or
    ``width <= 0``) wraps to ``[Line()]``.
    """
    if width <= 0:
        return [Line()]
    text = line.text
    if text == "":
        return [Line()]
    text = _normalize_tabs(text)
    return [slice_line(line, s, e) for s, e in wrap_spans(text, width)]


def fuse(segments: Iterable[Segment]) -> list[Segment]:
    """Coalesce adjacent runs sharing a style into single segments.

    Only *adjacent* segments with equal styles **and equal payloads** merge,
    and they merge in order; a segment with a style -- or a link/action -- of
    its own keeps it.  Two differently-linked runs must not fuse into one:
    the merged run would answer a click and open a hyperlink for the wrong
    half.  Empty segments stay (a zero-width run paints nothing at all, so
    dropping it is the caller's choice).  One segment in, one segment out.
    """
    out: list[Segment] = []
    for seg in segments:
        if (
            out
            and out[-1].style == seg.style
            and out[-1].link == seg.link
            and out[-1].action == seg.action
        ):
            out[-1] = Segment(
                out[-1].text + seg.text,
                seg.style,
                link=seg.link,
                action=seg.action,
            )
        else:
            out.append(seg)
    return out


def overlay(base: Style, segments: Iterable[Segment]) -> list[Segment]:
    """Apply ``base`` underneath ``segments``: the colored-vs-attribute rule.

    A segment that carries a color of its own (``fg`` or ``bg`` set) keeps
    that style absolute; an attribute-only segment (bold, italic, underline,
    ...) is merged onto ``base``, so a band painted underneath still shows
    through the emphasis.  Payloads (``link`` / ``action``) ride along
    unchanged.  One segment in, one segment out.
    """
    return [
        seg.with_style(
            seg.style
            if seg.style.fg is not None or seg.style.bg is not None
            else base.merge(seg.style)
        )
        for seg in segments
    ]
