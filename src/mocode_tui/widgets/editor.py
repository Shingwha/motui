"""Editor component: a multi-line, cursor-editable text buffer rendered as rows.

:class:`Editor` owns the editing state -- a ``list[str]`` of logical lines
plus a ``(row, col)`` cursor -- and a pure ``render(width)``.  The visual
geometry is recomputed from the text with the very same wrap rule the kernel
uses (:func:`mocode_tui.core.text._wrap_spans`, shared with
:func:`mocode_tui.core.lines.wrap_line`), so up/down cursor movement follows
the wrapped rows the user actually sees, exactly as
:class:`~mocode_tui.widgets.input.Input` documents.

Where ``Input`` is a single-line field, the buffer here holds newlines:
:meth:`newline` breaks a line at the cursor, :meth:`insert` accepts text
containing ``"\\n"`` (a multi-line paste), and :meth:`backspace` merges the
cursor's line into the previous one.  Unlike ``Input``, the editor renders
no prompt -- continuation rows exist there for the prompt's indent -- so
every visual row is a full-width wrap of its logical line.  ``max_rows`` caps
the rendered rows with a sliding window centred on the cursor's visual row,
so the block cursor never scrolls out of view.

Keys are routed by :meth:`handle_key` through the component's
:attr:`keymap` -- :data:`~mocode_tui.keys.keymap.DEFAULT_EDITOR_KEYMAP` by
default, which binds ``enter`` to ``newline``: **the editor itself consumes
the return key**.  A submit gesture is not a library binding; the host wires
one on an event the editor leaves unconsumed (``handle_key`` returns
``False`` for it), e.g. ``c-enter`` or ``escape``.

Styles resolve at render time as explicit parameter > theme field >
:data:`~mocode_tui.core.theme.DEFAULT_THEME`, the same rule every component
follows.  ``prompt_style`` is accepted for signature symmetry with ``Input``
and kept on the instance for hosts that compose a prompt around the editor;
``Editor`` itself renders none.
"""

from __future__ import annotations

from typing import NamedTuple

from ..keys.events import Key, Paste
from ..keys.keymap import DEFAULT_EDITOR_KEYMAP, Keymap
from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import _wrap_spans, visible_width
from ..core.theme import DEFAULT_THEME, Theme

__all__ = ["Editor"]

#: Width used for visual-line geometry before the first render (matches the
#: kernel's terminal fallback).
_DEFAULT_WIDTH = 80


class _VisualRow(NamedTuple):
    """One rendered text row as a span of the (tab-normalized) joined text."""

    start: int  # flat offset of the row's first shown character
    end: int  # flat offset just past the row's last shown character
    text: str  # the row's text
    line_start: int  # flat offset of the logical line's first character
    line_end: int  # flat offset of the logical line's end (before "\\n")


class Editor:
    """A multi-line text buffer with a reverse-video block cursor.

    ``text`` seeds the buffer (the cursor parks at its start);
    ``placeholder`` shows dim on the first row of an empty focused editor,
    with the cursor block trailing it exactly as on a typed row.
    ``focused=False`` renders the text plainly (no cursor, no placeholder).
    The cursor is drawn by re-styling the character under it as
    ``style.merge(cursor_style)``, or, at a row end, by appending a
    reverse-video space -- skipped when the row is already full so no row
    ever exceeds ``width``.  ``cursor_style`` and the placeholder's dim
    style fall back to the theme's ``cursor``/``dim`` when not given
    explicitly.  ``max_rows`` (``None`` = unlimited) caps the rendered rows
    with a sliding window that keeps the cursor's visual row visible.
    """

    __slots__ = (
        "_col",
        "_last_width",
        "_row",
        "cursor_style",
        "focused",
        "keymap",
        "lines",
        "max_rows",
        "placeholder",
        "prompt_style",
        "style",
        "theme",
    )

    def __init__(
        self,
        *,
        text: str = "",
        placeholder: str = "",
        style: Style | None = None,
        prompt_style: Style | None = None,
        cursor_style: Style | None = None,
        theme: Theme | None = None,
        keymap: Keymap | None = None,
        focused: bool = True,
        max_rows: int | None = None,
    ) -> None:
        self.lines = text.split("\n")
        self.placeholder = placeholder
        self.style = style
        self.prompt_style = prompt_style  # unused by render: no prompt (see module)
        self.cursor_style = cursor_style
        self.theme = theme
        self.keymap = keymap if keymap is not None else DEFAULT_EDITOR_KEYMAP
        self.focused = focused
        self.max_rows = max_rows
        self._row = 0
        self._col = 0
        self._last_width = _DEFAULT_WIDTH

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
    def cursor(self) -> tuple[int, int]:
        """The cursor as ``(row, col)``."""
        return self._row, self._col

    # -- editing --------------------------------------------------------------

    def handle_key(self, key: Key | Paste, width: int) -> bool:
        """Route one event through :attr:`keymap`; ``True`` when consumed.

        Same routing as :meth:`~mocode_tui.widgets.input.Input.handle_key`:
        a :class:`~mocode_tui.keys.events.Paste` inserts its text; a
        :class:`~mocode_tui.keys.events.Key` whose ``char`` is set -- a
        printable, ``space`` included -- is inserted directly, so printables
        never need a keymap entry; otherwise the event's ``name`` is looked
        up in :attr:`keymap` and the same-named no-argument editing method
        runs (the default table maps ``enter`` to :meth:`newline`).
        ``width`` seeds the wrap geometry exactly as ``render(width)`` does.

        Returns ``False`` for every event the buffer does not consume -- a
        name unbound in the keymap -- leaving the host free to route it.  A
        submit gesture is one such event: no library keymap binds it.
        """
        self._last_width = width
        if isinstance(key, Paste):
            self.insert(key.text)
            return True
        if key.char:
            self.insert(key.char)
            return True
        action = self.keymap.get(key.name)
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
        """Move to the previous visual row, keeping the inner column."""
        rows = self._visual_rows(self._last_width)
        index, column = self._locate(rows)
        if index == 0:
            return False
        target = rows[index - 1]
        return self._set_offset(target.start + min(column, target.end - target.start))

    def move_down(self) -> bool:
        """Move to the next visual row, keeping the inner column."""
        rows = self._visual_rows(self._last_width)
        index, column = self._locate(rows)
        if index + 1 >= len(rows):
            return False
        target = rows[index + 1]
        return self._set_offset(target.start + min(column, target.end - target.start))

    # -- visual geometry -------------------------------------------------------

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

    def _visual_rows(self, width: int) -> list[_VisualRow]:
        """Wrap every logical line at ``width`` (the last render's width).

        Offsets index the tab-normalized joined text, which is exactly as
        long as :attr:`value` (tabs become single spaces), so the cursor's
        flat offset stays valid across the normalization.
        """
        norm = [line.replace("\t", " ") for line in self.lines]
        rows: list[_VisualRow] = []
        base = 0
        for line in norm:
            spans = _wrap_spans(line, width) if width > 0 else [(0, 0)]
            for start, end in spans:
                rows.append(
                    _VisualRow(base + start, base + end, line[start:end], base, base + len(line))
                )
            base += len(line) + 1
        return rows

    def _locate(self, rows: list[_VisualRow]) -> tuple[int, int]:
        """Map the cursor's flat offset to ``(visual row, column within it)``.

        Same rules as :meth:`~mocode_tui.widgets.input.Input`'s internal
        locator: an exact wrap boundary belongs to the next row (which keeps
        the cursor visible and up/down symmetric), and whitespace dropped at
        a break keeps the cursor at the preceding row's end.
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

    def _window_start(self, total: int, cursor_index: int) -> int:
        """Flat start of the ``max_rows`` window that keeps the cursor visible.

        The window centres on the cursor's visual row and slides at the
        ends; without a cap (or when everything fits) it starts at 0.
        """
        cap = self.max_rows
        if cap is None or total <= cap:
            return 0
        return min(max(0, cursor_index - cap // 2), total - cap)

    def cursor_position(self, width: int) -> tuple[int, int]:
        """The cursor cell as ``(visual_row, col)`` of a ``render(width)``.

        Same semantics as
        :meth:`~mocode_tui.widgets.input.Input.cursor_position`, with the
        ``max_rows`` window applied: ``visual_row`` indexes the rows
        ``render(width)`` actually returns, so the reported cell always
        lands inside them.  ``col`` is the 0-based cell offset from the
        row's left edge (the editor renders no prompt).  Pure query: no
        state changes, no rendering.
        """
        rows = self._visual_rows(width)
        index, column = self._locate(rows)
        start = self._window_start(len(rows), index)
        col = visible_width(rows[index].text[:column])
        if width <= 0:
            return index - start, 0
        return index - start, min(col, width - 1)

    # -- rendering ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        self._last_width = width
        theme = self.theme or DEFAULT_THEME
        rows = self._visual_rows(width)
        cursor_index, cursor_column = self._locate(rows)
        start = self._window_start(len(rows), cursor_index)
        shown = rows if self.max_rows is None else rows[start : start + max(self.max_rows, 0)]
        empty = len(self.lines) == 1 and not self.lines[0]
        placeholder_mode = empty and self.focused
        style = self.style if self.style is not None else NONE
        cursor_style = self.cursor_style if self.cursor_style is not None else theme.cursor
        out: list[Line] = []
        for offset, row in enumerate(shown):
            index = start + offset
            if placeholder_mode:  # empty + focused: the first row is unique
                body = self._placeholder_body(width, theme.dim, cursor_style)
            elif self.focused and index == cursor_index:
                body = self._cursor_body(row.text, cursor_column, width, style, cursor_style)
            else:
                body = [Segment(row.text, style)] if row.text else []
            out.append(Line(body).fit(width))
        return out

    def _placeholder_body(
        self, width: int, dim: Style, cursor_style: Style
    ) -> list[Segment]:
        # The cursor trails the hint as the same full-cell block a typed row
        # ends in, so the empty and typed states share one cursor shape.
        text = self.placeholder
        segments = [Segment(text, dim)] if text else []
        if visible_width(text) + 1 <= width:
            segments.append(Segment(" ", dim.merge(cursor_style)))
        return segments

    def _cursor_body(
        self, text: str, column: int, width: int, style: Style, cursor_style: Style
    ) -> list[Segment]:
        if column < len(text):
            segments = [Segment(text[:column], style)] if column else []
            segments.append(Segment(text[column], style.merge(cursor_style)))
            if column + 1 < len(text):
                segments.append(Segment(text[column + 1 :], style))
            return segments
        # Row end: append a reverse-video space unless the row is already full.
        segments = [Segment(text, style)] if text else []
        if visible_width(text) + 1 <= width:
            segments.append(Segment(" ", style.merge(cursor_style)))
        return segments

    def __repr__(self) -> str:
        return f"Editor({self.value!r}, cursor=({self._row}, {self._col}))"
