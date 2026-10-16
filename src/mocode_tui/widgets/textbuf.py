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

**History.**  Every write point (``insert``, ``backspace``, ``delete``,
``newline``, ``clear``) snapshots ``(lines, row, col)`` **before** it
mutates and pushes the snapshot onto a bounded undo stack
(:data:`UNDO_LIMIT` steps); a new change drops the redo stack, so redo
never re-applies a change an edit has moved past.  Runs of single-character
inserts -- the keystrokes of one typed word, with no other operation or
move between them -- collapse into **one** undo step: a plain move, every
other write point and a multi-character ``insert`` (a paste) all break the
run.  Moves themselves record nothing: the cursor is not content.

**Selection.**  A text-internal selection is one flat-offset anchor:
:meth:`TextBuffer.select_all` parks the anchor at 0 and the cursor at the
text end, and the ``select_*`` methods extend the selection from the
anchor to wherever the matching ``move_*`` would land, so the shift chords
share the moves' own column and wrap semantics.  Every **plain** move
(:meth:`TextBuffer.move_left` .. :meth:`TextBuffer.place`), and every
write point, drops the selection first: :meth:`TextBuffer.insert` /
``backspace`` / ``delete`` / ``newline`` delete the selected range and
land their change where it was, and a plain move simply clears the anchor.
:attr:`TextBuffer.selected_text` reads the range out,
:meth:`TextBuffer.selection_range` resolves it as a normalized
``(start, stop)`` flat pair and :meth:`TextBuffer.clear_selection` drops
it.  The shell renders the range as a band; the buffer never styles.
"""

from __future__ import annotations

from collections import deque
from typing import NamedTuple

from ..core.events import Key, Paste
from ..core.lines import Segment
from ..core.style import Style
from ..core.text import index_bounds_at_columns, visible_width, wrap_spans
from ..keys.keymap import Keymap

__all__ = ["UNDO_LIMIT", "TextBuffer"]

#: Width the visual geometry uses before the first ``render(width)`` seeds
#: it (matches the kernel's terminal fallback).
DEFAULT_WIDTH = 80

#: How many undo steps one buffer keeps (the oldest fall off the stack).
UNDO_LIMIT = 100


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

    The undo/redo stacks are the buffer's own (see the module docstring):
    :data:`UNDO_LIMIT` steps deep, one snapshot per write point, runs of
    single-character inserts merged into one step.  The stacks are private
    state -- the host drives them through :meth:`undo`/:meth:`redo`, which
    the default keymaps bind to ``c-z``/``c-y``.
    """

    __slots__ = (
        "_anchor",
        "_chain",
        "_col",
        "_redo",
        "_row",
        "_undo",
        "indent",
        "keymap",
        "last_width",
        "lines",
    )

    def __init__(self, text: str = "", *, keymap: Keymap, indent: int = 0) -> None:
        self.lines = text.split("\n")
        self.keymap = keymap
        self.indent = indent
        self._row = 0
        self._col = 0
        self.last_width = DEFAULT_WIDTH
        # The selection anchor: the flat offset a shift-move extends from,
        # or ``None`` for "no selection".  Cleared by every plain move and
        # by every write point (which deletes the range first).
        self._anchor: int | None = None
        # The bounded history: snapshots of ``(lines, row, col)`` taken
        # before each write point, and the redo tail a new change drops.
        self._undo: deque[tuple[list[str], int, int]] = deque(maxlen=UNDO_LIMIT)
        self._redo: deque[tuple[list[str], int, int]] = deque(maxlen=UNDO_LIMIT)
        # True while the last recorded change was a single-character insert
        # and nothing happened since: the next one merges into its step.
        self._chain = False

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

    # -- selection ------------------------------------------------------------

    @property
    def anchor(self) -> int | None:
        """The selection's anchor as a flat offset (``None``: no selection).

        The origin a shift-move extends from; the live end is always the
        cursor.  A selection whose cursor sits back on the anchor counts as
        empty (:meth:`selection_range` answers ``None``) even though the
        anchor is still parked.
        """
        return self._anchor

    @property
    def selected_text(self) -> str:
        """The selected text (``""`` when there is no selection)."""
        span = self.selection_range()
        return "" if span is None else self.value[span[0] : span[1]]

    def selection_range(self) -> tuple[int, int] | None:
        """The selection as a normalized ``(start, stop)`` flat pair, or ``None``.

        The pair is independent of the direction the selection was drawn
        in: ``start`` is the smaller offset, ``stop`` the larger (right-open
        -- a caret selection of one character is ``(i, i + 1)``).  An empty
        selection -- no anchor, or the cursor back on it -- answers
        ``None``, so a host can branch on one truth.
        """
        if self._anchor is None:
            return None
        cursor = self._cursor_offset()
        if cursor == self._anchor:
            return None
        return (min(self._anchor, cursor), max(self._anchor, cursor))

    def clear_selection(self) -> None:
        """Drop the selection; the cursor stays where it is."""
        self._anchor = None

    def select_all(self) -> bool:
        """Select the whole buffer; ``False`` for an empty one.

        Parks the anchor at the first character and the cursor at the text
        end, so the following plain moves collapse the selection from
        either side.  ``c-a`` routes here (the key was the plain ``home``
        before the selection layer arrived; ``home`` itself is untouched).
        """
        length = self._text_length()
        self._chain = False
        if length == 0:
            self._anchor = None
            return False
        self._anchor = 0
        self._set_offset(length)
        return True

    def select_left(self) -> bool:
        """Extend the selection one character left (or from the cursor)."""
        return self._extend(self._move_left_cursor)

    def select_right(self) -> bool:
        """Extend the selection one character right (or from the cursor)."""
        return self._extend(self._move_right_cursor)

    def select_home(self) -> bool:
        """Extend the selection to the start of the cursor's logical line."""
        return self._extend(self._home_cursor)

    def select_end(self) -> bool:
        """Extend the selection to the end of the cursor's logical line."""
        return self._extend(self._end_cursor)

    def select_up(self) -> bool:
        """Extend the selection one visual row up, keeping the inner column."""
        return self._extend(self._move_up_cursor)

    def select_down(self) -> bool:
        """Extend the selection one visual row down, keeping the inner column."""
        return self._extend(self._move_down_cursor)

    def _extend(self, mover) -> bool:
        """Run ``mover`` as a selection extension; ``True`` when the cursor moved.

        With no anchor the mover runs first and its starting offset becomes
        the anchor (a shift-move that moves nowhere answers ``False`` and
        selects nothing); with an anchor the mover just walks the live end.
        A select move is a move: it breaks any insert merge run.
        """
        self._chain = False
        if self._anchor is None:
            before = self._cursor_offset()
            if not mover():
                return False
            self._anchor = before
            return True
        return mover()

    def _delete_selection(self) -> bool:
        """Delete the selected range, park the cursor at its start; ``False`` when none.

        The one splice every write point runs before landing: the range is
        removed across logical lines (a selection spanning a ``"\\n"``
        merges its edge lines) and the anchor is dropped.  Pure state
        change; the caller records its history step first.
        """
        span = self.selection_range()
        if span is None:
            return False
        start, stop = span
        start_row, start_col = self._split_offset(start)
        stop_row, stop_col = self._split_offset(stop)
        if start_row == stop_row:
            line = self.lines[start_row]
            self.lines[start_row] = line[:start_col] + line[stop_col:]
        else:
            self.lines[start_row] = (
                self.lines[start_row][:start_col] + self.lines[stop_row][stop_col:]
            )
            del self.lines[start_row + 1 : stop_row + 1]
        self._anchor = None
        self._set_offset(start)
        return True

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
        """Insert ``text`` (may contain newlines) at the cursor.

        A selection is replaced: the selected range is deleted first and
        the text lands where it started, in the same history step (one
        ``c-z`` restores both the un-inserted text and the deleted range).
        A run of single-character inserts merge into one undo step: each
        merged insert keeps the step's one pre-run snapshot, so ``c-z``
        after a typed word takes the whole word back.  A multi-character
        ``insert`` (a paste, ``"\\n"`` included) is a step of its own and
        ends any run -- and so does an insert that replaced a selection.
        """
        if not text:
            return
        replacing = self.selection_range() is not None
        single = len(text) == 1 and not replacing
        if not (single and self._chain):
            self._record()
        self._chain = single
        self._delete_selection()
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

        A selection is deleted first (the whole range, in one step, the
        cursor parked where it started).  At a line start the line is
        merged into the previous one and the cursor parks at the junction;
        ``False`` at the very start (and then nothing is recorded: a
        deleted nothing is not a step).
        """
        if self.selection_range() is not None:
            self._record()
            self._chain = False
            self._delete_selection()
            return True
        if self._col > 0:
            self._record()
            self._chain = False
            line = self.lines[self._row]
            self.lines[self._row] = line[: self._col - 1] + line[self._col :]
            self._col -= 1
            return True
        if self._row == 0:
            return False
        self._record()
        self._chain = False
        head = self.lines[self._row - 1]
        self.lines[self._row - 1] = head + self.lines[self._row]
        del self.lines[self._row]
        self._row -= 1
        self._col = len(head)
        return True

    def delete(self) -> bool:
        """Delete the character at the cursor.

        A selection is deleted first (the whole range, in one step, the
        cursor parked where it started).  At a line end the next line is
        merged up; ``False`` at the very end (and then nothing is recorded:
        a deleted nothing is not a step).
        """
        if self.selection_range() is not None:
            self._record()
            self._chain = False
            self._delete_selection()
            return True
        line = self.lines[self._row]
        if self._col < len(line):
            self._record()
            self._chain = False
            self.lines[self._row] = line[: self._col] + line[self._col + 1 :]
            return True
        if self._row + 1 >= len(self.lines):
            return False
        self._record()
        self._chain = False
        self.lines[self._row] = line + self.lines[self._row + 1]
        del self.lines[self._row + 1]
        return True

    def newline(self) -> bool:
        """Break the cursor's line at the cursor; the cursor moves to the
        new line's start.  Always succeeds (``True``), and always records a step.

        A selection is deleted first, in the same step: the break lands
        where the deleted range started.
        """
        self._record()
        self._chain = False
        self._delete_selection()
        line = self.lines[self._row]
        self.lines[self._row : self._row + 1] = [line[: self._col], line[self._col :]]
        self._row += 1
        self._col = 0
        return True

    def clear(self) -> None:
        """Drop the whole buffer and park the cursor at the start.

        A clear that changes something records a step; clearing the empty
        buffer is a no-op and records nothing.  Either way the selection is
        gone: there is nothing left to select.
        """
        self._anchor = None
        if self.lines == [""] and self._row == 0 and self._col == 0:
            return
        self._record()
        self._chain = False
        self.lines = [""]
        self._row = 0
        self._col = 0

    # -- history ----------------------------------------------------------------

    def _record(self) -> None:
        """Snapshot the state before a write point; drop the redo tail.

        The one bookkeeping call every write point runs first: the
        ``(lines, row, col)`` snapshot is copied onto the undo stack (the
        oldest step falls off past :data:`UNDO_LIMIT`), and the redo stack
        is cleared -- a new change has moved past every redone future.
        """
        self._undo.append((list(self.lines), self._row, self._col))
        self._redo.clear()

    def _restore(self, snapshot: tuple[list[str], int, int]) -> None:
        """Put a recorded ``(lines, row, col)`` snapshot back in place."""
        lines, row, col = snapshot
        self.lines = list(lines)
        self._row, self._col = row, col

    def undo(self) -> bool:
        """Restore the state before the last recorded step; ``False`` when empty.

        The current state is pushed onto the redo stack first, so
        :meth:`redo` walks the very history back.  The undo run is broken:
        typing after an undo starts a fresh merge chain.
        """
        if not self._undo:
            return False
        self._redo.append((list(self.lines), self._row, self._col))
        self._restore(self._undo.pop())
        self._chain = False
        return True

    def redo(self) -> bool:
        """Re-apply the last undone step; ``False`` when there is none.

        The current state goes back onto the undo stack, so undo/redo
        round-trips freely until a new write point drops the redo tail.
        """
        if not self._redo:
            return False
        self._undo.append((list(self.lines), self._row, self._col))
        self._restore(self._redo.pop())
        self._chain = False
        return True

    def move_left(self) -> bool:
        """Move one character left; drops any selection (a plain move)."""
        self._drop_selection()
        return self._move_left_cursor()

    def _move_left_cursor(self) -> bool:
        """The bare leftward walk, without the plain-move bookkeeping."""
        if self._col > 0:
            self._col -= 1
            return True
        if self._row == 0:
            return False
        self._row -= 1
        self._col = len(self.lines[self._row])
        return True

    def move_right(self) -> bool:
        """Move one character right; drops any selection (a plain move)."""
        self._drop_selection()
        return self._move_right_cursor()

    def _move_right_cursor(self) -> bool:
        """The bare rightward walk, without the plain-move bookkeeping."""
        if self._col < len(self.lines[self._row]):
            self._col += 1
            return True
        if self._row + 1 >= len(self.lines):
            return False
        self._row += 1
        self._col = 0
        return True

    def home(self) -> bool:
        """Move to the start of the cursor's logical line; drops any selection."""
        self._drop_selection()
        return self._home_cursor()

    def _home_cursor(self) -> bool:
        """The bare walk to the logical line's start."""
        moved = self._col != 0
        self._col = 0
        return moved

    def end(self) -> bool:
        """Move to the end of the cursor's logical line (before its "\\n");
        drops any selection."""
        self._drop_selection()
        return self._end_cursor()

    def _end_cursor(self) -> bool:
        """The bare walk to the logical line's end."""
        target = len(self.lines[self._row])
        moved = self._col != target
        self._col = target
        return moved

    def move_up(self) -> bool:
        """Move to the previous visual row, keeping the inner column.

        The rows are the ones :attr:`last_width` and :attr:`indent` describe
        -- exactly the geometry the shell's render wraps against.  A plain
        move: it drops any selection.
        """
        self._drop_selection()
        return self._move_up_cursor()

    def _move_up_cursor(self) -> bool:
        """The bare walk one visual row up."""
        rows = self.visual_rows(self.last_width, self.indent)
        index, column = self.locate(rows)
        if index == 0:
            return False
        target = rows[index - 1]
        return self._set_offset(target.start + min(column, target.end - target.start))

    def move_down(self) -> bool:
        """Move to the next visual row, keeping the inner column.

        The rows are the ones :attr:`last_width` and :attr:`indent` describe
        -- exactly the geometry the shell's render wraps against.  A plain
        move: it drops any selection.
        """
        self._drop_selection()
        return self._move_down_cursor()

    def _move_down_cursor(self) -> bool:
        """The bare walk one visual row down."""
        rows = self.visual_rows(self.last_width, self.indent)
        index, column = self.locate(rows)
        if index + 1 >= len(rows):
            return False
        target = rows[index + 1]
        return self._set_offset(target.start + min(column, target.end - target.start))

    def _drop_selection(self) -> None:
        """The plain-move bookkeeping: no selection, no open merge run."""
        self._anchor = None
        self._chain = False

    # -- flat offsets ----------------------------------------------------------

    def _text_length(self) -> int:
        return sum(len(line) + 1 for line in self.lines) - 1

    def _cursor_offset(self) -> int:
        return sum(len(line) + 1 for line in self.lines[: self._row]) + self._col

    def _set_offset(self, offset: int) -> bool:
        """Move the cursor to the flat ``offset`` (clamped); True when moved."""
        offset = max(0, min(offset, self._text_length()))
        moved = offset != self._cursor_offset()
        self._row, self._col = self._split_offset(offset)
        return moved

    def _split_offset(self, offset: int) -> tuple[int, int]:
        """The ``(row, col)`` a flat ``offset`` names (clamped to the text)."""
        offset = max(0, min(offset, self._text_length()))
        remaining = offset
        for row, line in enumerate(self.lines):
            if remaining <= len(line):
                return row, remaining
            remaining -= len(line) + 1
        last = len(self.lines) - 1  # unreachable with a clamped offset
        return last, len(self.lines[last])

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

    def place(self, visual_row: int, col: int) -> bool:
        """Dock the cursor at the rendered cell ``(visual_row, col)``; True on a hit.

        The inverse of :meth:`cursor_position`, and this engine's one
        cell-to-offset mapping.  ``visual_row`` counts *visual* rows -- the
        wrapped segments of :meth:`visual_rows` at :attr:`last_width`, the
        very rows a shell renders -- and ``col`` is a 0-based display column
        of that row with :attr:`indent` already included (the prompt's width
        for an ``Input``, 0 for an ``Editor``).  A row outside the rows
        answers ``False`` and changes nothing; a hit docks the cursor and
        answers ``True`` even when the cursor already sat there (a click is
        a hit whether or not it moved anything), the same ``bool`` every
        ``move_*`` answers.

        The column mapping goes by display width: a cell inside a wide
        cluster -- the second half of ``"中"`` or of an emoji -- folds onto
        that cluster's first character, a cell at or past the row's last
        cell lands on the row's end (:attr:`_VisualRow.end`), and a cell at
        or left of the ``indent`` columns -- a click on the prompt, on the
        indent of a wrapped row, on an empty row -- lands on the row's first
        character.  The cluster rules are not restated here: the
        cell-to-character step is
        :func:`~mocode_tui.core.text.index_bounds_at_columns`, the kernel's
        one boundary resolver, whose floor rule (a boundary inside a cluster
        resolves down to the cluster's start) is exactly this mapping.  The
        flat offset that comes back is then handed to :meth:`_set_offset`,
        the one offset-to-``(row, col)`` walk, so the landing position is a
        *logical* one and a visual row index is never mistaken for a line
        index.  Pure state change on a hit: no rendering.
        """
        rows = self.visual_rows(self.last_width, self.indent)
        if not 0 <= visual_row < len(rows):
            return False
        self._drop_selection()  # a click's docking drops the selection and any run
        row = rows[visual_row]
        offset = row.start + index_bounds_at_columns(row.text, col - self.indent)[0]
        self._set_offset(offset)
        return True

    # -- row bodies ------------------------------------------------------------

    def selected_local(
        self, row: _VisualRow, selection: tuple[int, int] | None
    ) -> tuple[int, int] | None:
        """The selected character range of one visual row, or ``None``.

        ``selection`` is a flat ``(start, stop)`` pair in the same offset
        space as :meth:`selection_range`; the answer is the range's
        intersection with the row, as character indices into ``row.text``
        (right-open, ``None`` when they do not meet).  A selection that
        reaches **past** the row's text -- across the ``"\\n"`` at a
        logical line's end, or into the next wrapped segment -- extends to
        the row's last character: highlighting stops at the break, but the
        break itself is inside the band.
        """
        if selection is None:
            return None
        start, stop = selection
        length = len(row.text)
        lo = min(max(start - row.start, 0), length)
        hi = length if stop >= row.end else min(max(stop - row.start, 0), length)
        if lo >= hi:
            return None
        return (lo, hi)

    def row_body(
        self,
        text: str,
        column: int,
        inner: int,
        style: Style,
        cursor_style: Style,
        *,
        selection: tuple[int, int] | None = None,
        selection_style: Style | None = None,
        show_cursor: bool = True,
        cursor_marked: bool = False,
    ) -> list[Segment]:
        """One rendered row's body: the base run, the cursor, the selection.

        The buffer's one styling site, so span arithmetic lives in exactly
        one place: ``text`` is the visual row's text (tab-normalized),
        ``column`` the cursor's character index in it, and the band rules
        stack in a fixed order -- the base style, then the block cursor
        (``style.merge(cursor_style)`` over the character under the cursor,
        or a reverse-video space at a row end -- skipped when the row
        already fills ``inner`` columns, so no row ever exceeds its width),
        then the selection (``merge(selection_style)`` over the selected
        characters, and over the row-end cursor's space when
        ``cursor_marked``): a cell inside both renders the **selection**
        band -- the selection outranks the cursor -- with the cursor still
        there underneath.  ``selection`` is the row-local range from
        :meth:`selected_local`; ``show_cursor`` False draws no cursor cell
        (an unfocused field, a row that is not the cursor's), and both
        arguments default to "plain row": with no selection and no cursor
        the answer is the one base-styled run, byte-for-byte what the
        shell always rendered.
        """
        length = len(text)
        lo, hi = selection if selection is not None else (0, 0)
        band = selection_style if selection_style is not None else Style()
        bounds = {0, length}
        if lo < hi:
            bounds.update((lo, hi))
        if show_cursor and column < length:
            bounds.update((column, column + 1))
        ordered = sorted(bound for bound in bounds if 0 <= bound <= length)
        segments: list[Segment] = []
        for start, end in zip(ordered, ordered[1:]):
            if start == end:
                continue
            cell_style = style
            if show_cursor and start <= column < end:
                cell_style = cell_style.merge(cursor_style)
            if lo < hi and lo <= start < hi:
                cell_style = cell_style.merge(band)
            segments.append(Segment(text[start:end], cell_style))
        if show_cursor and column >= length:
            # Row end: append a reverse-video space unless the row is already full.
            end_style = style.merge(cursor_style)
            if cursor_marked:
                end_style = end_style.merge(band)
            if visible_width(text) + 1 <= inner:
                segments.append(Segment(" ", end_style))
        return segments
