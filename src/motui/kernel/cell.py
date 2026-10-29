"""Cells, styled runs, rows and surfaces -- the 2.0 row model.

All four are immutable values. Construction is the content door: control
characters are deleted and tabs become one space, so content can never
drive the terminal."""

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
    """Delete control characters and normalize tabs: content must never carry
    terminal commands. Width is preserved."""
    if "\t" in text:
        text = text.replace("\t", " ")  # the repo's tab rule: one tab, one space
    if _CONTROL_RE.search(text) is None:
        return text  # the fast path: the same string, nothing allocated
    return _CONTROL_RE.sub("", text)


@dataclass(frozen=True, slots=True)
class Cell:
    """One display cell: a character, a style and the inline payloads.

    ``char`` and both payloads pass the content door; ``link``/``action`` are
    metadata and carry no width."""

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
    """A styled run of text: frozen and hashable.

    ``text`` and ``link`` pass the content door, so a run never carries an escape
    sequence. ``link`` participates in equality; ``action`` does not, because it
    never reaches a byte."""

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
        """The content door: sanitize ``text``, ``link`` and ``action`` before any
        measurement."""
        object.__setattr__(self, "text", _cells_only(self.text))
        if self.link is not None:
            object.__setattr__(self, "link", _cells_only(self.link) or None)
        if self.action is not None:
            object.__setattr__(self, "action", _cells_only(self.action) or None)

    @property
    def width(self) -> int:
        """Display width in columns, cached after the first measure."""
        if self._width < 0:
            object.__setattr__(self, "_width", visible_width(self.text))
        return self._width

    def with_style(self, style: Style) -> Segment:
        """A copy of this run in ``style``; text, link and action ride along."""
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
        """Plain-text view (styles dropped), cached."""
        cached = self._text
        if cached is None:
            cached = "".join(seg.text for seg in self._segments)
            object.__setattr__(self, "_text", cached)
        return cached

    @property
    def width(self) -> int:
        """Display width in columns, cached."""
        cached = self._width
        if cached is None:
            cached = sum(seg.width for seg in self._segments)
            object.__setattr__(self, "_width", cached)
        return cached

    # -- sizing ------------------------------------------------------------

    def _fit(self, width: int) -> Line:
        """Truncate to ``width`` columns, marking the cut with ``…``; the marker
        inherits the last kept segment's style and payloads."""
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
        """Grow this row to ``width`` columns with ``style`` underneath; a segment's
        own colors win over the base. The ``NONE`` fast path returns ``self``."""
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
        """A fresh row of ``width`` spaces in one segment, in ``style``."""
        if width <= 0:
            return cls()
        return cls((Segment(" " * width, style),))

    # -- combination -------------------------------------------------------

    def __add__(self, other: object) -> Line:
        if not isinstance(other, Line):
            return NotImplemented
        return Line(self._segments + other._segments)

    def merge_span(self, start: int, end: int, style: Style) -> Line:
        """Merge ``style`` over the segments intersecting columns ``[start, end)``;
        payloads ride along and a miss returns ``self``."""
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

        A plain unstyled space with no payload is transparent; every other cell wins
        with ``base_style.merge(top_style)``. Wide glyphs are replaced as whole
        clusters, never halved."""
        if self.width == 0:
            return base
        for seg in self._segments:
            if (
                seg.link is not None
                or seg.action is not None
                or seg.style != NONE
                or seg.text.strip(" ")
            ):
                break
        else:
            return base if base.width >= self.width else base.pad(self.width)
        narrow = _paint_narrow(self, base)
        if narrow is not None:
            return narrow
        top_cells = _line_cells(self)
        if not any(not _transparent(cell) for cell in top_cells):
            return base if base.width >= self.width else base.pad(self.width)
        return _paint_cells(top_cells, _line_cells(base))

    # -- the 2.0 width vocabulary -----------------------------------------

    def reflow(self, mode: WrapMode, width: int) -> list[Line]:
        """Lay this row out in ``width`` columns under ``mode``: WORD/CHAR wrap,
        ELLIPSIS cuts with ``…``, CLIP cuts hard, OVERFLOW returns the row."""
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
        """The single-row form of :meth:`reflow`: its first row."""
        return self.reflow(mode, width)[0]

    def _cut_width(self, width: int) -> Line:
        """A hard prefix no wider than ``width`` columns; a wide glyph that would
        straddle the edge is dropped."""
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
        """This row widened with spaces to ``width`` columns; never truncates."""
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
    """The longest prefix measuring at most ``width`` columns; zero-width
    continuations stay attached."""
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
    """One printing cell of a line: a whole grapheme cluster and its width;
    zero-width text is folded into its neighbour."""

    text: str
    width: int
    style: Style
    link: str | None = None
    action: str | None = None


def _narrow_widths(line: Line) -> bool:
    """Whether every glyph in ``line`` occupies exactly one column."""
    return all(not seg.text or seg.width == len(seg.text) for seg in line.segments)


def _paint_narrow(top: Line, base: Line) -> Line | None:
    """Compose two all-narrow rows run by run (the fast path); ``None`` sends wide
    input to the cluster pump."""
    if not _narrow_widths(top) or not _narrow_widths(base):
        return None
    base_width = base.width
    total = max(top.width, base_width)
    #: Opaque top spans ``(start, end, text, style, link, action)``; the
    #: transparent gaps between them never enter the list.
    spans: list[tuple[int, int, str, Style, str | None, str | None]] = []
    column = 0
    for seg in top.segments:
        text = seg.text
        if not text:
            continue
        if seg.style != NONE or seg.link is not None or seg.action is not None:
            spans.append(
                (column, column + len(text), text, seg.style, seg.link, seg.action)
            )
        else:
            start = None
            for index, char in enumerate(text):
                if char != " ":
                    if start is None:
                        start = index
                elif start is not None:
                    spans.append(
                        (
                            column + start,
                            column + index,
                            text[start:index],
                            NONE,
                            None,
                            None,
                        )
                    )
                    start = None
            if start is not None:
                spans.append(
                    (column + start, column + len(text), text[start:], NONE, None, None)
                )
        column += len(text)
    #: Base runs ``(start, end, text, style, link, action)``, contiguous.
    #: Base runs ``(start, end, segment)``, contiguous.
    runs: list[tuple[int, int, Segment]] = []
    column = 0
    for seg in base.segments:
        text = seg.text
        if not text:
            continue
        runs.append((column, column + len(text), seg))
        column += len(text)
    #: Output runs accumulated as text parts, fused on append and built once.
    pieces: list[tuple[list[str], Style, str | None, str | None]] = []

    def push_segment(seg: Segment) -> None:
        if not seg.text:
            return
        if (
            pieces
            and pieces[-1][1] == seg.style
            and pieces[-1][2] == seg.link
            and pieces[-1][3] == seg.action
        ):
            pieces[-1][0].append(seg.text)
        else:
            pieces.append(([seg.text], seg.style, seg.link, seg.action))

    def push(
        text: str, style: Style, link: str | None, action: str | None
    ) -> None:
        if not text:
            return
        if (
            pieces
            and pieces[-1][1] == style
            and pieces[-1][2] == link
            and pieces[-1][3] == action
        ):
            pieces[-1][0].append(text)
        else:
            pieces.append(([text], style, link, action))

    index = 0

    def emit_base(start: int, end: int) -> None:
        nonlocal index
        while start < end:
            while index < len(runs) and runs[index][1] <= start:
                index += 1
            if index >= len(runs):
                push(" " * (end - start), NONE, None, None)
                return
            run_start, run_end, seg = runs[index]
            take = min(end, run_end)
            if start == run_start and take == run_end:
                push_segment(seg)
            else:
                push(
                    seg.text[start - run_start : take - run_start],
                    seg.style,
                    seg.link,
                    seg.action,
                )
            start = take

    cursor = 0
    for start, end, text, style, link, action in spans:
        if start > cursor:
            stop = min(start, base_width)
            if cursor < stop:
                emit_base(cursor, stop)
                cursor = stop
            if cursor < start:
                push(" " * (start - cursor), NONE, None, None)
        low = start
        while low < end:
            if low >= base_width:
                push(text[low - start :], style, link, action)
                break
            while index < len(runs) and runs[index][1] <= low:
                index += 1
            if index >= len(runs):
                push(text[low - start :], style, link, action)
                break
            _run_start, run_end, base_seg = runs[index]
            take = min(end, run_end)
            push(
                text[low - start : take - start],
                base_seg.style.merge(style),
                link,
                action,
            )
            low = take
        cursor = end
    if cursor < base_width:
        emit_base(cursor, base_width)
    covered = max(cursor, base_width)
    if total > covered:
        push(" " * (total - covered), NONE, None, None)
    return Line(
        Segment("".join(parts), style, link=link, action=action)
        for parts, style, link, action in pieces
    )


def _line_cells(line: Line) -> list[_CellRun]:
    """Decompose ``line`` into one :class:`_CellRun` per printing cell, using the
    kernel's one cluster scanner."""
    cells: list[_CellRun] = []
    for seg in line.segments:
        text = seg.text
        if not text:
            continue
        if text.isascii():
            # ASCII has no combining marks and no wide clusters: one cell per
            # character, measured without the general cluster scanner.
            cells.extend(
                _CellRun(char, 1, seg.style, seg.link, seg.action) for char in text
            )
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
    """Whether ``cell`` lets the layer below show through: an unstyled space with
    no payloads."""
    return (
        cell.text == " "
        and cell.style == Style()
        and cell.link is None
        and cell.action is None
    )


def _paint_cells(top: list[_CellRun], base: list[_CellRun]) -> Line:
    """Compose top cells over base cells; an erased wide glyph leaves one-column
    blanks in its style, so no continuation is ever left dangling."""
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
    """Trim the row to ``width`` and lay ``band`` underneath; the ``NONE`` fast
    path leaves a resting row unchanged."""
    fitted = row._fit(width)
    return fitted if band == NONE else fitted.fill(fitted.width, band)


def action_at(line: Line, col: int) -> tuple[str, int, int] | None:
    """The inline action under column ``col`` as ``(action, start, end)`` or
    ``None``; intervals are left-closed, right-open."""
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
    """The sub-line covering ``line.text[start:end]``, keeping styles; payloads
    ride along and tabs inside the slice become spaces."""
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
    """The sub-line covering display columns ``[start, end)``; boundaries snap
    down to the cluster start, so a cluster is never halved."""
    if start >= end:
        return Line()
    text = line.text
    return slice_line(line, *index_pair_at_columns(text, start, end))


def wrap_line(line: Line, width: int) -> list[Line]:
    """Word-aware wrap into rows of at most ``width`` columns, sharing the break
    rule with :func:`motui.kernel.text.wrap_text`."""
    if width <= 0:
        return [Line()]
    text = line.text
    if text == "":
        return [Line()]
    text = _normalize_tabs(text)
    return [slice_line(line, s, e) for s, e in wrap_spans(text, width)]


def _wrap_chars(line: Line, width: int) -> list[Line]:
    """Hard character wrap; a cluster never straddles a break."""
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
    """Coalesce adjacent runs with equal styles and payloads; differently linked
    runs must not merge into one link span."""
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
    """Apply ``base`` underneath attribute-only segments; a segment with its own
    color keeps that style absolute. Payloads ride along."""
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

    Builders :meth:`of` and :meth:`clipped` enforce ``line.width <= width``;
    direct construction is not the contract. Reads as an immutable sequence of
    rows."""

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

    def overlay(self, base: Surface) -> Surface:
        """Paint this surface over ``base`` row by row; normalized through
        :meth:`of`, so every row is exactly the wider width. ``self`` is the top."""
        width = max(self.width, base.width)
        height = max(self.height, base.height)
        rows = [
            (
                self.rows[index] if index < self.height else Line()
            ).overlay(base.rows[index] if index < base.height else Line())
            for index in range(height)
        ]
        return Surface.of(rows, width)

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
        """A surface of ``rows`` with every row at most ``width`` columns; ``pad``
        grows short rows to exactly ``width``, ``pad=False`` keeps them short."""
        if width < 0:
            raise ValueError(f"surface width must not be negative, got {width}")
        if pad:
            normalized = tuple(row._cut_width(width).pad(width) for row in rows)
        else:
            normalized = tuple(row._cut_width(width) for row in rows)
        return cls(width=width, rows=normalized)

    @classmethod
    def clipped(cls, rows: Sequence[Line], width: int) -> Surface:
        """A surface of ``rows`` clipped to ``width``; short rows stay short (no
        padding)."""
        return cls.of(rows, width, pad=False)

