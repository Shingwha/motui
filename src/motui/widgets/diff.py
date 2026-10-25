"""Diff component: two texts, one line-level unified diff view.

:class:`Diff` computes a line-level longest-common-subsequence between
``before`` and ``after`` at construction, and again whenever a host assigns
one of the inputs (``before`` / ``after`` / ``context`` / ``numbers`` /
``theme`` are read-write; see the class docstring), storing the result as
the unified-diff rows it renders: an ``@@ -a,b +c,d @@`` header per hunk,
one row per changed line prefixed ``-`` or ``+``, the context lines around a
change prefixed with one space, and a ``\u2026 N lines`` row wherever hunks
skip lines between them (the count is the lines left out).  The styles are
the theme's own bands: deletions render in ``status.danger``'s hue with the
weight stripped, insertions in ``status.success``, the ``@@`` headers and
the ``\u2026`` markers in ``text.muted``, context rows in the default
style.  ``numbers=True``
puts each content row's line number in a ``text.muted`` cell in front of its
text; ``numbers=False`` (the default) renders no gutter at all.  Every row
is ``fit`` to the painting width like any other component's.

The view is **display only**: it implements no interaction protocol -- no
``chosen``, no cursor, no keys.  A host that wants a scrolling window keeps
the rendered rows in a scrollback; the component never changes on its own --
every change it has is an assignment to an input, and that change is
immediate.

**The trimmed walk.**  The LCS table costs one cell per *line pair*, so it
never runs over the whole texts: the common head and the common tail are
stripped line for line first, and only the middle -- the stretch that really
differs -- reaches the table, where it fits :data:`LCS_LIMIT` line pairs.
Trimming is what turns a real file's one-line edit back into one small hunk:
the unchanged hundreds of lines around the edit never enter a table, so the
budget is spent on the region that differs.  Two texts that split to the same
lines trim to an empty middle and render **no rows at all**.

**Anchors.**  A middle past the budget is split before it is walked: a line
that appears exactly once on each side is an *anchor* -- whatever else moved
around it, that one line can only pair with its one counterpart -- and the
middle is cut at every anchor whose pairing keeps the walk monotone.  Each
piece between two anchors is then the very same problem on a strictly shorter
stretch, so the rule recurses and must terminate.  A piece with no anchor to
cut is **replaced** wholesale: every ``before`` line, then every ``after``
line, one hunk -- which is correct (if unhelpful) for two files that share
almost nothing, and the exact shape to rely on in a test.  The ceiling is the
honest part: no region ever costs more edits than the ``n + m`` lines it
holds, so the pipeline can never be worse than the whole-text fallback it
replaces.  No timing assumption is made anywhere: the degradation is the
documented contract, not a performance accident.

Two lines-of-a-line notes that keep the diff honest: the texts are split with
``str.splitlines()``, so a trailing newline adds no line (and ``""`` is no
lines at all), and two texts that split to the same lines render **no rows**
-- a diff with nothing to say is empty, not a row of dots.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from ..kernel.glyphs import GLYPHS, Glyphs
from ..kernel.cell import Line, Segment, Surface
from ..kernel.layout import Constraints, as_constraints
from ..kernel.style import NONE, Style
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


def _anchors(before: list[str], after: list[str]) -> list[tuple[int, int]]:
    """The ``(i, j)`` pairs of lines occurring exactly once on **both** sides.

    A line unique within the region is an *anchor*: whatever else moved, it
    can only pair with its one counterpart, so the region may be split there
    with no table at all.  The pairs come back ordered by ``i`` with ``j``
    strictly increasing -- a candidate whose ``j`` would step backwards is
    dropped, because pairing across it would reorder the diff.  That
    monotone walk is what makes the split sound: every anchor's piece lies
    entirely before the next anchor's piece on both sides, so the pieces
    partition the region.  Uniqueness is checked **within the region**, never
    against the whole file -- a region is the only thing the walk sees.
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
    """The edit script of one region's middle: the budgeted walk or the replacement.

    The middle is what the head/tail trimming left: the stretch where the
    two texts really differ.  An empty side needs no walk at all (the other
    side is all insertions, or all deletions); a middle whose line pairs fit
    :data:`LCS_LIMIT` goes through the table.  Past that budget the middle is
    split at its anchors first -- each piece between two anchors is the same
    problem on a strictly shorter stretch, so this recursion terminates --
    and only a piece that still has no anchor, the honest end of the line, is
    replaced.  Because a replacement costs exactly its ``n + m`` lines and a
    split only ever partitions the region, the total edit cost never exceeds
    ``n + m``: the degradation is never worse than today's whole-text
    replacement, only coarser.
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


def _elision_text(skipped: int) -> str:
    """The elision row's text for ``skipped`` lines: ``"… 7 lines"``, ``"… 1 line"``.

    The marker first, then the count of lines the neighbouring hunks leave
    out -- the one thing a skipped stretch cannot show by itself, and the
    reason the row earns its place.  The text always starts with
    :data:`ELISION`: the constant stays the marker, and hosts and tests keep
    matching rows on it.  ``skipped`` is at least 1 -- two hunks are separate
    only when some ``same`` op lies between them -- so the plural is the
    ordinary spelling and the singular is exactly one line.
    """
    return f"{ELISION} {skipped} line" + ("" if skipped == 1 else "s")


def _gutter(number: int, width: int) -> str:
    """The line-number cell for one row: ``number`` right-aligned in ``width``.

    One string -- the digits, the padding to the component's one width, and
    the space that separates the cell from the row's own text.  The number
    is the row's **own side's** line: the before side for a kept or deleted
    line, the after side for an inserted one, which is what makes a modified
    line's ``-`` and ``+`` rows show different numbers once the versions
    have drifted apart.  Built once, per row, at construction: ``render``
    only has to paint what the row already carries, and the cell's width can
    never vary hunk by hunk.
    """
    return f"{number:>{width}} "


def _checked_context(value: int) -> int:
    """``value`` when it is a legal context count, ``ValueError`` when it is not.

    One home for the rule, run *before* either the constructor or the setter
    writes anything: a rejected ``context`` must leave a component's context
    -- and the rows built from it -- exactly as they were.
    """
    if value < 0:
        raise ValueError(f"context must be >= 0, got {value}")
    return value


class Diff(Widget):
    """A line-level unified diff of two texts, computed once at construction.

    ``before`` and ``after`` are the two versions; ``context`` (default 3)
    is how many unchanged lines surround each change -- a change group is
    rendered as one hunk with that much context, hunks closer than twice the
    context merge into one, and hunks that skip lines have a :data:`ELISION`
    row between them, carrying the number of lines they skip (``"… 7
    lines"``).  ``context=0`` renders the changes alone.

    The rows, in order: ``@@ -a,b +c,d @@`` per hunk, then that hunk's rows
    -- a leading space for a kept line, ``-`` for a deletion, ``+`` for an
    insertion (a modified line is one ``-`` row and one ``+`` row).  The
    styles resolve at render time from the widget's theme (or its
    ``styles`` overrides): ``status.danger`` / ``status.success`` /
    ``text.muted``; context rows keep the default style.  Weight is the
    *text's*, not the band's: a
    deletion shows the ``status.danger`` hue with its weight stripped, so
    the context, ``-`` and ``+``
    rows all read weight-neutral, and bold stays what it is everywhere else
    in the toolkit -- the markdown ``**...**`` syntax (the rule
    ``kernel/style.py``'s palette note spells out).  ``render(width)`` fits
    every row to the width, so a long line is truncated with ``\u2026`` like
    anywhere else, and caches the fitted rows for that width: a repaint
    answers from the cache, a resize rebuilds it.

    A middle past :data:`LCS_LIMIT` line pairs is split at the lines unique
    to both sides, each piece is walked on its own, and a piece that has no
    such anchor is replaced wholesale, one hunk (see the module docstring).
    Two texts that split to the same lines render **no rows**.

    ``before``, ``after``, ``context``, ``numbers``, ``glyphs``, ``theme``
    and ``styles`` are
    read-write: each text/row setter recomputes the rows on
    assignment (and drops the render cache), so a host that streams a new
    revision into the component renders the revision it assigned, never a
    stale frame.  A negative ``context`` is rejected before any state moves,
    and a theme or styles assigned later re-resolves the bands on the next
    render.  The reads are the ordinary ones.

    ``numbers`` (default ``False``) gives every content row a line-number
    cell in front of its text: the number, right-aligned to the width the
    longest line number of either side needs (one width for the whole view,
    so the column never jumps between hunks), then a space.  The cell is
    ``text.muted``; a kept or deleted row shows the before side's line, an
    inserted one the after side's, and the ``@@`` headers and elision rows
    carry no cell at all.  With ``numbers=False`` the rows are the
    single-segment lines they have always been, byte for byte.
    """

    __slots__ = (
        "_after",
        "_before",
        "_context",
        "_numbers",
        "_rendered_key",
        "_rendered_rows",
        "_rows",
        "_glyphs",
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
    ) -> None:
        super().__init__(theme, styles)
        self._before = before
        self._after = after
        self._context = _checked_context(context)
        self._numbers = numbers
        self._glyphs = glyphs
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
        """Recompute the rows for the current inputs and drop the cached render.

        The one rebuild the setters share (and the constructor calls):
        the rows are a pure function of the inputs, so recomputing them here
        is all an assignment owes the next render.
        """
        self._rows = self._build()
        # The one cached render: the inputs it was computed for (width,
        # theme, styles) and its rows.  ``None`` is "nothing fitted yet" --
        # a key of ``None`` cannot be mistaken for a real one, so a hit is a
        # plain equality test.  ``theme``/``styles`` join the key because the
        # bands resolve at render time: assigning one must repaint.
        self._rendered_key = None
        self._rendered_rows = None

    def _build(self) -> list[_Row]:
        """The diff as its rows, ``(kind, text, gutter)`` triples, one per line.

        The gutter cell is the row's line number, right-aligned to the width
        the whole texts need (the longest of the two sides' line counts), so
        a 9-line file and a 10-line one line their columns up the same way
        and a hunk's width never jumps mid-view.  Only the ``@@`` headers and
        the elision rows answer ``None``: they carry no line number.
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

    def revision(self) -> object:
        """The row cache's snapshot: every input ``render`` reads.

        The two texts (``before`` / ``after``), ``context``, ``numbers`` and
        ``glyphs`` determine the built rows; ``theme`` and ``styles``
        determine how those rows paint.  There is no cursor, hover or focus
        state in this component -- every change it has is an assignment to
        one of the public inputs -- so these seven values are the complete
        snapshot.  Equal snapshots therefore mean equal rows at one width,
        which is what makes a **sealed** block's next assignment reach the
        screen: the class's "never a stale frame" promise is exactly this
        key moving.
        """
        return (
            self._before,
            self._after,
            self._context,
            self._numbers,
            self._glyphs,
            self.theme,
            self.styles,
        )

    def render(self, c: Constraints | int) -> Surface:
        """The diff rows, each fitted to the width (``fit`` truncates).

        One render is cached, the way :class:`~.markdown.Markdown` caches its
        own: the rows are a pure function of the width and the resolved
        bands, a host repaints the
        same frame many times (the pointer tier re-renders every frame) and
        resizes rarely, so a repeated key answers from the cache and a new
        one rebuilds it.  One entry, not a history -- the previous width's
        rows are dropped when the pane moves on.  Every hand-out is a copy of
        the cache: the rows are immutable, but the caller's copy is its own,
        because the viewport treats a returned sequence as its own.

        A bare ``int`` is the 1.x width spelling and is normalized through
        :func:`~motui.kernel.layout.as_constraints`; the cache key stays the
        width (never ``max_height``), so a smaller budget truncates the
        returned rows without rebuilding them.  The surface is
        :meth:`~motui.kernel.cell.Surface.clipped`, not padded.  Long lines
        still truncate through ``fit`` exactly as before (the W2.5 decision).

        With ``numbers`` the content rows carry one more segment in front of
        their own: the muted line-number cell :meth:`_build` already made.
        The ``@@`` headers and the elision rows have no cell, and with
        ``numbers`` left at ``False`` the rows are the single-segment lines
        they have always been, byte for byte.
        """
        c = as_constraints(c)
        key = (c.width, self.theme, self.styles)
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
            self._rendered_rows = [
                self._paint(text, styles[kind], gutter, muted).fit(c.width)
                for kind, text, gutter in self._rows
            ]
        rows = list(self._rendered_rows)
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def _paint(self, text: str, style: Style, gutter: str | None, hunk_style: Style) -> Line:
        """One row: its number cell (when there is one and ``numbers`` is on) then its text."""
        if gutter is None or not self._numbers:
            return Line.from_text(text, style)
        return Line((Segment(gutter, hunk_style), Segment(text, style)))

    def __repr__(self) -> str:
        return f"Diff({len(self._rows)} rows, context={self.context})"
