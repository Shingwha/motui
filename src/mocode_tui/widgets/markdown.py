"""Markdown component: a rule-registry-driven line-level parser.

:class:`Markdown` turns a mutable text buffer into rendered rows through two
ordered registries.  A :class:`BlockRule` classifies the line at the cursor
(``match`` returns how many lines it consumes, ``None`` when it declines) and
renders exactly those lines (``render``); an :class:`InlineRule` recognizes one
inline construct at a position (``match`` returns the end offset plus the
segments it produces).  :data:`BLOCK_RULES` is tried in order and ends with
:class:`ParagraphRule`, the catch-all; :data:`INLINE_RULES` runs left to right
inside a line.

Streaming safety is a hard constraint (the demo assigns ``.text`` one chunk at
a time): a half-open fence renders its body to the end, a table is only a
table once header *and* delimiter row are both present, and an unclosed
inline marker stays literal.  Every row a rule returns is wrapped and
``fit`` to ``width``, so no row ever exceeds the painting width.

Both registries are dep-free module singletons: a rule holds no theme, no
registry and no highlighter of its own, so one instance serves every
:class:`Markdown`.  What a rule needs to render arrives in one frozen
:class:`RenderContext` -- ``theme``, ``highlighter``, ``divider_max_width``
and the two live registries -- which :class:`Markdown` builds once and passes
into ``render``.  Extending is therefore "implement the protocol, read the
ctx", not "implement five cloning conventions".

Fenced code blocks (:class:`FenceRule`) parse the language tag after the
opening fence (`` ```python ``) and hand the body to a :class:`Highlighter`:
the built-in regex highlighter by default, or your own object -- anything with
``highlight(code, lang) -> list[Line]`` -- via ``Markdown(text,
highlighter=...)``.  An unknown or missing tag renders the body monochrome
in the theme's ``code``; the fence's visual container is unaffected, only
the coloring of the code lines changes.

Extending is construction, not patching: pass your own registries --
``Markdown(text, block_rules=[MyRule(), *BLOCK_RULES],
inline_rules=[MyInline(), *INLINE_RULES])``.  A custom block rule placed
before the catch-all interrupts a paragraph exactly like a built-in one, and
it reaches quote bodies and list continuations too, because the context
carries the live registry.  Math (``$...$`` / ``$$...$$``) is deliberately
*not* implemented; it slots in as one more :class:`InlineRule` (or a
:class:`BlockRule` for display equations) -- see the module-level note under
:data:`INLINE_RULES`.

Like every component this module only imports the kernel (``lines``/
``style``/``text``/``theme``) and sibling components (``Table`` for GFM
tables, ``Divider`` for thematic breaks); it never touches a screen.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ..core.lines import Line, Segment, overlay, wrap_line
from ..core.style import NONE, Style
from ..core.text import visible_width
from ..core.theme import DEFAULT_THEME, Theme
from .chrome import Divider
from .syntax import Highlighter, RegexHighlighter, default_highlighter
from .table import Table

__all__ = [
    "BLOCK_RULES",
    "INLINE_RULES",
    "BoldInlineRule",
    "BlockRule",
    "CodeInlineRule",
    "FenceRule",
    "HeadingRule",
    "InlineRule",
    "ItalicInlineRule",
    "LinkInlineRule",
    "ListRule",
    "Markdown",
    "ParagraphRule",
    "QuoteRule",
    "RenderContext",
    "TableRule",
    "ThematicBreakRule",
    "default_block_rules",
    "inline_segments",
]


# --- protocols ---------------------------------------------------------------


class BlockRule(Protocol):
    """One block-level construct: classify at the cursor, then render.

    ``match`` returns the number of lines the rule consumes starting at
    ``lines[i]`` (``None`` -- or any falsy value -- when it declines);
    ``render`` receives exactly that slice plus the :class:`RenderContext`
    of the document being rendered and returns finished rows.  Matching never
    needs the context: the built-in rules classify on shape alone.  Rules are
    stateless: the same instance serves every :class:`Markdown`.
    """

    name: str

    def match(self, lines: list[str], i: int) -> int | None: ...

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]: ...


class InlineRule(Protocol):
    """One inline construct: recognize at ``pos``, produce segments.

    ``match`` returns ``(end, segments)`` when the construct starts at
    ``pos`` (``end > pos`` always -- a rule must advance), else ``None``; it
    reads the styles it needs off ``ctx``.  A segment style that sets a color
    is absolute; an attribute-only style (bold/italic/...) is merged onto the
    surrounding run's base style, so ``**x**`` inside an accent heading stays
    accent.
    """

    name: str

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None: ...


# --- patterns ----------------------------------------------------------------

# ATX heading: 1..6 leading '#' + whitespace + content.
_ATX_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# List item: optional indent, then '-', '*' or 'N.' + whitespace + content.
_LIST_RE = re.compile(r"^(\s*)(?:([-*])|(\d+)\.)\s+(.*)$")

# Fence delimiter: a line whose first non-space run is backticks.
_FENCE_RE = re.compile(r"^\s*```")

# Fence info string: whatever follows the opening backtick run.
_INFO_RE = re.compile(r"^\s*`{3,}(.*)$")

# Block quote: optional indent, '>', one optional space, content.
_QUOTE_RE = re.compile(r"^\s*> ?(.*)$")

# Thematic break: a standalone run of 3+ '-' or '*' (spaces allowed between).
_BREAK_RE = re.compile(r"^ {0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,})$")

# One GFM delimiter cell: dashes with optional ':' alignment markers.
_DELIM_CELL_RE = re.compile(r"^:?-+:?$")

# Inline link: [label](url) with a space- and paren-free url.
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")

#: Deepest list tier kept: indents 0 and 2 spaces are distinct levels, deeper
#: indents cap here (the ticket's "2 级" reading; see the report's tradeoffs).
_LIST_MAX_LEVEL = 1


# --- render context ----------------------------------------------------------


@dataclass(frozen=True)
class RenderContext:
    """Everything a rule reads while rendering, frozen and shared.

    ``theme`` and ``highlighter`` are already resolved by the component (a
    missing theme is :data:`~mocode_tui.core.theme.DEFAULT_THEME`, a missing
    highlighter the engine a fence would derive from the theme).  The two
    registries are the *live* ones of the document: a rule that re-runs
    blocks -- a quote body, a list continuation -- and the paragraph
    catch-all that yields to higher-priority rules both follow them, so a
    custom rule reaches every built-in block without any re-binding.
    """

    theme: Theme = DEFAULT_THEME
    highlighter: Highlighter | None = None
    divider_max_width: int | None = 80
    block_rules: Sequence[BlockRule] = ()
    inline_rules: Sequence[InlineRule] = ()


# --- inline engine -----------------------------------------------------------


def inline_segments(
    text: str, ctx: RenderContext, base: Style = NONE
) -> list[Segment]:
    """Split ``text`` into styled segments using ``ctx.inline_rules``.

    Unrecognized stretches -- including half-open markers such as a lone
    ``**`` or backtick -- accumulate as literal ``base`` text.  A rule's
    segment keeps its own style when that style sets a color; an
    attribute-only style is merged onto ``base`` (see :class:`InlineRule`).
    """
    out: list[Segment] = []
    literal_from = 0
    pos = 0
    n = len(text)
    while pos < n:
        for rule in ctx.inline_rules:
            matched = rule.match(text, pos, ctx)
            if matched is None:
                continue
            end, segments = matched
            if end <= pos:  # a rule must advance; treat a stall as a decline
                continue
            if pos > literal_from:
                out.append(Segment(text[literal_from:pos], base))
            out.extend(overlay(base, segments))
            pos = end
            literal_from = pos
            break
        else:
            pos += 1
    if literal_from < n:
        out.append(Segment(text[literal_from:], base))
    return out


class CodeInlineRule:
    """Inline code: `` `content` `` (no nested backticks) in the theme's
    inline-code style."""

    name = "code"

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None:
        if text[pos] != "`":
            return None
        end = text.find("`", pos + 1)
        if end < 0:
            return None
        return end + 1, [Segment(text[pos + 1 : end], ctx.theme.inline_code)]


class BoldInlineRule:
    """Strong emphasis: ``**content**`` (non-empty) merged bold onto base."""

    name = "bold"

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None:
        if not text.startswith("**", pos):
            return None
        end = text.find("**", pos + 2)
        if end < 0:
            return None
        content = text[pos + 2 : end]
        if not content:
            return None
        return end + 2, [Segment(content, Style(bold=True))]


class ItalicInlineRule:
    """Emphasis: ``*content*`` on word boundaries (so ``2*3`` stays literal)."""

    name = "italic"

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None:
        if text[pos] != "*" or text.startswith("**", pos):
            return None
        end = text.find("*", pos + 1)
        if end < 0:
            return None
        content = text[pos + 1 : end]
        if not content or "*" in content:
            return None
        if pos > 0 and _is_word_char(text[pos - 1]):
            return None
        if end + 1 < len(text) and _is_word_char(text[end + 1]):
            return None
        return end + 1, [Segment(content, Style(italic=True))]


class LinkInlineRule:
    """Link: ``[label](url)`` -- the label in the theme's link style (colored
    and underlined, never bold); the url is not rendered."""

    name = "link"

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None:
        if text[pos] != "[":
            return None
        matched = _LINK_RE.match(text, pos)
        if matched is None:
            return None
        return matched.end(), [Segment(matched.group(1), ctx.theme.link)]


def _is_word_char(ch: str) -> bool:
    """Word character for the italic boundaries (letters, digits, ``_``)."""
    return ch.isalnum() or ch == "_"


#: Inline registry, tried left to right.  Order matters: bold before italic
#: (both open with ``*``), and the whole list is the extension point for
#: math -- a ``$...$`` rule would be one more entry here, e.g.
#:
#:     class MathInlineRule:
#:         name = "math"
#:         def match(self, text, pos, ctx):
#:             if text[pos] != "$":
#:                 return None
#:             end = text.find("$", pos + 1)
#:             if end < 0:
#:                 return None
#:             return end + 1, [Segment(text[pos + 1:end], MATH_STYLE)]
#:
#: and register it with ``Markdown(text, inline_rules=[MathInlineRule(),
#: *INLINE_RULES])``.  Display equations (``$$...$$`` on their own lines)
#: would be a :class:`BlockRule` registered the same way.
INLINE_RULES: list[InlineRule] = [
    CodeInlineRule(),
    BoldInlineRule(),
    ItalicInlineRule(),
    LinkInlineRule(),
]


# --- block rules -------------------------------------------------------------


class HeadingRule:
    """ATX heading: ``#``..``######`` + space, on the theme's heading ladder.

    h1 and h2 strip their marker (h1 underlines, h2 stands alone); h3 and
    deeper keep their hashes -- once every level shares one color, the
    marker is the depth cue, the pi reference's convention.
    """

    name = "heading"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _ATX_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        matched = _ATX_RE.match(lines[0])
        if matched is None:  # defensive: match() gated this shape
            return [Line.from_text(lines[0]).fit(width)]
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
    injects a replacement engine (see :class:`Markdown`).  The opening
    (`` ```python ``) and closing (`` ``` ``) fence lines stay visible in
    the context theme's ``muted`` -- they name the language and frame the
    block, the pi reference shows them too.  An unclosed fence runs to the
    end of the buffer (streaming-safe): the opening marker renders, the
    closing one appears only once the fence actually closes.  Only the code
    lines' colors come from the highlighter -- the fence has no container of
    its own.
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
        engine = ctx.highlighter if ctx.highlighter is not None else _fence_highlighter(theme)
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


class TableRule:
    """GFM pipe table: header row + delimiter row, aligned per column.

    The table is only a table once *both* the header and a matching
    delimiter row are present (a half-typed table degrades to a paragraph
    -- the streaming-safety rule).  Cells render the document's inline
    markup (bold, code, links); every cell's segments carry no base style,
    and the :class:`Table` injects the column base (header style,
    first-column style).  Alignment (``:--`` / ``--:`` / ``:-:``) is
    computed from the delimiter row and handed to the grid as its
    ``aligns``; a cell's escaped ``\\|`` stays a literal pipe and never
    splits the row.
    """

    name = "table"

    def match(self, lines: list[str], i: int) -> int | None:
        if i + 1 >= len(lines):
            return None
        header = _split_row(lines[i])
        delim = _split_row(lines[i + 1])
        if header is None or delim is None or len(header) != len(delim):
            return None
        if not all(_DELIM_CELL_RE.match(cell) for cell in delim):
            return None
        j = i + 2
        while j < len(lines) and lines[j].strip() and "|" in lines[j]:
            j += 1
        return j - i

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        header = _split_row(lines[0]) or []
        delim = _split_row(lines[1]) or []
        marks = [_cell_align(cell) for cell in delim]
        body = [(_split_row(raw) or []) for raw in lines[2:]]
        ncols = len(header)
        aligns = [_align_of(marks, c) for c in range(ncols)]
        table = Table(
            [inline_segments(cell, ctx) for cell in header],
            [
                [inline_segments(row[c], ctx) if c < len(row) else "" for c in range(ncols)]
                for row in body
            ],
            aligns=aligns,
            theme=ctx.theme,
        )
        return table.render(width)


class ThematicBreakRule:
    """Thematic break: a standalone ``---`` / ``***`` line, as a Divider.

    The divider is capped at the context's ``divider_max_width`` (``None``
    spans the whole width) -- what :class:`Markdown`'s ``divider_max_width``
    parameter sets.
    """

    name = "thematic_break"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _BREAK_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        return Divider(theme=ctx.theme, max_width=ctx.divider_max_width).render(width)


class QuoteRule:
    """Block quote: ``> `` lines re-run as blocks behind a muted ``│ `` bar.

    One ``>`` level is stripped and the body re-renders through the
    context's live block registry at the bar-narrowed width, so nested
    quotes stack a bar per level and quotes hold lists, fenced code and
    tables like any document.  The body renders tight -- a ``>``-blank ends
    a paragraph but emits no blank row (block gaps stay a top-level document
    rhythm; the pi reference's quote bodies are compact).  Body text renders
    italic (colored and bold segments keep their own emphasis).
    """

    name = "quote"

    def match(self, lines: list[str], i: int) -> int | None:
        if not _QUOTE_RE.match(lines[i]):
            return None
        j = i + 1
        while j < len(lines) and _QUOTE_RE.match(lines[j]):
            j += 1
        return j - i

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        theme = ctx.theme
        inner = [
            matched.group(1) if (matched := _QUOTE_RE.match(raw)) else "" for raw in lines
        ]
        budget = max(width - 2, 1)  # the "│ " bar takes two columns
        rows = _run_blocks(inner, budget, ctx, gap=0)
        out: list[Line] = []
        for row in rows:
            if not row.text.strip():
                out.append(row)  # a blank separator row carries no bar
                continue
            body = Line(
                Segment(
                    seg.text,
                    seg.style
                    if seg.style.fg or seg.style.bg or seg.style.bold
                    else seg.style.merge(Style(italic=True)),
                )
                for seg in row.segments
            )
            out.append((Line((Segment("\u2502 ", theme.muted),)) + body).fit(width))
        return out


class ListRule:
    """List: a run of ``-``/``*``/``N.`` items, markers kept verbatim.

    A blank row ends the run, so a tight list is a single block and only
    blank-line-separated items end up in separate blocks -- ``Markdown``'s
    block gap then spaces a loose list apart, with no list-specific code.
    Lines indented past their item's marker are that item's continuation
    and re-render as blocks (through the context's registry) at the
    content-narrowed width: a quote, fenced code or table nested in an item
    indents under the marker, the pi reference's nested look.  Nested
    content renders tight (no blank rows inside an item).  The marker is
    rendered as typed (no bullet substitution); nesting follows the source
    indent, two spaces per level, deeper indents capped at
    :data:`_LIST_MAX_LEVEL`.  The marker carries the theme's
    ``list_marker``.
    """

    name = "list"

    def match(self, lines: list[str], i: int) -> int | None:
        if not _LIST_RE.match(lines[i]):
            return None
        j = i + 1
        while j < len(lines):
            if _LIST_RE.match(lines[j]):
                j += 1  # the next item
            elif lines[j].strip() and lines[j].startswith("  "):
                j += 1  # indented continuation of the last item
            else:
                break  # blank or dedented: the run ends here
        return j - i

    def render(self, lines: list[str], width: int, ctx: RenderContext) -> list[Line]:
        items: list[tuple[str, list[str]]] = []
        for raw in lines:
            if _LIST_RE.match(raw):
                items.append((raw, []))
            elif items:
                items[-1][1].append(raw)
        out: list[Line] = []
        for raw, continuation in items:
            out.extend(self._render_item(raw, continuation, width, ctx))
        return out

    def _render_item(
        self, raw: str, continuation: list[str], width: int, ctx: RenderContext
    ) -> list[Line]:
        theme = ctx.theme
        matched = _LIST_RE.match(raw)
        if matched is None:  # defensive: match() gated this shape
            return [Line.from_text(raw).fit(width)]
        indent, bullet, number, content = matched.groups()
        level = min(len(indent) // 2, _LIST_MAX_LEVEL)
        marker = f"{number}. " if number is not None else f"{bullet} "
        # Hanging indent: the marker opens the first row and every wrapped
        # row carries a matching blank indent (the wrapper drops leading
        # spaces, so the indent is prepended after wrapping, not before).
        prefix_text = "  " * level + marker
        prefix_w = visible_width(prefix_text)
        budget = max(width - prefix_w, 1)
        rows = wrap_line(Line(inline_segments(content, ctx)), budget)
        out: list[Line] = []
        for k, row in enumerate(rows):
            lead = (
                Line((Segment(prefix_text, theme.list_marker),))
                if k == 0
                else Line.from_text(" " * prefix_w)
            )
            out.append((lead + row).fit(width))
        if continuation:
            # The item's own blocks: strip the text column's indent, render
            # through the live registry at the content width, indent back.
            strip = len(indent) + len(marker)
            inner = []
            for line in continuation:
                drop = min(strip, len(line) - len(line.lstrip(" ")))
                inner.append(line[drop:])
            inner_rows = _run_blocks(inner, budget, ctx, gap=0)
            out.extend(
                (Line.from_text(" " * prefix_w) + row).fit(width) for row in inner_rows
            )
        return out


class ParagraphRule:
    """The catch-all: soft-wrapped lines plus inline rules.

    Consumes lines until a blank row; the block loop then trims the run at
    the first line another rule of the same registry claims (see
    :func:`_run_blocks`), so a custom block rule placed before the catch-all
    interrupts a paragraph exactly like a built-in one.  Must stay last in
    :data:`BLOCK_RULES`.
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


def _run_blocks(
    lines: list[str], width: int, ctx: RenderContext, gap: int = 1
) -> list[Line]:
    """Render ``lines`` through the context's registry -- the shared block loop.

    One blank row separates adjacent blocks when ``gap`` > 0 (never before
    the first or after the last; the source's blank rows are dropped, so
    consecutive gaps cannot pile up).  :class:`Markdown` renders its whole
    document through this, and quote bodies and list continuations re-run
    their inner content through it at the indented width.

    The paragraph catch-all yields to the rest of the registry: its run stops
    at the first interior line another rule claims, so a custom block rule
    placed before it cuts a soft-wrapped run exactly like a built-in one.
    Every other rule owns its whole run -- a fence body is code, not markup
    to split on.
    """
    rules = ctx.block_rules
    interrupters = [rule for rule in rules if not isinstance(rule, ParagraphRule)]
    out: list[Line] = []
    i = 0
    n = len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        for rule in rules:
            consumed = rule.match(lines, i)
            if consumed:
                if out and gap > 0:
                    out.append(Line())
                end = i + consumed
                if isinstance(rule, ParagraphRule):
                    end = _paragraph_end(lines, i, end, interrupters)
                out.extend(rule.render(lines[i:end], width, ctx))
                i = end
                break
        else:
            # No rule claims the line: only reachable when the registry
            # lacks a trailing catch-all.  Skip, never loop.
            i += 1
    return out


def _paragraph_end(
    lines: list[str], start: int, limit: int, interrupters: Sequence[BlockRule]
) -> int:
    """Where the paragraph run ends: ``limit``, or the first interior line
    another rule of the registry claims."""
    for j in range(start + 1, limit):
        if any(rule.match(lines, j) for rule in interrupters):
            return j
    return limit


#: Pipe-row splitter: a pipe preceded by a backslash is escaped (a cell may
#: hold a literal ``|`` that way), every other pipe delimits cells.
_ROW_SPLIT_RE = re.compile(r"(?<!\\)\|")


def _split_row(line: str) -> list[str] | None:
    """Split a pipe row into stripped cells, or ``None`` without a pipe.

    Splits on unescaped pipes only (``(?<!\\\\)\\|``) and restores a cell's
    ``\\|`` to a literal ``|``; leading and trailing pipes are dropped
    first.  A backslash right before a pipe always reads as an escape: a
    double backslash next to a pipe is not distinguished from a single
    one (documented simplification -- the fixture does not cover that
    corner).
    """
    stripped = line.strip()
    if "|" not in stripped:
        return None
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.replace("\\|", "|").strip() for cell in _ROW_SPLIT_RE.split(stripped)]


def _cell_align(cell: str) -> str:
    """Alignment of one delimiter cell: ``left``/``center``/``right``."""
    left = cell.startswith(":")
    right = cell.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    return "left"


def _align_of(aligns: list[str], column: int) -> str:
    """Alignment for ``column`` (``left`` when the delimiter row is short)."""
    return aligns[column] if column < len(aligns) else "left"


def default_block_rules() -> list[BlockRule]:
    """The built-in block registry, dep-free and shared.

    Order is the match priority; :class:`ParagraphRule` is the mandatory
    catch-all at the end.  Build a custom registry by prepending your own
    rules: ``[MyRule(), *default_block_rules()]``.
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


# --- component ---------------------------------------------------------------


class Markdown:
    """A Markdown document rendered as rows, rule-registry driven.

    ``text`` is a mutable attribute (streaming text assigns to it);
    ``render(width)`` is a pure function of ``text`` and ``width`` and never
    returns a row wider than ``width``.  ``block_rules`` / ``inline_rules``
    replace the built-in registries (the block registry must end with a
    paragraph-style catch-all; see :class:`ParagraphRule`).  ``theme``
    restyles the built-in rules (headings, code, quotes, list markers, links
    and the embedded ``Table``/``Divider``); custom rules keep their own
    styles -- they read what they need off the context they are handed.
    ``highlighter`` injects the fenced-code engine (anything with
    ``highlight(code, lang) -> list[Line]``; the built-in regex highlighter
    by default, restyled by ``theme``) into every block rule that accepts
    one.  ``gap`` sets how many blank rows separate adjacent blocks (default
    1, the pi reference's section breathing room; a negative value degrades
    to 0).  ``divider_max_width`` caps thematic-break rules' dividers at that
    many columns (default 80, the pi reference's rule width; ``None`` spans
    the whole width).  Blank input rows are dropped: the source's own blank
    lines never add spacing beyond one gap, and ``gap=0`` restores the old
    direct stacking (no blank rows between blocks).
    """

    __slots__ = ("_ctx", "_gap", "text", "theme")

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
        return _run_blocks(self.text.split("\n"), width, self._ctx, self._gap)

    def __repr__(self) -> str:
        return f"Markdown({self.text!r})"
