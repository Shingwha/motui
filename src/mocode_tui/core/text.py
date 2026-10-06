"""Text measurement, wrapping, and the plain-text component.

:func:`visible_width` is the single source of truth for display width in the
whole toolkit: components measure and truncate through it, and the painter
only counts rows.  It sums the one cluster scanner (:func:`_cell_spans`),
which :func:`index_at_column` reads as a second view -- an address into the
same cells -- so the column-space cut :func:`mocode_tui.core.lines.cut_line`
performs measures by the very clusters this module counts.  :func:`wrap_text`
(plain text) and :func:`wrap_spans` (offset pairs, shared with
:mod:`mocode_tui.core.lines` and the editing engine) implement one
word-aware break rule.  :class:`Text`, the simplest component, renders
through those very helpers -- which is why it lives here beside them.  The
Markdown renderer lives in :mod:`mocode_tui.widgets.markdown`.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
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
    "index_at_column",
    "index_pair_at_columns",
    "terminal_size",
    "visible_width",
    "wrap_spans",
    "wrap_text",
]

#: A tab counts as exactly one column (documented rule: no tab stops exist).
TAB_WIDTH = 1

#: Truncation marker; occupies exactly one column.
ELLIPSIS = "…"

# Grapheme-cluster rules, expressed with code points -- the runtime
# dependency stays ``wcwidth`` only.  These name the characters that
# continue a cluster instead of starting one.
_ZWJ = "\u200d"  # ZERO WIDTH JOINER: the following cell joins the cluster
_VARIATION = range(0xFE00, 0xFE10)  # variation selectors (VS16 widens its base)
_SKIN_TONE = range(0x1F3FB, 0x1F400)  # emoji modifiers
_REGIONAL = range(0x1F1E6, 0x1F200)  # regional indicators: two form one flag cell


def _cell_width(cell: str) -> int:
    """Width in columns of one printed cell: a base character with the
    variation selectors that widen it, or a regional-indicator pair."""
    width = wcswidth(cell)
    if width is None or width < 0:
        return sum(w for w in map(wcwidth, cell) if w and w > 0)
    return width


def _cell_spans(text: str) -> Iterator[tuple[int, int, int]]:
    """Yield ``(start, end, width)`` for every printing cell of ``text``.

    The toolkit's one cluster scanner: the same rule constants
    :func:`visible_width` has always run, exposed as the cells themselves
    instead of only their widths, so measurement and every column-space walk
    read the same boundaries and cannot disagree about where a cluster
    begins or ends again.  A cell is one printing base character, the
    variation selectors that widen it, and the continuation characters that
    join it; a character that starts no cell (a continuation with no base, a
    non-printable) yields nothing.
    """
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\t":
            yield (i, i + 1, TAB_WIDTH)
            i += 1
            continue
        code = ord(ch)
        if code in _REGIONAL:
            end = i + 2 if i + 1 < n and ord(text[i + 1]) in _REGIONAL else i + 1
            yield (i, end, _cell_width(text[i:end]))
            i = end
            continue
        if code in _SKIN_TONE:
            i += 1  # a modifier with no base of its own adds nothing
            continue
        width = wcwidth(ch)
        if width is None or width <= 0:
            i += 1  # a continuation with no base, or non-printable: 0 columns
            continue
        cell_end = i + 1
        while cell_end < n and ord(text[cell_end]) in _VARIATION:
            cell_end += 1  # variation selectors widen the base cell
        if cell_end == i + 1:
            cell_width = width  # the common cell: the base alone, no slice
        else:
            cell_width = _cell_width(text[i:cell_end])
        end = cell_end
        while end < n:  # every continuation character of the cluster adds 0
            nxt = text[end]
            if nxt == "\t":
                break
            code = ord(nxt)
            if code in _VARIATION or code in _SKIN_TONE or wcwidth(nxt) == 0:
                end += 1
                if nxt == _ZWJ and end < n and text[end] != "\t":
                    joined = wcwidth(text[end])
                    if joined is not None and joined > 0:
                        end += 1  # the cell a joiner introduces joins the cluster
                continue
            break
        yield (i, end, cell_width)
        i = end


def visible_width(text: str) -> int:
    """Display width of ``text`` in terminal columns, measured by grapheme
    cluster -- the toolkit's single source of truth for display width, built
    on ``wcwidth`` alone: the cluster rules are expressed with code points,
    so there is no second measure and no new runtime dependency.

    One cluster contributes the width of its first printing cell -- a base
    character together with the variation selectors that widen it, or a
    regional-indicator pair making one flag cell.  Every continuation
    character contributes 0:

    - a zero-width joiner (U+200D) joins the cell that follows it;
    - a variation selector (U+FE00-U+FE0F) widens its base (VS16 -> 2);
    - a skin-tone modifier (U+1F3FB-U+1F3FF) adds nothing;
    - two regional indicators (U+1F1E6-U+1F1FF) form one flag cell;
    - a combining mark -- anything ``wcwidth`` reports as 0 -- adds nothing,
      including one standing with no base at the start of the string.

    So ``"\\U0001F468\\u200d\\U0001F469\\u200d\\U0001F467\\u200d\\U0001F466"``
    measures 2 and ``"\\U0001F9D1\\U0001F3FD\\u200d\\U0001F4BB"`` measures 2.
    A tab contributes :data:`TAB_WIDTH` columns; every other non-printable
    character contributes 0; the empty string is 0.
    """
    if not text:
        return 0
    if text.isascii():
        # Every ASCII character is a cluster of its own, so the whole-string
        # measure is the cluster measure; a control or tab falls through,
        # wcswidth reporting no width for those.
        width = wcswidth(text)
        if width is not None and width >= 0:
            return width
    return sum(cell_width for _start, _end, cell_width in _cell_spans(text))


def index_at_column(text: str, column: int) -> int:
    """Character index of the cell that display column ``column`` lands in.

    The column walk -- the one cluster scanner :func:`visible_width` sums,
    read as an address instead of a measure, so a cut and a measurement can
    never disagree about where a cluster begins or ends.  A boundary falling
    strictly inside a multi-column cluster (a plain wide character, a
    VS16-widened base, a ZWJ run, a regional pair) resolves **down** to that
    cluster's start: read as a cut's start it keeps the cluster whole, and
    read as a cut's end it drops the cluster whole -- so a boundary never
    halves one, and the two cuts meeting at one boundary attribute the
    straddling cluster to exactly one of them.  ``column <= 0`` yields ``0``
    and a ``column`` past the last cell of ``text`` yields ``len(text)``.
    """
    return index_pair_at_columns(text, column, column)[0]


def index_pair_at_columns(text: str, first: int, second: int) -> tuple[int, int]:
    """Both boundary indices of ``[first, second)``, one scanner walk.

    :func:`index_at_column`'s semantics, resolved for two boundaries in a
    single pass -- the shape a cut needs, whose start and end each walked
    the whole prefix apart.  The floor rule is written once here: a
    boundary inside a multi-column cluster resolves down to the cluster's
    start, whatever boundary reads it.
    """
    n = len(text)
    if second <= 0:
        return (0, 0)
    if text.isascii() and text.isprintable():
        # Every printable ASCII character is a one-column cluster of its own
        # (the scanner's own rules), so a column is an index; anything a
        # terminal cannot print -- controls, a bare tab -- walks below.
        return (min(first, n), min(second, n))
    start_at_first = 0 if first <= 0 else None
    start_at_second = None
    used = 0
    for start, _end, width in _cell_spans(text):
        if used + width > second:
            start_at_second = start
            if start_at_first is None:
                start_at_first = start
            break
        if start_at_first is None and used + width > first:
            start_at_first = start
        used += width
    if start_at_first is None:
        start_at_first = n
    if start_at_second is None:
        start_at_second = n
    return (start_at_first, start_at_second)


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


def wrap_spans(text: str, width: int) -> list[tuple[int, int]]:
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
    return [text[s:e] for s, e in wrap_spans(text, width)]


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
