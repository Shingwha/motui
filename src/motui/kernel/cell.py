"""Cells, styled runs, rows and surfaces -- the 2.0 row model.

A :class:`Cell` is the write face: one character with its style and its two
inline payloads.  A :class:`Segment` is the same run in its run-length form,
which is what a :class:`Line` holds; a :class:`Surface` is a block of lines
at one content width.  All four are immutable values.

Construction is the content door.  A control character (C0, DEL, C1) inside
content would drive the terminal instead of painting cells, so ``Cell`` and
``Segment`` delete those characters and normalize a tab to one space -- the
same rule the 1.x row model applied.  The kernel never builds terminal bytes;
SGR rendering lives in :func:`motui.terminal.render.styled_line`.

A :class:`Line` is exactly one visual row: an ordered tuple of styled
:class:`Segment` values.  :func:`wrap_line` shares
:func:`motui.kernel.text.wrap_spans` with :func:`motui.kernel.text.wrap_text`,
so both wrap with the same break rule.  All width logic comes from
:func:`motui.kernel.text.visible_width` -- directly, or through
:func:`motui.kernel.text.fit_text` for per-segment truncation and
:func:`motui.kernel.text.index_pair_at_columns` for the column-space cut,
whose scanner lives beside the measure it shares its cluster rules with;
nothing here re-measures text.

Two module-level segment utilities round the model out: :func:`fuse`
coalesces runs that share a style, and :func:`overlay` applies one base style
underneath a segment list following the colored-vs-attribute rule.  Both
carry the segments' inline payloads (``link`` / ``action``) along, as every
rebuild in this module does -- a payload survives a cut, a re-style or a
coalesce.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import overload

from .geom import Size
from .style import NONE, Style
from .text import (
    ELLIPSIS,
    WrapMode,
    _cell_spans,
    _normalize_tabs,
    fit_text,
    index_pair_at_columns,
    visible_width,
    wrap_spans,
)

__all__ = [
    "ELLIPSIS",
    "Cell",
    "Line",
    "Segment",
    "Style",
    "Surface",
    "action_at",
    "cut_line",
    "fuse",
    "overlay",
    "rest",
    "slice_line",
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
    space -- the repo's only tab rule (:func:`motui.kernel.text._normalize_tabs`,
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
class Cell:
    """One display cell: a character, a style and the inline payloads.

    ``char`` and the two payloads pass through the content door at
    construction; ``link`` and ``action`` are metadata, so neither
    contributes width.  A control-only ``char`` becomes the empty string
    rather than raising: the door's contract is to delete, and an empty cell
    paints nothing.
    """

    char: str = " "
    style: Style = Style()
    link: str | None = None
    action: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "char", _cells_only(self.char))
        if self.link is not None:
            object.__setattr__(self, "link", _cells_only(self.link) or None)
        if self.action is not None:
            object.__setattr__(self, "action", _cells_only(self.action) or None)


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
    terminal should treat as a real hyperlink -- :func:`motui.terminal.render.styled_line`
    wraps the segment's text in the OSC 8 pair -- and ``action`` is the name the
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
        """The content door: ``text``, ``link`` and ``action`` are cells only.

        Runs before any measurement, so the lazy ``_width`` cache and every
        width a reader sees are computed from the sanitized run -- the door
        and the measure can never disagree.  A link that sanitizes to the
        empty string becomes ``None``: an empty OSC 8 target has no meaning,
        and plain text is what it would paint anyway.  ``action`` passes the
        same door as :class:`Cell`'s payload, so a control character can
        never ride an action name into a host's dispatch.
        """
        object.__setattr__(self, "text", _cells_only(self.text))
        if self.link is not None:
            object.__setattr__(self, "link", _cells_only(self.link) or None)
        if self.action is not None:
            object.__setattr__(self, "action", _cells_only(self.action) or None)

    @property
    def width(self) -> int:
        """Display width in columns, via :func:`motui.kernel.text.visible_width`."""
        if self._width < 0:
            object.__setattr__(self, "_width", visible_width(self.text))
        return self._width

    def with_style(self, style: Style) -> Segment:
        """A copy of this run in ``style``: text and payloads ride along.

        The one rebuild a restyling site uses (a selection highlight, a
        hover band, a fill underneath), so the ``link``/``action`` a run
        carries survive it -- and, with them, the OSC 8 pairing a later
        repaint emits and the span :func:`action_at` resolves.
        """
        return Segment(self.text, style, link=self.link, action=self.action)


class Line:
    """One immutable visual row made of styled :class:`Segment` values."""

    __slots__ = ("_segments", "_text", "_width")

    def __init__(self, segments: Iterable[Segment] = ()) -> None:
        object.__setattr__(self, "_segments", tuple(segments))
        # Derived caches: a line is a value, so its plain text and its width
        # are pure functions of the segments -- computed at most once each
        # (the Style._prefix pattern), invisible to eq/hash.
        object.__setattr__(self, "_text", None)
        object.__setattr__(self, "_width", None)

    # -- immutability ------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    # -- construction ------------------------------------------------------

    @classmethod
    def from_text(cls, text: str, style: Style | None = None) -> Line:
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
        cached = self._text
        if cached is None:
            cached = "".join(seg.text for seg in self._segments)
            object.__setattr__(self, "_text", cached)
        return cached

    @property
    def width(self) -> int:
        """Display width in columns, via :class:`Segment.width` (which measures
        through :func:`motui.kernel.text.visible_width`)."""
        cached = self._width
        if cached is None:
            cached = sum(seg.width for seg in self._segments)
            object.__setattr__(self, "_width", cached)
        return cached

    # -- sizing ------------------------------------------------------------

    def _fit(self, width: int) -> Line:
        """Truncate *this* row to ``width`` columns, marking the cut with ``…``.

        The private trim behind ``WrapMode.ELLIPSIS``; components reach it
        through :meth:`clip` / :meth:`reflow`.  Over-wide lines lose their
        tail; the marker takes one column and inherits the style of the last
        kept segment -- fused onto that segment when something survived, a
        plain unstyled marker when nothing did.  ``width <= 0`` yields an
        empty line, and a line that already fits is returned unchanged (the
        same object).
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

    def fill(self, width: int, style: Style = NONE) -> Line:
        """Grow *this* row to ``width`` columns, ``style`` laid underneath.

        The sizing family's growing member -- ``clip(WrapMode.ELLIPSIS,
        width)`` trims, ``fill`` extends, ``filled`` builds a blank row from
        scratch.  It is where
        the removed ``pad_to`` was absorbed: the ``NONE`` fast path is
        byte-identical to what ``pad_to`` answered.

        ``style`` is the band *underneath* the content (the Rich
        ``Padding(style=...)`` rule, ``ref/industry.md`` §2): every content
        segment comes back through :meth:`Segment.with_style` as
        ``style.merge(seg.style)`` -- ``style`` is the base, the segment's
        own colors win where it has them -- and a gap becomes one
        ``Segment(" " * gap, style)``.  ``fill`` never truncates;
        ``clip(WrapMode.ELLIPSIS, w)`` is the trim, so the canonical band
        pipeline is ``row.clip(WrapMode.ELLIPSIS, w).fill(w, band)``.

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
    def filled(cls, width: int, style: Style = NONE) -> Line:
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

    def __add__(self, other: object) -> Line:
        if not isinstance(other, Line):
            return NotImplemented
        return Line(self._segments + other._segments)

    def merge_span(self, start: int, end: int, style: Style) -> Line:
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

    def overlay(self, base: Line) -> Line:
        """Paint this row on top of ``base``, one cell at a time.

        The 2.0 composition primitive: ``self`` is the top layer and
        ``base`` the bottom.  A **transparent** cell -- a plain unstyled
        space carrying neither a link nor an action -- keeps the cell under
        it; every other cell replaces the base cell, its style merged as
        ``base_style.merge(top_style)`` (the underlying color shows through,
        the top layer's attributes win) and its ``link``/``action`` taken
        from the top.  The answer is as wide as the wider row; the short
        side is treated as blank, so a top cell past the base's end simply
        starts from ``Style()``.

        Wide characters are composed as whole clusters, never as columns: a
        non-transparent top cell overlapping any part of a double-wide base
        glyph replaces the **entire** glyph, and a cluster that straddles
        the top cell's span leaves blank cells (in the erased glyph's style)
        instead of a dangling continuation.  Transparent cells preserve the
        whole base glyph.  A top row with no visible cell -- ``Line()`` or
        one made only of transparent cells -- returns ``base`` itself (padded
        when the top row is wider), so an empty overlay layer costs nothing.
        """
        top_cells = _line_cells(self)
        if not any(not _transparent(cell) for cell in top_cells):
            return base if base.width >= self.width else base.pad(self.width)
        return _paint_cells(top_cells, _line_cells(base))

    # -- the 2.0 width vocabulary -----------------------------------------

    def reflow(self, mode: WrapMode, width: int) -> list[Line]:
        """Lay *this* row out in ``width`` columns under ``mode``.

        The one entry for every width response in the toolkit:

        - ``WORD``: word-aware wrap (:func:`wrap_line`), each row closed
          with :meth:`_fit` so a cluster measuring wider than ``width``
          still cannot overflow it;
        - ``CHAR``: hard character wrap (:func:`_wrap_chars`), same closing
          trim;
        - ``ELLIPSIS``: one row, tail cut and marked with ``…``;
        - ``CLIP``: one row, hard cut at the width (no marker);
        - ``OVERFLOW``: the row itself, even when wider than ``width`` --
          the container owns the clipping.

        An empty row (or ``width <= 0``) yields ``[Line()]`` for every mode
        except ``OVERFLOW``.  Styles and inline payloads survive every row
        the wrap emits, and an unknown mode raises ``ValueError``.
        """
        if mode is WrapMode.WORD:
            return [row._fit(width) for row in wrap_line(self, width)]
        if mode is WrapMode.CHAR:
            return [row._fit(width) for row in _wrap_chars(self, width)]
        if mode is WrapMode.ELLIPSIS:
            return [self._fit(width)]
        if mode is WrapMode.CLIP:
            return [cut_line(self, 0, width)]
        if mode is WrapMode.OVERFLOW:
            return [self]
        raise ValueError(f"unknown wrap mode: {mode!r}")

    def clip(self, mode: WrapMode, width: int) -> Line:
        """The single-row form of :meth:`reflow`: its first row.

        ``WORD`` / ``CHAR`` answer the first wrapped row; the other modes
        are single-row by definition.  Use this when the caller wants one
        row (a header, a label, a status line) and :meth:`reflow` when it
        wants the whole block.
        """
        return self.reflow(mode, width)[0]

    def _cut_width(self, width: int) -> Line:
        """A prefix of this row no wider than ``width`` columns -- hard cut.

        The private hard cut behind :meth:`Surface.of` /
        :meth:`Surface.clipped` (the surface invariant guard);
        ``clip(WrapMode.CLIP, width)`` is the public spelling.  A cut never
        splits a cell: a double-width character that would straddle the
        edge is dropped, leaving the line narrower than the limit.  Styling
        and inline payloads ride along on the kept runs.
        """
        if width < 0:
            raise ValueError(f"clip width must not be negative, got {width}")
        if self.width <= width:
            return self
        kept: list[Segment] = []
        remaining = width
        for seg in self._segments:
            if remaining <= 0:
                break
            if seg.width <= remaining:
                kept.append(seg)
                remaining -= seg.width
                continue
            prefix = _fit_prefix(seg.text, remaining)
            if prefix:
                kept.append(
                    Segment(prefix, seg.style, link=seg.link, action=seg.action)
                )
            break
        return Line(kept)

    def pad(self, width: int) -> Line:
        """This row widened with spaces to ``width`` columns.

        Padding never truncates; a row already at least ``width`` wide is
        returned unchanged.
        """
        if width < 0:
            raise ValueError(f"pad width must not be negative, got {width}")
        missing = width - self.width
        if missing <= 0:
            return self
        return Line((*self._segments, Segment(" " * missing)))

    # -- protocol ----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Line):
            return NotImplemented
        return self._segments == other._segments

    def __hash__(self) -> int:
        return hash(self._segments)

    def __repr__(self) -> str:
        return f"Line({self._segments!r})"


def _fit_prefix(text: str, width: int) -> str:
    """The longest prefix of ``text`` measuring at most ``width`` columns.

    Zero-width continuations (marks, joiners) stay attached to the cell they
    continue: the measurement is taken over the growing prefix, so a prefix
    never splits a cluster the way a per-character sum would.
    """
    if width <= 0:
        return ""
    taken = ""
    for index in range(len(text)):
        candidate = text[: index + 1]
        if visible_width(candidate) <= width:
            taken = candidate
        else:
            break
    return taken


@dataclass(frozen=True, slots=True)
class _CellRun:
    """One printing cell of a line: a whole grapheme cluster and its width.

    The overlay walk works in cells, not segments, so a wide glyph is one
    unit that is replaced or preserved whole.  Zero-width text is folded into
    the neighbouring cluster's ``text``: it paints nothing, so carrying it
    along is enough for a rebuild to preserve it.
    """

    text: str
    width: int
    style: Style
    link: str | None = None
    action: str | None = None


def _line_cells(line: Line) -> list[_CellRun]:
    """``line`` decomposed into one :class:`_CellRun` per printing cell.

    Segments are split through the kernel's one cluster scanner
    (:func:`motui.kernel.text._cell_spans`), so the boundaries the overlay
    composes on are the boundaries the measure and the cut already use.  A
    run's style and payloads come from its segment; zero-width characters
    between clusters ride on the preceding cluster of the same segment.  A
    segment holding only non-printing characters contributes no cell.
    """
    cells: list[_CellRun] = []
    for seg in line.segments:
        text = seg.text
        if not text:
            continue
        first = len(cells)
        pos = 0
        pending = ""
        for start, end, width in _cell_spans(text):
            gap = text[pos:start]
            if len(cells) > first:
                last = cells[-1]
                cells[-1] = _CellRun(
                    last.text + gap,
                    last.width,
                    last.style,
                    last.link,
                    last.action,
                )
            else:
                pending += gap
            cells.append(
                _CellRun(
                    pending + text[start:end],
                    width,
                    seg.style,
                    seg.link,
                    seg.action,
                )
            )
            pending = ""
            pos = end
        if len(cells) > first and pos < len(text):
            last = cells[-1]
            cells[-1] = _CellRun(
                last.text + text[pos:],
                last.width,
                last.style,
                last.link,
                last.action,
            )
    return cells


def _transparent(cell: _CellRun) -> bool:
    """Whether ``cell`` lets the layer below show through.

    The exact rule from the composition contract: a plain space with the
    default style and no inline payloads.
    """
    return (
        cell.text == " "
        and cell.style == Style()
        and cell.link is None
        and cell.action is None
    )


def _paint_cells(top: list[_CellRun], base: list[_CellRun]) -> Line:
    """Compose top cells over base cells into a fresh row.

    Columns are addressed through ``base_slots`` (one base cell index per
    column).  A non-transparent top cell picks the base style under its
    first column, removes every base cell it touches -- wide glyphs whole --
    and keeps its own glyph and payloads.  Leftover columns of an erased
    wide glyph become one-column blanks in that glyph's style, so no
    continuation is ever left dangling and an underlying band stays
    continuous.  The output is fused back into runs by equal style and
    payload, which keeps an untouched row equal to its input.
    """
    starts: list[int] = []
    slots: list[int] = []
    for index, cell in enumerate(base):
        starts.append(len(slots))
        slots.extend([index] * cell.width)
    # A base cell with width 0 would occupy no slot; the scanner never
    # yields one, so ``slots`` and ``base`` stay aligned.
    total = len(slots)
    top_width = 0
    for cell in top:
        top_width += cell.width
    if top_width > total:
        total = top_width

    placements: dict[int, _CellRun] = {}
    removed: set[int] = set()
    pos = 0
    for cell in top:
        if not _transparent(cell):
            base_style = (
                base[slots[pos]].style if pos < len(slots) else Style()
            )
            placements[pos] = _CellRun(
                cell.text,
                cell.width,
                base_style.merge(cell.style),
                cell.link,
                cell.action,
            )
            for col in range(pos, min(pos + cell.width, len(slots))):
                removed.add(slots[col])
        pos += cell.width

    out: list[_CellRun] = []
    col = 0
    while col < total:
        placed = placements.get(col)
        if placed is not None:
            out.append(placed)
            col += placed.width
            continue
        if col < len(slots):
            index = slots[col]
            cell = base[index]
            if index not in removed:
                # A surviving cell always starts here: a top cell that
                # skipped its first column would have removed the whole cell.
                out.append(cell)
                col += cell.width
                continue
            out.append(_CellRun(" ", 1, cell.style))
            col += 1
            continue
        out.append(_CellRun(" ", 1, Style()))
        col += 1
    return Line(fuse(
        Segment(cell.text, cell.style, link=cell.link, action=cell.action)
        for cell in out
        if cell.text
    ))


def rest(row: Line, width: int, band: Style) -> Line:
    """One row on its band: trim then fill at the trimmed row's width.

    The band rests under the row's own segments (the Rich
    ``Padding(style=...)`` rule); the ``NONE`` fast path leaves a resting
    row byte-for-byte unchanged.  The row widgets share this one lay-down
    beside the public :meth:`Line.clip` / :meth:`Line.fill` pair -- the
    trim is :meth:`Line._fit`, the same truncation ``clip(ELLIPSIS, w)``
    performs.
    """
    fitted = row._fit(width)
    return fitted if band == NONE else fitted.fill(fitted.width, band)


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
    columns measured with :func:`motui.kernel.text.visible_width`, not
    character counts.  The range clamps into the line's width -- a selection
    column past a short row simply reaches the row's end -- and a boundary
    landing inside a multi-column cluster snaps **down** to that cluster's
    start through :func:`motui.kernel.text.index_pair_at_columns`, which runs
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

    Same break rule as :func:`motui.kernel.text.wrap_text`: spaces preferred,
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


def _wrap_chars(line: Line, width: int) -> list[Line]:
    """Hard character wrap of ``line`` into rows of ``width`` columns.

    Walks the line's printing cells (:func:`motui.kernel.text._cell_spans`)
    and starts a new row before any cell that would overflow, so a grapheme
    cluster never straddles a break.  A cluster wider than ``width`` owns its
    row and the caller's closing :meth:`Line._fit` trims it with the marker.
    Styles and inline payloads survive through :func:`slice_line`; an empty
    line (or ``width <= 0``) yields ``[Line()]``.
    """
    if width <= 0:
        return [Line()]
    if line.width <= width:
        return [line]
    text = line.text
    spans: list[tuple[int, int]] = []
    start = 0
    used = 0
    for cell_start, _cell_end, cell_width in _cell_spans(text):
        if used and used + cell_width > width:
            spans.append((start, cell_start))
            start = cell_start
            used = 0
        used += cell_width
    spans.append((start, len(text)))
    return [slice_line(line, s, e) for s, e in spans]


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

@dataclass(frozen=True, slots=True, kw_only=True)
class Surface:
    """A block of rows at one content width.

    Direct construction is not the contract (fields are not a constructor
    argument): :meth:`of` and :meth:`clipped` are the builders that guarantee
    every row is at most ``width`` cells wide; :meth:`of` pads short rows and
    :meth:`clipped` leaves them short.  :attr:`rows` is still exposed for
    readers, as a tuple.

    The value is also a read-only sequence of rows (``len``, indexing,
    iteration), so a caller written against the 1.x ``list[Line]`` return can
    keep walking a render result without materializing it.  It is **not** a
    mutable list: ``rows`` is a tuple and the value is frozen.
    """

    width: int = 0
    rows: tuple[Line, ...] = ()

    def __post_init__(self) -> None:
        if self.width < 0:
            raise ValueError(f"surface width must not be negative, got {self.width}")
        object.__setattr__(self, "rows", tuple(self.rows))

    @property
    def height(self) -> int:
        """Number of rows in the surface."""
        return len(self.rows)

    # -- sequence protocol -------------------------------------------------

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[Line]:
        return iter(self.rows)

    @overload
    def __getitem__(self, index: int) -> Line: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Line, ...]: ...

    def __getitem__(self, index: int | slice) -> Line | tuple[Line, ...]:
        return self.rows[index]

    # -- construction ------------------------------------------------------

    @classmethod
    def blank(cls, size: Size) -> Surface:
        """An empty surface of ``size``: ``height`` empty rows."""
        if size.width < 0 or size.height < 0:
            raise ValueError(
                f"surface size must be non-negative, got {size.width}x{size.height}"
            )
        return cls(width=size.width, rows=tuple(Line() for _ in range(size.height)))

    @classmethod
    def of(cls, rows: Sequence[Line], width: int, *, pad: bool = True) -> Surface:
        """A surface of ``rows`` normalized to at most ``width`` columns.

        An overwide row is clipped at a cell boundary, so the surface invariant
        ``line.width <= width`` holds for every row it hands back.  With
        ``pad`` (the default, the component contract) a short row is also
        grown to exactly ``width`` columns; with ``pad=False`` the row keeps
        its natural width.  :meth:`clipped` is the named ``pad=False`` form.
        """
        if width < 0:
            raise ValueError(f"surface width must not be negative, got {width}")
        if pad:
            normalized = tuple(row._cut_width(width).pad(width) for row in rows)
        else:
            normalized = tuple(row._cut_width(width) for row in rows)
        return cls(width=width, rows=normalized)

    @classmethod
    def clipped(cls, rows: Sequence[Line], width: int) -> Surface:
        """A surface of ``rows`` clipped to ``width``; short rows stay short.

        The builder migrating components return through this wave: clipping
        enforces the row invariant without the padding that would change the
        bytes the painter writes (the 1.x render output was unpadded too).
        """
        return cls.of(rows, width, pad=False)

