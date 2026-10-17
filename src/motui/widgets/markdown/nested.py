"""The two block rules whose body is itself a document.

A block quote and a list item carry inner markup: the quote's ``>`` lines
and the lines indented past an item's marker are re-run through the shared
block loop (:func:`~.blocks._run_blocks`) at the narrowed width, using the
live registry carried by the context, so a custom block rule reaches inside
a quote or a list item exactly like a built-in one.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...kernel.lines import Line, Segment, wrap_line
from ...kernel.style import Style
from ...kernel.text import visible_width
from .blocks import _run_blocks
from .inline import inline_segments

if TYPE_CHECKING:  # annotations only: rendering happens through a ctx
    from .context import RenderContext

__all__ = ["ListRule", "QuoteRule"]

# List item: optional indent, then '-', '*' or 'N.' + whitespace + content.
_LIST_RE = re.compile(r"^(\s*)(?:([-*])|(\d+)\.)\s+(.*)$")

# Task-list item: a *bullet* item whose content opens with "[ ]" / "[x]".
# The marker must be complete -- a half-typed "- [x" stays an ordinary
# item, the streaming-safety rule -- and one space of separation is
# required (as in GFM), while an empty task ("- [ ]") is a task with no
# body.  Ordered items never take the marker: the bullet is what the task
# marker replaces.
_TASK_RE = re.compile(r"^\[([ xX])\](?:[ \t]+(.*))?$")

# Block quote: optional indent, '>', one optional space, content.
_QUOTE_RE = re.compile(r"^\s*> ?(.*)$")

#: Deepest list tier kept: indents 0 and 2 spaces are distinct levels, deeper
#: indents cap here (the ticket's "2 级" reading; see the report's tradeoffs).
_LIST_MAX_LEVEL = 1

#: The two task markers a bullet is replaced by: an unchecked / checked box,
#: one column each (so a task's hanging indent matches a bullet's).
TODO_MARK = "\u2610"  # ☐
DONE_MARK = "\u2611"  # ☑

#: The action a task marker carries out of :class:`ListRule`: the bare
#: ``"todo:"`` -- the *placeholder*, no ordinal yet.  The flat index is a
#: document-wide count, and the rule layer is stateless (one singleton
#: serves every component and every nesting level), so the ordinal is
#: stamped **after** the whole document is rendered, by
#: :meth:`~.component.Markdown._stamp_tasks`: the placeholder becomes
#: ``"todo:<flat index>"`` in draw order.  The rule never guesses the
#: number; the component owns the document-wide walk.
TASK_ACTION = "todo:"


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
                seg.with_style(
                    seg.style
                    if seg.style.fg or seg.style.bg or seg.style.bold
                    else seg.style.merge(Style(italic=True))
                )
                for seg in row.segments
            )
            out.append((Line((Segment("\u2502 ", theme.muted),)) + body).fit(width))
        return out


class ListRule:
    """List: a run of ``-``/``*``/``N.`` items, markers kept verbatim.

    A blank row ends the run, so a tight list is a single block and only
    blank-line-separated items end up in separate blocks -- the component's
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

    **Task items.**  A *bullet* item whose content opens with ``[ ]`` or
    ``[x]`` (one space of separation, as in GFM; a half-typed ``- [x`` is
    an ordinary item) is a task: the bullet is replaced by a one-column box
    -- :data:`TODO_MARK` (``\\u2610``) or :data:`DONE_MARK` (``\\u2611``) --
    and that marker rides its own segment, carrying the bare
    :data:`TASK_ACTION` placeholder as its ``action``: the whole ``"\\u2610 "``
    run is the click span, styled like any list marker.  The *ordinal* is
    not the rule's to know (the rule is a stateless singleton and the count
    is the document's): the component stamps ``"todo:<flat index>"`` onto
    the finished rows, flat across the whole document in draw order.
    Ordered items (``1. [ ]``) never take the marker -- the bullet is what
    it replaces -- and an item with no body (``- [ ]``) still renders its
    marker.
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
        assert matched is not None  # match() gated this shape
        indent, bullet, number, content = matched.groups()
        level = min(len(indent) // 2, _LIST_MAX_LEVEL)
        task = None if number is not None else _TASK_RE.match(content)
        if task is not None:
            return self._render_task(task, continuation, level, width, ctx)
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

    def _render_task(
        self,
        task: re.Match[str],
        continuation: list[str],
        level: int,
        width: int,
        ctx: RenderContext,
    ) -> list[Line]:
        """One task item: the box marker as the action span, then the body.

        The bullet is gone (the box replaces it); the box and its trailing
        space are **one segment** carrying :data:`TASK_ACTION`, so the whole
        ``"\\u2610 "`` run is the click span and the ordinal stamping in the
        component has exactly one segment per item to count.  The hanging
        indent matches a bullet item's at the same level (the box is one
        column, the space another), and the continuation blocks -- a task
        item may carry nested content like any other -- indent by the same
        width.
        """
        theme = ctx.theme
        checked = task.group(1) in "xX"
        body = task.group(2) or ""
        marker_text = f"{TODO_MARK if not checked else DONE_MARK} "
        prefix_text = "  " * level
        prefix_w = visible_width(prefix_text) + visible_width(marker_text)
        budget = max(width - prefix_w, 1)
        rows = wrap_line(Line(inline_segments(body, ctx)), budget)
        marker = Segment(marker_text, theme.list_marker, action=TASK_ACTION)
        lead = (
            Line((Segment(prefix_text, theme.list_marker), marker))
            if prefix_text
            else Line((marker,))
        )
        out: list[Line] = []
        for k, row in enumerate(rows):
            first = lead if k == 0 else Line.from_text(" " * prefix_w)
            out.append((first + row).fit(width))
        if continuation:
            strip = len(prefix_text) + len(marker_text)
            inner = []
            for line in continuation:
                drop = min(strip, len(line) - len(line.lstrip(" ")))
                inner.append(line[drop:])
            inner_rows = _run_blocks(inner, budget, ctx, gap=0)
            out.extend(
                (Line.from_text(" " * prefix_w) + row).fit(width) for row in inner_rows
            )
        return out
