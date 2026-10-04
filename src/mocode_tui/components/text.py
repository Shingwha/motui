"""Text components: :class:`Text` and :class:`Markdown`.

Both are plain content components: ``render(width)`` is a pure function of
the component's text and the given width.  ``Text`` keeps the caller's line
structure verbatim (one logical line per ``"\\n"``, word-wrapped); ``Markdown``
parses a light subset (paragraphs, ATX headings, fenced code, lists, inline
code/bold/italic) and degrades every unknown construct to plain paragraph
text.  Like every component, these modules only depend on the kernel
(``block``/``lines``/``style``/``text``) and never touch the screen.
"""

from __future__ import annotations

import re

from ..lines import Line, Segment, wrap_line
from ..style import ACCENT, CODE, MUTED, NONE, Style
from ..text import wrap_text

__all__ = ["Markdown", "Text"]

# Inline constructs, tried left to right: `code`, **bold**, *italic* (the
# italic delimiters must sit on word boundaries, so "2*3" stays literal).
_INLINE_RE = re.compile(r"`([^`]*)`|\*\*(.+?)\*\*|(?<![\w*])\*([^*\n]+)\*(?!\w)")

# ATX heading: 1..4 leading '#' followed by whitespace and content.
_ATX_RE = re.compile(r"^(#{1,4})\s+(.*)$")

# List item: '-', '*' or 'N.' marker, then content.
_LIST_RE = re.compile(r"^\s*(?:([-*])|(\d+)\.)\s+(.*)$")

# Heading styles: the accent family, decreasing prominence with depth.
_HEADING_STYLES: tuple[Style, ...] = (
    ACCENT,
    ACCENT.merge(Style(underline=True)),
    Style(fg="cyan"),
    Style(fg="cyan", dim=True),
)


class Text:
    """A block of plain text rendered verbatim, line by line.

    ``text`` is a mutable attribute (streaming text assigns to it).  Each
    logical line (``split("\\n")``) is word-wrapped with
    :func:`~mocode_tui.text.wrap_text` into rows of at most ``width`` columns,
    so blank lines survive as blank rows.  Every row carries ``style`` and is
    ``fit`` to ``width`` as a final guard.
    """

    __slots__ = ("style", "text")

    def __init__(self, text: str = "", *, style: Style = NONE) -> None:
        self.text = text
        self.style = style

    def render(self, width: int) -> list[Line]:
        out: list[Line] = []
        for row in self.text.split("\n"):
            for piece in wrap_text(row, width):
                out.append(Line.from_text(piece, self.style).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Text({self.text!r})"


def _inline_segments(text: str, base: Style) -> list[Segment]:
    """Split ``text`` into styled segments for the inline Markdown subset.

    ``code`` runs use :data:`~mocode_tui.style.CODE`, ``**bold**`` /
    ``*italic*`` merge bold/italic onto ``base``; anything unrecognized
    (including a lone backtick or asterisk) stays literal ``base`` text.
    """
    out: list[Segment] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            out.append(Segment(text[pos : m.start()], base))
        if m.group(1) is not None:
            out.append(Segment(m.group(1), CODE))
        elif m.group(2) is not None:
            out.append(Segment(m.group(2), base.merge(Style(bold=True))))
        else:
            out.append(Segment(m.group(3), base.merge(Style(italic=True))))
        pos = m.end()
    if pos < len(text):
        out.append(Segment(text[pos:], base))
    return out


def _block_starts(line: str) -> bool:
    """True when ``line`` opens a non-paragraph block (heading/list/fence)."""
    if line.strip().startswith("```"):
        return True
    return bool(_ATX_RE.match(line) or _LIST_RE.match(line))


class Markdown:
    """A light Markdown subset rendered as a component.

    Supported: paragraphs (soft line breaks join with a space), ATX headings
    ``#``..``####``, fenced code blocks (```` ``` ````), list items
    (``-``/``*`` and ``1.``), and inline ``code``/``**bold**``/``*italic*``.
    Everything else -- tables, HTML, block quotes, deeper nesting -- degrades
    to plain paragraph text rather than raising.  Blank input rows are
    dropped: blocks stack directly without extra vertical spacing.
    """

    __slots__ = ("style", "text")

    def __init__(self, text: str = "", *, style: Style = NONE) -> None:
        self.text = text
        self.style = style

    def render(self, width: int) -> list[Line]:
        lines = self.text.split("\n")
        out: list[Line] = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            if line.strip().startswith("```"):
                i += 1
                while i < n and not lines[i].strip().startswith("```"):
                    out.append(Line.from_text(lines[i], CODE).fit(width))
                    i += 1
                i += 1  # skip the closing fence (or run off the end)
                continue
            heading = _ATX_RE.match(line)
            if heading:
                level = len(heading.group(1))
                content = _inline_segments(heading.group(2), _HEADING_STYLES[level - 1])
                out.extend(row.fit(width) for row in wrap_line(Line(content), width))
                i += 1
                continue
            item = _LIST_RE.match(line)
            if item:
                marker = f"{item.group(2)}. " if item.group(2) is not None else "\u2022 "
                line_obj = Line((Segment(marker, MUTED),)) + Line(_inline_segments(item.group(3), NONE))
                out.extend(row.fit(width) for row in wrap_line(line_obj, width))
                i += 1
                continue
            # Paragraph: join soft line breaks until a blank row or a new block.
            para = [line.strip()]
            i += 1
            while i < n and lines[i].strip() and not _block_starts(lines[i]):
                para.append(lines[i].strip())
                i += 1
            para_line = Line(_inline_segments(" ".join(para), self.style))
            out.extend(row.fit(width) for row in wrap_line(para_line, width))
        return out

    def __repr__(self) -> str:
        return f"Markdown({self.text!r})"
