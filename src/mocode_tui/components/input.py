"""Input component: a cursor-editable text field rendered as rows.

:class:`Input` owns the editing state (``text`` plus a character ``cursor``)
and a pure ``render(width)``.  The visual geometry is recomputed from the
text with the very same wrap rule the kernel uses
(:func:`mocode_tui.text._wrap_spans`, shared with
:func:`mocode_tui.lines.wrap_line`), so up/down cursor movement follows the
wrapped rows the user actually sees.  The prompt is shown on the first visual
row only; continuation rows are indented by the prompt's width, and the text
area therefore wraps at ``width - visible_width(prompt)``.

No key is read here: the W4 driver feeds ``insert``/``backspace``/``move_*``.
A pure :meth:`Input.cursor_position` reports where the block cursor sits in
the rendered rows, for hosts that park the terminal cursor there (an IME
anchor on a real console).
"""

from __future__ import annotations

from typing import NamedTuple

from ..lines import Line, Segment
from ..style import ACCENT, CURSOR, DIM, NONE, Style
from ..text import _wrap_spans, visible_width

__all__ = ["Input"]

#: Width used for visual-line geometry before the first render (matches the
#: kernel's terminal fallback).
_DEFAULT_WIDTH = 80


class _VisualRow(NamedTuple):
    """One rendered text row as a span of the (tab-normalized) full text."""

    start: int  # global offset of the row's first shown character
    end: int  # global offset just past the row's last shown character
    text: str  # the row's text
    line_start: int  # global offset of the logical line's first character
    line_end: int  # global offset of the logical line's end (before "\\n")


class Input:
    """A prompt-led text field with a reverse-video block cursor.

    ``focused=False`` renders the text plainly (no cursor); an empty focused
    field shows ``placeholder`` in a dim style.  The cursor is drawn by
    re-styling the character under it as ``style.merge(cursor_style)``, or,
    at a row end, by appending a reverse-video space -- skipped when the row
    is already full so no row ever exceeds ``width``.
    """

    __slots__ = (
        "_last_width",
        "cursor",
        "cursor_style",
        "focused",
        "placeholder",
        "prompt",
        "prompt_style",
        "style",
        "text",
    )

    def __init__(
        self,
        *,
        prompt: str = "\u276e ",
        placeholder: str = "",
        style: Style = NONE,
        prompt_style: Style = ACCENT,
        cursor_style: Style = CURSOR,
        focused: bool = True,
    ) -> None:
        self.prompt = prompt
        self.placeholder = placeholder
        self.style = style
        self.prompt_style = prompt_style
        self.cursor_style = cursor_style
        self.focused = focused
        self.text = ""
        self.cursor = 0
        self._last_width = _DEFAULT_WIDTH

    # -- editing --------------------------------------------------------------

    def insert(self, text: str) -> None:
        """Insert ``text`` (may contain newlines) at the cursor."""
        self.text = self.text[: self.cursor] + text + self.text[self.cursor :]
        self.cursor += len(text)

    def backspace(self) -> bool:
        """Delete the character before the cursor; False at the start."""
        if self.cursor == 0:
            return False
        self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
        self.cursor -= 1
        return True

    def delete(self) -> bool:
        """Delete the character at the cursor; False at the end."""
        if self.cursor >= len(self.text):
            return False
        self.text = self.text[: self.cursor] + self.text[self.cursor + 1 :]
        return True

    def clear(self) -> None:
        """Drop all text and park the cursor at the start."""
        self.text = ""
        self.cursor = 0

    def move_left(self) -> bool:
        if self.cursor == 0:
            return False
        self.cursor -= 1
        return True

    def move_right(self) -> bool:
        if self.cursor >= len(self.text):
            return False
        self.cursor += 1
        return True

    def home(self) -> bool:
        """Move to the start of the cursor's logical line."""
        start = self.text.rfind("\n", 0, self.cursor) + 1
        return self._jump_to(start)

    def end(self) -> bool:
        """Move to the end of the cursor's logical line (before its "\\n")."""
        stop = self.text.find("\n", self.cursor)
        target = len(self.text) if stop < 0 else stop
        return self._jump_to(target)

    def move_up(self) -> bool:
        """Move to the previous visual row, keeping the inner column."""
        rows = self._visual_rows(self._last_width)
        index, column = self._locate(rows)
        if index == 0:
            return False
        target = rows[index - 1]
        return self._jump_to(target.start + min(column, target.end - target.start))

    def move_down(self) -> bool:
        """Move to the next visual row, keeping the inner column."""
        rows = self._visual_rows(self._last_width)
        index, column = self._locate(rows)
        if index + 1 >= len(rows):
            return False
        target = rows[index + 1]
        return self._jump_to(target.start + min(column, target.end - target.start))

    def _jump_to(self, offset: int) -> bool:
        offset = max(0, min(offset, len(self.text)))
        moved = offset != self.cursor
        self.cursor = offset
        return moved

    # -- visual geometry -------------------------------------------------------

    def _visual_rows(self, width: int) -> list[_VisualRow]:
        """Wrap the text at the last render width (``_DEFAULT_WIDTH`` before).

        Offsets index the tab-normalized text, which is exactly as long as
        ``text`` (tabs become single spaces), so ``cursor`` stays valid.
        """
        inner = max(0, width - visible_width(self.prompt))
        norm = self.text.replace("\t", " ")
        rows: list[_VisualRow] = []
        base = 0
        for line in norm.split("\n"):
            spans = _wrap_spans(line, inner) if inner > 0 else [(0, 0)]
            for start, end in spans:
                rows.append(
                    _VisualRow(base + start, base + end, line[start:end], base, base + len(line))
                )
            base += len(line) + 1
        return rows

    def _locate(self, rows: list[_VisualRow]) -> tuple[int, int]:
        """Map ``cursor`` to ``(row index, column within the row)``.

        A cursor sitting on whitespace that wrapping dropped at a break
        belongs to the end of the preceding visual row (documented rule).
        """
        cursor = self.cursor
        for index, row in enumerate(rows):
            nxt = rows[index + 1] if index + 1 < len(rows) else None
            if cursor <= row.end:
                if (
                    cursor == row.end
                    and nxt is not None
                    and nxt.line_start == row.line_start
                    and nxt.start == cursor
                ):
                    # Exact wrap boundary: the next row owns the offset, which
                    # keeps the cursor visible and up/down symmetric.
                    return index + 1, 0
                return index, max(0, cursor - row.start)
            if nxt is not None and nxt.line_start == row.line_start:
                if cursor < nxt.start:
                    # Dropped whitespace at a wrap break: previous row's end.
                    return index, row.end - row.start
                continue  # the cursor sits in a later row of this same line
            if cursor <= row.line_end:
                # Last visual row of the line: trailing whitespace / at "\\n".
                return index, row.end - row.start
        last = len(rows) - 1
        return last, len(rows[last].text)

    def cursor_position(self, width: int) -> tuple[int, int]:
        """The cursor cell as ``(visual_row, col)`` of a ``render(width)``.

        The geometry comes from the same wrap rule the render uses
        (:meth:`_visual_rows` + :meth:`_locate`), so the reported cell is
        exactly the cell the render paints as the block cursor: the character
        under the cursor, or the reverse-video space at a row end.

        ``col`` is the 0-based cell offset from the row's left edge -- row 0
        counts the prompt's width, continuation rows indent by it.  An empty
        field reports the prompt-width column (where the cursor space is
        painted).  A row that is exactly full has no cell past its edge, so
        the cursor clamps to the row's last cell.  The result always lands
        inside ``render(width)``: ``0 <= visual_row < len(render(width))`` and
        ``0 <= col < max(1, width)``.

        Pure query: no state changes, no rendering.
        """
        prompt_width = visible_width(self.prompt)
        rows = self._visual_rows(width)
        index, column = self._locate(rows)
        col = prompt_width + visible_width(rows[index].text[:column])
        if width <= 0:
            return index, 0
        return index, min(col, width - 1)

    # -- rendering ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        self._last_width = width
        rows = self._visual_rows(width)
        cursor_index, cursor_column = self._locate(rows)
        prompt_width = visible_width(self.prompt)
        inner = max(0, width - prompt_width)
        placeholder_mode = self.text == "" and self.focused
        out: list[Line] = []
        for index, row in enumerate(rows):
            if index == 0:
                prefix = Segment(self.prompt, self.prompt_style)
            else:
                prefix = Segment(" " * prompt_width)
            if placeholder_mode:  # empty + focused: the first row is unique
                body = self._placeholder_body(cursor_column, inner)
            elif self.focused and index == cursor_index:
                body = self._cursor_body(row.text, cursor_column, inner)
            else:
                body = [Segment(row.text, self.style)] if row.text else []
            out.append(Line((prefix, *body)).fit(width))
        return out

    def _placeholder_body(self, column: int, inner: int) -> list[Segment]:
        text = self.placeholder
        if column < len(text):
            segments = [Segment(text[:column], DIM)] if column else []
            segments.append(Segment(text[column], DIM.merge(self.cursor_style)))
            if column + 1 < len(text):
                segments.append(Segment(text[column + 1 :], DIM))
            return segments
        segments = [Segment(text, DIM)] if text else []
        if visible_width(text) + 1 <= inner:
            segments.append(Segment(" ", DIM.merge(self.cursor_style)))
        return segments

    def _cursor_body(self, text: str, column: int, inner: int) -> list[Segment]:
        if column < len(text):
            segments = [Segment(text[:column], self.style)] if column else []
            segments.append(Segment(text[column], self.style.merge(self.cursor_style)))
            if column + 1 < len(text):
                segments.append(Segment(text[column + 1 :], self.style))
            return segments
        # Row end: append a reverse-video space unless the row is already full.
        segments = [Segment(text, self.style)] if text else []
        if visible_width(text) + 1 <= inner:
            segments.append(Segment(" ", self.style.merge(self.cursor_style)))
        return segments

    def __repr__(self) -> str:
        return f"Input({self.text!r}, cursor={self.cursor})"
