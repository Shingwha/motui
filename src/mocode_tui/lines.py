"""Immutable row model: :class:`Segment` and :class:`Line`.

A :class:`Line` is exactly one visual row: an ordered tuple of styled
:class:`Segment` values.  :func:`wrap_line` shares
:func:`mocode_tui.text._wrap_spans` with :func:`mocode_tui.text.wrap_text`, so
both wrap with the same break rule.  All width logic comes from
:func:`mocode_tui.text.visible_width`; nothing here re-measures text.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .style import NONE, RESET, Style
from .text import ELLIPSIS, _wrap_spans, visible_width

__all__ = ["ELLIPSIS", "Line", "Segment", "wrap_line"]


@dataclass(frozen=True)
class Segment:
    """A styled run of text.  Segments are frozen and hashable."""

    text: str
    style: Style = Style()


class Line:
    """One immutable visual row made of styled :class:`Segment` values."""

    __slots__ = ("_segments",)

    def __init__(self, segments: Iterable[Segment] = ()) -> None:
        object.__setattr__(self, "_segments", tuple(segments))

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
        return "".join(seg.text for seg in self._segments)

    @property
    def width(self) -> int:
        """Display width in columns, via :func:`mocode_tui.text.visible_width`."""
        return sum(visible_width(seg.text) for seg in self._segments)

    def styled(self) -> str:
        """SGR-escaped rendering: prefix+text per segment, one trailing RESET."""
        if not self._segments:
            return ""
        return "".join(seg.style.prefix() + seg.text for seg in self._segments) + RESET

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
            seg_w = visible_width(seg.text)
            if used + seg_w <= budget:
                kept.append(seg)
                used += seg_w
                continue
            piece: list[str] = []
            for ch in seg.text:
                ch_w = visible_width(ch)
                if used + ch_w > budget:
                    break
                piece.append(ch)
                used += ch_w
            if piece:
                kept.append(Segment("".join(piece), seg.style))
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


def _slice_line(line: Line, start: int, end: int) -> Line:
    """The sub-line covering ``text[start:end]``, keeping per-segment styles.

    Offsets refer to ``line.text``; tabs inside a kept slice become single
    spaces (the module's documented tab rule) so widths stay consistent.
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


def wrap_line(line: Line, width: int) -> list[Line]:
    """Word-aware wrap of ``line`` into rows of at most ``width`` columns.

    Same break rule as :func:`mocode_tui.text.wrap_text`: spaces preferred,
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
    return [_slice_line(line, s, e) for s, e in _wrap_spans(text, width)]
