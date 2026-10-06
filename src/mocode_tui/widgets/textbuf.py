"""TextBuffer: the editing engine shared by :class:`Input` and :class:`Editor`.

One engine holds the text model both components edit -- ``list[str]``
logical lines plus a ``(row, col)`` cursor -- together with the full
editing-method set (``insert``, ``backspace``, ``delete``, ``clear``,
``newline``, ``move_*``, ``home``, ``end``), the keymap-driven routing,
the visual-row geometry, the reverse-video block-cursor body, and the
placeholder body.

The policy stays in the shells: the prompt and its indent
(:class:`~mocode_tui.widgets.input.Input`), the ``max_rows`` window
(:class:`~mocode_tui.widgets.editor.Editor`), the placeholder text, and
the resolved styles.  The geometry is one implementation parameterized by
``indent`` -- the columns every row is inset by, the prompt's width for
``Input`` and 0 for ``Editor`` -- so a row wraps at ``width - indent`` and
the cursor's cell is ``indent + text width``.  The wrap rule is the
kernel's (:func:`mocode_tui.core.text.wrap_spans`, shared with
:func:`mocode_tui.core.lines.wrap_line`), so up/down cursor movement
follows the wrapped rows the user sees.
"""

from __future__ import annotations

from typing import NamedTuple

from ..core.events import Key, Paste
from ..core.lines import Segment
from ..core.style import Style
from ..core.text import wrap_spans, visible_width
from ..keys.keymap import Keymap

__all__ = ["TextBuffer"]

#: Width the visual geometry uses before the first ``render(width)`` seeds
#: it (matches the kernel's terminal fallback).
DEFAULT_WIDTH = 80


class _VisualRow(NamedTuple):
    """One rendered text row as a span of the (tab-normalized) joined text."""

    start: int  # flat offset of the row's first shown character
    end: int  # flat offset just past the row's last shown character
    text: str  # the row's text
    line_start: int  # flat offset of the logical line's first character
    line_end: int  # flat offset of the logical line's end (before "\\n")


class TextBuffer:
    """The editing engine: rows, cursor, keymap routing, wrapped geometry.

    ``lines`` holds the logical lines and ``(row, col)`` the cursor's
    position in them.  ``insert`` accepts ``"\\n"`` (a multi-line paste
    splits the line at the cursor) and ``backspace``/``delete`` merge
    across line boundaries; :class:`~mocode_tui.widgets.input.Input` is a
    single-line field because it surfaces no :meth:`newline` and its
    keymap binds no ``enter`` -- a pasted newline simply stays in the text,
    exactly as it always did.

    ``last_width`` is the width the visual geometry wraps against: a
    ``render(width)`` seeds it and until the first render it is
    :data:`DEFAULT_WIDTH` (80), so ``move_up``/``move_down`` have a sane
    geometry before anything is painted.  ``indent`` is the columns every
    visual row is inset by -- the shell supplies the prompt's width for
    :class:`~mocode_tui.widgets.input.Input` and 0 for
    :class:`~mocode_tui.widgets.editor.Editor` -- and the routed visual
    moves read it from here, not from a per-call parameter.
    """

    __slots__ = ("_col", "_row", "indent", "keymap", "last_width", "lines")

    def __init__(self, text: str = "", *, keymap: Keymap, indent: int = 0) -> None:
        self.lines = text.split("\n")
        self.keymap = keymap
        self.indent = indent
        self._row = 0
        self._col = 0
        self.last_width = DEFAULT_WIDTH

    # -- buffer views -----------------------------------------------------------

    @property
    def value(self) -> str:
        """The full buffer text, logical lines joined by ``"\\n"``."""
        return "\n".join(self.lines)

    @property
    def row(self) -> int:
        """The cursor's logical line index."""
        return self._row

    @property
    def col(self) -> int:
        """The cursor's character offset inside line :attr:`row`."""
        return self._col

    @property
    def empty(self) -> bool:
        """True when the buffer is a single empty line (placeholder state)."""
        return len(self.lines) == 1 and not self.lines[0]

    @property
    def offset(self) -> int:
        """The cursor as a flat character offset into :attr:`value`."""
        return self._cursor_offset()

    # -- editing --------------------------------------------------------------

    def handle(self, event: Key | Paste) -> bool:
        """Consume an event: route it through :attr:`keymap`; ``True`` when consumed.

        A :class:`~mocode_tui.core.events.Paste` inserts its text.  A
        :class:`~mocode_tui.core.events.Key` whose ``char`` is set -- a
        printable, ``space`` included -- is inserted directly, so printables
        never need a keymap entry.  Otherwise the event's ``name`` is looked
        up in :attr:`keymap` and the same-named no-argument editing method
        runs; the editor's default table maps ``enter`` to :meth:`newline`
        and the input's maps it to nothing, which is how the return key
        reaches the host as its submit gesture.  The visual moves
        (``move_up``/``move_down``) wrap against :attr:`last_width` inset by
        :attr:`indent` -- the prompt width for an
        :class:`~mocode_tui.widgets.input.Input`, 0 for an
        :class:`~mocode_tui.widgets.editor.Editor` -- so they follow the
        wrapped rows the shell renders, including before the first render
        (``last_width`` then is :data:`DEFAULT_WIDTH`).

        Returns ``False`` for every event the buffer does not consume (a name
        unbound in the keymap): the host then routes it -- submit, palette,
        quit -- itself.
        """
        if isinstance(event, Paste):
            self.insert(event.text)
            return True
        if event.char:
            self.insert(event.char)
            return True
        action = self.keymap.get(event.name)
        if action is None:
            return False
        getattr(self, action)()
        return True

    def insert(self, text: str) -> None:
        """Insert ``text`` (may contain newlines) at the cursor."""
        parts = text.split("\n")
        if len(parts) == 1:
            line = self.lines[self._row]
            self.lines[self._row] = line[: self._col] + text + line[self._col :]
            self._col += len(text)
            return
        head = self.lines[self._row]
        tail = head[self._col :]
        parts[0] = head[: self._col] + parts[0]
        parts[-1] += tail
        self.lines[self._row : self._row + 1] = parts
        self._row += len(parts) - 1
        self._col = len(parts[-1]) - len(tail)

    def backspace(self) -> bool:
        """Delete the character before the cursor.

        At a line start the line is merged into the previous one and the
        cursor parks at the junction; ``False`` at the very start.
        """
        if self._col > 0:
            line = self.lines[self._row]
            self.lines[self._row] = line[: self._col - 1] + line[self._col :]
            self._col -= 1
            return True
        if self._row == 0:
            return False
        head = self.lines[self._row - 1]
        self.lines[self._row - 1] = head + self.lines[self._row]
        del self.lines[self._row]
        self._row -= 1
        self._col = len(head)
        return True

    def delete(self) -> bool:
        """Delete the character at the cursor.

        At a line end the next line is merged up; ``False`` at the very end.
        """
        line = self.lines[self._row]
        if self._col < len(line):
            self.lines[self._row] = line[: self._col] + line[self._col + 1 :]
            return True
        if self._row + 1 >= len(self.lines):
            return False
        self.lines[self._row] = line + self.lines[self._row + 1]
        del self.lines[self._row + 1]
        return True

    def newline(self) -> bool:
        """Break the cursor's line at the cursor; the cursor moves to the
        new line's start.  Always succeeds (``True``)."""
        line = self.lines[self._row]
        self.lines[self._row : self._row + 1] = [line[: self._col], line[self._col :]]
        self._row += 1
        self._col = 0
        return True

    def clear(self) -> None:
        """Drop the whole buffer and park the cursor at the start."""
        self.lines = [""]
        self._row = 0
        self._col = 0

    def move_left(self) -> bool:
        if self._col > 0:
            self._col -= 1
            return True
        if self._row == 0:
            return False
        self._row -= 1
        self._col = len(self.lines[self._row])
        return True

    def move_right(self) -> bool:
        if self._col < len(self.lines[self._row]):
            self._col += 1
            return True
        if self._row + 1 >= len(self.lines):
            return False
        self._row += 1
        self._col = 0
        return True

    def home(self) -> bool:
        """Move to the start of the cursor's logical line."""
        moved = self._col != 0
        self._col = 0
        return moved

    def end(self) -> bool:
        """Move to the end of the cursor's logical line (before its "\\n")."""
        target = len(self.lines[self._row])
        moved = self._col != target
        self._col = target
        return moved

    def move_up(self) -> bool:
        """Move to the previous visual row, keeping the inner column.

        The rows are the ones :attr:`last_width` and :attr:`indent` describe
        -- exactly the geometry the shell's render wraps against.
        """
        rows = self.visual_rows(self.last_width, self.indent)
        index, column = self.locate(rows)
        if index == 0:
            return False
        target = rows[index - 1]
        return self._set_offset(target.start + min(column, target.end - target.start))

    def move_down(self) -> bool:
        """Move to the next visual row, keeping the inner column.

        The rows are the ones :attr:`last_width` and :attr:`indent` describe
        -- exactly the geometry the shell's render wraps against.
        """
        rows = self.visual_rows(self.last_width, self.indent)
        index, column = self.locate(rows)
        if index + 1 >= len(rows):
            return False
        target = rows[index + 1]
        return self._set_offset(target.start + min(column, target.end - target.start))

    # -- flat offsets ----------------------------------------------------------

    def _text_length(self) -> int:
        return sum(len(line) + 1 for line in self.lines) - 1

    def _cursor_offset(self) -> int:
        return sum(len(line) + 1 for line in self.lines[: self._row]) + self._col

    def _set_offset(self, offset: int) -> bool:
        """Move the cursor to the flat ``offset`` (clamped); True when moved."""
        offset = max(0, min(offset, self._text_length()))
        moved = offset != self._cursor_offset()
        row, remaining = 0, offset
        for line in self.lines:
            if remaining <= len(line):
                self._row, self._col = row, remaining
                return moved
            remaining -= len(line) + 1
            row += 1
        last = len(self.lines) - 1  # unreachable with a clamped offset
        self._row, self._col = last, len(self.lines[last])
        return moved

    # -- visual geometry -------------------------------------------------------

    def visual_rows(self, width: int, indent: int = 0) -> list[_VisualRow]:
        """Wrap the buffer at ``width``, every row inset by ``indent``.

        Offsets index the tab-normalized joined text, which is exactly as
        long as :attr:`value` (tabs become single spaces), so the cursor's
        flat offset stays valid across the normalization.
        """
        inner = max(0, width - indent)
        rows: list[_VisualRow] = []
        base = 0
        for line in (line.replace("\t", " ") for line in self.lines):
            spans = wrap_spans(line, inner) if inner > 0 else [(0, 0)]
            for start, end in spans:
                rows.append(
                    _VisualRow(base + start, base + end, line[start:end], base, base + len(line))
                )
            base += len(line) + 1
        return rows

    def locate(self, rows: list[_VisualRow]) -> tuple[int, int]:
        """Map the cursor's flat offset to ``(visual row, column within it)``.

        An exact wrap boundary belongs to the next row (which keeps the
        cursor visible and up/down symmetric), and whitespace dropped at a
        break keeps the cursor at the preceding row's end.
        """
        cursor = self._cursor_offset()
        for index, row in enumerate(rows):
            nxt = rows[index + 1] if index + 1 < len(rows) else None
            if cursor <= row.end:
                if (
                    cursor == row.end
                    and nxt is not None
                    and nxt.line_start == row.line_start
                    and nxt.start == cursor
                ):
                    return index + 1, 0
                return index, max(0, cursor - row.start)
            if nxt is not None and nxt.line_start == row.line_start:
                if cursor < nxt.start:
                    return index, row.end - row.start
                continue  # the cursor sits in a later row of this same line
            if cursor <= row.line_end:
                return index, row.end - row.start
        last = len(rows) - 1
        return last, len(rows[last].text)

    def cursor_position(
        self, width: int, indent: int = 0, window: int = 0
    ) -> tuple[int, int]:
        """The block cursor's cell as ``(visual row, col)`` of a render.

        The geometry is the one ``render`` uses (``visual_rows`` +
        ``locate``), so the reported cell is exactly the cell a render
        paints as the block cursor: the character under the cursor, or the
        reverse-video space at a row end.  ``col`` is the 0-based cell
        offset from the row's left edge -- ``indent`` columns for a
        prompt-led row, 0 for the editor's -- and ``window`` shifts
        ``visual row`` into a rendered ``max_rows`` window, so the reported
        cell always lands inside the rows a render returns.  Pure query:
        no state changes, no rendering.
        """
        rows = self.visual_rows(width, indent)
        index, column = self.locate(rows)
        col = indent + visible_width(rows[index].text[:column])
        if width <= 0:
            return index - window, 0
        return index - window, min(col, width - 1)

    # -- row bodies ------------------------------------------------------------

    def cursor_body(
        self, text: str, column: int, inner: int, style: Style, cursor_style: Style
    ) -> list[Segment]:
        """The cursor row's body: the block cursor as reverse video.

        The character under the cursor is re-styled as
        ``style.merge(cursor_style)``; at a row end a reverse-video space
        is appended instead -- skipped when the row already fills ``inner``
        columns, so no row ever exceeds its width.
        """
        if column < len(text):
            segments = [Segment(text[:column], style)] if column else []
            segments.append(Segment(text[column], style.merge(cursor_style)))
            if column + 1 < len(text):
                segments.append(Segment(text[column + 1 :], style))
            return segments
        # Row end: append a reverse-video space unless the row is already full.
        segments = [Segment(text, style)] if text else []
        if visible_width(text) + 1 <= inner:
            segments.append(Segment(" ", style.merge(cursor_style)))
        return segments

    def placeholder_body(
        self,
        column: int,
        inner: int,
        text: str,
        dim: Style,
        cursor_style: Style,
        trail_style: Style,
    ) -> list[Segment]:
        """The empty-state body: the hint in ``dim`` plus the block cursor.

        ``column`` is the cursor's position inside the hint: the block
        paints over the character under it (an ``Input`` placeholder), or
        -- at and past the hint's end -- as a trailing space (an ``Editor``
        placeholder).  That trailing space rides ``trail_style`` under the
        cursor style: ``Input`` passes the dim (the whole placeholder
        reads dim), ``Editor`` passes its own text style so the empty row
        shares a typed row's cursor.  The trailing space is skipped when
        the hint already fills ``inner`` columns.

        Two measures meet here and deliberately stay apart: ``column`` and
        the ``text[:column]`` slicing are **character indices**, while the
        fit check (``visible_width(text) + 1 <= inner``) is in **display
        columns** -- for wide characters the two differ, and the width of
        the painted cell is what ``inner`` budgets.  :meth:`cursor_body`
        splits the same way.
        """
        if column < len(text):
            segments = [Segment(text[:column], dim)] if column else []
            segments.append(Segment(text[column], dim.merge(cursor_style)))
            if column + 1 < len(text):
                segments.append(Segment(text[column + 1 :], dim))
            return segments
        segments = [Segment(text, dim)] if text else []
        if visible_width(text) + 1 <= inner:
            segments.append(Segment(" ", trail_style.merge(cursor_style)))
        return segments
