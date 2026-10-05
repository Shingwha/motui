"""The inline engine: ordered rules that each recognize one construct.

An :class:`InlineRule` looks at one position in a line and either declines
(``None``) or returns ``(end, segments)`` -- the offset just past the
construct and the styled runs it produces.  :func:`inline_segments` walks the
line left to right, handing every position to the registry in order and
accumulating the unrecognized stretches (including half-open markers such as
a lone ``**`` or backtick) as literal text.

The registries themselves are dep-free module singletons -- a rule reads the
styles it needs off the :class:`~.context.RenderContext` it is handed, so one
instance serves every :class:`~.component.Markdown`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from ...core.lines import Segment, overlay
from ...core.style import NONE, Style

if TYPE_CHECKING:  # protocols only: the rules are constructed without a ctx
    from .context import RenderContext

# Inline link: [label](url) with a space- and paren-free url.
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")


class InlineRule(Protocol):
    """One inline construct: recognize at ``pos``, produce segments.

    ``match`` returns ``(end, segments)`` when the construct starts at
    ``pos`` (``end > pos`` always -- a rule must advance), else ``None``; it
    reads the styles it needs off ``ctx``.  A segment style that sets a
    color is absolute; an attribute-only style (bold/italic/...) is merged
    onto the surrounding run's base style, so ``**x**`` inside an accent
    heading stays accent.
    """

    name: str

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None: ...


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
#: would be a :class:`~.blocks.BlockRule` registered the same way.
INLINE_RULES: list[InlineRule] = [
    CodeInlineRule(),
    BoldInlineRule(),
    ItalicInlineRule(),
    LinkInlineRule(),
]
