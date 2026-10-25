"""Cells, styled runs, rows and surfaces -- the 2.0 row model.

A :class:`Cell` is the write face: one character with its style and its two
inline payloads.  A :class:`Segment` is the same run in its run-length form,
which is what a :class:`Line` holds; a :class:`Surface` is a block of lines
at one content width.  All four are immutable values.

Construction is the content door.  A control character (C0, DEL, C1) inside
content would drive the terminal instead of painting cells, so ``Cell`` and
``Segment`` delete those characters and normalize a tab to one space -- the
same rule the 1.x ``core.lines`` door applies.  The kernel never builds
terminal bytes; SGR rendering (``Line.styled``) is deliberately absent and
belongs to the terminal layer in a later wave.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache

from wcwidth import wcswidth, wcwidth

from .geom import Size

__all__ = ["Cell", "Line", "Segment", "Style", "Surface"]


#: Control characters a rendered cell may never carry: C0 with the tab set
#: aside (it has its own rule), DEL, and the C1 range as defense in depth.
#: The set is explicit rather than ``str.isprintable()`` because that test
#: would also reject the zero-width format characters (ZWJ, variation
#: selectors, combining marks) emoji and accented runs are built from.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")


def _cells_only(text: str) -> str:
    """The content door: ``text`` as display cells, never terminal commands.

    A tab is normalized to one space (the repo's tab rule) instead of being
    deleted, because it occupies one column; the returned string therefore
    measures exactly as wide as the input did.  Clean text comes back as the
    same string; the transform is idempotent.
    """
    if "\t" in text:
        text = text.replace("\t", " ")
    if _CONTROL_RE.search(text) is None:
        return text
    return _CONTROL_RE.sub("", text)


@lru_cache(maxsize=4096)
def _text_width(text: str) -> int:
    """Display width in columns, by the ``wcwidth`` cluster measure.

    Sanitized content contains no control character, so ``wcswidth`` is the
    whole rule; the per-character fallback only keeps a caller that bypassed
    the door from receiving ``-1``.
    """
    width = wcswidth(text)
    if width is None or width < 0:
        return sum(max(0, wcwidth(ch)) for ch in text)
    return width


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
        if _text_width(candidate) <= width:
            taken = candidate
        else:
            break
    return taken


@dataclass(frozen=True, slots=True)
class Style:
    """A transitional, rendering-free style carrier.

    W1 moves the real ``core.style.Style`` into the kernel and replaces this
    placeholder.  Until then a cell only needs an equality-comparable value
    to carry; no SGR construction lives in the kernel.
    """

    fg: object = None
    bg: object = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False
    strike: bool = False


@dataclass(frozen=True, slots=True)
class Cell:
    """One display cell: a character, a style and the inline payloads.

    ``char`` and ``link`` pass through the content door at construction;
    ``link`` and ``action`` are metadata, so neither contributes width.
    A control-only ``char`` becomes the empty string rather than raising:
    the door's contract is to delete, and an empty cell paints nothing.
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
    """A styled run of text: the run-length unit a :class:`Line` holds.

    ``text`` and ``link`` pass through the content door before the lazy
    width cache is read, so the door and the measure can never disagree.
    ``link`` participates in equality (a changed link must repaint a row);
    ``action`` does not (it never reaches a byte, so it must not make two
    visually equal rows compare different).  This is the 1.x segment model,
    copied rather than imported so the kernel stays a leaf.
    """

    text: str
    style: Style = Style()
    link: str | None = None
    action: str | None = field(default=None, compare=False)
    #: Derived cache: the run's display width, invisible to eq/hash/repr.
    _width: int = field(init=False, compare=False, repr=False, default=-1)

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _cells_only(self.text))
        if self.link is not None:
            object.__setattr__(self, "link", _cells_only(self.link) or None)

    @property
    def width(self) -> int:
        """Display width in columns (``link`` and ``action`` contribute none)."""
        if self._width < 0:
            object.__setattr__(self, "_width", _text_width(self.text))
        return self._width

    def with_style(self, style: Style) -> "Segment":
        """A copy of this run in ``style``; text and payloads ride along."""
        return Segment(self.text, style, link=self.link, action=self.action)


class Line:
    """One immutable visual row made of styled :class:`Segment` values.

    The line is the run-length view a painter and a container pass around;
    equality and hashing are over the segment tuple, so a row is a value.
    """

    __slots__ = ("_segments", "_text", "_width")

    def __init__(self, segments: Iterable[Segment] = ()) -> None:
        object.__setattr__(self, "_segments", tuple(segments))
        # Derived caches: text and width are pure functions of the segments,
        # computed at most once and invisible to eq/hash.
        object.__setattr__(self, "_text", None)
        object.__setattr__(self, "_width", None)

    # -- immutability ------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    # -- construction ------------------------------------------------------

    @classmethod
    def from_text(cls, text: str, style: Style | None = None) -> "Line":
        """A line holding ``text`` in one segment (``""`` -> empty line)."""
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
        """Display width in columns -- the sum of the segments' widths."""
        if self._width is None:
            object.__setattr__(
                self, "_width", sum(seg.width for seg in self._segments)
            )
        return self._width

    # -- value semantics ---------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Line):
            return NotImplemented
        return self._segments == other._segments

    def __hash__(self) -> int:
        return hash(self._segments)

    def __repr__(self) -> str:
        return f"Line({self._segments!r})"

    # -- sizing ------------------------------------------------------------

    def clip(self, width: int) -> "Line":
        """A prefix of this row no wider than ``width`` columns.

        A cut never splits a cell: a double-width character that would
        straddle the edge is dropped, leaving the line narrower than the
        limit.  Styling and inline payloads ride along on the kept runs.
        This is the minimal form for W0a; W2.5 replaces it with the shared
        ``reflow`` vocabulary.
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

    def pad(self, width: int) -> "Line":
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


@dataclass(frozen=True, slots=True, kw_only=True)
class Surface:
    """A block of rows at one content width.

    Direct construction is not the contract (fields are not a constructor
    argument): :meth:`of` is the builder that guarantees every row is exactly
    ``width`` cells wide, clipped or padded.  :attr:`rows` is still exposed
    for readers, as a tuple.
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

    @classmethod
    def blank(cls, size: Size) -> "Surface":
        """An empty surface of ``size``: ``height`` empty rows."""
        if size.width < 0 or size.height < 0:
            raise ValueError(
                f"surface size must be non-negative, got {size.width}x{size.height}"
            )
        return cls(width=size.width, rows=tuple(Line() for _ in range(size.height)))

    @classmethod
    def of(cls, rows: Sequence[Line], width: int) -> "Surface":
        """A surface of ``rows`` normalized to exactly ``width`` columns.

        A short row is padded with spaces and an overwide row is clipped at a
        cell boundary, so the surface invariant ``line.width <= width``
        holds for every row it hands back.
        """
        if width < 0:
            raise ValueError(f"surface width must not be negative, got {width}")
        return cls(width=width, rows=tuple(row.clip(width).pad(width) for row in rows))
