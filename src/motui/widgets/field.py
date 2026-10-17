"""The text field: the editing shell shared by :class:`Input` and :class:`Editor`.

Both public fields are one component twice: each owns a
:class:`~motui.widgets.textbuf.TextBuffer`, routes events through it,
forwards its editing methods, reports the cursor and the block cursor's
cell, docks the cursor on a click and renders wrapped rows.  This private
module carries that shared half -- the buffer composition,
:meth:`_TextField.handle`, the eleven forwarded editing methods,
:meth:`_TextField.cursor_position`, :meth:`_TextField.click` and the
render trunk (prefix / placeholder / cursor branches).  The shells differ
only in row policy:

* :class:`~motui.widgets.input.Input` leads every row with a prompt
  and wraps at ``width - visible_width(prompt)``;
* :class:`~motui.widgets.editor.Editor` spans the full width and slides
  an optional ``max_rows`` window around the cursor.

An empty focused field with a placeholder renders the hint in the theme's
``dim`` and **no cursor cell**: the hint is a label for the empty state, not
content, and a block painted over or after it reads as an artifact.  The
cursor block appears with the first typed character; an empty field *without*
a placeholder shows the block alone, exactly as a typed row does.

Hosts import the two shells, never this class.
"""

from __future__ import annotations

from ..kernel.events import Key, Paste
from ..kernel.lines import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme, Themed
from ..keys.keymap import Keymap
from .textbuf import TextBuffer, _VisualRow


class _TextField(Themed):
    """The shared editing shell: buffer, routing, geometry, render trunk.

    A shell supplies the keymap, the resolved styles and four policy hooks:
    the row indent (:meth:`_indent`), the row window
    (:meth:`_window_start`, :meth:`_row_cap`) and the row prefix
    (:meth:`_row_prefix`).  Everything else -- the text, the cursor,
    ``handle``, the editing methods, ``click`` and ``render`` -- is one
    implementation here.

    ``focused`` is the flag the focus tier writes
    (:class:`~motui.interaction.focus.FocusRing`, through
    :class:`~motui.kernel.block.Focusable`) -- the same flag a shell
    takes at construction; the shell only renders by it (the block cursor
    and the empty-field hint).  ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.block.Hoverable`): the fields take the
    **block-level** hover only -- the whole rendered row (prompt included)
    merges the theme's ``hover`` while it is ``True`` -- and implement no
    ``hover_at``: a text row has no sub-row items to mark.

    The selection is rendered here too: the shell asks the buffer for the
    selected character range of each visual row and hands it to the
    buffer's one row-body builder, which merges ``selection_style`` (the
    theme's ``selection``) over it -- the block cursor included, with the
    selection band on top ("selection outranks the cursor") and the cursor
    still there underneath.  The prompt is never selected: the band starts
    at the text.
    """

    __slots__ = (
        "_buf",
        "_cursor_style",
        "_dim",
        "_hover_style",
        "_selection_style",
        "_style",
        "focused",
        "hover",
        "placeholder",
        "theme",
    )

    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str = "",
        style: Style | None = None,
        cursor_style: Style | None = None,
        theme: Theme | None = None,
        keymap: Keymap,
        focused: bool = True,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.placeholder = placeholder
        self.focused = focused
        #: The pointer tier's flag; it only changes how the rows render.
        self.hover = False
        self._buf = TextBuffer(text, keymap=keymap)
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._style = style if style is not None else NONE
        self._cursor_style = self._pick(cursor_style, "cursor")
        self._dim = self._pick(None, "dim")
        self._hover_style = self._pick(None, "hover")
        self._selection_style = self._pick(None, "selection")

    # -- buffer views -----------------------------------------------------------

    @property
    def keymap(self) -> Keymap:
        """The table :meth:`handle` routes through."""
        return self._buf.keymap

    @keymap.setter
    def keymap(self, value: Keymap) -> None:
        self._buf.keymap = value

    @property
    def text(self) -> str:
        """The whole field text (a multi-line paste keeps its newlines)."""
        return self._buf.value

    @property
    def cursor(self) -> tuple[int, int]:
        """The cursor as ``(row, col)``."""
        return self._buf.row, self._buf.col

    @property
    def anchor(self) -> int | None:
        """The selection's anchor as a flat offset (``None``: no selection)."""
        return self._buf.anchor

    @property
    def selected_text(self) -> str:
        """The selected text (``""`` when there is no selection)."""
        return self._buf.selected_text

    def selection_range(self) -> tuple[int, int] | None:
        """The selection as a normalized ``(start, stop)`` flat pair, or ``None``."""
        return self._buf.selection_range()

    def clear_selection(self) -> None:
        """Drop the selection; the cursor stays where it is."""
        self._buf.clear_selection()

    def select_all(self) -> bool:
        """Select the whole buffer; ``False`` for an empty one."""
        return self._buf.select_all()

    # -- editing --------------------------------------------------------------

    def handle(self, event: Key | Paste) -> bool:
        """Consume an event via the buffer; see :meth:`TextBuffer.handle`.

        The buffer's :attr:`~TextBuffer.indent` is the field's row indent,
        kept in step by a shell that renders a prompt, so this shell only
        delegates.  ``False`` for an event the buffer does not consume
        leaves the host free to route it -- the editor's default table
        binds ``enter``, the input's does not, and a submit gesture is one
        such event: no library keymap binds one.
        """
        return self._buf.handle(event)

    def insert(self, text: str) -> None:
        """Insert ``text`` (may contain newlines) at the cursor."""
        self._buf.insert(text)

    def backspace(self) -> bool:
        """Delete the character before the cursor; at a line start the line
        is merged into the one above.  ``False`` at the very start."""
        return self._buf.backspace()

    def delete(self) -> bool:
        """Delete the character at the cursor; at a line end the next line
        is merged up.  ``False`` at the very end."""
        return self._buf.delete()

    def newline(self) -> bool:
        """Break the cursor's line at the cursor; the cursor moves to the
        new line's start.  Always succeeds (``True``)."""
        return self._buf.newline()

    def clear(self) -> None:
        """Drop the whole buffer and park the cursor at the start."""
        self._buf.clear()

    def undo(self) -> bool:
        """Restore the state before the last recorded write point; ``False`` when empty."""
        return self._buf.undo()

    def redo(self) -> bool:
        """Re-apply the last undone write point; ``False`` when there is none."""
        return self._buf.redo()

    def move_left(self) -> bool:
        return self._buf.move_left()

    def move_right(self) -> bool:
        return self._buf.move_right()

    def home(self) -> bool:
        """Move to the start of the cursor's logical line."""
        return self._buf.home()

    def end(self) -> bool:
        """Move to the end of the cursor's logical line (before its "\\n")."""
        return self._buf.end()

    def move_up(self) -> bool:
        """Move to the previous visual row, keeping the inner column."""
        return self._buf.move_up()

    def move_down(self) -> bool:
        """Move to the next visual row, keeping the inner column."""
        return self._buf.move_down()

    def select_left(self) -> bool:
        """Extend the selection one character left (or from the cursor)."""
        return self._buf.select_left()

    def select_right(self) -> bool:
        """Extend the selection one character right (or from the cursor)."""
        return self._buf.select_right()

    def select_home(self) -> bool:
        """Extend the selection to the start of the cursor's logical line."""
        return self._buf.select_home()

    def select_end(self) -> bool:
        """Extend the selection to the end of the cursor's logical line."""
        return self._buf.select_end()

    def select_up(self) -> bool:
        """Extend the selection one visual row up, keeping the inner column."""
        return self._buf.select_up()

    def select_down(self) -> bool:
        """Extend the selection one visual row down, keeping the inner column."""
        return self._buf.select_down()

    def click(self, row: int, col: int) -> bool:
        """Dock the block cursor at this field's own rendered cell; True on a hit.

        ``row``/``col`` are a 0-based cell of the component's own
        ``render`` output -- exactly what
        :meth:`~motui.app.TUI.hit_test` reports -- so the shell first
        undoes its own row policy and then lets the buffer resolve the
        column.  An :class:`~motui.widgets.editor.Editor` adds the
        ``max_rows`` window's first rendered row back onto ``row`` (the
        same window :meth:`render` slices by, read off the current cursor,
        via :meth:`_window`), so "the third row on screen" is the third row
        of the window whatever the buffer's length; an
        :class:`~motui.widgets.input.Input` hands ``col`` straight
        through, the prompt's width already being the buffer's indent, so a
        click on the prompt or on a wrapped row's indent folds onto that
        row's first character.  A row outside the rendered rows answers
        ``False`` and changes nothing; a hit docks the cursor -- even when
        it already sat there -- and answers ``True``.  ``focused`` is
        deliberately not consulted: moving the focus on a click is the
        host's (or a :class:`~motui.interaction.focus.FocusRing`'s) policy, never
        the field's.  A multi-row residue (an explicit :meth:`insert` of
        ``"\\n"`` into an ``Input``) is accepted row by row like any other
        buffer.
        """
        rows = self._buf.visual_rows(self._buf.last_width, self._indent())
        start, count = self._window(rows, self._buf.locate(rows)[0])
        if not 0 <= row < count:
            return False
        return self._buf.place(start + row, col)

    # -- visual geometry -------------------------------------------------------

    def _indent(self) -> int:
        """The columns every visual row is inset by (0 without a prompt)."""
        return 0

    def _window_start(self, total: int, cursor_index: int) -> int:
        """The first rendered row (0 without a ``max_rows`` window)."""
        return 0

    def _row_cap(self) -> int | None:
        """The rendered-row cap (``None`` renders every row)."""
        return None

    def _window(self, rows: list[_VisualRow], cursor_index: int) -> tuple[int, int]:
        """The rendered window as ``(start, count)`` -- the shell's row policy.

        ``start`` is the first rendered row that keeps the cursor's visual
        row (:meth:`_window_start`) and ``count`` how many rows are shown
        from there (:meth:`_row_cap`, clamped to the rows that remain).
        :meth:`render` slices by it, :meth:`cursor_position` shifts the
        cursor's row by ``start`` and :meth:`click` rejects a row outside
        it: one expression of the window, so the three cannot disagree.
        """
        start = self._window_start(len(rows), cursor_index)
        cap = self._row_cap()
        count = len(rows) - start if cap is None else min(max(cap, 0), len(rows) - start)
        return start, count

    def cursor_position(self, width: int) -> tuple[int, int]:
        """The cursor cell as ``(visual_row, col)`` of a ``render(width)``.

        The geometry is the one ``render`` uses, so the reported cell is
        exactly the cell the render paints as the block cursor: the
        character under the cursor, or the reverse-video space at a row
        end.  ``col`` is the 0-based cell offset from the row's left edge
        -- row 0 counts a shell's prompt, continuation rows indent by it.
        A ``max_rows`` window is applied, so ``visual_row`` indexes the
        rows ``render`` actually returns.  Pure query: no state changes,
        no rendering.
        """
        indent = self._indent()
        rows = self._buf.visual_rows(width, indent)
        start, _count = self._window(rows, self._buf.locate(rows)[0])
        return self._buf.cursor_position(width, indent, start)

    # -- rendering ---------------------------------------------------------------

    def _row_prefix(self, index: int, indent: int) -> Segment | None:
        """The row's leading segment, or ``None`` when the shell has none."""
        return None

    def render(self, width: int) -> list[Line]:
        indent = self._indent()
        self._buf.last_width = width
        rows = self._buf.visual_rows(width, indent)
        cursor_index, cursor_column = self._buf.locate(rows)
        start, count = self._window(rows, cursor_index)
        shown = rows[start : start + count]
        inner = max(0, width - indent)
        selection = self._buf.selection_range()
        # Empty + focused + a hint is the field's label state: the hint
        # renders as text, with no cursor cell to ride it.
        placeholder = self.placeholder if self._buf.empty and self.focused else ""
        out: list[Line] = []
        for offset, row in enumerate(shown):
            index = start + offset
            prefix = self._row_prefix(index, indent)
            if placeholder:
                body = [Segment(placeholder, self._dim)]
            else:
                cursor_here = self.focused and index == cursor_index
                marked = (
                    cursor_here
                    and selection is not None
                    and selection[0] <= self._buf.offset < selection[1]
                )
                body = self._buf.row_body(
                    row.text,
                    cursor_column,
                    inner,
                    self._style,
                    self._cursor_style,
                    selection=self._buf.selected_local(row, selection),
                    selection_style=self._selection_style,
                    show_cursor=cursor_here,
                    cursor_marked=marked,
                )
            line = Line((prefix, *body)) if prefix is not None else Line(body)
            if self.hover:
                # The block-level hover: the whole row -- prompt and cursor
                # cell included -- takes the theme's hover band on top of
                # whatever each segment carries.
                line = Line(
                    seg.with_style(seg.style.merge(self._hover_style))
                    for seg in line.segments
                )
            out.append(line.fit(width))
        return out

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.text!r}, cursor={self.cursor})"
