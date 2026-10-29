"""Diff component: two texts, one line-level unified diff view.

``Diff`` computes an LCS-based unified diff at construction and on input
assignment.  The walk trims common head/tail and only tables the differing
middle; past :data:`LCS_LIMIT` line pairs it splits at lines unique to both
sides and replaces an anchorless piece wholesale.  The view is display only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from ..kernel.cell import Line, Segment, Surface
from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["LCS_LIMIT", "Diff"]

#: The most line pairs (before x after) **one** LCS table may visit.  The
#: walk runs per trimmed middle and per anchored piece of one, so this
#: bounds a single comparison's window, not the whole texts: past it the
#: region is split at its anchors, and a piece without one is replaced
#: (see the module docstring).
LCS_LIMIT = 20_000

#: The elision marker between two hunks -- the lines the hunks skip over.
ELISION = "\u2026"

#: Row kinds the constructor records.
_SAME = "same"
_DEL = "del"
_INS = "ins"
_HUNK = "hunk"
_ELIDE = "elide"

#: One built row: its kind, its text, and the gutter cell it paints behind
#: (``None`` for the rows that never carry a line number -- the ``@@``
#: headers and the elision rows).
_Row = tuple[str, str, str | None]


def _split_lines(text: str) -> list[str]:
    """The text's logical lines; a trailing newline adds none and ``""`` is empty."""
    return text.splitlines()


def _lcs_ops(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """The edit script of two line lists as ``(kind, text)`` ops, in order.

    Classic LCS table; ties prefer the deletion, so a modified line reads as
    its ``-`` row before its ``+`` row.  The caller bounds the table size.
    """
    n, m = len(before), len(after)
    # ``lengths[i][j]`` is the LCS length of before[i:] and after[j:].
    lengths = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row = lengths[i]
        below = lengths[i + 1]
        bi = before[i]
        for j in range(m - 1, -1, -1):
            if bi == after[j]:
                row[j] = below[j + 1] + 1
            else:
                row[j] = below[j] if below[j] >= row[j + 1] else row[j + 1]
    ops: list[tuple[str, str]] = []
    i = j = 0
    while i < n and j < m:
        if before[i] == after[j]:
            ops.append((_SAME, before[i]))
            i += 1
            j += 1
        elif lengths[i + 1][j] >= lengths[i][j + 1]:
            ops.append((_DEL, before[i]))
            i += 1
        else:
            ops.append((_INS, after[j]))
            j += 1
    ops.extend((_DEL, line) for line in before[i:])
    ops.extend((_INS, line) for line in after[j:])
    return ops


def _replaced(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """Every line of one region, both sides in order: the honest degradation.

    Costs exactly ``n + m`` edits, so it is never worse than the walk it
    replaces -- only coarser.  Its ops form one non-``same`` run.
    """
    return [(_DEL, line) for line in before] + [(_INS, line) for line in after]


def _anchors(before: list[str], after: list[str]) -> list[tuple[int, int]]:
    """The ``(i, j)`` pairs of lines occurring exactly once on both sides.

    Anchors allow splitting without a table.  Pairs are ordered by ``i``
    with strictly increasing ``j`` (a backwards pairing is dropped), so
    pieces partition the region.  Uniqueness is within the region only.
    """
    counts_before = Counter(before)
    counts_after = Counter(after)
    positions_after = {
        line: j for j, line in enumerate(after) if counts_after[line] == 1
    }
    anchors: list[tuple[int, int]] = []
    last = -1
    for i, line in enumerate(before):
        if counts_before[line] != 1:
            continue
        j = positions_after.get(line)
        if j is None or j <= last:
            continue
        anchors.append((i, j))
        last = j
    return anchors


def _middle_ops(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """The edit script of one region's middle: budgeted walk or replacement.

    Empty sides are pure insertions/deletions; a middle fitting
    :data:`LCS_LIMIT` pairs goes through the table; otherwise split at
    anchors and recurse, replacing only an anchorless piece.  Total cost
    never exceeds ``n + m``.
    """
    if not before:
        return [(_INS, line) for line in after]
    if not after:
        return [(_DEL, line) for line in before]
    if len(before) * len(after) <= LCS_LIMIT:
        return _lcs_ops(before, after)
    anchors = _anchors(before, after)
    if not anchors:
        return _replaced(before, after)
    ops: list[tuple[str, str]] = []
    i = j = 0
    for anchor_i, anchor_j in anchors:
        ops.extend(_ops(before[i:anchor_i], after[j:anchor_j]))
        ops.append((_SAME, before[anchor_i]))
        i, j = anchor_i + 1, anchor_j + 1
    ops.extend(_ops(before[i:], after[j:]))
    return ops


def _ops(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """The edit script of two line lists: trim common ends, walk the middle.

    Trimming keeps unchanged lines out of the table, spending the budget on
    the differing region; identical texts produce no ops.
    """
    head = 0
    while head < len(before) and head < len(after) and before[head] == after[head]:
        head += 1
    tail = 0
    while (
        tail < len(before) - head
        and tail < len(after) - head
        and before[len(before) - 1 - tail] == after[len(after) - 1 - tail]
    ):
        tail += 1
    ops = [(_SAME, line) for line in before[:head]]
    ops.extend(
        _middle_ops(
            before[head : len(before) - tail], after[head : len(after) - tail]
        )
    )
    if tail:
        ops.extend((_SAME, line) for line in before[len(before) - tail :])
    return ops


def _regions(ops: list[tuple[str, str]]) -> list[tuple[int, int]]:
    """The ``[start, stop)`` op ranges of every maximal non-``same`` run."""
    regions: list[tuple[int, int]] = []
    index = 0
    total = len(ops)
    while index < total:
        if ops[index][0] == _SAME:
            index += 1
            continue
        start = index
        while index < total and ops[index][0] != _SAME:
            index += 1
        regions.append((start, index))
    return regions


def _line_counts(ops: list[tuple[str, str]], count: int) -> tuple[int, int]:
    """The ``(before, after)`` line indices after the first ``count`` ops."""
    b = a = 0
    for kind, _text in ops[:count]:
        if kind != _INS:
            b += 1
        if kind != _DEL:
            a += 1
    return b, a


def _range(start: int, count: int) -> str:
    """One side of a hunk header: ``"start,count"`` with unified-diff numbering."""
    return f"{start + 1 if count else start},{count}"


def _elision_text(skipped: int) -> str:
    """The elision row's text: ``"… 7 lines"`` / ``"… 1 line"``."""
    return f"{ELISION} {skipped} line" + ("" if skipped == 1 else "s")


def _gutter(number: int, width: int) -> str:
    """The line-number cell: ``number`` right-aligned in one width, plus a space.

    A row shows its own side's number, so drifted versions differ.
    """
    return f"{number:>{width}} "


def _checked_context(value: int) -> int:
    """Validate a context count before any state moves; ``ValueError`` when negative."""
    if value < 0:
        raise ValueError(f"context must be >= 0, got {value}")
    return value


class Diff(Widget):
    """A line-level unified diff of two texts, rebuilt when an input is assigned.

    ``context`` (default 3) merges nearby hunks and surrounds each with
    unchanged lines; skipped stretches become ``… N lines`` rows.  Rows are
    ``@@`` headers, space/``-``/``+`` prefixed lines; deletions lose the
    danger band's weight.  ``numbers`` adds a muted right-aligned gutter.
    ``render`` reflows under ``wrap`` and caches the width's rows.
    """

    __slots__ = (
        "_after",
        "_before",
        "_context",
        "_glyphs",
        "_numbers",
        "_rendered_key",
        "_rendered_rows",
        "_rows",
        "wrap",
    )

    def __init__(
        self,
        before: str,
        after: str,
        *,
        context: int = 3,
        numbers: bool = False,
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
        wrap: WrapMode = WrapMode.ELLIPSIS,
    ) -> None:
        super().__init__(theme, styles)
        self._before = before
        self._after = after
        self._context = _checked_context(context)
        self._numbers = numbers
        self._glyphs = glyphs
        #: How an over-wide row responds to the width: ``ELLIPSIS`` (the
        #: default) truncates, ``WORD`` / ``CHAR`` wrap, ``CLIP`` cuts hard
        #: and ``OVERFLOW`` keeps the row whole for the container to clip.
        self.wrap = wrap
        # The constructor builds once, through the same private path every
        # setter takes afterwards: one build site for both.
        self._rebuild()

    # -- inputs (assigning one rebuilds) -------------------------------------

    @property
    def before(self) -> str:
        """The original text; assigning a new one rebuilds the rows."""
        return self._before

    @before.setter
    def before(self, value: str) -> None:
        self._before = value
        self._rebuild()

    @property
    def after(self) -> str:
        """The revised text; assigning a new one rebuilds the rows."""
        return self._after

    @after.setter
    def after(self, value: str) -> None:
        self._after = value
        self._rebuild()

    @property
    def context(self) -> int:
        """Unchanged lines kept around each change; assigning rebuilds the rows."""
        return self._context

    @context.setter
    def context(self, value: int) -> None:
        self._context = _checked_context(value)  # rejected: nothing was touched
        self._rebuild()

    @property
    def numbers(self) -> bool:
        """Whether the content rows carry a line-number gutter; assigning rebuilds."""
        return self._numbers

    @numbers.setter
    def numbers(self, value: bool) -> None:
        self._numbers = value
        self._rebuild()

    @property
    def glyphs(self) -> Glyphs:
        """The row-marker vocabulary; assigning a new one rebuilds the rows."""
        return self._glyphs

    @glyphs.setter
    def glyphs(self, value: Glyphs) -> None:
        self._glyphs = value
        self._rebuild()

    def _rebuild(self) -> None:
        """Recompute the rows for the current inputs and drop the cached render."""
        self._rows = self._build()
        # The one cached render: the inputs it was computed for (width,
        # theme, styles) and its rows.  ``None`` is "nothing fitted yet" --
        # a key of ``None`` cannot be mistaken for a real one, so a hit is a
        # plain equality test.  ``theme``/``styles`` join the key because the
        # bands resolve at render time: assigning one must repaint.
        self._rendered_key = None
        self._rendered_rows = None

    def _build(self) -> list[_Row]:
        """The diff as ``(kind, text, gutter)`` rows; one gutter width for the view.

        Only ``@@`` and elision rows carry no gutter.
        """
        before = _split_lines(self._before)
        after = _split_lines(self._after)
        ops = _ops(before, after)
        gutter_width = len(str(max(len(before), len(after), 1)))
        rows: list[_Row] = []
        regions = _regions(ops)
        if not regions:
            return rows  # no differences: a diff with nothing to say is empty
        # Every region's op window widened by the context it can reach: the
        # unchanged ops before and after it, never past a neighbour region
        # (so two changes close together merge below, and ones further apart
        # keep the lines between them elided).
        windows: list[tuple[int, int]] = []
        for index, (start, stop) in enumerate(regions):
            previous_stop = regions[index - 1][1] if index else 0
            next_start = regions[index + 1][0] if index + 1 < len(regions) else len(ops)
            pre = min(self._context, start - previous_stop)
            post = min(self._context, next_start - stop)
            windows.append((start - pre, stop + post))
        hunks: list[tuple[int, int]] = []
        for start, stop in windows:
            if hunks and start <= hunks[-1][1]:  # two windows meet: one hunk
                hunks[-1] = (hunks[-1][0], max(hunks[-1][1], stop))
            else:
                hunks.append((start, stop))
        for index, (start, stop) in enumerate(hunks):
            if index:  # the lines between two hunks are the skipped ones
                rows.append((_ELIDE, _elision_text(start - hunks[index - 1][1]), None))
            b_start, a_start = _line_counts(ops, start)
            b_stop, a_stop = _line_counts(ops, stop)
            rows.append(
                (
                    _HUNK,
                    f"@@ -{_range(b_start, b_stop - b_start)}"
                    f" +{_range(a_start, a_stop - a_start)} @@",
                    None,
                )
            )
            # The two sides' line numbers walk along with the ops: a kept or
            # deleted row shows the before side's number, an inserted one the
            # after side's.
            b_line, a_line = b_start, a_start
            for kind, text in ops[start:stop]:
                if kind == _SAME:
                    b_line += 1
                    a_line += 1
                    rows.append(
                        (_SAME, f"{self.glyphs.diff_context}{text}", _gutter(b_line, gutter_width))
                    )
                elif kind == _DEL:
                    b_line += 1
                    rows.append(
                        (_DEL, f"{self.glyphs.diff_remove}{text}", _gutter(b_line, gutter_width))
                    )
                else:
                    a_line += 1
                    rows.append(
                        (_INS, f"{self.glyphs.diff_add}{text}", _gutter(a_line, gutter_width))
                    )
        return rows

    def render(self, c: Constraints) -> Surface:
        """The diff rows reflowed under ``wrap``, cached per width/theme/styles.

        ``max_height`` truncates the returned copy without invalidating the
        cache.  ``OVERFLOW`` widens the surface to the widest row; other
        modes clip at ``c.width``.  The danger band loses its weight here.
        """
        key = (c.width, self.wrap, self.theme, self.styles)
        if self._rendered_rows is None or self._rendered_key != key:
            # The deletion band loses its weight here: the ``status.danger``
            # hue tells a reader what the row is, and weight is reserved for
            # the ``**...**`` syntax everywhere else in the toolkit.  Only
            # ``bold`` is stripped -- anything else on the band rides along.
            danger = replace(self.group("status").danger, bold=False)
            success = self.group("status").success
            muted = self.group("text").muted
            styles = {
                _SAME: NONE,
                _DEL: danger,
                _INS: success,
                _HUNK: muted,
                _ELIDE: muted,
            }
            self._rendered_key = key
            rendered: list[Line] = []
            for kind, text, gutter in self._rows:
                rendered.extend(
                    self._paint(text, styles[kind], gutter, muted).reflow(
                        self.wrap, c.width
                    )
                )
            self._rendered_rows = rendered
        rows = list(self._rendered_rows)
        content_width = max(
            [c.width, *(row.width for row in rows)], default=c.width
        )
        if c.max_height is not None:
            rows = rows[: c.max_height]
        if self.wrap is WrapMode.OVERFLOW:
            return Surface.of(rows, content_width, pad=False)
        return Surface.clipped(rows, c.width)

    def _paint(self, text: str, style: Style, gutter: str | None, hunk_style: Style) -> Line:
        """One row: its number cell (when there is one and ``numbers`` is on) then its text."""
        if gutter is None or not self._numbers:
            return Line.from_text(text, style)
        return Line((Segment(gutter, hunk_style), Segment(text, style)))

    def __repr__(self) -> str:
        return f"Diff({len(self._rows)} rows, context={self.context})"
