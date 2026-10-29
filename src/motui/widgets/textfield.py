"""The text fields, :class:`Input` and :class:`Editor`, over one editing shell.

Editing state lives in :class:`~motui.widgets.textbuf.TextBuffer`; the shell
routes typed events through the field's keymap and renders the buffer rows.
"""

from __future__ import annotations

import re

from ..kernel.cell import Line, Segment, Surface
from ..kernel.events import Event, KeyEvent, MouseEvent, PasteEvent
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, seat
from ..kernel.keymap import (
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    Keymap,
)
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import (
    WrapMode,
    index_bounds_at_columns,
    index_pair_at_columns,
    visible_width,
)
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget
from .textbuf import TextBuffer, _VisualRow

__all__ = ["Editor", "Input"]

#: A run of newlines -- ``\r\n``, ``\r`` or ``\n``, consecutive included --
#: folded into one space when a paste reaches a single-line field.
_NEWLINE_RUN = re.compile(r"(?:\r\n|\r|\n)+")


class _TextField(Widget):
    """The shared editing shell: buffer, routing, geometry and render trunk.

    Subclasses supply the keymap and four policy hooks: row indent, row
    window, row cap and row prefix.  ``focused`` renders the block cursor
    (a placeholder takes its place on an empty focused field); ``hover``
    paints the whole-row hover band.  ``mask`` is display-only: every
    rendered character becomes its first glyph while ``text`` stays plain.
    ``render`` is memoized on width and ``generation``.
    """

    __slots__ = (
        "_buf",
        "_mask",
        "_memo_generation",
        "_memo_rows",
        "_memo_width",
        "_wrap",
        "placeholder",
    )

    #: A field takes the focus ring, pointer clicks (the caret docks where
    #: the user clicked) and the block-level hover band.  It has no
    #: activation of its own: ``enter`` is the host's submit gesture.
    focusable = True
    clickable = True
    hoverable = True

    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str = "",
        theme: Theme | None = None,
        styles: Styles | None = None,
        keymap: Keymap,
        mask: str = "",
        read_only: bool = False,
        wrap: WrapMode = WrapMode.ELLIPSIS,
    ) -> None:
        super().__init__(theme, styles)
        self.placeholder = placeholder
        #: The old constructor default: a field starts focused.
        self.focused = True
        # A field keeps its own keymap copy: rebinding an instance key (the
        # 2.0 ``field.keymap["c-j"] = "newline"``) must never write through
        # to the module-level default table.
        self._buf = TextBuffer(text, keymap=dict(keymap), read_only=read_only)
        # A content write moves the buffer's version; this is the shell's
        # half of the invalidation contract (a cursor move is touched by the
        # hooks below, which do not bump the version).
        self._buf.on_change = self.touch
        # The display mask: the first character stands in for every rendered
        # character (see ``_mask_row``); ``""`` renders the text itself.
        self._mask = mask
        # The single-row response to a row wider than the field.  The buffer
        # geometry is always word-aware; this only shapes the final row
        # guard, so the editing algorithm does not move.  The plain Input
        # scrolls horizontally (OVERFLOW, its own ``_rows_for``), the Editor
        # re-wraps (WORD).
        self._wrap = wrap
        # The memory: the rows of the last render while ``_memo_generation``
        # and ``_memo_width`` still describe the field.  ``None`` rows mean
        # "nothing remembered" -- the generation is always an int here, so the
        # empty marker cannot be confused with a valid key.
        self._memo_rows: list[Line] | None = None
        self._memo_width: int | None = None
        self._memo_generation: object = None

    # -- buffer views -----------------------------------------------------------

    @property
    def keymap(self) -> Keymap:
        """The table :meth:`on_key` routes through."""
        return self._buf.keymap

    @keymap.setter
    def keymap(self, value: Keymap) -> None:
        self._buf.keymap = value

    @property
    def text(self) -> str:
        """The whole field text (a multi-line paste keeps its newlines)."""
        return self._buf.value

    @text.setter
    def text(self, value: str) -> None:
        """Replace the whole text; undo history is cleared and the cursor parks at the start.

        A read-only field still accepts it: the flag guards routed input,
        not programmatic writes.
        """
        self._buf.set_text(value)

    @property
    def read_only(self) -> bool:
        """Whether routed events are refused without touching the buffer.

        Direct editing methods and ``text =`` remain programmatic writes.
        """
        return self._buf.read_only

    @read_only.setter
    def read_only(self, value: bool) -> None:
        self._buf.read_only = value

    @property
    def mask(self) -> str:
        """The display mask (``""`` renders the text itself).

        Read-only construction parameter; a reveal switch redraws from
        :attr:`text`.
        """
        return self._mask

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
        self.touch()

    def select_all(self) -> bool:
        """Select the whole buffer; ``False`` for an empty one."""
        selected = self._buf.select_all()
        if selected:
            self.touch()
        return selected

    # -- editing --------------------------------------------------------------

    def _route(self, event: Event) -> bool:
        """Send one event to the buffer; ``False`` while read-only."""
        if self.read_only:
            return False
        consumed = self._buf.handle(event)
        if consumed:
            # Cursor and selection moves are row inputs too; a content
            # write has already touched through ``on_change``.
            self.touch()
        return consumed

    def on_key(self, e: KeyEvent) -> bool:
        """Consume one key through the buffer's keymap; ``False`` to decline."""
        return self._route(e)

    def on_mouse(self, e: MouseEvent) -> bool:
        """Route one mouse report; the buffer declines reports it does not use."""
        return self._route(e)

    def on_paste(self, e: PasteEvent) -> bool:
        """Insert one paste payload through the buffer."""
        return self._route(e)

    def on_action(self, name: str) -> bool:
        """Run one keymap action by name; ``False`` when unbound or ``"activate"``.

        A field has no activation; unknown names stay with the host.
        """
        if name == "activate":
            return False  # a field has no activation of its own
        if name not in set(self._buf.keymap.values()):
            return False
        method = getattr(self, name, None)
        if not callable(method):
            return False
        method()
        self.touch()
        return True

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
        return self._moved(self._buf.move_left())

    def move_right(self) -> bool:
        return self._moved(self._buf.move_right())

    def home(self) -> bool:
        """Move to the start of the cursor's logical line."""
        return self._moved(self._buf.home())

    def end(self) -> bool:
        """Move to the end of the cursor's logical line (before its "\\n")."""
        return self._moved(self._buf.end())

    def move_up(self) -> bool:
        """Move to the previous visual row, keeping the inner column."""
        return self._moved(self._buf.move_up())

    def move_down(self) -> bool:
        """Move to the next visual row, keeping the inner column."""
        return self._moved(self._buf.move_down())

    def select_left(self) -> bool:
        """Extend the selection one character left (or from the cursor)."""
        return self._moved(self._buf.select_left())

    def select_right(self) -> bool:
        """Extend the selection one character right (or from the cursor)."""
        return self._moved(self._buf.select_right())

    def select_home(self) -> bool:
        """Extend the selection to the start of the cursor's logical line."""
        return self._moved(self._buf.select_home())

    def select_end(self) -> bool:
        """Extend the selection to the end of the cursor's logical line."""
        return self._moved(self._buf.select_end())

    def select_up(self) -> bool:
        """Extend the selection one visual row up, keeping the inner column."""
        return self._moved(self._buf.select_up())

    def select_down(self) -> bool:
        """Extend the selection one visual row down, keeping the inner column."""
        return self._moved(self._buf.select_down())

    def _moved(self, moved: bool) -> bool:
        if moved:
            self.touch()
        return moved

    def on_click(self, pos: Pos) -> bool:
        """Dock the block cursor at this field's own rendered cell; True on a hit.

        The shell undoes its row window (and an Editor's ``max_rows`` offset)
        before the buffer resolves the column.  A row outside the rendered
        rows answers ``False``; ``focused`` is not consulted.
        """
        rows = self._buf.visual_rows(self._buf.last_width, self._indent())
        start, count = self._window(rows, self._buf.locate(rows)[0])
        if not 0 <= pos.y < count:
            return False
        hit = self._buf.place(start + pos.y, pos.x)
        if hit:
            self.touch()
        return hit

    # -- visual geometry -------------------------------------------------------

    def _indent(self) -> int:
        return 0

    def _window_start(self, total: int, cursor_index: int) -> int:
        return 0

    def _row_cap(self) -> int | None:
        return None

    def _window(self, rows: list[_VisualRow], cursor_index: int) -> tuple[int, int]:
        """The rendered window as ``(start, count)``: one expression of the row policy.

        ``render``, :meth:`cursor_position` and :meth:`on_click` all read it,
        so they cannot disagree.
        """
        start = self._window_start(len(rows), cursor_index)
        cap = self._row_cap()
        count = len(rows) - start if cap is None else min(max(cap, 0), len(rows) - start)
        return start, count

    def cursor_position(self, width: int) -> tuple[int, int]:
        """The cursor cell as ``(visual_row, col)`` of a ``render(c)``.

        Same geometry as ``render``, window applied; pure query.  A mask
        preserves display width, so the cell is the masked render's too.
        """
        indent = self._indent()
        rows = self._buf.visual_rows(width, indent)
        start, _count = self._window(rows, self._buf.locate(rows)[0])
        return self._buf.cursor_position(width, indent, start)

    # -- rendering ---------------------------------------------------------------

    def _row_prefix(self, index: int, indent: int) -> Segment | None:
        return None

    def _mask_row(
        self, text: str, column: int, selection: tuple[int, int] | None
    ) -> tuple[str, int, tuple[int, int] | None]:
        """One row's text masked, with caret and selection remapped.

        Each character becomes whole glyphs of the mask's first character
        filling its display width, so row width -- and caret geometry -- are
        the unmasked row's.  A zero-width mask leaves the row alone.
        """
        glyph = self._mask[0]
        width = visible_width(glyph)
        if width <= 0:
            return text, column, selection
        starts: list[int] = []
        pieces: list[str] = []
        offset = 0
        for char in text:
            cells = visible_width(char)
            piece = glyph * max(1, cells // width)
            piece += " " * max(0, cells - visible_width(piece))
            starts.append(offset)
            pieces.append(piece)
            offset += len(piece)
        starts.append(offset)  # the row-end sentinel: the caret past the text
        caret = starts[min(max(column, 0), len(text))]
        band = None if selection is None else (starts[selection[0]], starts[selection[1]])
        return "".join(pieces), caret, band

    def render(self, c: Constraints) -> Surface:
        """The rendered rows at the constrained width, memoized on width and generation.

        ``max_height`` truncates the returned rows without invalidating the
        memo.  ``last_width`` is seeded on every call for the buffer's own
        moves and clicks.
        """
        width = c.width
        self._buf.last_width = width
        generation = self.generation
        rows = self._memo_rows
        if (
            rows is None
            or self._memo_width != width
            or self._memo_generation != generation
        ):
            rows = self._rows_for(width)
            self._memo_generation = generation
            self._memo_width = width
            self._memo_rows = rows
        out = list(rows)
        surface_width = self._surface_width(out, c.width)
        if c.max_height is not None:
            out = out[: c.max_height]
        return Surface.of(out, surface_width, pad=False)

    def _surface_width(self, rows: list[Line], width: int) -> int:
        """The constraint width; an OVERFLOW editor widens to the natural rows."""
        return width

    def _field_floor(self) -> Style:
        """The row floor: ``surfaces.control`` plus the field's state overlay.

        Read-only merges ``text.faint`` and the disabled overlay (it wins
        over hover); focus adds nothing because the caret is the signal.
        """
        floor = self.group("surfaces").control
        controls = self.group("controls")
        if self.read_only:
            return floor.merge(self.group("text").faint).merge(
                controls.overlay(disabled=True)
            )
        if self.hover:
            return floor.merge(controls.overlay(hovered=True))
        return floor

    @staticmethod
    def _on_floor(line: Line, floor: Style) -> Line:
        """``line`` with ``floor`` under every segment's own style.

        Caret, selection, prompt and placeholder styles still win on top.
        """
        if floor == NONE:
            return line
        return Line(seg.with_style(floor.merge(seg.style)) for seg in line.segments)

    def _rows_for(self, width: int) -> list[Line]:
        text_styles = self.group("text")
        floor = self._field_floor()
        indent = self._indent()
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
                body = [Segment(placeholder, text_styles.faint)]
            else:
                cursor_here = self.focused and index == cursor_index
                local = self._buf.selected_local(row, selection)
                text, column = row.text, cursor_column
                if self._mask:
                    text, column, local = self._mask_row(text, column, local)
                marked = (
                    cursor_here
                    and selection is not None
                    and selection[0] <= self._buf.offset < selection[1]
                )
                body = self._buf.row_body(
                    text,
                    column,
                    inner,
                    text_styles.base,
                    text_styles.caret,
                    selection=local,
                    selection_style=text_styles.selection,
                    show_cursor=cursor_here,
                    cursor_marked=marked,
                )
            line = Line((prefix, *body)) if prefix is not None else Line(body)
            line = self._on_floor(line, floor)
            if line.width <= width:
                # The buffer's geometry already fits (and keeps trailing
                # spaces the word rule would drop), so the default is the row
                # itself; only an over-wide cluster reaches the guard.
                out.append(line)
            elif self._wrap in (WrapMode.WORD, WrapMode.CHAR):
                out.extend(line.reflow(self._wrap, width))
            else:
                out.append(line.clip(self._wrap, width))
        return out

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.text!r}, cursor={self.cursor})"


class Input(_TextField):
    """A prompt-led, single-line text field with a block cursor.

    ``prompt`` defaults to ``seat(glyphs.prompt)``; its width is the row
    indent.  The default ``wrap=OVERFLOW`` renders one horizontally sliding
    row under the cursor; a paste folds every newline run into one space so
    nothing can submit.  ``mask`` masks the display only.  ``cursor_shape``
    is ``"beam"`` for the host's terminal cursor.
    """

    __slots__ = ("_prompt",)

    #: The DECSCUSR shape a focused single-line field asks the host for.
    cursor_shape = "beam"

    def __init__(
        self,
        text: str = "",
        *,
        prompt: str | None = None,
        placeholder: str = "",
        mask: str = "",
        glyphs: Glyphs = GLYPHS,
        theme: Theme | None = None,
        styles: Styles | None = None,
        keymap: Keymap | None = None,
        read_only: bool = False,
        wrap: WrapMode = WrapMode.OVERFLOW,
    ) -> None:
        super().__init__(
            text,
            placeholder=placeholder,
            theme=theme,
            styles=styles,
            keymap=keymap if keymap is not None else DEFAULT_INPUT_KEYMAP,
            mask=mask,
            read_only=read_only,
            wrap=wrap,
        )
        # The default prompt is the vocabulary's cue plus one separator
        # column; an explicit prompt wins and may be ``""`` (no prompt).
        self.prompt = seat(glyphs.prompt) if prompt is None else prompt

    # -- buffer views -----------------------------------------------------------

    @property
    def prompt(self) -> str:
        """The first row's prompt; its width is the buffer's row indent."""
        return self._prompt

    @prompt.setter
    def prompt(self, value: str) -> None:
        self._prompt = value
        self._buf.indent = visible_width(value)
        self.touch()

    @property
    def wrap(self) -> WrapMode:
        """How an over-wide row responds to ``render``'s width.

        ``OVERFLOW`` (default) slides one row; other modes delegate to the
        shared shell's row guard.
        """
        return self._wrap

    @wrap.setter
    def wrap(self, value: WrapMode) -> None:
        if value is self._wrap:
            return
        self._wrap = value
        self._memo_rows = None
        self._memo_generation = None
        self.touch()

    @property
    def cursor(self) -> tuple[int, int]:
        """The cursor as ``(0, col)``, ``col`` being the flat character offset."""
        return 0, self._buf.offset

    # -- routing ----------------------------------------------------------------

    def on_paste(self, e: PasteEvent) -> bool:
        """Fold every newline run of a paste into one space, then insert it.

        The editor's paste path and an explicit ``insert`` keep newlines.
        """
        return super().on_paste(PasteEvent(_NEWLINE_RUN.sub(" ", e.text)))

    def on_key(self, event: Event) -> bool:
        """Consume one event; a ``PasteEvent`` folds like :meth:`on_paste`."""
        if isinstance(event, PasteEvent):
            return self.on_paste(event)
        return super().on_key(event)

    # -- rendering ---------------------------------------------------------------

    def cursor_position(self, width: int) -> tuple[int, int]:
        """The cursor cell as ``(0, col)`` of the single-row render.

        A prompt wider than the field reports the last cell.  Non-OVERFLOW
        modes keep the shared answer.
        """
        if self._wrap is not WrapMode.OVERFLOW or width <= 0:
            return super().cursor_position(width)
        indent = self._indent()
        if indent >= width:
            return 0, width - 1
        visible, local, _start = self._single_line_geometry(width)
        return 0, min(width - 1, indent + visible_width(visible[:local]))

    def _single_line_geometry(self, width: int) -> tuple[str, int, int]:
        """The visible window, the cursor's index in it, and its start index.

        Newlines become spaces in place so display indices equal buffer
        offsets; the window slides to keep the cursor visible and never ends
        exactly at the cursor without a cell for the block.
        """
        inner = max(0, width - self._indent())
        value = self._buf.value
        display = self._mask[0] * len(value) if self._mask else value
        display = (
            display.replace("\r\n", "  ").replace("\r", " ").replace("\n", " ")
        )
        cursor = self._buf.offset
        cursor_col = visible_width(display[:cursor])
        scroll_x = cursor_col - inner + 1 if cursor_col >= inner else 0
        start, end = index_pair_at_columns(display, scroll_x, scroll_x + inner)
        if cursor >= len(display) and visible_width(display[start:end]) + 1 > inner:
            while start < end and visible_width(display[start:end]) + 1 > inner:
                start += 1
        visible = display[start:end]
        local = max(0, min(len(visible), cursor - start))
        return visible, local, start

    @staticmethod
    def _window_selection(
        selection: tuple[int, int] | None, start: int, length: int
    ) -> tuple[int, int] | None:
        if selection is None:
            return None
        lo = min(max(selection[0] - start, 0), length)
        hi = (
            length
            if selection[1] >= start + length
            else min(max(selection[1] - start, 0), length)
        )
        return (lo, hi) if lo < hi else None

    def _rows_for(self, width: int) -> list[Line]:
        """The single row of the horizontal-overflow view.

        The prompt takes its columns; the rest is the column window from
        :meth:`_single_line_geometry`, hard-clipped (never ellipsized).  A
        placeholder is a label without a cursor cell.  Other modes use the
        shared rows.
        """
        if self._wrap is not WrapMode.OVERFLOW:
            return super()._rows_for(width)
        text_styles = self.group("text")
        floor = self._field_floor()
        indent = self._indent()
        prefix = self._row_prefix(0, indent)
        if indent >= width:
            line = Line((prefix,))
        elif self.placeholder and self._buf.empty and self.focused:
            line = Line((prefix, Segment(self.placeholder, text_styles.faint)))
        else:
            visible, local, start = self._single_line_geometry(width)
            selection = self._buf.selection_range()
            marked = (
                self.focused
                and selection is not None
                and selection[0] <= self._buf.offset < selection[1]
            )
            body = self._buf.row_body(
                visible,
                local,
                max(0, width - indent),
                text_styles.base,
                text_styles.caret,
                selection=self._window_selection(selection, start, len(visible)),
                selection_style=text_styles.selection,
                show_cursor=self.focused,
                cursor_marked=marked,
            )
            line = Line((prefix, *body))
        line = self._on_floor(line, floor)
        return [line.clip(WrapMode.CLIP, width)]

    def _indent(self) -> int:
        return visible_width(self._prompt)

    def _row_prefix(self, index: int, indent: int) -> Segment:
        if index == 0:
            return Segment(self._prompt, self.group("content").accent)
        return Segment(" " * indent)


class Editor(_TextField):
    """A multi-line text buffer with a block cursor.

    ``text`` seeds the buffer with the cursor at its start; ``max_rows``
    caps the rendered rows with a window that keeps the cursor visible.
    ``mask`` masks the display only; ``cursor_shape`` is ``"beam"``.
    ``wrap=WORD`` is the default final row guard.  ``OVERFLOW`` instead
    renders one natural-width row per logical line for a horizontal scroll
    container, and up/down step logical lines.
    """

    __slots__ = ("max_rows",)

    #: The DECSCUSR shape a focused editor asks the host for.
    cursor_shape = "beam"

    def __init__(
        self,
        text: str = "",
        *,
        placeholder: str = "",
        mask: str = "",
        theme: Theme | None = None,
        styles: Styles | None = None,
        keymap: Keymap | None = None,
        max_rows: int | None = None,
        read_only: bool = False,
        wrap: WrapMode = WrapMode.WORD,
    ) -> None:
        super().__init__(
            text,
            placeholder=placeholder,
            theme=theme,
            styles=styles,
            keymap=keymap if keymap is not None else DEFAULT_EDITOR_KEYMAP,
            mask=mask,
            read_only=read_only,
            wrap=wrap,
        )
        self.max_rows = max_rows

    @property
    def wrap(self) -> WrapMode:
        """How an over-wide row responds to ``render``'s width."""
        return self._wrap

    @wrap.setter
    def wrap(self, value: WrapMode) -> None:
        if value is self._wrap:
            return
        self._wrap = value
        self.touch()

    # -- the logical-line view (OVERFLOW) --------------------------------------

    def on_click(self, pos: Pos) -> bool:
        """Dock the cursor on a logical-line cell in ``OVERFLOW`` mode.

        ``pos.y`` indexes the rendered window and ``pos.x`` a display column
        of the line.  Other modes keep the shared implementation.
        """
        if self._wrap is not WrapMode.OVERFLOW:
            return super().on_click(pos)
        rows = self._logical_rows()
        start, count = self._window(rows, self._buf.row)
        if not 0 <= pos.y < count:
            return False
        line = rows[start + pos.y]
        offset = line.start + index_bounds_at_columns(line.text, pos.x)[0]
        self._buf._drop_selection()
        self._buf._set_offset(offset)
        self.touch()
        return True

    def move_up(self) -> bool:
        """Move one logical line up in ``OVERFLOW``; the shared visual row otherwise."""
        if self._wrap is not WrapMode.OVERFLOW:
            return super().move_up()
        return self._step_logical(-1, extend=False)

    def move_down(self) -> bool:
        """Move one logical line down in ``OVERFLOW``; the shared visual row otherwise."""
        if self._wrap is not WrapMode.OVERFLOW:
            return super().move_down()
        return self._step_logical(1, extend=False)

    def select_up(self) -> bool:
        """Extend one logical line up in ``OVERFLOW``; the shared visual row otherwise."""
        if self._wrap is not WrapMode.OVERFLOW:
            return super().select_up()
        return self._step_logical(-1, extend=True)

    def select_down(self) -> bool:
        """Extend one logical line down in ``OVERFLOW``; the shared visual row otherwise."""
        if self._wrap is not WrapMode.OVERFLOW:
            return super().select_down()
        return self._step_logical(1, extend=True)

    def _step_logical(self, delta: int, *, extend: bool) -> bool:
        """Walk ``delta`` logical lines, keeping the character column.

        A step past the ends moves nowhere; a plain step drops the selection
        and an extending one anchors at the start; the column clamps to the
        target line's length.
        """
        buf = self._buf
        if not extend:
            buf._drop_selection()  # a plain move drops the selection even at an edge
        row = buf.row + delta
        if not 0 <= row < len(buf.lines):
            return False
        if extend:
            if buf.anchor is None:
                buf._anchor = buf.offset
            buf._chain = False
        offset = sum(len(line) + 1 for line in buf.lines[:row]) + min(
            buf.col, len(buf.lines[row])
        )
        moved = buf._set_offset(offset)
        if moved:
            self.touch()
        return moved

    def cursor_position(self, width: int) -> tuple[int, int]:
        """The cursor cell as ``(logical row, content column)`` in ``OVERFLOW``.

        The row indexes the rendered ``max_rows`` window; the column may
        reach past ``width`` because the surface carries the content width.
        Other modes keep the shared answer.
        """
        if self._wrap is not WrapMode.OVERFLOW:
            return super().cursor_position(width)
        rows = self._logical_rows()
        index = self._buf.row
        start, _count = self._window(rows, index)
        return index - start, visible_width(rows[index].text[: self._buf.col])

    def _logical_rows(self) -> list[_VisualRow]:
        """One natural-width row per logical buffer line.

        Tabs become one space exactly as the buffer's visual geometry does,
        keeping character offsets and the cursor column valid.
        """
        rows: list[_VisualRow] = []
        base = 0
        for line in self._buf.lines:
            normalized = line.replace("\t", " ")
            rows.append(
                _VisualRow(
                    base,
                    base + len(normalized),
                    normalized,
                    base,
                    base + len(normalized),
                )
            )
            base += len(normalized) + 1
        return rows

    def _surface_width(self, rows: list[Line], width: int) -> int:
        """The natural width in ``OVERFLOW``; the constraint's width otherwise."""
        if self._wrap is not WrapMode.OVERFLOW:
            return width
        return max(width, max((row.width for row in rows), default=0))

    def _rows_for(self, width: int) -> list[Line]:
        """The logical-line rows in ``OVERFLOW``; the shared rows otherwise."""
        if self._wrap is not WrapMode.OVERFLOW:
            return super()._rows_for(width)
        text_styles = self.group("text")
        floor = self._field_floor()
        rows = self._logical_rows()
        cursor_index, cursor_column = self._buf.row, self._buf.col
        start, count = self._window(rows, cursor_index)
        shown = rows[start : start + count]
        selection = self._buf.selection_range()
        placeholder = self.placeholder if self._buf.empty and self.focused else ""
        out: list[Line] = []
        for offset, row in enumerate(shown):
            index = start + offset
            if placeholder:
                body = [Segment(placeholder, text_styles.faint)]
            else:
                cursor_here = self.focused and index == cursor_index
                local = self._buf.selected_local(row, selection)
                text, column = row.text, cursor_column
                if self._mask:
                    text, column, local = self._mask_row(text, column, local)
                marked = (
                    cursor_here
                    and selection is not None
                    and selection[0] <= self._buf.offset < selection[1]
                )
                body = self._buf.row_body(
                    text,
                    column,
                    visible_width(row.text) + 1,
                    text_styles.base,
                    text_styles.caret,
                    selection=local,
                    selection_style=text_styles.selection,
                    show_cursor=cursor_here,
                    cursor_marked=marked,
                )
            line = Line(body)
            line = self._on_floor(line, floor)
            out.append(line)
        return out

    # -- visual geometry -------------------------------------------------------

    def _window_start(self, total: int, cursor_index: int) -> int:
        """Flat start of the ``max_rows`` window that keeps the cursor visible.

        The window centres on the cursor's visual row and slides at the
        ends; without a cap (or when everything fits) it starts at 0.
        """
        cap = self.max_rows
        if cap is None or total <= cap:
            return 0
        return min(max(0, cursor_index - cap // 2), total - cap)

    def _row_cap(self) -> int | None:
        return self.max_rows
