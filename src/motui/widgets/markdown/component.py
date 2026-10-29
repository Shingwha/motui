"""The component: a Markdown document rendered as rows.

``Markdown`` owns the document's :class:`RenderContext` and hands it to the
shared block loop; rules stay dep-free singletons.
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
    """A fresh built-in block registry, in match order.

    The paragraph catch-all must stay last.  Prepend custom rules; the
    factory returns new instances so callers can extend without touching
    :data:`BLOCK_RULES`.
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

    ``new`` extends ``old``; the walk compares overlapping runs (text, style
    and payloads) and answers ``limit`` when the common prefix parses alike.
    The append-only paragraph render rebuilds rows from this offset on.
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

    The append-only wrap cut: a changed word width can move the break before
    it, so rows from this word on (plus the preceding row) are rebuilt.
    Offsets index the tab-normalized rendered text; whitespace-only tails
    answer the text's end.
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

    Keeps the joined text, parsed segments, wrap spans and rows.  A grown
    text re-parses, then rebuilds only rows from the changed word onward
    (the parse is cheap; keeping the prefix is the point).  Never consulted
    for a different text, width or a shrink.
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
        """The rows for ``text`` and the memory to keep: full or suffix render."""
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

    Holds the last ``(text, width, code_wrap)`` render, its source lines,
    block boundaries and claiming rules.  An unchanged key returns the rows;
    a pure growth re-renders only the tail block (a paragraph may re-render
    only its changed suffix); anything else renders whole.  Reuse is sound
    because a rule reads only the lines it consumes.  Every hand-out is a
    copy.
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

        Applies only when ``text`` is the cached text plus more (no shrink or
        earlier-line change).  Earlier blocks keep their row objects; an
        unchanged tail keeps its rows too, and a grown built-in paragraph
        rebuilds only its suffix.
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
        """Re-run the block loop from block ``first`` on, earlier blocks kept.

        The seed is the loop state after ``first - 1``: earlier rows,
        boundaries and rules plus the line where ``first`` begins.
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

        Needs the tail block to be the built-in paragraph ending at the old
        buffer's end and no rule able to claim the grown line.  With a memory
        only the changed suffix re-parses; without one the paragraph renders
        whole once and keeps the memory.  Any other shape declines.
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

    Display-column, left-closed and right-open, matching
    ``kernel.cell.action_at``; derived once per render for hit testing.
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

    Rewrites ``TASK_ACTION`` placeholders as ``"todo:<i>"`` in draw order
    across the whole document.  The walk runs after the cache, on the copy
    handed out, so cached rows stay unstamped and streaming resumes match a
    whole render.  Rows without a placeholder are returned unchanged.
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
    """A Markdown document rendered as rows, driven by a rule registry.

    ``render`` is a pure function of ``text``, width and ``code_wrap``; the
    stream cache reuses the unchanged answer and splices a grown tail (a
    paragraph rebuilds only its changed suffix), so streaming text costs per
    frame what its new words cost.  ``block_rules``/``inline_rules`` replace
    the registries; ``theme``/``styles``, ``glyphs``, ``gap``,
    ``divider_max_width`` and ``max_width`` configure the built-ins.
    Links and task boxes are clickable action spans: ``on_click`` leaves
    their payload pending for :meth:`take`; ``fences()`` reads top-level
    fences from the source text.
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
        """How an over-wide fenced-code row responds.

        A write replaces the mode, drops the stream cache and touches the
        widget; fence delimiter lines stay ellipsized in every mode.
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
        """The theme the rules see: every non-``None`` ``styles`` group merged."""
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

        A changed effective theme rebuilds the context and default
        highlighter and drops the stream cache.
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
        """The document's rows at the constrained width.

        The width is clamped to :attr:`max_width` before the stream cache,
        which serves unchanged answers, splices grown tails and otherwise
        renders whole.  Task ordinals and the span index are derived once
        per ``(text, width, code_wrap)``; the hovered span is merged into the
        returned copy.  ``OVERFLOW`` widens the surface to the content.
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

        Parsed from :attr:`text` by the block engine's fence rule: info
        string's first word is the language, an unclosed fence runs to the
        end, and fences nested in quotes or lists are excluded.  Memoized
        per text; the caller owns the returned list.
        """
        if self._fences_text != self.text:
            self._fences = _scan_fences(self.text)
            self._fences_text = self.text
        return list(self._fences)

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the action span under the pointer; True when the render changed.

        ``None`` clears it; cells outside a span clear it too.
        """
        hit = None if pos is None else self._hit(pos.y, pos.x)
        span = None if hit is None else (pos.y, hit[1], hit[2])
        changed = span != self._hover_span
        if changed:
            self._hover_span = span
            self.touch()
        return changed

    def on_click(self, pos: Pos) -> bool:
        """Leave the action under ``pos`` pending; ``False`` off every span."""
        hit = self._hit(pos.y, pos.x)
        if hit is None:
            return False
        self._emit(hit[0])
        return True

    def _hit(self, row: int, col: int) -> tuple[str, int, int] | None:
        if 0 <= row < len(self._acts):
            for action, start, end in self._acts[row]:
                if start <= col < end:
                    return action, start, end
        return None

    def __repr__(self) -> str:
        return f"Markdown({self.text!r})"
