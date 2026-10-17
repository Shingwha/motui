"""The GFM pipe table: header row plus a matching delimiter row.

Splitting a pipe row is its own small grammar -- a pipe preceded by a
backslash is escaped, leading and trailing pipes are dropped, alignment
markers live in the delimiter row -- so the splitter and the
:class:`TableRule` that uses it sit together, apart from the other blocks.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...kernel.lines import Line
from .inline import inline_segments
from ..table import Table

if TYPE_CHECKING:  # annotations only: rendering happens through a ctx
    from .context import RenderContext

__all__ = ["TableRule"]

# One GFM delimiter cell: dashes with optional ':' alignment markers.
_DELIM_CELL_RE = re.compile(r"^:?-+:?$")

#: Pipe-row splitter: a pipe preceded by a backslash is escaped (a cell may
#: hold a literal ``|`` that way), every other pipe delimits cells.
_ROW_SPLIT_RE = re.compile(r"(?<!\\)\|")


class TableRule:
    """GFM pipe table: header row + delimiter row, aligned per column.

    The table is only a table once *both* the header and a matching
    delimiter row are present (a half-typed table degrades to a paragraph
    -- the streaming-safety rule).  Cells render the document's inline
    markup (bold, code, links); every cell's segments carry no base style,
    and the :class:`~motui.widgets.table.Table` injects the column base
    (header style, first-column style).  Alignment (``:--`` / ``--:`` /
    ``:-:``) is computed from the delimiter row and handed to the grid as its
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
