"""The component: a Markdown document rendered as rows.

``Markdown`` owns the one :class:`~.context.RenderContext` of a document --
the resolved theme, the fenced-code engine, the divider cap and the two live
registries -- and hands it to the shared block loop on every ``render``.
Rules themselves stay dep-free singletons, so the component is the only
place that resolves anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ...core.lines import Line
from ...core.theme import DEFAULT_THEME, Theme
from .blocks import (
    BlockRule,
    FenceRule,
    HeadingRule,
    ParagraphRule,
    ThematicBreakRule,
    _fence_highlighter,
    _run_blocks,
)
from .context import RenderContext
from .inline import INLINE_RULES, InlineRule
from .nested import ListRule, QuoteRule
from ..syntax import Highlighter
from .tables import TableRule

__all__ = ["BLOCK_RULES", "Markdown", "default_block_rules"]


def default_block_rules() -> list[BlockRule]:
    """The built-in block registry, dep-free and shared.

    Order is the match priority; :class:`~.blocks.ParagraphRule` is the
    mandatory catch-all at the end.  Build a custom registry by prepending
    your own rules: ``[MyRule(), *default_block_rules()]``.
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


#: Block registry: tried in order, first match consumes; last is the
#: paragraph catch-all.
BLOCK_RULES: list[BlockRule] = default_block_rules()


@dataclass(frozen=True)
class _CachedRender:
    """One ``render`` answer, keyed by the values it derives from (D3).

    ``text`` and ``width`` are the whole key: they are exactly what a
    render depends on, so the entry is replaced by the same mutation -- a
    new text value or a new width -- that would change the answer.  One
    entry per component: a streaming working set, not a history.  ``rows``
    is the component's private copy -- every hand-out is a copy, because
    the viewport treats a returned list as its own.

    ``lines`` is the source the rows came from and ``boundaries`` the
    ``(end, rows so far)`` pair the block loop recorded for every block:
    together they let a text that only *grew* re-render just its tail
    (see :func:`_resume_append_only`).
    """

    text: str
    width: int
    rows: list[Line]
    lines: list[str]
    boundaries: list[tuple[int, int]]


def _resume_append_only(
    cache: _CachedRender, text: str, width: int, ctx: RenderContext, gap: int
) -> _CachedRender | None:
    """The render of a ``text`` that only grew past ``cache``, or ``None``.

    ``None`` whenever the reuse does not apply -- a different width, a text
    that shrank or whose earlier lines changed, or a cached render with
    nothing sealed in it -- and the caller then takes the full-render path.

    A block boundary is sealed once the line following it is inside the
    buffer: the rule that claimed the block stopped at that line, so no line
    appended afterwards can change what the block rendered.  The tail render
    therefore opens at the *last* sealed boundary and extends the rows
    already emitted for the prefix -- which keeps the one-row gap exactly
    where a from-scratch render puts it.  Nothing inside an open paragraph,
    fence, table, list or quote is ever reused: those blocks ran to the
    buffer's end, so their boundary did not seal.

    This is sound because the BlockRule protocol has a rule classify from
    its cursor over the lines it consumes -- it reads nothing before its
    start and nothing past its end -- so a render that opens mid-buffer at
    a sealed boundary sees for its tail exactly what a whole-buffer render
    sees.
    """
    lines = text.split("\n")
    cached = cache.lines
    cached_count = len(cached)
    if len(lines) <= cached_count or lines[:cached_count] != cached:
        return None  # shrank, or a line the cached render consumed changed
    resume = rows_emitted = 0
    for end, emitted in cache.boundaries:
        if end >= cached_count:
            break  # ran to the buffer's end: that block is still open
        resume, rows_emitted = end, emitted
    if not resume:
        return None  # every block is still open: no sealed prefix to reuse
    boundaries = [entry for entry in cache.boundaries if entry[0] <= resume]
    rows = _run_blocks(
        lines,
        width,
        ctx,
        gap,
        boundaries=boundaries,
        start=resume,
        out=cache.rows[:rows_emitted],
    )
    return _CachedRender(
        text=text, width=width, rows=rows, lines=lines, boundaries=boundaries
    )


class Markdown:
    """A Markdown document rendered as rows, rule-registry driven.

    ``text`` is a mutable attribute (streaming text assigns to it);
    ``render(width)`` is a pure function of ``text`` and ``width`` and never
    returns a row wider than ``width``.  The last answer is cached on the
    ``(text, width)`` pair and replaced whenever either value changes, so a
    document re-rendered every frame (the viewport re-renders an open block
    on every layout) parses once, not once per frame -- the cache is
    invisible: a repeated call hands back a copy of the very same rows.  A
    text that only *grew* does better still: the tail past the last sealed
    block boundary re-renders and splices onto the cached rows, so a reply
    streaming in line by line renders its new lines and nothing else.
    ``block_rules`` / ``inline_rules`` replace the built-in registries (the
    block registry must end with a paragraph-style catch-all; see
    :class:`~.blocks.ParagraphRule`).
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
    """

    __slots__ = ("_cache", "_ctx", "_gap", "text", "theme")

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
        self.text = text
        self.theme = theme
        self._gap = gap if gap > 0 else 0  # degrade negatives, never raise
        # One render answer cached, keyed on the values it derives from --
        # see _CachedRender.  Empty until the first render.
        self._cache: _CachedRender | None = None
        # One frozen context for the whole document: the resolved deps every
        # rule reads, plus the live registries so nested rendering (quote
        # bodies, list continuations) and paragraph interruption follow the
        # caller's rules exactly like the built-in ones.
        self._ctx = RenderContext(
            theme=theme if theme is not None else DEFAULT_THEME,
            highlighter=(
                highlighter if highlighter is not None else _fence_highlighter(theme)
            ),
            divider_max_width=divider_max_width,
            block_rules=BLOCK_RULES if block_rules is None else list(block_rules),
            inline_rules=INLINE_RULES if inline_rules is None else list(inline_rules),
        )

    def render(self, width: int) -> list[Line]:
        """The document's rows at ``width``: a pure function of text and width.

        The last answer is served from the cache when both key values are
        unchanged; a text that only grew past it re-renders just its tail
        and splices it on (:func:`_resume_append_only`); anything else --
        a new width, a shrink, a mid-string change -- renders from scratch
        and replaces the entry.  The returned list is always a fresh copy,
        the caller's to keep or trash.
        """
        text = self.text
        cache = self._cache
        if cache is not None and cache.width == width:
            if cache.text == text:
                return list(cache.rows)
            grown = _resume_append_only(cache, text, width, self._ctx, self._gap)
            if grown is not None:
                self._cache = grown
                return list(grown.rows)
        lines = text.split("\n")
        boundaries: list[tuple[int, int]] = []
        rows = _run_blocks(lines, width, self._ctx, self._gap, boundaries=boundaries)
        self._cache = _CachedRender(
            text=text, width=width, rows=rows, lines=lines, boundaries=boundaries
        )
        return list(rows)

    def __repr__(self) -> str:
        return f"Markdown({self.text!r})"
