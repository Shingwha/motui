"""Markdown component: a rule-registry-driven line-level parser.

:class:`Markdown` turns a mutable text buffer into rendered rows through two
ordered registries.  A :class:`BlockRule` classifies the line at the cursor
(``match`` returns how many lines it consumes, ``None`` when it declines) and
renders exactly those lines (``render``); an :class:`InlineRule` recognizes one
inline construct at a position (``match`` returns the end offset plus the
segments it produces).  :data:`BLOCK_RULES` is tried in order and ends with
:class:`ParagraphRule`, the catch-all; :data:`INLINE_RULES` runs left to right
inside a line.

Both registries are dep-free module singletons: a rule holds no theme, no
registry and no highlighter of its own, so one instance serves every
:class:`Markdown`.  What a rule needs to render arrives in one frozen
:class:`RenderContext` -- ``theme``, ``highlighter``, ``divider_max_width``
and the two live registries -- which :class:`Markdown` builds once and passes
into ``render``.  Extending is therefore "implement the protocol, read the
ctx", not "implement five cloning conventions".

Streaming safety is a hard constraint (the demo assigns ``.text`` one chunk at
a time): a half-open fence renders its body to the end, a table is only a
table once header *and* delimiter row are both present, and an unclosed
inline marker stays literal.  Every row a rule returns is wrapped and
``fit`` to ``width``, so no row ever exceeds the painting width.

Fenced code blocks (:class:`FenceRule`) parse the language tag after the
opening fence (`` ```python ``) and hand the body to a
:class:`~mocode_tui.widgets.syntax.Highlighter`: the built-in regex
highlighter by default, or your own object -- anything with
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

Like every component this package only imports the kernel (``lines``/
``style``/``text``/``theme``) and sibling components (``Table`` for GFM
tables, ``Divider`` for thematic breaks); it never touches a screen.

Module map: :mod:`~.inline` the inline engine, :mod:`~.blocks` the block
protocol, the leaf rules and the shared block loop, :mod:`~.nested` the
quote and list rules (bodies that are documents), :mod:`~.tables` the GFM
table, :mod:`~.context` the render context, :mod:`~.component` the component
and the default registry.
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
    inline_segments,
)
from .nested import ListRule, QuoteRule
from .tables import TableRule

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
    "StrikeInlineRule",
    "TableRule",
    "ThematicBreakRule",
    "default_block_rules",
    "inline_segments",
]
