"""The two block rules whose body is itself a document.

A quote's ``>`` lines and a list item's indented continuation re-run the
shared block loop at the narrowed width through the context's live registry,
so custom rules reach inside them.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...kernel.cell import Line, Segment, wrap_line
from ...kernel.glyphs import pair_seat
from ...kernel.text import WrapMode, visible_width
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
    """Block quote: ``> `` lines re-run as blocks behind a ``text.muted`` bar.

    One level is stripped; nested quotes stack bars.  The body renders tight
    (no block gaps) at the bar-narrowed width, italicized where uncolored.
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
                    else seg.style.merge(theme.content.emphasis)
                )
                for seg in row.segments
            )
            out.append(
                (Line((Segment(f"{ctx.glyphs.quote} ", theme.text.muted),)) + body).clip(
                    WrapMode.ELLIPSIS, width
                )
            )
        return out


class ListRule:
    """List: a run of ``-``/``*``/``N.`` items with hanging indents.

    Markers stay verbatim (the ``glyphs.bullets`` override excepted); a
    blank row ends the run.  Indented continuation re-renders as nested
    blocks at the content width, two spaces per level up to
    ``_LIST_MAX_LEVEL``.  A task item's box marker is one action span
    carrying ``TASK_ACTION``; the component stamps the ordinal later.
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
        if number is not None:
            marker = f"{number}. "
        elif ctx.glyphs.bullets:
            marker = f"{ctx.glyphs.bullets[min(level, len(ctx.glyphs.bullets) - 1)]} "
        else:
            marker = f"{bullet} "
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
                Line((Segment(prefix_text, theme.content.marker),))
                if k == 0
                else Line.from_text(" " * prefix_w)
            )
            out.append((lead + row).clip(WrapMode.ELLIPSIS, width))
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
                (Line.from_text(" " * prefix_w) + row).clip(WrapMode.ELLIPSIS, width)
                for row in inner_rows
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

        The box and its space are one segment carrying ``TASK_ACTION``;
        checked and unchecked boxes share the pair's wider seat.  An empty
        pair renders the body alone.  Continuations indent like a bullet's.
        """
        theme = ctx.theme
        checked = task.group(1) in "xX"
        body = task.group(2) or ""
        open_mark, done_mark = ctx.glyphs.check_off, ctx.glyphs.check_on
        glyph, other = (done_mark, open_mark) if checked else (open_mark, done_mark)
        marker_text = pair_seat(glyph, other)
        prefix_text = "  " * level
        prefix_w = visible_width(prefix_text) + visible_width(marker_text)
        budget = max(width - prefix_w, 1)
        rows = wrap_line(Line(inline_segments(body, ctx)), budget)
        marker = (
            Segment(marker_text, theme.content.marker, action=TASK_ACTION)
            if marker_text
            else None
        )
        if marker is None:
            lead = (
                Line((Segment(prefix_text, theme.content.marker),))
                if prefix_text
                else Line()
            )
        else:
            lead = (
                Line((Segment(prefix_text, theme.content.marker), marker))
                if prefix_text
                else Line((marker,))
            )
        out: list[Line] = []
        for k, row in enumerate(rows):
            first = lead if k == 0 else Line.from_text(" " * prefix_w)
            out.append((first + row).clip(WrapMode.ELLIPSIS, width))
        if continuation:
            strip = prefix_w
            inner = []
            for line in continuation:
                drop = min(strip, len(line) - len(line.lstrip(" ")))
                inner.append(line[drop:])
            inner_rows = _run_blocks(inner, budget, ctx, gap=0)
            out.extend(
                (Line.from_text(" " * prefix_w) + row).clip(WrapMode.ELLIPSIS, width)
                for row in inner_rows
            )
        return out
