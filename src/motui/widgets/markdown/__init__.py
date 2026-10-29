"""Markdown component: a rule-registry-driven line-level parser.

Block rules classify and render line runs; inline rules style constructs.
Both registries are immutable tuples and rules are stateless, reading a
frozen ``RenderContext``.  Streaming input stays safe (half-open constructs
remain literal or run to the end) and every row fits ``width``.
"""

from .blocks import (
    BlockRule,
    FenceRule,
    HeadingRule,
    ParagraphRule,
    ThematicBreakRule,
)
from .component import BLOCK_RULES, Markdown, default_block_rules
from .context import RenderContext
from .inline import (
    INLINE_RULES,
    BoldInlineRule,
    CodeInlineRule,
    InlineRule,
    ItalicInlineRule,
    LinkInlineRule,
    StrikeInlineRule,
    default_inline_rules,
    inline_segments,
)
from .nested import ListRule, QuoteRule
from .tables import TableRule

__all__ = [
    "BLOCK_RULES",
    "INLINE_RULES",
    "BlockRule",
    "BoldInlineRule",
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
    "StrikeInlineRule",
    "TableRule",
    "ThematicBreakRule",
    "default_block_rules",
    "default_inline_rules",
    "inline_segments",
]
