"""The component: a Markdown document rendered as rows.

``Markdown`` owns the one :class:`~.context.RenderContext` of a document --
the resolved theme, the fenced-code engine, the task marks, the divider cap
and the two live registries -- and hands it to the shared block loop on every
``render``.
Rules themselves stay dep-free singletons, so the component is the only
place that resolves anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from ...kernel.cell import Line, Segment, Surface, slice_line
from ...kernel.geom import Pos
from ...kernel.glyphs import GLYPHS, Glyphs
from ...kernel.layout import Constraints
from ...kernel.text import WrapMode, _normalize_tabs, wrap_spans
from ...kernel.theme import Styles, Theme
from ...widgets.base import ResultWidget
from ..syntax import Highlighter
from .blocks import (
    BlockRule,
    FenceRule,
    HeadingRule,
    ParagraphRule,
    ThematicBreakRule,
    _BlockScan,
    _fence_highlighter,
    _paragraph_text,
    _scan_fences,
    _wrap_paragraph,
)
from .context import RenderContext
from .inline import INLINE_RULES, InlineRule, inline_segments
from .nested import TASK_ACTION, ListRule, QuoteRule
from .tables import TableRule

__all__ = ["BLOCK_RULES", "Markdown", "default_block_rules"]


def default_block_rules() -> list[BlockRule]:
    """A fresh built-in block registry, dep-free and in match order.

    Order is the match priority; :class:`~.blocks.ParagraphRule` is the
    mandatory catch-all at the end.  Build a custom registry by prepending
    your own rules: ``[MyRule(), *default_block_rules()]``.  The tuple
    singleton the component ships with is :data:`BLOCK_RULES`; the factory
    hands out new instances so a caller can extend one without touching
    the shared registry.
    """
    return [
        HeadingRule(),
        FenceRule(),
        TableRule(),
        ThematicBreakRule(),
        QuoteRule(),
        ListRule(),
        ParagraphRule(),
    ]


#: Block registry singleton: tried in order, first match consumes; the last
#: entry is the paragraph catch-all.  Immutable -- extend a copy.
BLOCK_RULES: tuple[BlockRule, ...] = tuple(default_block_rules())


def _first_parse_difference(
    old: Sequence[Segment], new: Sequence[Segment], limit: int
) -> int:
    """The first character offset below ``limit`` where two parses disagree.

    ``old`` and ``new`` are the segment runs of two texts where the second is
    the first plus an appended suffix, so both runs cover the common prefix;
    the walk compares the overlapping pieces -- text, style and payloads --
    and answers the offset where the first difference starts (``limit`` when
    the whole prefix parses identically).  The component's append-only
    paragraph render rebuilds its rows from this offset on and keeps the rows
    before it; answering too early costs a re-wrap, never a wrong row.
    """
    old_at = new_at = 0  # the character offset where the current run starts
    old_i = new_i = 0
    pos = 0
    while pos < limit and old_i < len(old) and new_i < len(new):
        run_old, run_new = old[old_i], new[new_i]
        if (
            run_old.style != run_new.style
            or run_old.link != run_new.link
            or run_old.action != run_new.action
        ):
            return pos
        step = min(old_at + len(run_old.text), new_at + len(run_new.text)) - pos
        if step <= 0:  # a zero-width run: the shapes already disagree here
            return pos
        if (
            run_old.text[pos - old_at : pos - old_at + step]
            != run_new.text[pos - new_at : pos - new_at + step]
        ):
            return pos
        pos += step
        if pos >= old_at + len(run_old.text):
            old_i, old_at = old_i + 1, pos
        if pos >= new_at + len(run_new.text):
            new_i, new_at = new_i + 1, pos
    return pos


def _word_start(rendered: str, offset: int) -> int:
    """The start of the word the character at ``offset`` belongs to.

    The append-only render's wrap cut: a re-parse can change a word's width,
    and a word's width is what decides whether the *preceding* row kept it, so
    every row from the changed word's start on is rebuilt -- plus the one row
    that tried to keep it, which the caller reserves (the cut is answered for
    the word, not for the row).  A ``offset`` past the end means "the word
    appended after the text", a whitespace tail means the word after it does
    not exist yet: both answer the text's end, so the rows before it are the
    ones kept.  Offsets are into the **tab-normalized rendered text** the
    spans live in.
    """
    if not rendered:
        return 0
    index = min(offset, len(rendered) - 1)
    while index < len(rendered) and rendered[index] == " ":
        index += 1
    if index >= len(rendered):
        return len(rendered)  # only whitespace left: no word to blame
    while index > 0 and rendered[index - 1] != " ":
        index -= 1
    return index


class _Paragraph:
    """One paragraph's last render, plus the append-only growth rule.

    The component's memory of the **tail** block when that block was claimed
    by the built-in :class:`~.blocks.ParagraphRule`: the joined text, the
    parsed line's segments, the wrap spans and the fitted rows.  A text that
    only grew at its end renders a suffix instead of the paragraph -- the
    parse is a full re-scan (through the candidate-driven loop, so a literal
    stretch costs one regex pass rather than a Python step per character),
    but the rows before the changed region are kept as they are:
    :func:`_first_parse_difference` finds the first character two parses
    disagree at, :func:`_word_start` walks back to the word that owns it (a
    changed word width can move the break in front of it), and only the rows
    from there -- bar the one row that tried the changed word -- are rebuilt.

    The memory is a *renderer* result, never a renderer input: :meth:`render`
    always builds the rows from the text it is handed.  Every path that is
    not a pure append -- a different text, a width the memory was not built
    at, a shrink -- is the caller's full-render decision, and the caller
    drops the memory when it takes it.
    """

    __slots__ = ("end", "rendered", "rendered_len", "rows", "segs", "spans", "start", "text")

    def __init__(
        self, text: str, line: Line, spans: list[tuple[int, int]], rows: list[Line]
    ) -> None:
        self.text = text
        self.segs = line.segments
        self.spans = spans
        self.rows = rows
        #: The tab-normalized rendered text the spans and the segments live in
        #: (a link contributes its label, not its source brackets) -- the
        #: offsets of this render's spans, and the ruler the next render's
        #: difference walk and word scan read.
        self.rendered = _normalize_tabs(line.text)
        self.rendered_len = len(self.rendered)
        #: The paragraph's source-line range, filled in by the cache that
        #: owns the memory (the paragraph renderer never sees the lines): the
        #: block loop's ``[start, end)`` slice of the document at build time.
        self.start = 0
        self.end = 0

    @classmethod
    def render(
        cls, text: str, width: int, ctx: RenderContext, previous: _Paragraph | None = None
    ) -> tuple[list[Line], _Paragraph]:
        """The rows for ``text`` and the memory to keep: full or suffix render.

        ``previous`` is the memory of the same paragraph's earlier render
        (the caller has checked that the block, the width and the growth
        still line up); an unchanged text answers the very same rows, a
        grown one answers the suffix render, anything else renders whole.
        """
        if previous is not None:
            if previous.text == text:
                return list(previous.rows), previous
            grown = previous._grow(text, width, ctx)
            if grown is not None:
                return grown
        line, spans, rows = _wrap_paragraph(text, width, ctx)
        return list(rows), cls(text, line, spans, rows)

    def _grow(
        self, text: str, width: int, ctx: RenderContext
    ) -> tuple[list[Line], _Paragraph] | None:
        """The appended-text path, or ``None`` when ``text`` is not a growth."""
        if not text.startswith(self.text):
            return None
        line = Line(inline_segments(text, ctx))
        difference = _first_parse_difference(self.segs, line.segments, self.rendered_len)
        cut = _word_start(self.rendered, difference)
        reuse = 0
        while reuse < len(self.spans) and self.spans[reuse][1] < cut:
            reuse += 1
        # The row that tried the changed word (the last one ending before the
        # word's start) may absorb it with its new width, so it is rebuilt as
        # well; the last row is always rebuilt -- it is the open one.
        reuse = min(max(reuse - 1, 0), len(self.rows) - 1)
        start = self.spans[reuse][0]
        rendered = _normalize_tabs(line.text)
        tail = wrap_spans(rendered[start:], width)
        spans = self.spans[:reuse] + [
            (start + piece_start, start + piece_end) for piece_start, piece_end in tail
        ]
        rows = self.rows[:reuse] + [
            slice_line(line, piece_start, piece_end).clip(WrapMode.ELLIPSIS, width)
            for piece_start, piece_end in spans[reuse:]
        ]
        return list(rows), _Paragraph(text, line, spans, rows)


class _StreamCache:
    """One Markdown render answer, and the append-only reuse rule.

    Holds the last ``(text, width, code_wrap)`` render: its rows, the source
    lines they came from, ``boundaries`` -- the ``(end, rows so far)`` pair the
    block loop recorded for every block -- and the claiming rule of each
    block in the same order.  :meth:`render` answers a new key one of
    three ways:

    * an unchanged key returns a copy of the cached rows;
    * a text that only *grew* past its last line re-renders just the tail
      block and splices the cached prefix on (:meth:`_resume`), which for a
      tail block claimed by the built-in paragraph rule goes further and
      re-renders only the paragraph's changed suffix (:class:`_Paragraph`):
      a paragraph streaming in word by word costs the same per frame whatever
      landed before it (render-cost W4);
    * anything else -- a different width, a shrink, a mid-string change --
      renders the whole document and replaces the entry.

    One entry per component: a streaming working set, not a history.  The
    rows are the component's private copy -- every hand-out is a copy,
    because the viewport treats a returned list as its own.

    The reuse is sound because the :class:`~.blocks.BlockRule` protocol has
    a rule classify from its cursor over the lines it consumes -- it reads
    nothing before its start and nothing past its end -- so a render that
    opens mid-buffer at a completed boundary sees for its tail exactly what a
    whole-buffer render sees.  The boundary and rule of every block before
    the tail are kept, so the tail block is re-rendered from **its own**
    start: every earlier block's rows are the very same objects.
    """

    __slots__ = (
        "_boundaries",
        "_code_wrap",
        "_lines",
        "_memo",
        "_primed",
        "_rows",
        "_rules",
        "_text",
        "_width",
    )

    def __init__(self) -> None:
        self._primed = False
        self._text = ""
        self._width = 0
        #: The fenced-code wrap the cached rows were laid out under.  A mode
        #: change is a full re-render: the code rows' row count depends on it.
        self._code_wrap: WrapMode | None = None
        self._rows: list[Line] = []
        self._lines: list[str] = []
        self._boundaries: list[tuple[int, int]] = []
        self._rules: list[BlockRule] = []
        # The tail paragraph's append-only memory, when the last render left
        # one; ``None`` means "no memory" and is also what every non-append
        # path leaves behind (a stale memory is never consulted: the checks
        # in _grow_paragraph pin the block, the width and the growth).
        self._memo: _Paragraph | None = None

    def render(
        self, text: str, width: int, ctx: RenderContext, gap: int
    ) -> list[Line]:
        """The rows for ``(text, width)``, reusing the cached prefix when sound."""
        if (
            self._primed
            and self._width == width
            and self._code_wrap is ctx.code_wrap
        ):
            if self._text == text:
                return list(self._rows)
            if self._resume(text, width, ctx, gap):
                return list(self._rows)
        self._render_whole(text, width, ctx, gap)
        return list(self._rows)

    def _render_whole(
        self, text: str, width: int, ctx: RenderContext, gap: int
    ) -> None:
        """Render the whole document from scratch and replace the entry."""
        lines = text.split("\n")
        scan = _BlockScan(lines, width, ctx, gap)
        scan.run()
        self._memo = None
        self._store(
            text,
            width,
            lines,
            scan.rows,
            scan.boundaries,
            scan.rules,
            code_wrap=ctx.code_wrap,
        )

    def _resume(self, text: str, width: int, ctx: RenderContext, gap: int) -> bool:
        """The append-only path: re-render the tail, keep every earlier block.

        The reuse applies only when ``text`` is the cached text plus more: a
        shrink, or a change to any line before the last, is the caller's
        full-render path (``False``).  The tail block -- the last block the
        block loop recorded, whose start, rows and claiming rule are all kept
        -- is re-rendered against the new buffer, and every block before it
        hands back the very row objects of the cached render.  When the tail
        block ends before the old buffer did, even its own lines did not
        change and its rows are kept too; when it is the built-in paragraph
        and only grew at its end, only the paragraph's changed suffix is
        rebuilt (:meth:`_grow_paragraph`).  Nothing is ever guessed: a growth
        the incremental paths cannot vouch for falls back to re-rendering the
        tail block whole, and a rule that needs the lines past its recorded
        end (an unclosed fence closing later) is simply the tail block.
        """
        lines = text.split("\n")
        cached_count = len(self._lines)
        if cached_count == 0 or not self._boundaries:
            return False
        if len(lines) < cached_count:
            return False  # a shrink
        if lines[: cached_count - 1] != self._lines[: cached_count - 1]:
            return False  # a line before the last one changed
        if not lines[cached_count - 1].startswith(self._lines[-1]):
            return False  # the last cached line is not a prefix of the new one
        tail_end, tail_rows = self._boundaries[-1]
        if tail_end < cached_count - 1 or (
            tail_end < cached_count and not lines[cached_count - 1].strip()
        ):
            # The tail block's own lines did not grow and the line that ended
            # it (a blank line, or several -- everything the loop skipped
            # after the last block) is still blank: the block cannot stretch
            # over the growth (a blank line ends a paragraph, a list, a
            # quote and a table alike), so keep its rows as they are and scan
            # the growth normally.  When the grown line *is* the terminator,
            # the block may swallow it (a paragraph continues over a line
            # that stopped being blank) and the generic path re-renders the
            # tail block instead.
            scan = _BlockScan(
                lines,
                width,
                ctx,
                gap,
                start=tail_end,
                rows=self._rows[:tail_rows],
                boundaries=list(self._boundaries),
                rules=list(self._rules),
            )
            scan.run()
            self._store(
                text,
                width,
                lines,
                scan.rows,
                scan.boundaries,
                scan.rules,
                code_wrap=ctx.code_wrap,
            )
            return True
        if self._grow_paragraph(lines, width, ctx, gap):
            return True
        # The generic tail path: re-render the last block over the new lines,
        # with every earlier block's rows and boundary spliced back on.  When
        # the tail block *starts* at the grown line, the block before it may
        # swallow that line (a list item or table row that only now parses),
        # so the re-render starts one block earlier and lets the loop decide.
        tail_at = self._boundaries[-2][0] if len(self._boundaries) > 1 else 0
        first = len(self._boundaries) - 1
        if len(self._boundaries) > 1 and tail_at == cached_count - 1:
            first -= 1
        scan = self._rerender_from(first, lines, width, ctx, gap)
        self._memo = None
        self._store(
            text,
            width,
            lines,
            scan.rows,
            scan.boundaries,
            scan.rules,
            code_wrap=ctx.code_wrap,
        )
        return True

    def _rerender_from(
        self, first: int, lines: list[str], width: int, ctx: RenderContext, gap: int
    ) -> _BlockScan:
        """Re-run the block loop from block ``first`` on, blocks before it kept.

        The seed is exactly the state the loop had when it finished block
        ``first - 1``: the rows and boundaries of every earlier block (their
        lines are unchanged, and a rule classifies and renders from its own
        slice, so their rows -- the very objects -- stand) and the source line
        where block ``first`` begins.  ``first <= 0`` re-renders the whole
        document through the same door.
        """
        if first <= 0:
            start, rows, boundaries, rules = 0, [], [], []
        else:
            start = self._boundaries[first - 1][0]
            rows = self._rows[: self._boundaries[first - 1][1]]
            boundaries = self._boundaries[:first]
            rules = self._rules[:first]
        scan = _BlockScan(
            lines,
            width,
            ctx,
            gap,
            start=start,
            rows=rows,
            boundaries=boundaries,
            rules=rules,
        )
        scan.run()
        return scan

    def _grow_paragraph(
        self, lines: list[str], width: int, ctx: RenderContext, gap: int
    ) -> bool:
        """Re-render the tail paragraph through its memory; ``False`` declines.

        Only reachable through :meth:`_resume`, whose checks have already
        pinned the buffer: every line before the last is unchanged and the
        last is a prefix-extension.  The fast path additionally needs the
        tail block to be the **built-in** paragraph (``type(...) is``, not a
        subclass) and to end exactly where the buffer did -- the paragraph is
        then extended from its own start over the new lines, and that extent
        is *computed here* (blank line or a claim of another rule ends it,
        the same two checks the block loop makes), not guessed.  With a
        memory of the same paragraph only the changed suffix re-parses and
        re-wraps; without one (the first growth after a full render) the
        paragraph renders whole -- exactly once, and the memory is kept for
        the next growth.  Any shape that is not a clean extension declines
        (``False``): the tail block then re-renders whole through the generic
        path rather than guess.
        """
        if not self._rules or type(self._rules[-1]) is not ParagraphRule:
            return False
        cached_count = len(self._lines)
        start = self._boundaries[-2][0] if len(self._boundaries) > 1 else 0
        if len(self._boundaries) > 1 and start == cached_count - 1:
            # The paragraph *is* the grown line and another block precedes it:
            # that block may swallow the line now (its stop line is the one
            # that changed), so the paragraph's own start is not pinned any
            # more -- the generic path re-runs the loop from that block and
            # decides.  With no block before it (the whole document is this
            # one paragraph) there is nothing that could absorb it.
            return False
        interrupters = [
            rule for rule in ctx.block_rules if not isinstance(rule, ParagraphRule)
        ]
        # The block's own lines must keep their shape as paragraph lines.  The
        # last line is checked even when it did not grow -- a rule that reads
        # the line *after* its cursor (the GFM table, over the pair
        # ``lines[i]``/``lines[i + 1]``) can claim it the moment new lines
        # follow -- and when the last line did grow, its predecessor is
        # checked too: it is that claim which reads the grown line.
        grown = self._lines[-1]
        new_last = lines[cached_count - 1]
        affected = [cached_count - 1]
        if new_last != grown and cached_count >= 2:
            affected.append(cached_count - 2)
        if any(rule.match(lines, index) for index in affected for rule in interrupters):
            return False
        memo = self._memo
        if memo is not None and (memo.end != cached_count or memo.start != start):
            memo = None  # a memory of another paragraph (or another block)
        if new_last != grown and not new_last.strip():
            return False
        end = cached_count
        while end < len(lines):
            if not lines[end].strip() or any(
                rule.match(lines, end) for rule in interrupters
            ):
                break  # the paragraph ends here; the rest is the block loop's
            end += 1
        if memo is None:
            text = _paragraph_text(lines[start:end])
        else:
            suffix = ""
            if new_last != grown:
                extension = new_last.strip()
                if not extension.startswith(grown.strip()):
                    return False
                suffix = extension[len(grown.strip()) :]
            for index in range(cached_count, end):
                suffix += " " + lines[index].strip()
            text = memo.text + suffix
        block_start = self._boundaries[-2][1] if len(self._boundaries) > 1 else 0
        if block_start > 0 and gap > 0:
            block_start += 1  # the block gap the loop appended before the tail
        rows, memo = _Paragraph.render(text, width, ctx, previous=memo)
        memo.start = start
        memo.end = end
        rows = self._rows[:block_start] + rows
        boundaries = [*self._boundaries[:-1], (end, len(rows))]
        rules = [*self._rules[:-1], self._rules[-1]]
        scan = _BlockScan(
            lines, width, ctx, gap, start=end, rows=rows, boundaries=boundaries, rules=rules
        )
        scan.run()
        self._store(
            text,
            width,
            lines,
            scan.rows,
            scan.boundaries,
            scan.rules,
            memo,
            code_wrap=ctx.code_wrap,
        )
        return True

    def _store(
        self,
        text: str,
        width: int,
        lines: list[str],
        rows: list[Line],
        boundaries: list[tuple[int, int]],
        rules: list[BlockRule],
        memo: _Paragraph | None = None,
        *,
        code_wrap: WrapMode,
    ) -> None:
        self._primed = True
        self._text = text
        self._width = width
        self._code_wrap = code_wrap
        self._lines = lines
        self._rows = rows
        self._boundaries = boundaries
        self._rules = rules
        self._memo = memo


def _span_index(rows: Sequence[Line]) -> list[list[tuple[str, int, int]]]:
    """The action spans of ``rows``: one ``(action, start, end)`` list per row.

    The index :meth:`Markdown.on_click` / :meth:`Markdown.on_hover` read, so the
    hit testing never re-walks the segments: derived in display columns (the
    :attr:`~motui.kernel.cell.Segment.width` walk, left-closed and
    right-open, exactly what :func:`~motui.kernel.cell.action_at` answers
    per row) from the rows a render just produced.  The rules are not asked:
    whatever a rule hangs on a segment's ``action`` turns up here, the
    built-in link rule included.
    """
    index: list[list[tuple[str, int, int]]] = []
    for row in rows:
        spans: list[tuple[str, int, int]] = []
        pos = 0
        for seg in row.segments:
            end = pos + seg.width
            if seg.action is not None and pos < end:
                spans.append((seg.action, pos, end))
            pos = end
        index.append(spans)
    return index


def _stamp_tasks(rows: list[Line]) -> list[Line]:
    """Stamp each task marker with its flat document ordinal.

    :class:`~.nested.ListRule` hangs the bare :data:`~.nested.TASK_ACTION`
    placeholder (``"todo:"``) on a task item's box marker; this walks the
    finished rows -- in draw order, which is the document's own order -- and
    rewrites every placeholder as ``"todo:<i>"``, counting from zero across
    the whole document, margins, quotes and nesting included (a task under
    a quote or a list continuation is stamped where it draws).  The walk is
    **after** the render cache, on the copy handed out -- the hover
    transform's rule -- so the cached rows stay unstamped, the ``(text,
    width)`` key and the streaming splice are untouched, and a resumed tail
    render stamps into the same sequence a whole render produces.

    The rows are Lines (immutable), so a row holding a placeholder is
    rebuilt with each placeholder segment replaced (its style and any link
    riding along); rows without one are the very same objects, and a
    document with no tasks hands back its list untouched.
    """
    ordinal = 0
    out: list[Line] | None = None
    for index, row in enumerate(rows):
        stamped: list[Segment] | None = None
        for position, seg in enumerate(row.segments):
            if seg.action != TASK_ACTION:
                continue
            if stamped is None:
                stamped = list(row.segments)
            stamped[position] = Segment(
                seg.text,
                seg.style,
                link=seg.link,
                action=f"{TASK_ACTION}{ordinal}",
            )
            ordinal += 1
        if stamped is not None:
            if out is None:
                out = list(rows)
            out[index] = Line(stamped)
    return rows if out is None else out


class Markdown(ResultWidget):
    """A Markdown document rendered as rows, rule-registry driven.

    ``text`` is a mutable attribute (streaming text assigns to it);
    ``render(c)`` is a pure function of ``text`` and ``c.width`` and, in
    every mode except ``code_wrap=OVERFLOW``, never returns a row wider than
    ``width`` (the OVERFLOW document hands its natural width out for a
    horizontal scroll container).  The last answer lives in one
    :class:`_StreamCache` entry keyed on the ``(text, width)`` pair, so a
    document re-rendered every frame (the viewport re-renders an open block
    on every layout) parses once, not once per frame -- the cache is
    invisible: a repeated call hands back a copy of the very same rows.  A
    text that only *grew* does better still: the tail block re-renders and
    splices onto the cached rows -- for a paragraph, only the suffix that
    changed re-parses and re-wraps (:class:`_Paragraph`) -- so a reply
    streaming in line by line renders its new words and nothing else, at a
    per-frame cost that does not grow with what already landed.  The stamped
    rows and the span index are remembered with the render they describe, so
    a hit frame rebuilds neither (:func:`_stamp_tasks` / :func:`_span_index`).
    Every mutable input touches the widget -- ``text``/``max_width`` and the
    rest through ``Widget.__setattr__``, ``code_wrap`` and ``hover_at``
    explicitly -- so a block's
    row cache follows a max-width change, a task-mark change or a hover on
    a sealed document.
    ``block_rules`` / ``inline_rules`` replace the built-in registries
    (:data:`BLOCK_RULES` / :data:`INLINE_RULES` are immutable tuples; the
    defaults are copied per component, and the block registry must end with
    a paragraph-style catch-all; see :class:`~.blocks.ParagraphRule`).
    ``theme`` (and its ``styles`` group overrides) restyles the built-in
    rules (headings, code, quotes, list
    markers, links and the embedded ``Table``/``Divider``); custom rules keep
    their own styles -- they read what they need off the context they are
    handed.  ``highlighter`` injects the fenced-code engine (anything with
    ``highlight(code, lang) -> list[Line]``; the built-in regex highlighter
    by default, restyled by the effective theme).  ``glyphs`` is the
    structural
    vocabulary every built-in rule reads: the task box's ``check_off`` /
    ``check_on``, the list ``bullets`` and the ``quote`` bar, each seated so
    the states share one column; empty glyphs turn a mark off (the body
    takes the marker's seat instead).  ``gap`` sets how many blank rows
    separate adjacent blocks (default 1, the pi reference's section breathing
    room; a negative value degrades to 0).  ``divider_max_width`` caps
    thematic-break rules' dividers at that many columns (default 80, the pi
    reference's rule width; ``None`` spans the whole width).
    ``code_wrap`` is the fenced-code row policy (``WrapMode.WORD`` by
    default, so a long code line wraps instead of losing its tail;
    ``ELLIPSIS`` / ``CLIP`` keep one row, ``OVERFLOW`` leaves the natural
    width to the container).  It is a plain mutable attribute: a write
    replaces the context's mode and drops the stream cache, and the setter touches the
    widget so a sealed document repaints too.
    ``max_width`` caps the document's **own** wrap width (``None`` by
    default, no cap) -- the sibling of ``divider_max_width``, and Textual's
    ``max-width``: the rows are wrapped at ``min(width, max_width)`` and come
    out narrower than the painting width, never padded back up to it, since
    a painter clears the tail past a short row.  It is a plain mutable
    attribute, so a host can re-cap one document in place; the clamp runs
    before the stream cache and the cache key carries the width it
    produced, so a moved cap re-renders instead of serving the other
    width's rows.  Blank input
    rows are dropped: the source's own blank lines never add spacing beyond
    one gap, and ``gap=0`` restores the old direct stacking (no blank rows
    between blocks).

    **Inline links are clickable spans.**  A ``[label](url)`` run carries the
    url as its ``Segment.link`` (the terminal gets a real OSC 8 hyperlink)
    and as its ``Segment.action``, so the component is ``hoverable`` and
    ``clickable`` over its **last render's** row table:
    ``on_click(pos)`` leaves the url of the span the cell hit pending
    (the host reads it once through :meth:`take`) and answers
    ``True`` -- a cell off every span declines -- and ``on_hover(pos)``
    remembers the span under the pointer, answering whether the render
    changed.  The span index (row -> ``(action, start, end)``, columns as
    :func:`~motui.kernel.cell.action_at` reports them) is derived from
    the rows once per render, after the cache and never inside it; the hover
    is a **post-transform of those cached rows** (the hit row is rebuilt with
    the theme's ``surfaces.hover`` merged onto the span), so the ``(text, width)``
    cache key and the row cache itself stay hover-free -- and a document with
    no pointer on it renders byte-for-byte what it always did.

    **Task lists** are the same door with a different payload.  A bullet
    item whose content opens with ``[ ]`` / ``[x]`` (one space, GFM's rule)
    renders its bullet as a one-column box -- ``glyphs.check_off`` /
    ``glyphs.check_on`` -- and the whole
    ``"\\u2610 "`` seat run is one action span whose
    payload is ``"todo:<flat index>"``: the index of the task among the
    document's tasks, counting from zero in draw order across every list,
    margin and nesting level.  The rule layer is stateless, so it hangs the
    bare placeholder and :func:`_stamp_tasks` writes the ordinal onto the
    finished rows after the cache (the hover rule's shape: cache untouched,
    streaming resume unaffected).  A click on the box leaves the payload
    pending -- read once through :meth:`take` -- and the *host* owns
    the rest of the loop, because ``text`` is the host's::

        result = md.take()
        if result and result.startswith("todo:"):
            index = int(result.removeprefix("todo:"))
            md.text = toggle_task(md.text, index)   # the host's own rewrite

    ``toggle_task`` scans the source lines for the task markers in order
    and flips the ``index``-th one -- the payload's flat index *is* that
    ordinal, by construction.  The widget never rewrites ``text`` itself.

    **``fences()``** is the document's fenced-code accessor: the
    ``(lang, code)`` pairs of every top-level fence, parsed from ``text``
    itself (never from the render cache or the last render's rows), so a
    host can copy a code block -- ``screen.copy(code)`` -- without walking
    the rows.  The parse is the block engine's own fence rule (see
    :func:`~.blocks._scan_fences`).
    """

    #: Inline links and task boxes take pointer clicks and paint a hover.
    clickable = True
    hoverable = True

    __slots__ = (
        "_acts",
        "_cache",
        "_ctx",
        "_fences",
        "_fences_text",
        "_gap",
        "_hover_span",
        "_rows",
        "_stamp",
        "_stamp_key",
        "_user_highlighter",
        "max_width",
        "text",
    )

    def __init__(
        self,
        text: str = "",
        *,
        block_rules: Sequence[BlockRule] | None = None,
        inline_rules: Sequence[InlineRule] | None = None,
        theme: Theme | None = None,
        styles: Styles | None = None,
        highlighter: Highlighter | None = None,
        glyphs: Glyphs = GLYPHS,
        gap: int = 1,
        divider_max_width: int | None = 80,
        max_width: int | None = None,
        code_wrap: WrapMode = WrapMode.WORD,
    ) -> None:
        super().__init__(theme, styles)
        self.text = text
        #: The wrap-width cap: the sibling of ``divider_max_width`` (Textual's
        #: ``max-width``).  A plain mutable attribute, so a host can re-cap one
        #: document in place -- the clamp runs before the cache and the cache
        #: key carries the width it produced, so a moved cap re-renders rather
        #: than serving the other width's rows.
        self.max_width = max_width
        self._gap = gap if gap > 0 else 0  # degrade negatives, never raise
        #: The injected engine (``None``: the built-in one is derived from the
        #: effective theme in :meth:`_sync_theme`).
        self._user_highlighter = highlighter
        #: The last render's rows (the viewport's copy is its own; these are
        #: the base rows the hit testing reads) and the span index derived
        #: from them, one entry per row: ``(action, start, end)``.
        self._rows: list[Line] = []
        self._acts: list[list[tuple[str, int, int]]] = []
        # The stamped rows and the span index of the last render: rebuilding
        # them on every hit frame was the frame's cost (render-cost W4).
        # ``_stamp_key`` is the triple they describe -- text, painted width,
        # code wrap -- so a different one re-derives both from the stream
        # cache's answer.
        self._stamp: list[Line] = []
        self._stamp_key: tuple[str, int, WrapMode] | None = None
        #: The span under the pointer: ``(row, start, end)`` or ``None``.
        self._hover_span: tuple[int, int, int] | None = None
        # The one-entry render cache; empty until the first render.
        self._cache = _StreamCache()
        # The fences memo: the last parsed text and its pairs (an empty text
        # is a legitimate key, so ``None`` marks "nothing parsed yet").
        self._fences: list[tuple[str, str]] = []
        self._fences_text: str | None = None
        # One context for the whole document: the resolved deps every rule
        # reads, plus the live registries so nested rendering (quote
        # bodies, list continuations) and paragraph interruption follow the
        # caller's rules exactly like the built-in ones.  The theme is the
        # *effective* one (the explicit theme with every non-None ``styles``
        # group merged over it), and ``_sync_theme`` keeps it in step when
        # either input is reassigned.
        effective = self._effective_theme()
        self._ctx = RenderContext(
            theme=effective,
            highlighter=(
                highlighter
                if highlighter is not None
                else _fence_highlighter(effective)
            ),
            glyphs=glyphs,
            divider_max_width=divider_max_width,
            block_rules=list(BLOCK_RULES) if block_rules is None else list(block_rules),
            inline_rules=list(INLINE_RULES) if inline_rules is None else list(inline_rules),
            code_wrap=code_wrap,
        )

    @property
    def code_wrap(self) -> WrapMode:
        """How a fenced-code row wider than the document wrap responds.

        ``WORD`` (the default) reflows the row, so a long code line stays
        fully readable; ``ELLIPSIS`` / ``CLIP`` keep one row (marked / hard
        cut) and ``OVERFLOW`` hands the natural-width row to the container.
        A write replaces the context's mode, drops the stream cache and the
        stamp key, and touches the widget; the fence delimiter lines are
        single-row labels and stay ellipsized in every mode.
        """
        return self._ctx.code_wrap

    @code_wrap.setter
    def code_wrap(self, value: WrapMode) -> None:
        if value is self._ctx.code_wrap:
            return
        self._ctx = replace(self._ctx, code_wrap=value)
        self._cache = _StreamCache()
        self._stamp_key = None
        self.touch()

    def _effective_theme(self) -> Theme:
        """The theme the rules see: every non-``None`` ``styles`` group merged.

        A group set on :attr:`styles` replaces the theme's whole group; a
        ``None`` field inherits it.  With no override this is the widget's
        own theme (``DEFAULT_THEME`` when none was given), so the common
        path allocates nothing.
        """
        if self.styles is None:
            return self._theme
        overrides = {
            name: group
            for name in (
                "text",
                "surfaces",
                "borders",
                "controls",
                "rows",
                "status",
                "content",
                "chrome",
                "overlays",
                "syntax",
            )
            if (group := getattr(self.styles, name)) is not None
        }
        return replace(self._theme, **overrides) if overrides else self._theme

    def _sync_theme(self) -> None:
        """Re-derive the context theme when ``theme``/``styles`` moved.

        The rule layer reads ``ctx.theme``, so a retheme must reach a mounted
        document: a changed effective theme rebuilds the context (and the
        default highlighter with it) and drops the stream cache and the
        stamp key, so the next render parses and paints under the new bands
        instead of serving the old rows.
        """
        effective = self._effective_theme()
        if effective == self._ctx.theme:
            return
        self._ctx = replace(
            self._ctx,
            theme=effective,
            highlighter=(
                self._ctx.highlighter
                if self._user_highlighter is not None
                else _fence_highlighter(effective)
            ),
        )
        self._cache = _StreamCache()
        self._stamp_key = None

    def render(self, c: Constraints) -> Surface:
        """The document's rows at the constrained width: a pure function of inputs.

        The answer comes from
        the component's one-entry stream cache (:class:`_StreamCache`): an
        unchanged ``(text, width, code_wrap)`` is served as a copy, a text
        that only grew past a sealed block boundary re-renders just its tail
        (for a paragraph, only the suffix that changed) and splices it on,
        anything else renders from scratch.  The returned sequence is always
        fresh, the caller's to keep or trash.

        A changed ``theme``/``styles`` effective theme is synced first
        (:meth:`_sync_theme`): the context theme moves, the stream cache is
        dropped, and every rule paints the new bands.

        The wrap width is the constrained width clamped to :attr:`max_width`
        when the cap is set -- ``max(0, min(width, max_width))``, so a
        degenerate cap (``<= 0``) paints the zero-width answer instead of a
        negative one -- and the clamp happens **before** the cache: the key,
        the streaming splice and the three remembered walks all read the
        clamped width, so a pane wider than the cap still hits the cache.
        The cap never pads: the rows come out narrower than the painting
        width and a painter clears the tail past them.  A ``max_height``
        budget truncates the assembled rows after the hover transform (the
        cache key stays the width, never the budget).  With
        ``code_wrap=OVERFLOW`` a row wider than the painting width hands the
        whole document its natural width (``max(c.width, widest row)``) and
        the answer is :meth:`~motui.kernel.cell.Surface.of` with
        ``pad=False``; every other mode -- the default ``WORD`` included --
        answers :meth:`~motui.kernel.cell.Surface.clipped` and keeps the old
        bytes.

        Three passes sit **around** the cache, never inside it, and the first
        two are remembered with the ``(text, width)`` render they describe
        (render-cost W4: rebuilding them was the frame's cost on every hit):
        the task markers' flat ordinals are stamped onto the rows
        (:func:`_stamp_tasks`), the span index of the stamped rows is derived
        (:func:`_span_index` -- the table ``on_click`` / ``on_hover`` hit-test
        against), and the hovered span, when the pointer is on one, is merged
        into its row of the returned copy.  The remembered rows stay
        hover-free and unstamped by the hover, so the cache's key and the
        streaming splice are exactly what they were.
        """
        self._sync_theme()
        paint = (
            c.width if self.max_width is None else max(0, min(c.width, self.max_width))
        )
        key = (self.text, paint, self._ctx.code_wrap)
        if self._stamp_key != key:
            rows = self._cache.render(self.text, paint, self._ctx, self._gap)
            self._stamp = _stamp_tasks(rows)
            self._acts = _span_index(self._stamp)
            self._stamp_key = key
        rows = list(self._stamp)
        self._rows = rows
        span = self._hover_span
        if span is not None:
            index, start, end = span
            if 0 <= index < len(rows):
                rows[index] = rows[index].merge_span(
                    start, end, self._ctx.theme.surfaces.hover
                )
        content_width = c.width
        if self._ctx.code_wrap is WrapMode.OVERFLOW:
            content_width = max([c.width, *(row.width for row in rows)])
        if c.max_height is not None:
            rows = rows[: c.max_height]
        if content_width > c.width:
            return Surface.of(rows, content_width, pad=False)
        return Surface.clipped(rows, c.width)

    def fences(self) -> list[tuple[str, str]]:
        """The document's top-level fences as ``(lang, code)`` pairs.

        Parsed from :attr:`text` itself -- never from the render cache or the
        last render's rows -- with the block engine's own fence rule
        (:class:`~.blocks.FenceRule`; the shared scanner is
        :func:`~.blocks._scan_fences`): a line whose first non-space run is
        backticks opens a fence, the next such line closes it, the info
        string's first word is the language tag (``""`` when the fence
        carries none), and an unclosed fence runs to the end of the
        document -- the same streaming-safe shape the rule renders.  A
        fence inside a quote body (``> ``` ``) or a list continuation is
        that inner document's, not a top-level line, and is not listed.
        ``code`` is the body's source lines joined with ``"\\n"`` (no
        trailing newline) -- exactly what the rule hands the highlighter --
        and the pairs come in source order.  A host may walk the list for a
        picker -- each pair is the fence's language and its code.

        The parse is remembered per text value (it is a pure function of the
        text, and a streaming host may call this on every frame), and the
        answer is a fresh list of the remembered pairs: the caller owns it,
        the memory keeps its own.
        """
        if self._fences_text != self.text:
            self._fences = _scan_fences(self.text)
            self._fences_text = self.text
        return list(self._fences)

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the cell under the pointer; answer whether the render changed.

        ``None`` (the pointer left) clears the mark.  The cell resolves
        against the span index of the last render: a column inside a span
        remembers ``(row, start, end)``, anything else -- plain prose, a
        column past the row -- clears it.  The answer is whether that span
        differs from the one remembered, exactly when the frame repaints.
        """
        hit = None if pos is None else self._hit(pos.y, pos.x)
        span = None if hit is None else (pos.y, hit[1], hit[2])
        changed = span != self._hover_span
        if changed:
            self._hover_span = span
            self.touch()
        return changed

    def on_click(self, pos: Pos) -> bool:
        """Leave the span's action under ``pos`` pending; hit?

        A cell on a link (or any other action-carrying run a custom rule
        renders) leaves that payload pending for the host to read once
        through :meth:`take`, and answers ``True``; a cell anywhere else --
        plain prose, a column outside the row -- answers ``False`` and
        consumes nothing.
        """
        hit = self._hit(pos.y, pos.x)
        if hit is None:
            return False
        self._emit(hit[0])
        return True

    def _hit(self, row: int, col: int) -> tuple[str, int, int] | None:
        """The action span at ``(row, col)``, off the last render's index."""
        if 0 <= row < len(self._acts):
            for action, start, end in self._acts[row]:
                if start <= col < end:
                    return action, start, end
        return None

    def __repr__(self) -> str:
        return f"Markdown({self.text!r})"
