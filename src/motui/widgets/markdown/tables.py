"""The GFM pipe table: header row plus a matching delimiter row.

Escaped pipes, edge pipes and alignment markers live here with the rule.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...kernel.cell import Line
from ...kernel.layout import Constraints
from ..table import Table
from .inline import inline_segments

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

    Both rows must be present (a half-typed table degrades to a paragraph).
    Cells render inline markup; alignment comes from the delimiter row and
    escaped ``\\|`` stays literal.
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
            [
                [
                    inline_segments(row[c], ctx) if c < len(row) else ""
                    for c in range(ncols)
                ]
                for row in body
            ],
            headers=[inline_segments(cell, ctx) for cell in header],
            aligns=aligns,
            theme=ctx.theme,
        )
        return table.render(Constraints(width=width))


def _split_row(line: str) -> list[str] | None:
    """Split a pipe row into stripped cells, or ``None`` without a pipe.

    Splits on unescaped pipes and restores ``\\|``; edge pipes are dropped.
    A double backslash next to a pipe is a documented simplification.
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
