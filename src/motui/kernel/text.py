"""Text measurement and wrapping: the width truth and the break rule.

:func:`visible_width` is the single source of truth for display width in the
whole toolkit: components measure and truncate through it, and the painter
only counts rows.  It sums the one cluster scanner (:func:`_cell_spans`),
whose per-character width is memoized on the character (:func:`_wcwidth`),
which :func:`index_bounds_at_columns` reads as a second view -- an address
into the same cells, for any number of display columns at once -- so the
column-space cut :func:`motui.kernel.cell.cut_line` performs measures by
the very clusters this module counts.  :func:`wrap_text`
(plain text) and :func:`wrap_spans` (offset pairs, shared with
:mod:`motui.kernel.cell` and the editing engine) implement one word-aware
break rule.  The Markdown renderer lives in :mod:`motui.widgets.markdown`,
and the plain-text component beside the rows it renders through:
:class:`motui.widgets.text.Text`.

:class:`WrapMode` names *how* a row responds to a width limit; the algorithms
that consume it arrive with the 2.0 render contract (W2.5).
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from functools import lru_cache

from wcwidth import wcswidth, wcwidth

__all__ = [
    "ELLIPSIS",
    "WrapMode",
    "ellipsize_tail",
    "fit_text",
    "index_bounds_at_columns",
    "index_pair_at_columns",
    "visible_width",
    "wrap_spans",
    "wrap_text",
]


class WrapMode(Enum):
    """How a line is fitted to a width.

    ``WORD`` and ``CHAR`` may produce several rows (1..N); ``ELLIPSIS``,
    ``CLIP`` and ``OVERFLOW`` are single-row modes.  ``OVERFLOW`` is the only
    mode that may return a row wider than the limit; the container clips it
    at its own edge.
    """

    WORD = "word"
    CHAR = "char"
    ELLIPSIS = "ellipsis"
    CLIP = "clip"
    OVERFLOW = "overflow"


#: A tab counts as exactly one column (documented rule: no tab stops exist).
TAB_WIDTH = 1

#: Truncation marker; occupies exactly one column.
ELLIPSIS = "…"


def _normalize_tabs(text: str) -> str:
    """The module's tab rule, in one place: every tab becomes one space.

    A length-preserving substitution -- a tab counts :data:`TAB_WIDTH`
    column, never a jump to a tab stop -- so offsets into the normalized
    text stay valid and the wrap rule sees breakable whitespace where the
    measure counted a cell.  The one entry point for the rule: wrapping
    (:func:`wrap_text`) and the column-space cut
    (:func:`motui.kernel.cell.slice_line`) both normalize through it.
    """
    return text.replace("\t", " ")

# Grapheme-cluster rules, expressed with code points -- the runtime
# dependency stays ``wcwidth`` only.  These name the characters that
# continue a cluster instead of starting one.
_ZWJ = "\u200d"  # ZERO WIDTH JOINER: the following cell joins the cluster
_VARIATION = range(0xFE00, 0xFE10)  # variation selectors VS1..VS16
_VARIATION_SUPPLEMENT = range(0xE0100, 0xE01F0)  # VS17..VS256 (the supplement)
_SKIN_TONE = range(0x1F3FB, 0x1F400)  # emoji modifiers
_REGIONAL = range(0x1F1E6, 0x1F200)  # regional indicators: two form one flag cell

# The assigned combining marks (Mn/Me), code point range by range -- the
# generated Unicode 15.1 tables, a compact constant in place of a runtime
# ``unicodedata`` walk (field is not in the toolkit's vocabulary) and of a
# per-character list.  A mark is zero columns wherever it stands, and it can
# never start a cell of its own.  Marks assigned after this table still read
# zero through the scanner's ``wcwidth`` continuation test below, which this
# table only makes explicit.
_MARK_RANGES = (
    (0x0300, 0x036F), (0x0483, 0x0489), (0x0591, 0x05BD), (0x05BF, 0x05BF), (0x05C1, 0x05C2),
    (0x05C4, 0x05C5), (0x05C7, 0x05C7), (0x0610, 0x061A), (0x064B, 0x065F), (0x0670, 0x0670),
    (0x06D6, 0x06DC), (0x06DF, 0x06E4), (0x06E7, 0x06E8), (0x06EA, 0x06ED), (0x0711, 0x0711),
    (0x0730, 0x074A), (0x07A6, 0x07B0), (0x07EB, 0x07F3), (0x07FD, 0x07FD), (0x0816, 0x0819),
    (0x081B, 0x0823), (0x0825, 0x0827), (0x0829, 0x082D), (0x0859, 0x085B), (0x0898, 0x089F),
    (0x08CA, 0x08E1), (0x08E3, 0x0902), (0x093A, 0x093A), (0x093C, 0x093C), (0x0941, 0x0948),
    (0x094D, 0x094D), (0x0951, 0x0957), (0x0962, 0x0963), (0x0981, 0x0981), (0x09BC, 0x09BC),
    (0x09C1, 0x09C4), (0x09CD, 0x09CD), (0x09E2, 0x09E3), (0x09FE, 0x09FE), (0x0A01, 0x0A02),
    (0x0A3C, 0x0A3C), (0x0A41, 0x0A42), (0x0A47, 0x0A48), (0x0A4B, 0x0A4D), (0x0A51, 0x0A51),
    (0x0A70, 0x0A71), (0x0A75, 0x0A75), (0x0A81, 0x0A82), (0x0ABC, 0x0ABC), (0x0AC1, 0x0AC5),
    (0x0AC7, 0x0AC8), (0x0ACD, 0x0ACD), (0x0AE2, 0x0AE3), (0x0AFA, 0x0AFF), (0x0B01, 0x0B01),
    (0x0B3C, 0x0B3C), (0x0B3F, 0x0B3F), (0x0B41, 0x0B44), (0x0B4D, 0x0B4D), (0x0B55, 0x0B56),
    (0x0B62, 0x0B63), (0x0B82, 0x0B82), (0x0BC0, 0x0BC0), (0x0BCD, 0x0BCD), (0x0C00, 0x0C00),
    (0x0C04, 0x0C04), (0x0C3C, 0x0C3C), (0x0C3E, 0x0C40), (0x0C46, 0x0C48), (0x0C4A, 0x0C4D),
    (0x0C55, 0x0C56), (0x0C62, 0x0C63), (0x0C81, 0x0C81), (0x0CBC, 0x0CBC), (0x0CBF, 0x0CBF),
    (0x0CC6, 0x0CC6), (0x0CCC, 0x0CCD), (0x0CE2, 0x0CE3), (0x0D00, 0x0D01), (0x0D3B, 0x0D3C),
    (0x0D41, 0x0D44), (0x0D4D, 0x0D4D), (0x0D62, 0x0D63), (0x0D81, 0x0D81), (0x0DCA, 0x0DCA),
    (0x0DD2, 0x0DD4), (0x0DD6, 0x0DD6), (0x0E31, 0x0E31), (0x0E34, 0x0E3A), (0x0E47, 0x0E4E),
    (0x0EB1, 0x0EB1), (0x0EB4, 0x0EBC), (0x0EC8, 0x0ECE), (0x0F18, 0x0F19), (0x0F35, 0x0F35),
    (0x0F37, 0x0F37), (0x0F39, 0x0F39), (0x0F71, 0x0F7E), (0x0F80, 0x0F84), (0x0F86, 0x0F87),
    (0x0F8D, 0x0F97), (0x0F99, 0x0FBC), (0x0FC6, 0x0FC6), (0x102D, 0x1030), (0x1032, 0x1037),
    (0x1039, 0x103A), (0x103D, 0x103E), (0x1058, 0x1059), (0x105E, 0x1060), (0x1071, 0x1074),
    (0x1082, 0x1082), (0x1085, 0x1086), (0x108D, 0x108D), (0x109D, 0x109D), (0x135D, 0x135F),
    (0x1712, 0x1714), (0x1732, 0x1733), (0x1752, 0x1753), (0x1772, 0x1773), (0x17B4, 0x17B5),
    (0x17B7, 0x17BD), (0x17C6, 0x17C6), (0x17C9, 0x17D3), (0x17DD, 0x17DD), (0x180B, 0x180D),
    (0x180F, 0x180F), (0x1885, 0x1886), (0x18A9, 0x18A9), (0x1920, 0x1922), (0x1927, 0x1928),
    (0x1932, 0x1932), (0x1939, 0x193B), (0x1A17, 0x1A18), (0x1A1B, 0x1A1B), (0x1A56, 0x1A56),
    (0x1A58, 0x1A5E), (0x1A60, 0x1A60), (0x1A62, 0x1A62), (0x1A65, 0x1A6C), (0x1A73, 0x1A7C),
    (0x1A7F, 0x1A7F), (0x1AB0, 0x1ACE), (0x1B00, 0x1B03), (0x1B34, 0x1B34), (0x1B36, 0x1B3A),
    (0x1B3C, 0x1B3C), (0x1B42, 0x1B42), (0x1B6B, 0x1B73), (0x1B80, 0x1B81), (0x1BA2, 0x1BA5),
    (0x1BA8, 0x1BA9), (0x1BAB, 0x1BAD), (0x1BE6, 0x1BE6), (0x1BE8, 0x1BE9), (0x1BED, 0x1BED),
    (0x1BEF, 0x1BF1), (0x1C2C, 0x1C33), (0x1C36, 0x1C37), (0x1CD0, 0x1CD2), (0x1CD4, 0x1CE0),
    (0x1CE2, 0x1CE8), (0x1CED, 0x1CED), (0x1CF4, 0x1CF4), (0x1CF8, 0x1CF9), (0x1DC0, 0x1DFF),
    (0x20D0, 0x20F0), (0x2CEF, 0x2CF1), (0x2D7F, 0x2D7F), (0x2DE0, 0x2DFF), (0x302A, 0x302D),
    (0x3099, 0x309A), (0xA66F, 0xA672), (0xA674, 0xA67D), (0xA69E, 0xA69F), (0xA6F0, 0xA6F1),
    (0xA802, 0xA802), (0xA806, 0xA806), (0xA80B, 0xA80B), (0xA825, 0xA826), (0xA82C, 0xA82C),
    (0xA8C4, 0xA8C5), (0xA8E0, 0xA8F1), (0xA8FF, 0xA8FF), (0xA926, 0xA92D), (0xA947, 0xA951),
    (0xA980, 0xA982), (0xA9B3, 0xA9B3), (0xA9B6, 0xA9B9), (0xA9BC, 0xA9BD), (0xA9E5, 0xA9E5),
    (0xAA29, 0xAA2E), (0xAA31, 0xAA32), (0xAA35, 0xAA36), (0xAA43, 0xAA43), (0xAA4C, 0xAA4C),
    (0xAA7C, 0xAA7C), (0xAAB0, 0xAAB0), (0xAAB2, 0xAAB4), (0xAAB7, 0xAAB8), (0xAABE, 0xAABF),
    (0xAAC1, 0xAAC1), (0xAAEC, 0xAAED), (0xAAF6, 0xAAF6), (0xABE5, 0xABE5), (0xABE8, 0xABE8),
    (0xABED, 0xABED), (0xFB1E, 0xFB1E), (0xFE00, 0xFE0F), (0xFE20, 0xFE2F), (0x101FD, 0x101FD),
    (0x102E0, 0x102E0), (0x10376, 0x1037A), (0x10A01, 0x10A03), (0x10A05, 0x10A06), (0x10A0C, 0x10A0F),
    (0x10A38, 0x10A3A), (0x10A3F, 0x10A3F), (0x10AE5, 0x10AE6), (0x10D24, 0x10D27), (0x10EAB, 0x10EAC),
    (0x10EFD, 0x10EFF), (0x10F46, 0x10F50), (0x10F82, 0x10F85), (0x11001, 0x11001), (0x11038, 0x11046),
    (0x11070, 0x11070), (0x11073, 0x11074), (0x1107F, 0x11081), (0x110B3, 0x110B6), (0x110B9, 0x110BA),
    (0x110C2, 0x110C2), (0x11100, 0x11102), (0x11127, 0x1112B), (0x1112D, 0x11134), (0x11173, 0x11173),
    (0x11180, 0x11181), (0x111B6, 0x111BE), (0x111C9, 0x111CC), (0x111CF, 0x111CF), (0x1122F, 0x11231),
    (0x11234, 0x11234), (0x11236, 0x11237), (0x1123E, 0x1123E), (0x11241, 0x11241), (0x112DF, 0x112DF),
    (0x112E3, 0x112EA), (0x11300, 0x11301), (0x1133B, 0x1133C), (0x11340, 0x11340), (0x11366, 0x1136C),
    (0x11370, 0x11374), (0x11438, 0x1143F), (0x11442, 0x11444), (0x11446, 0x11446), (0x1145E, 0x1145E),
    (0x114B3, 0x114B8), (0x114BA, 0x114BA), (0x114BF, 0x114C0), (0x114C2, 0x114C3), (0x115B2, 0x115B5),
    (0x115BC, 0x115BD), (0x115BF, 0x115C0), (0x115DC, 0x115DD), (0x11633, 0x1163A), (0x1163D, 0x1163D),
    (0x1163F, 0x11640), (0x116AB, 0x116AB), (0x116AD, 0x116AD), (0x116B0, 0x116B5), (0x116B7, 0x116B7),
    (0x1171D, 0x1171F), (0x11722, 0x11725), (0x11727, 0x1172B), (0x1182F, 0x11837), (0x11839, 0x1183A),
    (0x1193B, 0x1193C), (0x1193E, 0x1193E), (0x11943, 0x11943), (0x119D4, 0x119D7), (0x119DA, 0x119DB),
    (0x119E0, 0x119E0), (0x11A01, 0x11A0A), (0x11A33, 0x11A38), (0x11A3B, 0x11A3E), (0x11A47, 0x11A47),
    (0x11A51, 0x11A56), (0x11A59, 0x11A5B), (0x11A8A, 0x11A96), (0x11A98, 0x11A99), (0x11C30, 0x11C36),
    (0x11C38, 0x11C3D), (0x11C3F, 0x11C3F), (0x11C92, 0x11CA7), (0x11CAA, 0x11CB0), (0x11CB2, 0x11CB3),
    (0x11CB5, 0x11CB6), (0x11D31, 0x11D36), (0x11D3A, 0x11D3A), (0x11D3C, 0x11D3D), (0x11D3F, 0x11D45),
    (0x11D47, 0x11D47), (0x11D90, 0x11D91), (0x11D95, 0x11D95), (0x11D97, 0x11D97), (0x11EF3, 0x11EF4),
    (0x11F00, 0x11F01), (0x11F36, 0x11F3A), (0x11F40, 0x11F40), (0x11F42, 0x11F42), (0x13440, 0x13440),
    (0x13447, 0x13455), (0x16AF0, 0x16AF4), (0x16B30, 0x16B36), (0x16F4F, 0x16F4F), (0x16F8F, 0x16F92),
    (0x16FE4, 0x16FE4), (0x1BC9D, 0x1BC9E), (0x1CF00, 0x1CF2D), (0x1CF30, 0x1CF46), (0x1D167, 0x1D169),
    (0x1D17B, 0x1D182), (0x1D185, 0x1D18B), (0x1D1AA, 0x1D1AD), (0x1D242, 0x1D244), (0x1DA00, 0x1DA36),
    (0x1DA3B, 0x1DA6C), (0x1DA75, 0x1DA75), (0x1DA84, 0x1DA84), (0x1DA9B, 0x1DA9F), (0x1DAA1, 0x1DAAF),
    (0x1E000, 0x1E006), (0x1E008, 0x1E018), (0x1E01B, 0x1E021), (0x1E023, 0x1E024), (0x1E026, 0x1E02A),
    (0x1E08F, 0x1E08F), (0x1E130, 0x1E136), (0x1E2AE, 0x1E2AE), (0x1E2EC, 0x1E2EF), (0x1E4EC, 0x1E4EF),
    (0x1E8D0, 0x1E8D6), (0x1E944, 0x1E94A), (0xE0100, 0xE01EF),
)


@lru_cache(maxsize=4096)
def _wcwidth(ch: str) -> int | None:
    """One character's ``wcwidth``, memoized.

    The scanner's innermost call -- asked for every character of every row
    it reads, and a row's characters repeat massively across frames (a CJK
    transcript's alphabet is a few hundred cells).  The answer is a pure
    function of the character, so it is cached on the character itself, the
    ``Style._prefix`` pattern: the cache keys on the value it derives from,
    nothing invalidates it, and its bound is the only thing that keeps it
    finite.  ``None`` and ``-1`` pass through unchanged, so every rule about
    what a width means stays the scanner's and does not become this
    memo's.
    """
    return wcwidth(ch)


@lru_cache(maxsize=4096)
def _is_mark(ch: str) -> bool:
    """Whether ``ch`` is a combining mark (Mn/Me) by the compact table.

    The table's own test, the one question the scanner asks it: ``in`` on a
    tuple of ranges would compare tuples, so the walk is spelled out -- with
    an early exit, the ranges being sorted -- and memoized on the character
    exactly like :func:`_wcwidth` beside it (asked only for the continuation
    characters that follow a base, and the same few hundred marks repeat
    across a transcript's whole alphabet).  The answer is a pure function of
    the character; the caller falls back to ``wcwidth`` for anything past
    the table (a mark assigned after Unicode 15.1).
    """
    code = ord(ch)
    for start, stop in _MARK_RANGES:
        if start > code:
            return False
        if code <= stop:
            return True
    return False


@lru_cache(maxsize=4096)
def _char_width(cell: str) -> int:
    """Width in columns of one printed cell: a base character with the
    variation selectors that widen it, or a regional-indicator pair.

    The multi-character cell's measure, asked only for the cells that are
    not a bare base character -- so it is memoized on the cell text, which
    repeats as massively as the characters do.
    """
    width = wcswidth(cell)
    if width is None or width < 0:
        return sum(w for w in map(_wcwidth, cell) if w and w > 0)
    return width


def _cell_spans(text: str) -> Iterator[tuple[int, int, int]]:
    """Yield ``(start, end, width)`` for every printing cell of ``text``.

    The toolkit's one cluster scanner: the same rule constants
    :func:`visible_width` has always run, exposed as the cells themselves
    instead of only their widths, so measurement and every column-space walk
    read the same boundaries and cannot disagree about where a cluster
    begins or ends again.  A cell is one printing base character, the
    variation selectors that widen it (VS1..VS16 and the VS17..VS256
    supplement), and the continuation characters that join it; a character
    that starts no cell (a continuation with no base, a non-printable)
    yields nothing.  A combining mark is a continuation wherever it stands
    -- by the compact :data:`_MARK_RANGES` table, the ``wcwidth``
    zero-width test, or both -- so it never adds a column and never starts
    a cell of its own.
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
            yield (i, end, _char_width(text[i:end]))
            i = end
            continue
        if code in _SKIN_TONE:
            i += 1  # a modifier with no base of its own adds nothing
            continue
        width = _wcwidth(ch)
        if width is None or width <= 0 or _is_mark(ch):
            i += 1  # a continuation with no base, a mark, or non-printable: 0 columns
            continue
        cell_end = i + 1
        while cell_end < n and (
            ord(text[cell_end]) in _VARIATION
            or ord(text[cell_end]) in _VARIATION_SUPPLEMENT
        ):
            cell_end += 1  # variation selectors widen the base cell
        cell_width = (
            width if cell_end == i + 1 else _char_width(text[i:cell_end])
        )  # the common cell is the base alone, no slice
        end = cell_end
        while end < n:  # every continuation character of the cluster adds 0
            nxt = text[end]
            if nxt == "\t":
                break
            code = ord(nxt)
            if (
                code in _VARIATION
                or code in _VARIATION_SUPPLEMENT
                or code in _SKIN_TONE
                or _wcwidth(nxt) == 0
                or _is_mark(nxt)
            ):
                end += 1
                if nxt == _ZWJ and end < n and text[end] != "\t":
                    joined = _wcwidth(text[end])
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

    - a combining mark (a Mn/Me code point -- the compact
      :data:`_MARK_RANGES` table, or anything ``wcwidth`` reports as 0)
      adds nothing, including one standing with no base at the start of the
      string;
    - a variation selector, VS1..VS16 (U+FE00-U+FE0F) or the VS17..VS256
      supplement (U+E0100-U+E01EF), merges into its base (VS16 widens it ->
      2; the supplement is zero width, and it can widen a base the same
      way when the tables say so);
    - a zero-width joiner (U+200D) joins the cell that follows it, so the
      joiner and the joined cell add nothing to the cluster's width;
    - a skin-tone modifier (U+1F3FB-U+1F3FF) adds nothing;
    - two regional indicators (U+1F1E6-U+1F1FF) form one flag cell -- the
      pair measures 2, a second indicator contributing 0 beyond the flag's
      own two columns, and a lone indicator keeps its 2-column cell.

    So ``"\\U0001F468\\u200d\\U0001F469\\u200d\\U0001F467\\u200d\\U0001F466"``
    measures 2, ``"\\U0001F9D1\\U0001F3FD\\u200d\\U0001F4BB"`` measures 2,
    ``"e\\u0301"`` measures 1 and ``"\\U0001F1EF\\U0001F1F5"`` measures 2.
    This is deliberately **not a full UAX #29 segmentation**: the four
    classes above are the terminal-relevant corners, and everything else
    the scanner meets follows ``wcwidth`` alone -- a character ``wcwidth``
    reports as printable starts its own cell at that width.  A tab
    contributes :data:`TAB_WIDTH` columns; every other non-printable
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


def index_pair_at_columns(text: str, first: int, second: int) -> tuple[int, int]:
    """Both boundary indices of ``[first, second)``, one scanner walk.

    The two-boundary form of :func:`index_bounds_at_columns`, for the shape
    a cut needs: its start and end resolved in a single pass.  The floor
    rule is written once there: a boundary inside a multi-column cluster
    resolves down to the cluster's start, whatever boundary reads it.
    """
    start_at, end_at = index_bounds_at_columns(text, first, second)
    return start_at, end_at


def _ascii_run_end(text: str, at: int) -> int:
    """The end of the run of printable-ASCII characters starting at ``at``."""
    n = len(text)
    end = at
    while end < n and " " <= text[end] <= "~":
        end += 1
    return end


def _ascii_run_head(text: str, at: int) -> int:
    """The first index at or after ``at`` where a run of printable ASCII begins.

    A run's second character and every character after it is a one-column
    cell of its own: a cell absorbs a printable ASCII character only by
    continuing past its predecessor, and a printable ASCII predecessor ends
    its own cell there.  So the first index whose character *and* whose
    predecessor are both printable ASCII is the first index the walk may skip
    to without asking the scanner a question -- the one statement about a run
    the fast path needs, and it is the ASCII rule and nothing else.
    """
    n = len(text)
    while at < n and not (
        " " <= text[at] <= "~" and " " <= text[at - 1] <= "~"
    ):
        at += 1
    return at


def index_bounds_at_columns(text: str, *columns: int) -> tuple[int, ...]:
    """Character index of the cell each of ``columns`` lands in, one walk.

    The boundary resolver for any number of cut points at once, answered in
    one pass -- the shape a splice needs, whose three cut points each walked
    the row's prefix apart before.  Each boundary is answered
    independently and the answers come back in the order the columns were
    given, so a caller may repeat, reorder or overlap them freely.

    The floor rule is written once here, for every boundary alike: a boundary
    inside a multi-column cluster resolves down to that cluster's start, a
    boundary at or past the last cell resolves to ``len(text)``, and
    ``column <= 0`` resolves to ``0``.

    The walk keeps one home for the cluster rules (D1).  A run of printable
    ASCII is one cell per character -- the scanner's own rule for those
    characters -- so a wholly printable-ASCII string resolves arithmetically
    and a mixed string's run resolves arithmetically too.  The one thing the
    fast path must not presume is that the run's *last* character ends a
    cluster: what follows it may be a continuation the scanner folds into
    that character's cell, so the run is skipped only up to its last
    character and the character itself is read by :func:`_cell_spans`, which
    remains the only code that decides where a cluster begins or ends.
    """
    n = len(text)
    if not columns:
        return ()
    if n == 0:
        return (0,) * len(columns)
    bounds = {column: 0 for column in columns if column <= 0}
    pending = sorted({column for column in columns if column > 0})
    if not pending:
        return tuple(bounds[column] for column in columns)
    if text.isascii() and text.isprintable():
        # One cell per character, so a column *is* an index; anything a
        # terminal cannot print -- controls, a bare tab -- walks below with
        # the scanner, which reads it as a cell of its own.
        for column in pending:
            bounds[column] = min(column, n)
        return tuple(bounds[column] for column in columns)
    used = 0  # display columns consumed before ``at``
    at = 0  # character index the walk stands at -- always a cell's start
    index = 0  # the next unresolved boundary of ``pending``
    count = len(pending)
    while index < count and at < n:
        if " " <= text[at] <= "~":
            # A run of printable ASCII, skipped up to its last character: a
            # boundary inside the run is an offset into it, and the run's
            # characters before the last cannot be part of a wider cluster,
            # so the walk skips them without a single scanner call.
            end = _ascii_run_end(text, at)
            while index < count and pending[index] < used + (end - at - 1):
                bounds[pending[index]] = at + (pending[index] - used)
                index += 1
            used += end - at - 1
            at = end - 1
        # Everything else is the scanner's: it reads the stretch up to the
        # next run the fast path may skip to -- one cell of it may end where
        # the next run begins -- and yields the cells of it, so a boundary
        # resolved there is the very cluster the measure counts, snapped
        # down to its start and never halved.
        end = _ascii_run_head(text, at + 1)
        for start, _cell_end, width in _cell_spans(text[at:end]):
            while index < count and pending[index] < used + width:
                bounds[pending[index]] = at + start
                index += 1
            used += width
            if index >= count:
                at = end
                break
        at = end
    for column in pending[index:]:
        bounds[column] = n  # a boundary at or past the last cell
    return tuple(bounds[column] for column in columns)


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


def wrap_spans(
    text: str, width: int, *, preserve_whitespace: bool = False
) -> list[tuple[int, int]]:
    """Character spans of ``text`` that make up each wrapped row.

    The break rule (shared by :func:`wrap_text` and :func:`lines.wrap_line`):
    prefer breaking at spaces, hard-break words longer than ``width``, and let
    wide characters occupy a line of their own when ``width`` is smaller than
    the character.  Whitespace at a break is dropped: leading whitespace of a
    row is skipped and trailing whitespace never extends a span.  Returns at
    least one span; ``(0, 0)`` means "one empty row".  ``text`` is expected to
    be tab-normalized (same length, so offsets stay valid).

    ``preserve_whitespace=True`` selects the **editing** rule instead: every
    character of ``text`` belongs to exactly one span (the spans are
    contiguous and concatenate back to ``text``), because in an editable
    buffer a space is content, not layout.  Leading and trailing spaces
    therefore render, and a row that would otherwise break inside a word
    backs up to the last space it holds so the word can continue whole on
    the next row; only a word with no space behind it is hard-broken.  The
    word-aware preference and the wide-character rule are the same, so
    cursor movement and rendering still read one geometry.
    """
    spans: list[tuple[int, int]] = []
    if width <= 0 or text == "":
        return [(0, 0)]
    if preserve_whitespace:
        return _wrap_spans_kept(text, width)
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


def _wrap_spans_kept(text: str, width: int) -> list[tuple[int, int]]:
    """The editing rule behind ``wrap_spans(preserve_whitespace=True)``.

    Walks the text's printing cells (:func:`_cell_spans`) and fills each row
    to ``width`` columns.  Nothing is ever dropped: a space is an ordinary
    one-column cell, a run of spaces may fill a row by itself, and the
    concatenated spans reassemble ``text`` exactly.

    The break still prefers a word boundary.  When the next cell would
    overflow and the cut would land inside a word (both the previous and the
    next character are not a space), the row backs up to just past its last
    space -- the spaces stay at the end of the row they were typed on and
    the word starts whole on the next one.  A word with no space inside the
    row (a single long token) is hard-broken at the width, and a cell wider
    than ``width`` owns its row, exactly as in the prose rule.
    """
    spans: list[tuple[int, int]] = []
    n = len(text)
    start = 0  # the row's first character
    used = 0  # the row's display width so far
    last_space = -1  # the last space cell inside the row, -1 when none
    for cell_start, cell_end, cell_width in _cell_spans(text):
        if used and used + cell_width > width:
            cut = cell_start
            if (
                last_space > start
                and text[cell_start] != " "
                and text[cell_start - 1] != " "
            ):
                cut = last_space + 1
            spans.append((start, cut))
            start = cut
            used = visible_width(text[cut:cell_start])
            last_space = -1
        if cell_width > width:
            # A cluster wider than the row owns it, even alone; a partial
            # word already in the row keeps its own row first.
            if used:
                spans.append((start, cell_start))
                start = cell_start
                used = 0
                last_space = -1
            spans.append((start, cell_end))
            start = cell_end
            continue
        used += cell_width
        if text[cell_start] == " ":
            last_space = cell_start
    if start < n:
        spans.append((start, n))
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
    text = _normalize_tabs(text)
    return [text[s:e] for s, e in wrap_spans(text, width)]
