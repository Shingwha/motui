"""The block engine: ordered rules that classify a line, then render it.

A rule matches a run of lines at the cursor and renders exactly that slice.
Rules are stateless and dep-free; this module holds the protocol, the
single-line/delimiter rules, paragraphs and the shared block loop.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from ...kernel.cell import Line, slice_line
from ...kernel.text import WrapMode, _normalize_tabs, wrap_spans
from ...kernel.theme import Theme
from ..decor import Divider
from .inline import inline_segments
from ..syntax import Highlighter, RegexHighlighter, default_highlighter
from ...kernel.layout import Constraints

if TYPE_CHECKING:  # annotations only: rendering happens through a ctx
    from .context import RenderContext

__all__ = [
    "BlockRule",
    "FenceRule",
    "HeadingRule",
    "ParagraphRule",
    "ThematicBreakRule",
]


class BlockRule(Protocol):
    """One block-level construct: classify at the cursor, then render.

    ``match`` returns the lines consumed at ``lines[i]`` (``None`` to
    decline); ``render`` gets that slice and the document context.  Rules
    are stateless and shared.
    """

    name: str

    def match(self, lines: list[str], i: int) -> int | None: ...

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]: ...


# --- patterns ----------------------------------------------------------------

# ATX heading: 1..6 leading '#' + whitespace + content.
_ATX_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# Fence delimiter: a line whose first non-space run is backticks.
_FENCE_RE = re.compile(r"^\s*```")

# Fence info string: whatever follows the opening backtick run.
_INFO_RE = re.compile(r"^\s*`{3,}(.*)$")

# Thematic break: a standalone run of 3+ '-' or '*' (spaces allowed between).
_BREAK_RE = re.compile(r"^ {0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,})$")


class HeadingRule:
    """ATX heading: ``#``..``######`` plus a space, on the heading ladder.

    h1/h2 strip the marker; h3+ keep it as the depth cue.
    """

    name = "heading"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _ATX_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        matched = _ATX_RE.match(lines[0])
        assert matched is not None  # match() gated this shape
        level = len(matched.group(1))
        base = ctx.theme.content.headings[level - 1]
        text = matched.group(2).strip()
        if level >= 3:
            text = f"{matched.group(1)} {text}"  # the hashes stay visible
        line = Line(inline_segments(text, ctx, base))
        return line.reflow(WrapMode.WORD, width)


def _fence_highlighter(theme: Theme | None) -> Highlighter:
    """The engine a fence uses: the shared default, or a theme-bound one."""
    return default_highlighter() if theme is None else RegexHighlighter(theme=theme)


def _fence_lang(opening: str) -> str:
    """The language tag: the info string's first word, or ``""``."""
    matched = _INFO_RE.match(opening)
    info = matched.group(1).split() if matched else []
    return info[0] if info else ""


def _scan_fences(text: str) -> list[tuple[str, str]]:
    """Every top-level fence of ``text`` as ``(lang, code)``, in source order.

    Same rules as :class:`FenceRule`: backtick runs open/close, the first
    info word is the language, an unclosed fence runs to the end.  Fences
    nested in quotes/lists are not top-level; this never reads a render
    cache.
    """
    lines = text.split("\n")
    out: list[tuple[str, str]] = []
    i, count = 0, len(lines)
    while i < count:
        if not _FENCE_RE.match(lines[i]):
            i += 1
            continue
        j = i + 1
        while j < count and not _FENCE_RE.match(lines[j]):
            j += 1
        out.append((_fence_lang(lines[i]), "\n".join(lines[i + 1 : j])))
        i = j + 1 if j < count else count  # step past the closing fence, or stop
    return out


class FenceRule:
    """Fenced code: ```` ``` ````-delimited lines with an optional language.

    The info string's first word selects highlighting; unknown/missing tags
    fall back to monochrome.  Delimiter lines stay visible in
    ``text.muted`` and ellipsized; code lines use ``ctx.code_wrap`` and
    keep the highlighter's segment styles.  An unclosed fence runs to the
    end (streaming-safe).
    """

    name = "fence"

    def match(self, lines: list[str], i: int) -> int | None:
        if not _FENCE_RE.match(lines[i]):
            return None
        j = i + 1
        while j < len(lines) and not _FENCE_RE.match(lines[j]):
            j += 1
        return min(j + 1, len(lines)) - i  # include the closing fence when present

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        theme = ctx.theme
        engine = (
            ctx.highlighter
            if ctx.highlighter is not None
            else _fence_highlighter(theme)
        )
        closed = len(lines) > 1 and _FENCE_RE.match(lines[-1])
        body = lines[1:-1] if closed else lines[1:]
        code = "\n".join(body)
        out = [Line.from_text(lines[0].strip(), theme.text.muted).clip(WrapMode.ELLIPSIS, width)]
        for row in engine.highlight(code, _fence_lang(lines[0])):
            out.extend(row.reflow(ctx.code_wrap, width))
        if closed:
            out.append(Line.from_text(lines[-1].strip(), theme.text.muted).clip(WrapMode.ELLIPSIS, width))
        return out


class ThematicBreakRule:
    """Thematic break: a standalone ``---`` / ``***`` line, as a Divider.

    Capped at the context's ``divider_max_width``.
    """

    name = "thematic_break"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _BREAK_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        return Divider(
            theme=ctx.theme,
            glyphs=ctx.glyphs,
            max_width=ctx.divider_max_width,
        ).render(Constraints(width=width))


def _paragraph_text(lines: list[str]) -> str:
    """The paragraph body: the run's lines stripped and joined with one space."""
    return " ".join(raw.strip() for raw in lines)


def _wrap_paragraph(
    text: str, width: int, ctx: RenderContext
) -> tuple[Line, list[tuple[int, int]], list[Line]]:
    """A paragraph text's parsed line, wrap spans and rows.

    Shared by the rule and the append-only tail render, which need the same
    spans; wrapping uses the rendered text's tab-normalized offsets.
    """
    line = Line(inline_segments(text, ctx))
    normalized = _normalize_tabs(line.text)
    spans = wrap_spans(normalized, width)
    rows = [slice_line(line, start, end).clip(WrapMode.ELLIPSIS, width) for start, end in spans]
    return line, spans, rows


class ParagraphRule:
    """The catch-all: soft-wrapped lines plus inline rules.

    Consumes until a blank row; the loop trims the run at the first line
    another rule claims, so custom rules interrupt it.  Must stay last in
    ``BLOCK_RULES``.
    """

    name = "paragraph"

    def match(self, lines: list[str], i: int) -> int | None:
        j = i + 1
        while j < len(lines) and lines[j].strip():
            j += 1
        return j - i

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        return _wrap_paragraph(_paragraph_text(lines), width, ctx)[2]


class _BlockScan:
    """One walk over a document's lines: classify, render, record boundaries.

    ``boundaries`` records ``(end, len(rows))`` after each block and
    ``rules`` the claiming rule, so a streaming resume can find a sealed
    prefix; ``start``/``rows``/``boundaries``/``rules`` seed a resume that
    matches a from-scratch render row for row.
    """

    __slots__ = ("boundaries", "ctx", "gap", "lines", "rows", "rules", "start", "width")

    def __init__(
        self,
        lines: list[str],
        width: int,
        ctx: RenderContext,
        gap: int = 1,
        *,
        start: int = 0,
        rows: list[Line] | None = None,
        boundaries: list[tuple[int, int]] | None = None,
        rules: list[BlockRule] | None = None,
    ) -> None:
        self.lines = lines
        self.width = width
        self.ctx = ctx
        self.gap = gap
        self.start = start
        self.rows: list[Line] = [] if rows is None else rows
        self.boundaries: list[tuple[int, int]] = (
            [] if boundaries is None else boundaries
        )
        self.rules: list[BlockRule] = [] if rules is None else rules

    def run(self) -> None:
        """Walk from ``start`` to the end, extending ``rows``/``boundaries``/``rules``."""
        rules = self.ctx.block_rules
        interrupters = [rule for rule in rules if not isinstance(rule, ParagraphRule)]
        out = self.rows
        i, n = self.start, len(self.lines)
        while i < n:
            if not self.lines[i].strip():
                i += 1
                continue
            for rule in rules:
                consumed = rule.match(self.lines, i)
                if consumed:
                    if out and self.gap > 0:
                        out.append(Line())
                    end = i + consumed
                    if isinstance(rule, ParagraphRule):
                        end = _paragraph_end(self.lines, i, end, interrupters)
                    out.extend(rule.render(self.lines[i:end], self.width, self.ctx))
                    self.boundaries.append((end, len(out)))
                    self.rules.append(rule)
                    i = end
                    break
            else:
                # No rule claims the line: only reachable when the registry
                # lacks a trailing catch-all.  Skip, never loop.
                i += 1


def _run_blocks(
    lines: list[str],
    width: int,
    ctx: RenderContext,
    gap: int = 1,
) -> list[Line]:
    """Render ``lines`` through the context's registry -- the shared block loop.

    One blank row separates blocks when ``gap`` > 0.  The paragraph
    catch-all yields to any other rule at an interior line; other rules own
    their whole run.
    """
    scan = _BlockScan(lines, width, ctx, gap)
    scan.run()
    return scan.rows


def _paragraph_end(
    lines: list[str], start: int, limit: int, interrupters: list[BlockRule]
) -> int:
    """Where the paragraph run ends: ``limit``, or the first interior line another rule claims."""
    for j in range(start + 1, limit):
        if any(rule.match(lines, j) for rule in interrupters):
            return j
    return limit
