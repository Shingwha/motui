"""Text measurement, wrapping, and the plain-text component.

:func:`visible_width` is the single source of truth for display width in the
whole toolkit: components measure and truncate through it, and the painter
only counts rows.  :func:`wrap_text` and the private :func:`_wrap_spans`
implement one shared word-aware break rule that :mod:`mocode_tui.core.lines`
reuses (with styles attached) via :func:`_wrap_spans`.  :class:`Text`, the
simplest component, renders through those very helpers -- which is why it
lives here beside them.  The Markdown renderer lives in
:mod:`mocode_tui.widgets.markdown`.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from wcwidth import wcswidth, wcwidth

from .style import Style
from .theme import Theme

if TYPE_CHECKING:
    from .lines import Line

__all__ = [
    "ELLIPSIS",
    "Text",
    "ellipsize_tail",
    "fit_text",
    "terminal_size",
    "visible_width",
    "wrap_text",
]

#: A tab counts as exactly one column (documented rule: no tab stops exist).
TAB_WIDTH = 1

#: Truncation marker; occupies exactly one column.
ELLIPSIS = "…"


def visible_width(text: str) -> int:
    """Display width of ``text`` in terminal columns.

    Uses ``wcswidth``; when the string contains non-printable characters (or
    ``wcswidth`` is unavailable/``None``), falls back to summing per-character
    ``wcwidth``.  A tab contributes :data:`TAB_WIDTH` columns; every other
    non-printable character contributes 0.  Empty string is 0.
    """
    if not text:
        return 0
    width = wcswidth(text)
    if width is not None and width >= 0:
        return width
    total = 0
    for ch in text:
        if ch == "\t":
            total += TAB_WIDTH
            continue
        w = wcwidth(ch)
        if w is None or w < 0:
            continue  # non-printable: zero columns
        total += w
    return total


def fit_text(text: str, budget: int) -> str:
    """Longest one-shot prefix of ``text`` measuring at most ``budget`` columns.

    ``budget <= 0`` yields ``""`` and text that already fits is returned
    whole.  The postcondition ``visible_width(fit_text(text, b)) <= b``
    holds for every input -- including emoji sequences whose whole-string
    measurement disagrees with the per-character sum: a VS16 selector
    widens its base character (``"\\u26a0\\ufe0f"`` measures 2 whole but 1
    per character) while a ZWJ run collapses into one cluster (a family
    emoji measures 2 whole but 8 per character).  A greedy per-character
    scan proposes the cut; the prefix is then re-measured whole and shrunk
    until it fits (VS16 direction) and grown while the next character
    still fits (ZWJ direction), so both discrepancies are corrected.  The
    cut is greedy: the returned prefix never leaves room for one more
    character, but a cluster collapse completing later in the string is
    not chased.
    """
    if budget <= 0:
        return ""
    if visible_width(text) <= budget:
        return text
    used = 0
    cut = 0
    for ch in text:
        w = visible_width(ch)
        if used + w > budget:
            break
        used += w
        cut += 1
    while cut > 0 and visible_width(text[:cut]) > budget:
        cut -= 1  # the cluster measures wider than its characters (VS16)
    while cut < len(text) and visible_width(text[: cut + 1]) <= budget:
        cut += 1  # the cluster measures narrower than its characters (ZWJ)
    return text[:cut]


def ellipsize_tail(text: str, width: int) -> str:
    """Truncate ``text`` to ``width`` columns, marking the cut with ``…`` at the end.

    Returns ``""`` for ``width <= 0``, ``"…"`` for ``width == 1`` (when the
    text does not already fit), and the text unchanged when it fits.  The
    cut comes from :func:`fit_text`, so the result never overflows
    ``width`` -- including emoji whose whole-string width differs from the
    per-character sum.
    """
    if width <= 0:
        return ""
    if visible_width(text) <= width:
        return text
    if width == 1:
        return ELLIPSIS
    return fit_text(text, width - 1) + ELLIPSIS


def _wrap_spans(text: str, width: int) -> list[tuple[int, int]]:
    """Character spans of ``text`` that make up each wrapped row.

    The break rule (shared by :func:`wrap_text` and :func:`lines.wrap_line`):
    prefer breaking at spaces, hard-break words longer than ``width``, and let
    wide characters occupy a line of their own when ``width`` is smaller than
    the character.  Whitespace at a break is dropped: leading whitespace of a
    row is skipped and trailing whitespace never extends a span.  Returns at
    least one span; ``(0, 0)`` means "one empty row".  ``text`` is expected to
    be tab-normalized (same length, so offsets stay valid).
    """
    spans: list[tuple[int, int]] = []
    if width <= 0 or text == "":
        return [(0, 0)]
    line_start = -1  # offset of the row's first kept char; -1 while row is empty
    line_end = 0  # offset just past the row's last kept char
    line_w = 0  # display width of the row so far
    pending = 0  # spaces seen since the last kept char (kept only if they fit)
    i = 0
    n = len(text)
    while i < n:
        if text[i] == " ":
            j = i
            while j < n and text[j] == " ":
                j += 1
            if line_start >= 0:
                pending += j - i  # leading spaces of an empty row are dropped
            i = j
            continue
        j = i
        while j < n and text[j] != " ":
            j += 1
        word_w = visible_width(text[i:j])
        if line_start < 0:
            if word_w <= width:
                line_start, line_end, line_w, pending = i, j, word_w, 0
            else:
                # Hard-break the over-long word; the row starts empty.
                piece_start = i
                piece_w = 0
                k = i
                while k < j:
                    cw = visible_width(text[k])
                    if piece_w and piece_w + cw > width:
                        spans.append((piece_start, k))
                        piece_start, piece_w = k, 0
                    piece_w += cw
                    k += 1
                line_start, line_end, line_w, pending = piece_start, j, piece_w, 0
        elif line_w + pending + word_w <= width:
            line_end, line_w, pending = j, line_w + pending + word_w, 0
        elif word_w <= width:
            spans.append((line_start, line_end))
            line_start, line_end, line_w, pending = i, j, word_w, 0
        else:
            spans.append((line_start, line_end))
            piece_start = i
            piece_w = 0
            k = i
            while k < j:
                cw = visible_width(text[k])
                if piece_w and piece_w + cw > width:
                    spans.append((piece_start, k))
                    piece_start, piece_w = k, 0
                piece_w += cw
                k += 1
            line_start, line_end, line_w, pending = piece_start, j, piece_w, 0
        i = j
    if line_start < 0:
        spans.append((0, 0))
    else:
        spans.append((line_start, line_end))
    return spans


def wrap_text(text: str, width: int) -> list[str]:
    """Word-aware wrap of ``text`` into rows of at most ``width`` columns.

    Breaks prefer spaces; over-long words and CJK runs are hard-broken; a wide
    character wider than ``width`` occupies a row by itself (the rows stay
    finite, so ``width == 1`` terminates).  Empty input yields ``[""]``, and
    ``width <= 0`` also yields ``[""]``.  Tabs count as one space and become
    break opportunities.
    """
    if width <= 0 or text == "":
        return [""]
    text = text.replace("\t", " ")
    return [text[s:e] for s, e in _wrap_spans(text, width)]


def terminal_size() -> tuple[int, int]:
    """Current terminal size as ``(columns, rows)``, falling back to 80x24."""
    size = shutil.get_terminal_size(fallback=(80, 24))
    return (size.columns, size.lines)


class Text:
    """A block of plain text rendered verbatim, line by line.

    ``text`` is a mutable attribute (streaming text assigns to it).  Each
    logical line (``split("\\n")``) is word-wrapped with
    :func:`wrap_text` into rows of at most ``width`` columns, so blank lines
    survive as blank rows.  Every row carries ``style`` and is ``fit`` to
    ``width`` as a final guard.

    ``style`` defaults to ``None``, which renders as the unstyled default
    (``NONE``); ``theme`` is accepted for the uniform component signature and
    carried for hosts that pass one theme down a tree of components -- plain
    text has no theme-able styles of its own.
    """

    __slots__ = ("style", "text", "theme")

    def __init__(
        self,
        text: str = "",
        *,
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        self.text = text
        self.style = style
        self.theme = theme

    def render(self, width: int) -> list[Line]:
        from .lines import Line  # deferred: lines imports this module's wrap rule

        out: list[Line] = []
        for row in self.text.split("\n"):
            for piece in wrap_text(row, width):
                out.append(Line.from_text(piece, self.style).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Text({self.text!r})"
