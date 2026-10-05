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

Fenced code blocks (``FenceRule``) parse the language tag after the opening
fence (`` ```python ``) and hand the body to a :class:`Highlighter`: the
built-in regex highlighter by default, or your own object -- anything with
``highlight(code, lang) -> list[Line]`` -- via ``Markdown(text,
highlighter=...)``.  An unknown or missing tag renders the body monochrome
in the theme's ``code``; the fence's visual container is unaffected, only
the coloring of the code lines changes.

Extending is construction, not patching: pass your own registries --
``Markdown(text, block_rules=[MyRule(), *BLOCK_RULES],
inline_rules=[MyInline(), *INLINE_RULES])``.  Block rules that parse inline
markup expose ``with_inline_rules(rules)`` and :class:`Markdown` re-binds the
built-ins to the caller's inline registry, so a custom inline rule reaches
every built-in block.  Math (``$...$`` / ``$$...$$`) is deliberately *not*
implemented; it slots in as one more :class:`InlineRule` (or a
:class:`BlockRule` for display equations) -- see the module-level note under
:data:`INLINE_RULES`.

Like every component this module only imports the kernel (``lines``/
``style``/``text``) and sibling components (``Table`` for GFM tables,
``Divider`` for thematic breaks); it never touches a screen.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Protocol

from ..core.lines import Line, Segment, wrap_line
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
    ``render`` receives exactly that slice and returns finished rows.  Rules
    are stateless: the same instance serves every :class:`Markdown`.
    """

    name: str

    def match(self, lines: list[str], i: int) -> int | None: ...

    def render(self, lines: list[str], width: int) -> list[Line]: ...


class InlineRule(Protocol):
    """One inline construct: recognize at ``pos``, produce segments.

    ``match`` returns ``(end, segments)`` when the construct starts at
    ``pos`` (``end > pos`` always -- a rule must advance), else ``None``.  A
    segment style that sets a color is absolute; an attribute-only style
    (bold/italic/...) is merged onto the surrounding block's base style, so
    ``**x**`` inside an accent heading stays accent.
    """

    name: str

    def match(self, text: str, pos: int) -> tuple[int, list[Segment]] | None: ...


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


# --- inline engine -----------------------------------------------------------


def inline_segments(
    text: str, base: Style = NONE, rules: Sequence[InlineRule] | None = None
) -> list[Segment]:
    """Split ``text`` into styled segments using ``rules`` (default registry).

    Unrecognized stretches -- including half-open markers such as a lone
    ``**`` or backtick -- accumulate as literal ``base`` text.  A rule's
    segment keeps its own style when that style sets a color; an
    attribute-only style is merged onto ``base`` (see :class:`InlineRule`).
    """
    active = INLINE_RULES if rules is None else rules
    out: list[Segment] = []
    literal_from = 0
    pos = 0
    n = len(text)
    while pos < n:
        for rule in active:
            matched = rule.match(text, pos)
            if matched is None:
                continue
            end, segments = matched
            if end <= pos:  # a rule must advance; treat a stall as a decline
                continue
            if pos > literal_from:
                out.append(Segment(text[literal_from:pos], base))
            for seg in segments:
                colored = seg.style.fg is not None or seg.style.bg is not None
                out.append(Segment(seg.text, seg.style if colored else base.merge(seg.style)))
            pos = end
            literal_from = pos
            break
        else:
            pos += 1
    if literal_from < n:
        out.append(Segment(text[literal_from:], base))
    return out


class CodeInlineRule:
    """Inline code: `` `content` `` (no nested backticks) in ice blue."""

    name = "code"

    def __init__(self, theme: Theme | None = None) -> None:
        self._theme = theme

    def with_theme(self, theme: Theme | None) -> "CodeInlineRule":
        """A copy of this rule bound to ``theme``."""
        return CodeInlineRule(theme)

    def match(self, text: str, pos: int) -> tuple[int, list[Segment]] | None:
        if text[pos] != "`":
            return None
        end = text.find("`", pos + 1)
        if end < 0:
            return None
        theme = self._theme or DEFAULT_THEME
        return end + 1, [Segment(text[pos + 1 : end], theme.code)]


class BoldInlineRule:
    """Strong emphasis: ``**content**`` (non-empty) merged bold onto base."""

    name = "bold"

    def match(self, text: str, pos: int) -> tuple[int, list[Segment]] | None:
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

    def match(self, text: str, pos: int) -> tuple[int, list[Segment]] | None:
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
    """Link: ``[label](url)`` -- accent-underlined label, muted `` (url)``."""

    name = "link"

    def __init__(self, theme: Theme | None = None) -> None:
        self._theme = theme

    def with_theme(self, theme: Theme | None) -> "LinkInlineRule":
        """A copy of this rule bound to ``theme``."""
        return LinkInlineRule(theme)

    def match(self, text: str, pos: int) -> tuple[int, list[Segment]] | None:
        if text[pos] != "[":
            return None
        matched = _LINK_RE.match(text, pos)
        if matched is None:
            return None
        label, url = matched.group(1), matched.group(2)
        theme = self._theme or DEFAULT_THEME
        return matched.end(), [
            Segment(label, theme.accent.merge(Style(underline=True))),
            Segment(f" ({url})", theme.muted),
        ]


def _is_word_char(ch: str) -> bool:
    """Word character for the italic boundaries (letters, digits, ``_``)."""
    return ch.isalnum() or ch == "_"


#: Inline registry, tried left to right.  Order matters: bold before italic
#: (both open with ``*``), and the whole list is the extension point for
#: math -- a ``$...$`` rule would be one more entry here, e.g.
#:
#:     class MathInlineRule:
#:         name = "math"
#:         def match(self, text, pos):
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


class _InlineMixin:
    """Plumbing for block rules that parse inline markup.

    The inline registry is constructor-injected (default: the module
    registry).  :class:`Markdown` re-binds every rule exposing
    :meth:`with_inline_rules` to the caller's inline rules, so custom inline
    constructs reach the built-in blocks too; :meth:`with_theme` does the
    same for the theme, so a themed :class:`Markdown` restyles the built-in
    rules (and the inline rules they run) as well.
    """

    def __init__(
        self,
        inline_rules: Sequence[InlineRule] | None = None,
        theme: Theme | None = None,
    ) -> None:
        self._theme = theme
        self._inline = list(INLINE_RULES if inline_rules is None else inline_rules)
        if theme is not None:
            self._inline = [
                rule.with_theme(theme) if hasattr(rule, "with_theme") else rule
                for rule in self._inline
            ]

    def with_inline_rules(self, rules: Sequence[InlineRule]) -> "_InlineMixin":
        """A copy of this rule bound to ``rules``."""
        return type(self)(rules, self._theme)

    def with_theme(self, theme: Theme | None) -> "_InlineMixin":
        """A copy of this rule (and its inline registry) bound to ``theme``."""
        return type(self)(self._inline, theme)

    def _segments(self, text: str, base: Style = NONE) -> list[Segment]:
        return inline_segments(text, base, self._inline)


class HeadingRule(_InlineMixin):
    """ATX heading: ``#``..``######`` + space, on the theme's heading ladder."""

    name = "heading"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _ATX_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int) -> list[Line]:
        matched = _ATX_RE.match(lines[0])
        if matched is None:  # defensive: match() gated this shape
            return [Line.from_text(lines[0]).fit(width)]
        level = len(matched.group(1))
        theme = self._theme or DEFAULT_THEME
        base = theme.headings[level - 1]
        line = Line(self._segments(matched.group(2).strip(), base))
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
    is the language tag; the body goes through a :class:`Highlighter`, so a
    tagged fence renders with syntax colors.  An unknown or missing tag
    falls back to the theme's ``code`` monochrome, and ``highlighter``
    injects a replacement engine (see :class:`Markdown`).  An unclosed fence
    runs to the end of the buffer (streaming-safe); the opening line and the
    closing fence are dropped, content lines are ``fit`` to ``width``
    without wrapping.  Only the code lines' colors come from the
    highlighter -- the fence has no container of its own.
    """

    name = "fence"

    def __init__(
        self,
        theme: Theme | None = None,
        highlighter: Highlighter | None = None,
    ) -> None:
        self._theme = theme
        self._explicit = highlighter is not None
        self._highlighter: Highlighter = (
            highlighter
            if highlighter is not None
            else _fence_highlighter(theme)
        )

    def with_theme(self, theme: Theme | None) -> "FenceRule":
        """A copy of this rule bound to ``theme``.

        An injected highlighter is kept as-is (it owns its colors); only a
        theme-derived engine is rebuilt for the new theme.
        """
        return FenceRule(theme, self._highlighter if self._explicit else None)

    def with_highlighter(self, highlighter: Highlighter) -> "FenceRule":
        """A copy of this rule bound to ``highlighter`` (wins over theme)."""
        return FenceRule(self._theme, highlighter)

    def match(self, lines: list[str], i: int) -> int | None:
        if not _FENCE_RE.match(lines[i]):
            return None
        j = i + 1
        while j < len(lines) and not _FENCE_RE.match(lines[j]):
            j += 1
        return min(j + 1, len(lines)) - i  # include the closing fence when present

    def render(self, lines: list[str], width: int) -> list[Line]:
        body = lines[1:]
        if len(lines) > 1 and _FENCE_RE.match(lines[-1]):
            body = lines[1:-1]  # closed: drop the closing fence
        code = "\n".join(body)
        return [row.fit(width) for row in self._highlighter.highlight(code, _fence_lang(lines[0]))]


class TableRule(_InlineMixin):
    """GFM pipe table: header row + delimiter row, aligned per column.

    The table is only a table once *both* the header and a matching
    delimiter row are present (a half-typed table degrades to a paragraph
    -- the streaming-safety rule).  Cells render inline markup (bold,
    code, links); every cell's segments carry no base style, and the
    :class:`Table` injects the column base (header style, first-column
    style).  Alignment (``:--`` / ``--:`` / ``:-:``) is computed from the
    delimiter row and handed to the grid as its ``aligns``; a cell's
    escaped ``\\|`` stays a literal pipe and never splits the row.
    """

    name = "table"

    def __init__(
        self,
        theme: Theme | None = None,
        inline_rules: Sequence[InlineRule] | None = None,
    ) -> None:
        super().__init__(inline_rules, theme)

    def with_theme(self, theme: Theme | None) -> "TableRule":
        """A copy of this rule bound to ``theme``.

        The mixin's default binds the first constructor argument to the
        inline registry -- the opposite of this class's ``theme``-first
        signature -- so it is spelled out here.
        """
        return TableRule(theme, self._inline)

    def with_inline_rules(self, rules: Sequence[InlineRule]) -> "TableRule":
        """A copy of this rule bound to ``rules`` (see :meth:`with_theme`)."""
        return TableRule(self._theme, rules)

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

    def render(self, lines: list[str], width: int) -> list[Line]:
        header = _split_row(lines[0]) or []
        delim = _split_row(lines[1]) or []
        marks = [_cell_align(cell) for cell in delim]
        body = [(_split_row(raw) or []) for raw in lines[2:]]
        ncols = len(header)
        aligns = [_align_of(marks, c) for c in range(ncols)]
        table = Table(
            [self._segments(cell) for cell in header],
            [
                [self._segments(row[c]) if c < len(row) else "" for c in range(ncols)]
                for row in body
            ],
            aligns=aligns,
            theme=self._theme,
        )
        return table.render(width)


class ThematicBreakRule:
    """Thematic break: a standalone ``---`` / ``***`` line, as a Divider."""

    name = "thematic_break"

    def __init__(self, theme: Theme | None = None) -> None:
        self._theme = theme

    def with_theme(self, theme: Theme | None) -> "ThematicBreakRule":
        """A copy of this rule bound to ``theme``."""
        return ThematicBreakRule(theme)

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _BREAK_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int) -> list[Line]:
        return Divider(theme=self._theme).render(width)


class QuoteRule(_InlineMixin):
    """Block quote: ``> `` lines, each rendered with a muted ``│ `` prefix."""

    name = "quote"

    def match(self, lines: list[str], i: int) -> int | None:
        if not _QUOTE_RE.match(lines[i]):
            return None
        j = i + 1
        while j < len(lines) and _QUOTE_RE.match(lines[j]):
            j += 1
        return j - i

    def render(self, lines: list[str], width: int) -> list[Line]:
        theme = self._theme or DEFAULT_THEME
        out: list[Line] = []
        for raw in lines:
            matched = _QUOTE_RE.match(raw)
            content = matched.group(1) if matched else ""
            line = Line((Segment("\u2502 ", theme.muted),)) + Line(self._segments(content))
            out.extend(row.fit(width) for row in wrap_line(line, width))
        return out


class ListRule(_InlineMixin):
    """List item: ``-``/``*``/``N.`` marker kept verbatim, 2 indent levels.

    The marker is rendered as typed (no bullet substitution, matching the pi
    reference); nesting follows the source indent, two spaces per level,
    deeper indents capped at :data:`_LIST_MAX_LEVEL`.  The marker carries the
    theme's ``muted``.
    """

    name = "list"

    def match(self, lines: list[str], i: int) -> int | None:
        return 1 if _LIST_RE.match(lines[i]) else None

    def render(self, lines: list[str], width: int) -> list[Line]:
        theme = self._theme or DEFAULT_THEME
        matched = _LIST_RE.match(lines[0])
        if matched is None:  # defensive: match() gated this shape
            return [Line.from_text(lines[0]).fit(width)]
        indent, bullet, number, content = matched.groups()
        level = min(len(indent) // 2, _LIST_MAX_LEVEL)
        marker = f"{number}. " if number is not None else f"{bullet} "
        # Hanging indent: the marker opens the first row and every wrapped
        # row carries a matching blank indent (the wrapper drops leading
        # spaces, so the indent is prepended after wrapping, not before).
        prefix_text = "  " * level + marker
        prefix_w = visible_width(prefix_text)
        budget = max(width - prefix_w, 1)
        rows = wrap_line(Line(self._segments(content)), budget)
        out: list[Line] = []
        for k, row in enumerate(rows):
            lead = (
                Line((Segment(prefix_text, theme.muted),))
                if k == 0
                else Line.from_text(" " * prefix_w)
            )
            out.append((lead + row).fit(width))
        return out


class ParagraphRule(_InlineMixin):
    """The catch-all: soft-wrapped lines plus inline rules.

    Consumes lines until a blank row or a line where another built-in block
    starts (``starts_block``).  Must stay last in :data:`BLOCK_RULES`; a
    custom ``stops`` callable ``(lines, i) -> bool`` narrows or widens that
    interruption set.
    """

    name = "paragraph"

    def __init__(
        self,
        inline_rules: Sequence[InlineRule] | None = None,
        stops: Callable[[list[str], int], bool] | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(inline_rules, theme)
        self._stops = stops

    def with_inline_rules(self, rules: Sequence[InlineRule]) -> "ParagraphRule":
        return ParagraphRule(rules, self._stops, self._theme)

    def with_theme(self, theme: Theme | None) -> "ParagraphRule":
        return ParagraphRule(self._inline, self._stops, theme)

    def with_stops(self, rules: Sequence[BlockRule]) -> "ParagraphRule":
        """A copy that interrupts paragraphs wherever ``rules`` match.

        :class:`Markdown` calls this with the live registry, so a custom
        block rule placed before the catch-all stops a paragraph exactly
        like a built-in one.  An explicit ``stops`` callable wins and is
        returned unchanged.
        """
        if self._stops is not None:
            return self

        def stops(lines: list[str], i: int) -> bool:
            return any(rule.match(lines, i) for rule in rules if not isinstance(rule, ParagraphRule))

        return ParagraphRule(self._inline, stops, self._theme)

    def match(self, lines: list[str], i: int) -> int | None:
        stops = self._stops if self._stops is not None else starts_block
        j = i + 1
        while j < len(lines) and lines[j].strip() and not stops(lines, j):
            j += 1
        return j - i

    def render(self, lines: list[str], width: int) -> list[Line]:
        text = " ".join(raw.strip() for raw in lines)
        line = Line(self._segments(text))
        return [row.fit(width) for row in wrap_line(line, width)]


def starts_block(lines: list[str], i: int) -> bool:
    """True when a non-paragraph built-in block starts at ``lines[i]``.

    Delegates to the built-in rules' own ``match`` (table included, so its
    two-line lookahead decides), which is what interrupts a paragraph run.
    """
    return any(
        rule.match(lines, i)
        for rule in BLOCK_RULES
        if not isinstance(rule, ParagraphRule)
    )


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


def default_block_rules(
    inline_rules: Sequence[InlineRule] | None = None,
) -> list[BlockRule]:
    """The built-in block registry, bound to ``inline_rules``.

    Order is the match priority; :class:`ParagraphRule` is the mandatory
    catch-all at the end.  Build a custom registry by prepending your own
    rules: ``[MyRule(), *default_block_rules()]``.
    """
    rules = INLINE_RULES if inline_rules is None else inline_rules
    return [
        HeadingRule(rules),
        FenceRule(),
        TableRule(),
        ThematicBreakRule(),
        QuoteRule(rules),
        ListRule(rules),
        ParagraphRule(rules),
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
    styles.  ``highlighter`` injects the fenced-code engine (anything with
    ``highlight(code, lang) -> list[Line]``; the built-in regex highlighter
    by default, restyled by ``theme``) into every block rule that accepts
    one.  Blank input rows are dropped: blocks stack directly without
    extra vertical spacing.
    """

    __slots__ = ("_block_rules", "_inline_rules", "text", "theme")

    def __init__(
        self,
        text: str = "",
        *,
        block_rules: Sequence[BlockRule] | None = None,
        inline_rules: Sequence[InlineRule] | None = None,
        theme: Theme | None = None,
        highlighter: Highlighter | None = None,
    ) -> None:
        self.text = text
        self.theme = theme
        inline = list(INLINE_RULES if inline_rules is None else inline_rules)
        if theme is not None:
            inline = [
                rule.with_theme(theme) if hasattr(rule, "with_theme") else rule
                for rule in inline
            ]
        self._inline_rules = inline
        source = list(BLOCK_RULES if block_rules is None else block_rules)
        self._block_rules = [
            rule.with_inline_rules(inline) if hasattr(rule, "with_inline_rules") else rule
            for rule in source
        ]
        if theme is not None:
            self._block_rules = [
                rule.with_theme(theme) if hasattr(rule, "with_theme") else rule
                for rule in self._block_rules
            ]
        # Fenced code: an injected engine wins over the theme-derived one.
        if highlighter is not None:
            self._block_rules = [
                rule.with_highlighter(highlighter)
                if hasattr(rule, "with_highlighter")
                else rule
                for rule in self._block_rules
            ]
        # Paragraph interruption follows the live registry: a custom block
        # rule placed before the catch-all stops paragraphs like a built-in.
        self._block_rules = [
            rule.with_stops(self._block_rules) if hasattr(rule, "with_stops") else rule
            for rule in self._block_rules
        ]

    def render(self, width: int) -> list[Line]:
        lines = self.text.split("\n")
        out: list[Line] = []
        i = 0
        n = len(lines)
        while i < n:
            if not lines[i].strip():
                i += 1
                continue
            for rule in self._block_rules:
                consumed = rule.match(lines, i)
                if consumed:
                    out.extend(rule.render(lines[i : i + consumed], width))
                    i += consumed
                    break
            else:
                # No rule claims the line: only reachable when the caller's
                # registry lacks a trailing catch-all.  Skip, never loop.
                i += 1
        return out

    def __repr__(self) -> str:
        return f"Markdown({self.text!r})"
