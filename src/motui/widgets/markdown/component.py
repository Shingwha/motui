"""The component: a Markdown document rendered as rows.

``Markdown`` owns the one :class:`~.context.RenderContext` of a document --
the resolved theme, the fenced-code engine, the divider cap and the two live
registries -- and hands it to the shared block loop on every ``render``.
Rules themselves stay dep-free singletons, so the component is the only
place that resolves anything.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...kernel.lines import Line, Segment
from ...kernel.theme import Theme, Themed
from .blocks import (
    BlockRule,
    FenceRule,
    HeadingRule,
    ParagraphRule,
    ThematicBreakRule,
    _BlockScan,
    _fence_highlighter,
    _scan_fences,
)
from .context import RenderContext
from .inline import INLINE_RULES, InlineRule
from .nested import ListRule, QuoteRule, TASK_ACTION
from ..syntax import Highlighter
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


class _StreamCache:
    """One Markdown render answer, and the append-only reuse rule.

    Holds the last ``(text, width)`` render: its rows, the source lines
    they came from and ``boundaries``, the ``(end, rows so far)`` pair the
    block loop recorded for every block.  :meth:`render` answers a new key
    one of three ways:

    * an unchanged key returns a copy of the cached rows;
    * a text that only *grew* past the last sealed boundary re-renders just
      its tail and splices the cached prefix on (:meth:`_resume`);
    * anything else -- a different width, a shrink, a mid-string change --
      renders the whole document and replaces the entry.

    One entry per component: a streaming working set, not a history.  The
    rows are the component's private copy -- every hand-out is a copy,
    because the viewport treats a returned list as its own.

    The reuse is sound because the :class:`~.blocks.BlockRule` protocol has
    a rule classify from its cursor over the lines it consumes -- it reads
    nothing before its start and nothing past its end -- so a render that
    opens mid-buffer at a sealed boundary sees for its tail exactly what a
    whole-buffer render sees.
    """

    __slots__ = ("_boundaries", "_lines", "_primed", "_rows", "_text", "_width")

    def __init__(self) -> None:
        self._primed = False
        self._text = ""
        self._width = 0
        self._rows: list[Line] = []
        self._lines: list[str] = []
        self._boundaries: list[tuple[int, int]] = []

    def render(
        self, text: str, width: int, ctx: RenderContext, gap: int
    ) -> list[Line]:
        """The rows for ``(text, width)``, reusing the cached prefix when sound."""
        if self._primed and self._width == width:
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
        self._store(text, width, lines, scan.rows, scan.boundaries)

    def _resume(self, text: str, width: int, ctx: RenderContext, gap: int) -> bool:
        """The append-only path: re-render the tail past the sealed prefix.

        The reuse applies only when ``text`` is the cached text plus more:
        a different width, a shrink, or a changed earlier line is the
        caller's full-render path (``False``).  A block boundary is sealed
        once the line following it is inside the buffer: the rule that
        claimed the block stopped at that line, so no line appended
        afterwards can change what the block rendered.  The tail render
        opens at the *last* sealed boundary and extends the rows already
        emitted for the prefix, which keeps the one-row gap exactly where a
        from-scratch render puts it.  Nothing inside an open paragraph,
        fence, table, list or quote is ever reused: those blocks ran to the
        buffer's end, so their boundary did not seal.
        """
        lines = text.split("\n")
        cached_count = len(self._lines)
        if len(lines) <= cached_count or lines[:cached_count] != self._lines:
            return False  # shrank, or a line the cached render consumed changed
        sealed = [
            index
            for index, (end, _rows) in enumerate(self._boundaries)
            if end < cached_count
        ]
        if not sealed:
            return False  # every block is still open: no sealed prefix to reuse
        last = sealed[-1]
        resume, rows_emitted = self._boundaries[last]
        boundaries = self._boundaries[: last + 1]
        scan = _BlockScan(
            lines,
            width,
            ctx,
            gap,
            start=resume,
            rows=self._rows[:rows_emitted],
            boundaries=boundaries,
        )
        scan.run()
        self._store(text, width, lines, scan.rows, scan.boundaries)
        return True

    def _store(
        self,
        text: str,
        width: int,
        lines: list[str],
        rows: list[Line],
        boundaries: list[tuple[int, int]],
    ) -> None:
        self._primed = True
        self._text = text
        self._width = width
        self._lines = lines
        self._rows = rows
        self._boundaries = boundaries


def _span_index(rows: Sequence[Line]) -> list[list[tuple[str, int, int]]]:
    """The action spans of ``rows``: one ``(action, start, end)`` list per row.

    The index :meth:`Markdown.click` / :meth:`Markdown.hover_at` read, so the
    hit testing never re-walks the segments: derived in display columns (the
    :attr:`~motui.kernel.lines.Segment.width` walk, left-closed and
    right-open, exactly what :func:`~motui.kernel.lines.action_at` answers
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


class Markdown(Themed):
    """A Markdown document rendered as rows, rule-registry driven.

    ``text`` is a mutable attribute (streaming text assigns to it);
    ``render(width)`` is a pure function of ``text`` and ``width`` and never
    returns a row wider than ``width``.  The last answer lives in one
    :class:`_StreamCache` entry keyed on the ``(text, width)`` pair, so a
    document re-rendered every frame (the viewport re-renders an open block
    on every layout) parses once, not once per frame -- the cache is
    invisible: a repeated call hands back a copy of the very same rows.  A
    text that only *grew* does better still: the tail past the last sealed
    block boundary re-renders and splices onto the cached rows, so a reply
    streaming in line by line renders its new lines and nothing else.
    ``block_rules`` / ``inline_rules`` replace the built-in registries
    (:data:`BLOCK_RULES` / :data:`INLINE_RULES` are immutable tuples; the
    defaults are copied per component, and the block registry must end with
    a paragraph-style catch-all; see :class:`~.blocks.ParagraphRule`).
    ``theme`` restyles the built-in rules (headings, code, quotes, list
    markers, links and the embedded ``Table``/``Divider``); custom rules keep
    their own styles -- they read what they need off the context they are
    handed.  ``highlighter`` injects the fenced-code engine (anything with
    ``highlight(code, lang) -> list[Line]``; the built-in regex highlighter
    by default, restyled by ``theme``).  ``gap`` sets how many blank rows
    separate adjacent blocks (default 1, the pi reference's section breathing
    room; a negative value degrades to 0).  ``divider_max_width`` caps
    thematic-break rules' dividers at that many columns (default 80, the pi
    reference's rule width; ``None`` spans the whole width).  Blank input
    rows are dropped: the source's own blank lines never add spacing beyond
    one gap, and ``gap=0`` restores the old direct stacking (no blank rows
    between blocks).

    **Inline links are clickable spans.**  A ``[label](url)`` run carries the
    url as its ``Segment.link`` (the terminal gets a real OSC 8 hyperlink)
    and as its ``Segment.action``, so the component is :class:`Hoverable` and
    :class:`Clickable` over its **last render's** row table:
    ``click(row, col)`` lands the url of the span the cell hit in
    :attr:`chosen` (the host reads it once and resets it) and answers
    ``True`` -- a cell off every span declines -- and ``hover_at(row, col)``
    remembers the span under the pointer, answering whether the render
    changed.  The span index (row -> ``(action, start, end)``, columns as
    :func:`~motui.kernel.lines.action_at` reports them) is derived from
    the rows once per render, after the cache and never inside it; the hover
    is a **post-transform of those cached rows** (the hit row is rebuilt with
    the theme's ``hover`` merged onto the span), so the ``(text, width)``
    cache key and the row cache itself stay hover-free -- and a document with
    no pointer on it renders byte-for-byte what it always did.

    **Task lists** are the same door with a different payload.  A bullet
    item whose content opens with ``[ ]`` / ``[x]`` (one space, GFM's rule)
    renders its bullet as a one-column box -- :data:`~.nested.TODO_MARK`
    (``\\u2610``) unchecked, :data:`~.nested.DONE_MARK` (``\\u2611``)
    checked -- and the whole ``"\\u2610 "`` run is one action span whose
    payload is ``"todo:<flat index>"``: the index of the task among the
    document's tasks, counting from zero in draw order across every list,
    margin and nesting level.  The rule layer is stateless, so it hangs the
    bare placeholder and :func:`_stamp_tasks` writes the ordinal onto the
    finished rows after the cache (the hover rule's shape: cache untouched,
    streaming resume unaffected).  A click on the box lands the payload in
    ``chosen`` -- read once, like a link's url -- and the *host* owns the
    rest of the loop, because ``text`` is the host's::

        if md.chosen and md.chosen.startswith("todo:"):
            index = int(md.chosen.removeprefix("todo:"))
            md.text = toggle_task(md.text, index)   # the host's own rewrite
            md.chosen = None

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

    __slots__ = (
        "_acts",
        "_cache",
        "_ctx",
        "_gap",
        "_hover_span",
        "_hover_style",
        "_rows",
        "chosen",
        "hover",
        "text",
        "theme",
    )

    def __init__(
        self,
        text: str = "",
        *,
        block_rules: Sequence[BlockRule] | None = None,
        inline_rules: Sequence[InlineRule] | None = None,
        theme: Theme | None = None,
        highlighter: Highlighter | None = None,
        gap: int = 1,
        divider_max_width: int | None = 80,
    ) -> None:
        super().__init__(theme)
        self.text = text
        self.theme = theme
        self._gap = gap if gap > 0 else 0  # degrade negatives, never raise
        #: The pointer tier's flag, the peer of ``focused``: written by
        #: ``Pointer`` and never read here -- the visual is the hovered span.
        self.hover = False
        #: The pending pick: ``click`` lands a hit span's action (the url of
        #: a link) here, and the host reads it once, resetting it to None.
        self.chosen: str | None = None
        # The one themed style this component picks beyond its rules: the
        # pointer-hover band a hovered span merges.
        self._hover_style = self._pick(None, "hover")
        #: The last render's rows (the viewport's copy is its own; these are
        #: the base rows the hit testing reads) and the span index derived
        #: from them, one entry per row: ``(action, start, end)``.
        self._rows: list[Line] = []
        self._acts: list[list[tuple[str, int, int]]] = []
        #: The span under the pointer: ``(row, start, end)`` or ``None``.
        self._hover_span: tuple[int, int, int] | None = None
        # The one-entry render cache; empty until the first render.
        self._cache = _StreamCache()
        # One frozen context for the whole document: the resolved deps every
        # rule reads, plus the live registries so nested rendering (quote
        # bodies, list continuations) and paragraph interruption follow the
        # caller's rules exactly like the built-in ones.
        self._ctx = RenderContext(
            theme=self._theme,
            highlighter=(
                highlighter if highlighter is not None else _fence_highlighter(theme)
            ),
            divider_max_width=divider_max_width,
            block_rules=list(BLOCK_RULES) if block_rules is None else list(block_rules),
            inline_rules=list(INLINE_RULES) if inline_rules is None else list(inline_rules),
        )

    def render(self, width: int) -> list[Line]:
        """The document's rows at ``width``: a pure function of text and width.

        The answer comes from the component's one-entry stream cache
        (:class:`_StreamCache`): an unchanged ``(text, width)`` is served
        as a copy, a text that only grew past a sealed block re-renders
        just its tail and splices it on, anything else renders from
        scratch.  The returned list is always fresh, the caller's to keep
        or trash.

        Two things happen around the cache, never inside it: the span index
        of the rows is derived (the hit testing of ``click`` / ``hover_at``
        reads it, so it always describes the render the user is looking at),
        and the hovered span -- when the pointer is on one -- is merged into
        its row on the returned copy.  The cache's own rows stay hover-free,
        so the key and the streaming splice are exactly what they were.

        One more pass sits between the cache and the span index: the task
        markers' flat ordinals are stamped onto the returned rows
        (:func:`_stamp_tasks`), so the ``"todo:<i>"`` payloads follow the
        document's draw order while the cached rows keep the bare
        placeholder.  A document with no tasks skips it (the list comes
        back untouched).
        """
        rows = self._cache.render(self.text, width, self._ctx, self._gap)
        rows = _stamp_tasks(rows)
        self._rows = rows
        self._acts = _span_index(rows)
        span = self._hover_span
        if span is not None:
            index, start, end = span
            if 0 <= index < len(rows):
                rows[index] = rows[index].merge_span(start, end, self._hover_style)
        return rows

    def fences(self) -> list[tuple[str, str]]:
        """The document's top-level fences as ``(lang, code)`` pairs.

        Parsed from :attr:`text` itself on every call -- never from the
        render cache or the last render's rows -- with the block engine's
        own fence rule (:class:`~.blocks.FenceRule`; the shared scanner is
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
        """
        return _scan_fences(self.text)

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the cell under the pointer; answer whether the render changed.

        ``row < 0`` (the pointer left) clears the mark.  The cell resolves
        against the span index of the last render: a column inside a span
        remembers ``(row, start, end)``, anything else -- plain prose, a
        column past the row -- clears it.  The answer is whether that span
        differs from the one remembered, exactly when the frame repaints.
        """
        hit = self._hit(row, col)
        span = None if hit is None else (row, hit[1], hit[2])
        changed = span != self._hover_span
        self._hover_span = span
        return changed

    def click(self, row: int, col: int) -> bool:
        """Take the span's action under ``(row, col)`` into :attr:`chosen`; hit?

        A cell on a link (or any other action-carrying run a custom rule
        renders) lands that payload in ``chosen`` for the host to read once
        and answers ``True``; a cell anywhere else -- plain prose, a column
        outside the row -- answers ``False`` and consumes nothing.
        """
        hit = self._hit(row, col)
        if hit is None:
            return False
        self.chosen = hit[0]
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
