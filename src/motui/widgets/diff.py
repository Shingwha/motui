"""Diff component: two texts, one line-level unified diff view.

:class:`Diff` computes a line-level longest-common-subsequence between
``before`` and ``after`` **once, at construction**, and stores the result as
the unified-diff rows it renders: an ``@@ -a,b +c,d @@`` header per hunk,
one row per changed line prefixed ``-`` or ``+``, the context lines around a
change prefixed with one space, and a ``\u2026`` row wherever hunks skip
lines between them.  The styles are the theme's own bands: deletions render
in ``error``, insertions in ``success``, the ``@@`` headers and the ``\u2026``
markers in ``muted``, context rows in the default style.  Every row is
``fit`` to the painting width like any other component's.

The view is **display only**: it implements no interaction protocol -- no
``chosen``, no cursor, no keys.  A host that wants a scrolling window keeps
the rendered rows in a scrollback; the component itself never changes after
construction.

**The trimmed walk.**  The LCS table costs one cell per *line pair*, so it
never runs over the whole texts: the common head and the common tail are
stripped line for line first, and only the middle -- the stretch that really
differs -- reaches the table, where it fits :data:`LCS_LIMIT` line pairs.
Trimming is what turns a real file's one-line edit back into one small hunk:
the unchanged hundreds of lines around the edit never enter a table, so the
budget is spent on the region that differs.  Two texts that split to the same
lines trim to an empty middle and render **no rows at all**.  A middle past
the budget without a shared line to split it is **replaced** wholesale: every
``before`` line, then every ``after`` line, one hunk -- which is correct (if
unhelpful) for two files that share almost nothing, and the exact shape to
rely on in a test.  The replacement is the honest ceiling, never a surprise:
no region costs more edits than the ``n + m`` lines it holds, so the pipeline
can never be worse than the whole-text fallback it replaces.  No timing
assumption is made anywhere: the degradation is the documented contract, not
a performance accident.

Two lines-of-a-line notes that keep the diff honest: the texts are split with
``str.splitlines()``, so a trailing newline adds no line (and ``""`` is no
lines at all), and two texts that split to the same lines render **no rows**
-- a diff with nothing to say is empty, not a row of dots.
"""

from __future__ import annotations

from ..kernel.lines import Line
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme, Themed

__all__ = ["LCS_LIMIT", "Diff"]

#: The most line pairs (before x after) **one** LCS table may visit.  The
#: walk runs per trimmed middle, so this bounds a comparison's window, not
#: the whole texts: past it the region is replaced (see the module
#: docstring).
LCS_LIMIT = 20_000

#: The elision marker between two hunks -- the lines the hunks skip over.
ELISION = "\u2026"

#: Row kinds the constructor records, ``(kind, text)`` pairs.
_SAME = "same"
_DEL = "del"
_INS = "ins"
_HUNK = "hunk"
_ELIDE = "elide"


def _split_lines(text: str) -> list[str]:
    """The text's logical lines, as ``str.splitlines`` reads them.

    The one line rule of the component: every line break ends a line, so a
    trailing newline adds none and ``""`` is no lines at all.
    """
    return text.splitlines()


def _lcs_ops(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """The edit script of two line lists as ``(kind, text)`` ops, in order.

    One walk of the classic LCS table: equal lines pair off as ``same`` ops,
    everything else is a ``del`` (from ``before``) or an ``ins`` (from
    ``after``).  Ties prefer the deletion, so a modified line reads as its
    ``-`` row before its ``+`` row -- the shape a unified diff shows.  The
    table is one cell per line pair; the caller has already bounded the
    product (:data:`LCS_LIMIT`).
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

    The shape a unified diff spells a rewritten region with -- all the
    ``before`` lines, then all the ``after`` lines -- and the shape today's
    whole-text fallback already has.  It costs ``n + m`` edits, the most a
    replacement can cost, so a region that takes this path is never *worse*
    than a walk that would have run over it, only coarser.  Its ops are one
    uninterrupted non-``same`` run, so the row stage renders it as one hunk
    with no special case anywhere.
    """
    return [(_DEL, line) for line in before] + [(_INS, line) for line in after]


def _middle_ops(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """The edit script of one region's middle: the budgeted walk or the replacement.

    The middle is what the head/tail trimming left: the stretch where the
    two texts really differ.  An empty side needs no walk at all (the other
    side is all insertions, or all deletions); a middle whose line pairs fit
    :data:`LCS_LIMIT` goes through the table; anything past that budget
    without a line to split it degrades to :func:`_replaced`.
    """
    if not before:
        return [(_INS, line) for line in after]
    if not after:
        return [(_DEL, line) for line in before]
    if len(before) * len(after) <= LCS_LIMIT:
        return _lcs_ops(before, after)
    return _replaced(before, after)


def _ops(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """The edit script of two line lists: trim the common ends, walk the middle.

    The head and the tail are stripped while the two sides are strictly
    equal, line for line, and the ``same`` ops they contribute are emitted
    verbatim; only the middle goes through :func:`_middle_ops`.  Trimming is
    what turns a real file's one-line edit back into one small hunk: the
    unchanged lines around the edit never enter a table, so the
    :data:`LCS_LIMIT` budget is spent where the two texts differ.  Two
    identical texts trim to an empty middle and produce no ops at all, and
    the hunk/window stage reads the stream exactly as it always did.
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
    """The op-index ranges of every change run, as ``[start, stop)`` pairs.

    One region is a maximal stretch of non-``same`` ops: the op window a
    hunk has to cover, however many deletions and insertions it holds.
    """
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
    """The ``(before, after)`` line indices after the first ``count`` ops.

    Every op advances its own side: a ``same`` both, a ``del`` the before
    side, an ``ins`` the after side.  The constructor tracks neither while
    emitting, so this walk turns an op index into the two 0-based line
    indices a hunk header needs.
    """
    b = a = 0
    for kind, _text in ops[:count]:
        if kind != _INS:
            b += 1
        if kind != _DEL:
            a += 1
    return b, a


def _range(start: int, count: int) -> str:
    """One side of a hunk header: ``"start,count"`` with unified-diff numbers.

    A non-empty range starts at its first line (1-based); an empty one
    starts at the line *before* the gap (0 when the gap is at the top),
    which is the canonical ``-0,0`` / ``-N,0`` spelling.
    """
    return f"{start + 1 if count else start},{count}"


class Diff(Themed):
    """A line-level unified diff of two texts, computed once at construction.

    ``before`` and ``after`` are the two versions; ``context`` (default 3)
    is how many unchanged lines surround each change -- a change group is
    rendered as one hunk with that much context, hunks closer than twice the
    context merge into one, and hunks that skip lines have a
    :data:`ELISION` row between them.  ``context=0`` renders the changes
    alone.

    The rows, in order: ``@@ -a,b +c,d @@`` per hunk, then that hunk's rows
    -- a leading space for a kept line, ``-`` for a deletion, ``+`` for an
    insertion (a modified line is one ``-`` row and one ``+`` row).  The
    styles resolve once, at construction, as this component's theme fields
    (``error`` / ``success`` / ``muted``); context rows keep the default
    style.  ``render(width)`` fits every row to the width, so a long line is
    truncated with ``\u2026`` like anywhere else.

    Beyond :data:`LCS_LIMIT` line pairs in one region's middle the walk is
    skipped and that region is replaced wholesale, one hunk (see the module
    docstring).  Two texts that split to the same lines render **no rows**.
    """

    __slots__ = (
        "_del_style",
        "_hunk_style",
        "_ins_style",
        "_rows",
        "after",
        "before",
        "context",
        "theme",
    )

    def __init__(
        self,
        before: str,
        after: str,
        *,
        context: int = 3,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.before = before
        self.after = after
        self.context = context
        self._del_style = self._pick(None, "error")
        self._ins_style = self._pick(None, "success")
        self._hunk_style = self._pick(None, "muted")
        self._rows = self._build()

    def _build(self) -> list[tuple[str, str]]:
        """The diff as its rows, ``(kind, text)`` pairs, one per rendered line."""
        if self.context < 0:
            raise ValueError(f"context must be >= 0, got {self.context}")
        ops = _ops(_split_lines(self.before), _split_lines(self.after))
        rows: list[tuple[str, str]] = []
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
            pre = min(self.context, start - previous_stop)
            post = min(self.context, next_start - stop)
            windows.append((start - pre, stop + post))
        hunks: list[tuple[int, int]] = []
        for start, stop in windows:
            if hunks and start <= hunks[-1][1]:  # two windows meet: one hunk
                hunks[-1] = (hunks[-1][0], max(hunks[-1][1], stop))
            else:
                hunks.append((start, stop))
        for index, (start, stop) in enumerate(hunks):
            if index:  # the lines between two hunks are the skipped ones
                rows.append((_ELIDE, ELISION))
            b_start, a_start = _line_counts(ops, start)
            b_stop, a_stop = _line_counts(ops, stop)
            rows.append(
                (
                    _HUNK,
                    f"@@ -{_range(b_start, b_stop - b_start)}"
                    f" +{_range(a_start, a_stop - a_start)} @@",
                )
            )
            for kind, text in ops[start:stop]:
                if kind == _SAME:
                    rows.append((_SAME, f" {text}"))
                elif kind == _DEL:
                    rows.append((_DEL, f"-{text}"))
                else:
                    rows.append((_INS, f"+{text}"))
        return rows

    def render(self, width: int) -> list[Line]:
        """The diff rows, each fitted to ``width`` (``fit`` truncates)."""
        styles = {
            _SAME: NONE,
            _DEL: self._del_style,
            _INS: self._ins_style,
            _HUNK: self._hunk_style,
            _ELIDE: self._hunk_style,
        }
        return [
            Line.from_text(text, styles[kind]).fit(width) for kind, text in self._rows
        ]

    def __repr__(self) -> str:
        return f"Diff({len(self._rows)} rows, context={self.context})"
