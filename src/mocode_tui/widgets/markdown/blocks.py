"""The block engine: ordered rules that classify a line, then render it.

A :class:`BlockRule` looks at the cursor and either declines (``match``
returns ``None``) or claims a number of lines starting there; it then renders
exactly that slice into finished rows.  Matching never needs the render
context -- the built-in rules classify on shape alone -- so ``match`` stays
ctx-free, and every rule is a stateless dep-free singleton that reads
``theme`` / ``highlighter`` / the live registries off the
:class:`~.context.RenderContext` it is handed at render time.

This module holds the protocol, the rules that own a single line or a
delimiter-bounded run (headings, fences, thematic breaks, the paragraph
catch-all), and :func:`_run_blocks` -- the shared loop every renderer of a
document (and every quote body or list continuation) goes through.  The two
rules whose bodies are themselves documents live in :mod:`.nested`; the GFM
table lives in :mod:`.tables`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from ...core.lines import Line, wrap_line
from ...core.theme import DEFAULT_THEME, Theme
from ..decor import Divider
from .inline import inline_segments
from ..syntax import Highlighter, RegexHighlighter, default_highlighter

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

    ``match`` returns the number of lines the rule consumes starting at
    ``lines[i]`` (``None`` -- or any falsy value -- when it declines);
    ``render`` receives exactly that slice plus the
    :class:`~.context.RenderContext` of the document being rendered and
    returns finished rows.  Rules are stateless: the same instance serves
    every :class:`~.component.Markdown`.
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
    """ATX heading: ``#``..``######`` + space, on the theme's heading ladder.

    h1 and h2 strip their marker (h1 underlines, h2 stands alone); h3 and
    deeper keep their hashes -- once every level shares one color, the
    marker is the depth cue, the reference palette's convention.
    """

    name = "heading"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _ATX_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        matched = _ATX_RE.match(lines[0])
        assert matched is not None  # match() gated this shape
        level = len(matched.group(1))
        base = ctx.theme.headings[level - 1]
        text = matched.group(2).strip()
        if level >= 3:
            text = f"{matched.group(1)} {text}"  # the hashes stay visible
        line = Line(inline_segments(text, ctx, base))
        return [row.fit(width) for row in wrap_line(line, width)]


def _fence_highlighter(theme: Theme | None) -> Highlighter:
    """The engine a fence uses when none was injected: shared default, or a
    theme-bound one for a custom theme."""
    return default_highlighter() if theme is None else RegexHighlighter(theme=theme)


def _fence_lang(opening: str) -> str:
    """The language tag of an opening fence line.

    The first word of its info string -- the "```python title=x" line tags
    as "python" -- or "" when the fence carries no info string at all.
    """
    matched = _INFO_RE.match(opening)
    info = matched.group(1).split() if matched else []
    return info[0] if info else ""


class FenceRule:
    """Fenced code: ```` ``` ````-delimited lines, optional language tag.

    The info string's first word after the opening fence (`` ```python ``)
    is the language tag; the body goes through the context's highlighter, so
    a tagged fence renders with syntax colors.  An unknown or missing tag
    falls back to the theme's ``code`` monochrome, and ``highlighter``
    injects a replacement engine (see :class:`~.component.Markdown`).  The
    opening (`` ```python ``) and closing (`` ``` ``) fence lines stay
    visible in the context theme's ``muted`` -- they name the language and
    frame the block, the pi reference shows them too.  An unclosed fence runs
    to the end of the buffer (streaming-safe): the opening marker renders,
    the closing one appears only once the fence actually closes.  Only the
    code lines' colors come from the highlighter -- the fence has no
    container of its own.
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
        out = [Line.from_text(lines[0].strip(), theme.muted).fit(width)]
        out.extend(
            row.fit(width) for row in engine.highlight(code, _fence_lang(lines[0]))
        )
        if closed:
            out.append(Line.from_text(lines[-1].strip(), theme.muted).fit(width))
        return out


class ThematicBreakRule:
    """Thematic break: a standalone ``---`` / ``***`` line, as a Divider.

    The divider is capped at the context's ``divider_max_width`` (``None``
    spans the whole width) -- what :class:`~.component.Markdown`'s
    ``divider_max_width`` parameter sets.
    """

    name = "thematic_break"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _BREAK_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        return Divider(theme=ctx.theme, max_width=ctx.divider_max_width).render(width)


class ParagraphRule:
    """The catch-all: soft-wrapped lines plus inline rules.

    Consumes lines until a blank row; the block loop then trims the run at
    the first line another rule of the same registry claims (see
    :func:`_run_blocks`), so a custom block rule placed before the catch-all
    interrupts a paragraph exactly like a built-in one.  Must stay last in
    :data:`~.component.BLOCK_RULES`.
    """

    name = "paragraph"

    def match(self, lines: list[str], i: int) -> int | None:
        j = i + 1
        while j < len(lines) and lines[j].strip():
            j += 1
        return j - i

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        text = " ".join(raw.strip() for raw in lines)
        line = Line(inline_segments(text, ctx))
        return [row.fit(width) for row in wrap_line(line, width)]


class _BlockScan:
    """One walk over a document's lines: classify, render, record boundaries.

    The shared loop behind :func:`_run_blocks` and the component's streaming
    reuse.  ``rows`` accumulates the rendered rows; ``boundaries`` receives
    ``(end, len(rows))`` after every block -- the source-line index just
    past it and the row count so far -- which is how a caller finds where a
    sealed prefix ends.

    The constructor's ``start``, ``rows`` and ``boundaries`` seed a resume
    at a boundary an earlier render of these same lines closed: the gap
    rule then reads exactly the state a from-scratch render has at that
    cursor, so the two renders agree row for row.
    """

    __slots__ = ("boundaries", "ctx", "gap", "lines", "rows", "start", "width")

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

    def run(self) -> None:
        """Walk from ``start`` to the end, extending ``rows`` and ``boundaries``."""
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

    One blank row separates adjacent blocks when ``gap`` > 0 (never before
    the first or after the last; the source's blank rows are dropped, so
    consecutive gaps cannot pile up).  :class:`~.component.Markdown` renders
    its whole document through this, and quote bodies and list continuations
    re-run their inner content through it at the indented width.

    The paragraph catch-all yields to the rest of the registry: its run stops
    at the first interior line another rule claims, so a custom block rule
    placed before it cuts a soft-wrapped run exactly like a built-in one.
    Every other rule owns its whole run -- a fence body is code, not markup
    to split on.
    """
    scan = _BlockScan(lines, width, ctx, gap)
    scan.run()
    return scan.rows


def _paragraph_end(
    lines: list[str], start: int, limit: int, interrupters: list[BlockRule]
) -> int:
    """Where the paragraph run ends: ``limit``, or the first interior line
    another rule of the registry claims."""
    for j in range(start + 1, limit):
        if any(rule.match(lines, j) for rule in interrupters):
            return j
    return limit
