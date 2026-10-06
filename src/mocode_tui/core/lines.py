"""Immutable row model: :class:`Segment` and :class:`Line`.

A :class:`Line` is exactly one visual row: an ordered tuple of styled
:class:`Segment` values.  :func:`wrap_line` shares
:func:`mocode_tui.core.text.wrap_spans` with :func:`mocode_tui.core.text.wrap_text`, so
both wrap with the same break rule.  All width logic comes from
:func:`mocode_tui.core.text.visible_width` -- directly, or through
:func:`mocode_tui.core.text.fit_text` for per-segment truncation and
:func:`mocode_tui.core.text.index_pair_at_columns` for the column-space cut,
whose scanner lives beside the measure it shares its cluster rules with;
nothing here re-measures text.

Two module-level segment utilities round the model out: :func:`fuse`
coalesces runs that share a style, and :func:`overlay` applies one base style
underneath a segment list following the colored-vs-attribute rule.

Cutting lives here too, in two offset spaces: :func:`slice_line` cuts by
character offsets into ``line.text`` (what word wrapping needs) and
:func:`cut_line` cuts by display columns (what column-addressed overlays such
as text selection need).  ``cut_line`` is built on ``slice_line`` -- one
per-segment cut, one set of width rules, never a second copy of either.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .style import NONE, RESET, Style
from .text import ELLIPSIS, index_pair_at_columns, wrap_spans, fit_text, visible_width

__all__ = [
    "ELLIPSIS",
    "Line",
    "Segment",
    "cut_line",
    "fuse",
    "overlay",
    "slice_line",
    "wrap_line",
]


@dataclass(frozen=True)
class Segment:
    """A styled run of text.  Segments are frozen and hashable."""

    text: str
    style: Style = Style()
    #: Derived cache: the segment's display width in columns, computed at
    #: most once per instance (the ``Style._prefix`` pattern) and invisible
    #: to eq/hash/repr.  A row is re-measured frame after frame -- by the
    #: painter, the padding, the splice -- through the very same Segment
    #: values, so the one walk lands on the value, not on every reader.
    _width: int = field(init=False, compare=False, repr=False, default=-1)

    @property
    def width(self) -> int:
        """Display width in columns, via :func:`mocode_tui.core.text.visible_width`."""
        if self._width < 0:
            object.__setattr__(self, "_width", visible_width(self.text))
        return self._width


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
        through :func:`mocode_tui.core.text.visible_width`)."""
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
        The rendering is cached: a line is a value, and the painter re-styles
        the same row frame after frame.
        """
        if self._styled is None:
            parts: list[str] = []
            for seg in self._segments:
                if not seg.text:
                    continue  # a zero-width segment paints nothing at all
                if parts:
                    parts.append(RESET)  # a clean slate: no attribute crosses a boundary
                parts.append(seg.style.prefix() + seg.text)
            object.__setattr__(
                self, "_styled", "".join(parts) + RESET if parts else ""
            )
        return self._styled

    # -- sizing ------------------------------------------------------------

    def fit(self, width: int) -> "Line":
        """Truncate to ``width`` columns, marking the cut with ``…``.

        Over-wide lines lose their tail; the marker inherits the style of the
        last kept segment.  ``width <= 0`` yields an empty line, and a line
        that already fits is returned unchanged.
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
            # Same measurement root as core.text.ellipsize_tail: cut the
            # segment through fit_text so clusters that measure wider (or
            # narrower) than their characters cannot overflow the budget.
            piece = fit_text(seg.text, budget - used)
            if piece:
                kept.append(Segment(piece, seg.style))
                used += visible_width(piece)
            break
        marker_style = kept[-1].style if kept else Style()
        if kept and kept[-1].text:
            # Marker shares the truncated run's style: fuse into one segment.
            kept[-1] = Segment(kept[-1].text + ELLIPSIS, marker_style)
        else:
            kept.append(Segment(ELLIPSIS, marker_style))
        return Line(kept)

    def pad_to(self, width: int) -> "Line":
        """Pad with plain spaces up to ``width``; wide enough already -> self."""
        gap = width - self.width
        if gap <= 0:
            return self
        return self + Line.from_text(" " * gap)

    @classmethod
    def filled(cls, width: int, style: Style = NONE) -> "Line":
        """A full-width row of spaces in one segment: the band/padding primitive.

        Equivalent to ``Line.from_text(" " * width, style).fit(width)`` but
        expressed once for the components that render solid background rows
        (``Message``/``ToolBlock``/``EditBlock`` build their bands on it)
        and for custom components.  ``width <= 0`` yields an empty line.
        """
        if width <= 0:
            return cls()
        return cls((Segment(" " * width, style),))

    # -- combination -------------------------------------------------------

    def __add__(self, other: object) -> "Line":
        if not isinstance(other, Line):
            return NotImplemented
        return Line(self._segments + other._segments)

    # -- protocol ----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Line):
            return NotImplemented
        return self._segments == other._segments

    def __hash__(self) -> int:
        return hash(self._segments)

    def __repr__(self) -> str:
        return f"Line({self._segments!r})"


def slice_line(line: Line, start: int, end: int) -> Line:
    """The sub-line covering ``line.text[start:end]``, keeping per-segment styles.

    Offsets are character offsets into ``line.text`` (the concatenation of the
    segments, so a slice may start or end mid-segment); tabs inside a kept
    slice become single spaces (the module's documented tab rule) so widths
    stay consistent.  An empty range yields an empty line.  This is the cut
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
            out.append(Segment(piece.replace("\t", " "), seg.style))
    return Line(out)


def cut_line(line: Line, start: int, end: int) -> Line:
    """The sub-line covering display columns ``[start, end)``.

    The column-space counterpart of :func:`slice_line`: offsets are terminal
    columns measured with :func:`mocode_tui.core.text.visible_width`, not
    character counts.  The range clamps into the line's width -- a selection
    column past a short row simply reaches the row's end -- and a boundary
    landing inside a multi-column cluster snaps **down** to that cluster's
    start through :func:`mocode_tui.core.text.index_pair_at_columns`, which runs
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

    Same break rule as :func:`mocode_tui.core.text.wrap_text`: spaces preferred,
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
    text = text.replace("\t", " ")
    return [slice_line(line, s, e) for s, e in wrap_spans(text, width)]


def fuse(segments: Iterable[Segment]) -> list[Segment]:
    """Coalesce adjacent runs sharing a style into single segments.

    Only *adjacent* segments with equal styles merge, and they merge in
    order; a segment with a style of its own keeps it.  Empty segments stay
    (a zero-width run paints nothing at all, so dropping it is the caller's
    choice).  One segment in, one segment out.
    """
    out: list[Segment] = []
    for seg in segments:
        if out and out[-1].style == seg.style:
            out[-1] = Segment(out[-1].text + seg.text, seg.style)
        else:
            out.append(seg)
    return out


def overlay(base: Style, segments: Iterable[Segment]) -> list[Segment]:
    """Apply ``base`` underneath ``segments``: the colored-vs-attribute rule.

    A segment that carries a color of its own (``fg`` or ``bg`` set) keeps
    that style absolute; an attribute-only segment (bold, italic, underline,
    ...) is merged onto ``base``, so a band painted underneath still shows
    through the emphasis.  One segment in, one segment out.
    """
    return [
        Segment(
            seg.text,
            seg.style
            if seg.style.fg is not None or seg.style.bg is not None
            else base.merge(seg.style),
        )
        for seg in segments
    ]
