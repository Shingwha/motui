"""The text field: the editing shell shared by :class:`Input` and :class:`Editor`.

Both public fields are one component twice: each owns a
:class:`~mocode_tui.widgets.textbuf.TextBuffer`, routes events through it,
forwards its editing methods, reports the cursor and the block cursor's
cell, and renders wrapped rows.  This private module carries that shared
half -- the buffer composition, :meth:`_TextField.handle`, the eleven
forwarded editing methods, :meth:`_TextField.cursor_position` and the
render trunk (prefix / placeholder / cursor branches).  The shells differ
only in row policy:

* :class:`~mocode_tui.widgets.input.Input` leads every row with a prompt
  and wraps at ``width - visible_width(prompt)``;
* :class:`~mocode_tui.widgets.editor.Editor` spans the full width and slides
  an optional ``max_rows`` window around the cursor.

An empty focused field with a placeholder renders the hint in the theme's
``dim`` and **no cursor cell**: the hint is a label for the empty state, not
content, and a block painted over or after it reads as an artifact.  The
cursor block appears with the first typed character; an empty field *without*
a placeholder shows the block alone, exactly as a typed row does.

Hosts import the two shells, never this class.
"""

from __future__ import annotations

from ..core.events import Key, Paste
from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import Theme, Themed
from ..keys.keymap import Keymap
from .textbuf import TextBuffer


class _TextField(Themed):
    """The shared editing shell: buffer, routing, geometry, render trunk.

    A shell supplies the keymap, the resolved styles and four policy hooks:
    the row indent (:meth:`_indent`), the row window
    (:meth:`_window_start`, :meth:`_row_cap`) and the row prefix
    (:meth:`_row_prefix`).  Everything else -- the text, the cursor,
    ``handle``, the editing methods and ``render`` -- is one implementation
    here.

    ``focused`` is the flag the focus tier writes
    (:class:`~mocode_tui.focus.FocusRing`, through
    :class:`~mocode_tui.core.block.Focusable`) -- the same flag a shell
    takes at construction; the shell only renders by it (the block cursor
    and the empty-field hint).
    """

    __slots__ = (
        "_buf",
        "_cursor_style",
        "_dim",
        "_style",
        "focused",
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
        self._buf = TextBuffer(text, keymap=keymap)
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._style = style if style is not None else NONE
        self._cursor_style = self._pick(cursor_style, "cursor")
        self._dim = self._pick(None, "dim")

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
        index, _column = self._buf.locate(rows)
        return self._buf.cursor_position(
            width, indent, self._window_start(len(rows), index)
        )

    # -- rendering ---------------------------------------------------------------

    def _row_prefix(self, index: int, indent: int) -> Segment | None:
        """The row's leading segment, or ``None`` when the shell has none."""
        return None

    def render(self, width: int) -> list[Line]:
        indent = self._indent()
        self._buf.last_width = width
        rows = self._buf.visual_rows(width, indent)
        cursor_index, cursor_column = self._buf.locate(rows)
        start = self._window_start(len(rows), cursor_index)
        cap = self._row_cap()
        shown = rows if cap is None else rows[start : start + max(cap, 0)]
        inner = max(0, width - indent)
        # Empty + focused + a hint is the field's label state: the hint
        # renders as text, with no cursor cell to ride it.
        placeholder = self.placeholder if self._buf.empty and self.focused else ""
        out: list[Line] = []
        for offset, row in enumerate(shown):
            index = start + offset
            prefix = self._row_prefix(index, indent)
            if placeholder:
                body = [Segment(placeholder, self._dim)]
            elif self.focused and index == cursor_index:
                body = self._buf.cursor_body(
                    row.text, cursor_column, inner, self._style, self._cursor_style
                )
            else:
                body = [Segment(row.text, self._style)] if row.text else []
            line = Line((prefix, *body)) if prefix is not None else Line(body)
            out.append(line.fit(width))
        return out

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.text!r}, cursor={self.cursor})"
