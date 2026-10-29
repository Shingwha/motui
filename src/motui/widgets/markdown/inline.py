"""The inline engine: ordered rules that each recognize one construct.

An :class:`InlineRule` matches at a position and returns ``(end, segments)``.
``inline_segments`` walks left to right, trying the registry in order and
keeping unmatched stretches literal.  Rules are stateless singletons.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol

from ...kernel.cell import Segment, overlay
from ...kernel.style import NONE, Style

if TYPE_CHECKING:  # protocols only: the rules are constructed without a ctx
    from .context import RenderContext

# Inline link: [label](url) with a space- and paren-free url.
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")

#: The characters a built-in rule can open a construct at: an inline code
#: span opens at a backtick, strong/emphasis at a ``*``, strikethrough at a
#: ``~`` and a link at a ``[``.  :func:`inline_segments` visits exactly these
#: positions when every rule of the registry is a built-in -- the candidate
#: scan is complete for that registry because each built-in ``match``
#: declines on any other character before reading further.
_OPENER = re.compile("[`*~[]")


class InlineRule(Protocol):
    """One inline construct: recognize at ``pos``, produce segments.

    ``match`` returns ``(end, segments)`` (``end > pos``) or ``None``.
    Colored segment styles are absolute; attribute-only styles merge onto the
    surrounding base.
    """

    name: str

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None: ...


def inline_segments(
    text: str, ctx: RenderContext, base: Style = NONE
) -> list[Segment]:
    """Split ``text`` into styled segments using ``ctx.inline_rules``.

    Unrecognized stretches stay literal ``base`` text.  With only built-in
    rules the scan visits opener characters only, which is equivalent and
    cheaper for streaming paragraphs.
    """
    rules = ctx.inline_rules
    out: list[Segment] = []
    literal_from = 0
    pos = 0
    n = len(text)
    # The candidate positions: every offset for a registry that could match
    # anywhere, only the opener runs for the built-in one (a rule outside
    # ``_OPENER_RULES`` -- a custom ``inline_rules=`` entry -- may open at a
    # character no built-in pattern names).
    if all(type(rule) in _OPENER_RULES for rule in rules):
        candidates: Iterable[int] = (found.start() for found in _OPENER.finditer(text))
    else:
        candidates = range(n)
    for at in candidates:
        if at < pos:
            continue  # a matched construct already consumed this position
        for rule in rules:
            matched = rule.match(text, at, ctx)
            if matched is None:
                continue
            end, segments = matched
            if end <= at:  # a rule must advance; treat a stall as a decline
                continue
            if at > literal_from:
                out.append(Segment(text[literal_from:at], base))
            out.extend(overlay(base, segments))
            pos = end
            literal_from = end
            break
        # A decline consumes nothing: the loop moves on to the next
        # candidate (the next character, in the every-position registry).
    if literal_from < n:
        out.append(Segment(text[literal_from:], base))
    return out


class CodeInlineRule:
    """Inline code: `` `content` `` (no nested backticks) in the theme's
    ``content.inline_code`` style."""

    name = "code"

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None:
        if text[pos] != "`":
            return None
        end = text.find("`", pos + 1)
        if end < 0:
            return None
        return end + 1, [Segment(text[pos + 1 : end], ctx.theme.content.inline_code)]


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
        return end + 2, [Segment(content, ctx.theme.content.strong)]


class StrikeInlineRule:
    """Strikethrough: ``~~content~~`` (non-empty) struck; unclosed stays
    literal, so a streaming prefix renders safely."""

    name = "strike"

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None:
        if not text.startswith("~~", pos):
            return None
        end = text.find("~~", pos + 2)
        if end < 0:
            return None
        content = text[pos + 2 : end]
        if not content:
            return None
        return end + 2, [Segment(content, ctx.theme.content.strike)]


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
        return end + 1, [Segment(content, ctx.theme.content.emphasis)]


class LinkInlineRule:
    """Link: ``[label](url)`` in ``content.link``; the url is not rendered.

    The label carries the url as both ``link`` (OSC 8) and ``action`` (click
    payload for ``Markdown.take``).
    """

    name = "link"

    def match(
        self, text: str, pos: int, ctx: RenderContext
    ) -> tuple[int, list[Segment]] | None:
        if text[pos] != "[":
            return None
        matched = _LINK_RE.match(text, pos)
        if matched is None:
            return None
        url = matched.group(2)
        return matched.end(), [
            Segment(matched.group(1), ctx.theme.content.link, link=url, action=url)
        ]


def _is_word_char(ch: str) -> bool:
    """Word character for the italic boundaries (letters, digits, ``_``)."""
    return ch.isalnum() or ch == "_"


#: The exact built-in rule types :data:`_OPENER` is complete for.  Exact
#: types, not subclasses: a subclass may override ``match`` and open anywhere,
#: and then the every-position loop is the only safe scan.  Read at call time
#: (the classes are defined above), never re-derived.
_OPENER_RULES: tuple[type, ...] = (
    CodeInlineRule,
    BoldInlineRule,
    StrikeInlineRule,
    ItalicInlineRule,
    LinkInlineRule,
)


def default_inline_rules() -> list[InlineRule]:
    """A fresh built-in inline registry, in match order (bold before italic)."""
    return [
        CodeInlineRule(),
        BoldInlineRule(),
        StrikeInlineRule(),
        ItalicInlineRule(),
        LinkInlineRule(),
    ]


#: Inline registry singleton, tried left to right.  Order matters: bold
#: before italic (both open with ``*``), and the whole tuple is the
#: extension point for math -- a ``$...$`` rule would be one more entry
#: here, e.g.
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
INLINE_RULES: tuple[InlineRule, ...] = tuple(default_inline_rules())
