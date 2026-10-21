"""The text fields: :class:`Input` and :class:`Editor` over one editing shell.

The editing state -- the text, the cursor, the keymap routing, the wrapped-row
geometry, the undo history and the selection -- lives in one
:class:`~motui.widgets.textbuf.TextBuffer`, and the shared editing shell --
buffer composition, event routing, the render trunk -- in
:class:`_TextField`; this module carries both shells and that shell.

The two public fields are one component twice:

* :class:`Input` leads every row with a prompt and wraps at
  ``width - visible_width(prompt)``; a :class:`~motui.kernel.events.PasteEvent`
  entering a **single-line** field has every run of newlines folded into one
  space, so a pasted paragraph stays one row (the editor's paste path keeps
  its newlines, and so does an explicit ``insert``).
* :class:`Editor` spans the full width and slides an optional ``max_rows``
  window around the cursor.

No key is read here: the host feeds events to ``handle``, which routes them
through the component's ``keymap``
(:data:`~motui.keys.keymap.DEFAULT_INPUT_KEYMAP` /
:data:`~motui.keys.keymap.DEFAULT_EDITOR_KEYMAP` unless overridden) and
returns ``False`` for every key it leaves to the host's own routing.  The
wrap geometry comes from the width of the last ``render`` call (80 before
the first render), so up/down cursor movement follows the wrapped rows the
user sees.  A pure ``cursor_position`` reports where the block cursor sits
in the rendered rows, for hosts that park the terminal cursor there (an IME
anchor on a real console).

An empty focused field with a placeholder renders the hint in the theme's
``dim`` and **no cursor cell**: the hint is a label for the empty state, not
content, and a block painted over or after it reads as an artifact.  The
cursor block appears with the first typed character; an empty field *without*
a placeholder shows the block alone, exactly as a typed row does.

``mask`` is the display-only secret input: non-empty, every rendered
character is replaced by the mask's own glyph while :attr:`~Input.text`
stays plain, the caret geometry is measured against the masked width and
the block cursor still covers the cell under it.  Reveal/hide switching is
the host's own -- it re-draws from ``text`` -- and deliberately not a
component feature.

Styles resolve once, at construction, as explicit parameter > theme field >
:data:`~motui.kernel.theme.DEFAULT_THEME`, the same rule every component
follows.
"""

from __future__ import annotations

import re

from ..kernel.events import Event, PasteEvent
from ..kernel.lines import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed
from ..keys.keymap import (
    DEFAULT_EDITOR_KEYMAP,
    DEFAULT_INPUT_KEYMAP,
    Keymap,
)
from .textbuf import TextBuffer, _VisualRow

__all__ = ["Editor", "Input"]

#: A run of newlines -- ``\r\n``, ``\r`` or ``\n``, consecutive included --
#: folded into one space when a paste reaches a single-line field.
_NEWLINE_RUN = re.compile(r"(?:\r\n|\r|\n)+")


class _TextField(Themed):
    """The shared editing shell: buffer, routing, geometry, render trunk.

    A shell supplies the keymap, the resolved styles and four policy hooks:
    the row indent (:meth:`_indent`), the row window
    (:meth:`_window_start`, :meth:`_row_cap`) and the row prefix
    (:meth:`_row_prefix`).  Everything else -- the text, the cursor,
    ``handle``, the editing methods, ``click`` and ``render`` -- is one
    implementation here.

    ``focused`` is the flag the focus tier writes
    (:class:`~motui.interaction.focus.FocusManager`, through
    :class:`~motui.kernel.block.Focusable`) -- the same flag a shell
    takes at construction; the shell only renders by it (the block cursor
    and the empty-field hint).  ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.block.Hoverable`): the fields take the
    **block-level** hover only -- the whole rendered row (prompt included)
    merges the theme's ``hover`` while it is ``True`` -- and implement no
    ``hover_at``: a text row has no sub-row items to mark.

    ``mask`` is the display-only mask: non-empty, every character of every
    rendered row is replaced by glyphs of its first character while the
    buffer's text stays plain (:meth:`_mask_row`); the caret's cell and the
    selection band are remapped through the same table, so the block cursor
    covers the masked cell exactly where it always sat.  The mask is a
    construction parameter -- there is no setter, and a host that wants a
    reveal switch redraws from :attr:`text` itself.

    The selection is rendered here too: the shell asks the buffer for the
    selected character range of each visual row and hands it to the
    buffer's one row-body builder, which merges ``selection_style`` (the
    theme's ``selection``) over it -- the block cursor included, with the
    selection band on top ("selection outranks the cursor") and the cursor
    still there underneath.  The prompt is never selected: the band starts
    at the text.

    **The memory.**  Rendering walks the buffer's whole visual geometry --
    a 3000-line buffer wraps every line to show twenty -- and a host
    repaints the same field frame after frame (every mouse move repaints),
    so :meth:`render` remembers its last answer: while the width and
    :meth:`revision` are unchanged, the remembered rows come back as a
    list copy.  The snapshot is the buffer's :attr:`~motui.widgets.textbuf.TextBuffer.version`
    plus the cursor, the selection anchor, the flags, the placeholder, the
    mask, the styles and the shell's own policy values
    (:meth:`_policy_revision`); the wrap geometry underneath is remembered
    by the buffer itself, per line, so a keystroke in a 3000-line editor
    re-wraps one line and a move re-wraps none.  :meth:`revision` is the
    :class:`~motui.kernel.block.Revisioned` door, which is how a sealed
    field's caret still reaches the screen (D4).
    """

    __slots__ = (
        "_buf",
        "_caret_style",
        "_dim",
        "_hover_style",
        "_mask",
        "_memo_revision",
        "_memo_rows",
        "_memo_width",
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
        caret_style: Style | None = None,
        theme: Theme | None = None,
        keymap: Keymap,
        focused: bool = True,
        mask: str = "",
        read_only: bool = False,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.placeholder = placeholder
        self.focused = focused
        #: The pointer tier's flag; it only changes how the rows render.
        self.hover = False
        self._buf = TextBuffer(text, keymap=keymap, read_only=read_only)
        # The display mask: the first character stands in for every rendered
        # character (see ``_mask_row``); ``""`` renders the text itself.
        self._mask = mask
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._style = style if style is not None else NONE
        self._caret_style = self.pick(caret_style, self._theme.text.caret)
        self._dim = self.pick(None, self._theme.text.faint)
        self._hover_style = self.pick(None, self._theme.surfaces.hover)
        self._selection_style = self.pick(None, self._theme.text.selection)
        # The memory: the rows of the last render while ``_memo_revision``
        # and ``_memo_width`` still describe the field.  ``None`` rows mean
        # "nothing remembered" -- the revision never answers ``None`` here,
        # so the empty marker cannot be confused with a snapshot value.
        self._memo_rows: list[Line] | None = None
        self._memo_width: int | None = None
        self._memo_revision: object = None

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

    @text.setter
    def text(self, value: str) -> None:
        """Replace the whole text; the buffer's undo/redo history is cleared.

        The cursor parks at the start (the constructor's own rule), so an
        assignment is a fresh buffer rather than an undoable edit.  A
        read-only field accepts it: the flag guards routed input, not the
        host's own writes.
        """
        self._buf.set_text(value)

    @property
    def read_only(self) -> bool:
        """Whether routed events are refused without touching the buffer.

        ``handle`` answers ``False`` for every event while this is set, so
        a host can route keys into a field it has made read-only and the
        text never changes.  The direct editing methods (``insert``,
        ``backspace``, the moves, ``text =``) are programmatic writes and
        remain available -- the host owns the flag.
        """
        return self._buf.read_only

    @read_only.setter
    def read_only(self, value: bool) -> None:
        self._buf.read_only = value

    @property
    def mask(self) -> str:
        """The display mask (``""`` = the text renders itself).

        A construction parameter: there is no setter, and the property is
        read-only so a host never mistakes it for a reveal switch (that is
        the host's own render off ``text``).
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

    def select_all(self) -> bool:
        """Select the whole buffer; ``False`` for an empty one."""
        return self._buf.select_all()

    # -- editing --------------------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Consume an event via the buffer; see :meth:`TextBuffer.handle`.

        The buffer's :attr:`~TextBuffer.indent` is the field's row indent,
        kept in step by a shell that renders a prompt, so this shell only
        delegates.  ``False`` for an event the buffer does not consume
        leaves the host free to route it -- the editor's default table
        binds ``enter``, the input's does not, so a submit gesture reaches
        the host.  A ``read_only`` field refuses every routed event
        (``False``) before the buffer sees it; the direct editing methods
        and the ``text`` setter are programmatic writes and stay available.
        """
        if self.read_only:
            return False
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
        :meth:`~motui.app.TUI.hit` reports -- so the shell first
        undoes its own row policy and then lets the buffer resolve the
        column.  An :class:`Editor` adds the ``max_rows`` window's first
        rendered row back onto ``row`` (the same window :meth:`render`
        slices by, read off the current cursor, via :meth:`_window`), so
        "the third row on screen" is the third row of the window whatever
        the buffer's length; an :class:`Input` hands ``col`` straight
        through, the prompt's width already being the buffer's indent, so a
        click on the prompt or on a wrapped row's indent folds onto that
        row's first character.  A row outside the rendered rows answers
        ``False`` and changes nothing; a hit docks the cursor -- even when
        it already sat there -- and answers ``True``.  ``focused`` is
        deliberately not consulted: moving the focus on a click is the
        host's (or a :class:`~motui.interaction.focus.FocusManager`'s) policy, never
        the field's.  A multi-row residue (an explicit :meth:`insert` of
        ``"\\n"`` into an ``Input``) is accepted row by row like any other
        buffer.  A mask covers the cells, not the geometry: a click lands
        on the same logical character it would without one.
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
        rows ``render`` actually returns.  A mask preserves the display
        width of every cell, so the reported cell is the masked render's
        too.  Pure query: no state changes, no rendering.
        """
        indent = self._indent()
        rows = self._buf.visual_rows(width, indent)
        start, _count = self._window(rows, self._buf.locate(rows)[0])
        return self._buf.cursor_position(width, indent, start)

    # -- rendering ---------------------------------------------------------------

    def _row_prefix(self, index: int, indent: int) -> Segment | None:
        """The row's leading segment, or ``None`` when the shell has none."""
        return None

    def _mask_row(
        self, text: str, column: int, selection: tuple[int, int] | None
    ) -> tuple[str, int, tuple[int, int] | None]:
        """One row's text with every character masked, and the caret remapped.

        The mask replaces each character with whole glyphs of its first
        character, repeated to fill the character's own display width (a
        cell narrower than a wide glyph takes one glyph and spaces fill the
        rest), so the row's width -- and with it the caret geometry -- is
        the unmasked row's.  ``column`` and ``selection`` are character
        indices into the row, so both are remapped through the same table:
        the block cursor and the selection band land on the very cells they
        would without the mask.  A zero-width mask cannot stand for a cell
        and leaves the row alone.
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

    def _policy_revision(self) -> object:
        """The shell's own row inputs, read through the hooks the render reads.

        Everything the shared trunk renders comes from the buffer, the flags
        or the four policy hooks -- and the indent is already in the shared
        tuple.  The remaining two are asked here exactly as :meth:`render`
        asks them: the row cap (an :class:`Editor`'s ``max_rows`` window;
        ``None`` for no cap) and the **first row's prefix** (the prompt an
        :class:`Input` leads with; ``None`` for a shell without one).  They
        are *derived* values, not live state: two answers compare equal
        exactly while the fields behind them do, which is all the protocol's
        promise needs -- and a shell the hooks cannot express (a policy of
        its own) overrides this method with its fields instead.
        """
        indent = self._indent()
        return (self._row_cap(), self._row_prefix(0, indent))

    def _revision(self) -> object:
        """The value snapshot of everything the rendered rows are made of.

        The buffer's :attr:`~motui.widgets.textbuf.TextBuffer.version` and
        cursor (``row``/``col``), the selection anchor, the focus and hover
        flags, the placeholder, the mask, the resolved styles and the
        shell's own policy values -- every one a plain value, so the
        snapshot is a copy by construction.  The geometry itself is
        deliberately **not** in here: the wrapped spans are a function of
        the buffer's text and the width (the buffer's own memory), and the
        cursor's cell is a function of the version, the cursor and the
        width, so equal snapshots at one width render equal rows -- the
        protocol's promise.
        """
        buf = self._buf
        return (
            buf.version,
            buf.row,
            buf.col,
            buf.anchor,
            self.focused,
            self.hover,
            self.placeholder,
            self._mask,
            self._style,
            self._caret_style,
            self._selection_style,
            self._dim,
            self._hover_style,
            self._indent(),
            self._policy_revision(),
        )

    def revision(self) -> object:
        """The :class:`~motui.kernel.block.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a block holding this
        component keys its own row cache on the same value, so a keystroke,
        a moved cursor or a hover invalidates the block's copy and this
        component's memory in one move -- and a *sealed* field's caret
        still reaches the screen.
        """
        return self._revision()

    def render(self, width: int) -> list[Line]:
        """The rendered rows at ``width``, remembered while the snapshot holds.

        While the width and :meth:`_revision` are unchanged, the remembered
        rows of the last render come back as a list copy -- no re-walk over
        the buffer's visual geometry, no row bodies rebuilt (the
        component's memory).  A keystroke bumps the buffer's version and a
        move changes the cursor, so either one misses; a miss builds the
        rows, remembers them and moves the key.  ``last_width`` is seeded
        on every call, hit or miss: it is the geometry the buffer's own
        moves and clicks read, not part of the rendered bytes.  The
        returned list is always the caller's own.
        """
        self._buf.last_width = width
        revision = self._revision()
        rows = self._memo_rows
        if (
            rows is None
            or self._memo_width != width
            or self._memo_revision != revision
        ):
            rows = self._rows_for(width)
            self._memo_revision = revision
            self._memo_width = width
            self._memo_rows = rows
        return list(rows)

    def _rows_for(self, width: int) -> list[Line]:
        """The freshly built rows at ``width``: :meth:`render`'s miss path."""
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
                body = [Segment(placeholder, self._dim)]
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
                    self._style,
                    self._caret_style,
                    selection=local,
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


class Input(_TextField):
    """A prompt-led text field with a reverse-video block cursor.

    ``focused=False`` renders the text plainly (no cursor); an empty focused
    field shows ``placeholder`` in a dim style, with no cursor cell riding it
    -- the block appears with the first typed character.  The cursor is drawn
    by re-styling the character under it as ``style.merge(caret_style)``, or,
    at a row end, by appending a reverse-video space -- skipped when the row
    is already full so no row ever exceeds ``width``.  ``prompt_style``,
    ``caret_style`` and the placeholder's dim style resolve once, at
    construction, as explicit > theme field (``accent``/``caret``/``dim``)
    > :data:`~motui.kernel.theme.DEFAULT_THEME`.  ``keymap`` (default
    :data:`~motui.keys.keymap.DEFAULT_INPUT_KEYMAP`) is the table
    :meth:`handle` routes through; it carries no ``enter`` binding, so
    the return key reaches the host untouched.  A multi-line paste is
    folded into the single line at :meth:`handle`: a paste fills a field,
    and a field whose keymap cannot even bind ``enter`` must not let the
    paste smuggle in a row break.  ``hover`` is the pointer tier's
    block-level band: while it is ``True`` every rendered row (prompt
    included) merges the theme's ``hover``; there is no row-level
    ``hover_at`` -- a text row has no sub-row items to mark.  ``mask``
    (``""`` = plain) replaces every rendered character with its own glyph
    while :attr:`~_TextField.text` stays plain: the display-only secret
    field, set at construction (a host that wants a reveal switch redraws
    from ``text``).  The class declares ``cursor_shape = "beam"``: a text
    field reads best with the terminal's bar cursor, and the host reads the
    attribute off the focused leaf and passes it to
    :meth:`~motui.app.TUI.set_cursor_shape`.
    """

    __slots__ = ("_prompt", "_prompt_style")

    #: The DECSCUSR shape a focused single-line field asks the host for.
    cursor_shape = "beam"

    def __init__(
        self,
        text: str = "",
        *,
        prompt: str = "\u276e ",
        placeholder: str = "",
        mask: str = "",
        style: Style | None = None,
        prompt_style: Style | None = None,
        caret_style: Style | None = None,
        focused: bool = True,
        theme: Theme | None = None,
        keymap: Keymap | None = None,
        read_only: bool = False,
    ) -> None:
        super().__init__(
            text,
            placeholder=placeholder,
            style=style,
            caret_style=caret_style,
            theme=theme,
            keymap=keymap if keymap is not None else DEFAULT_INPUT_KEYMAP,
            focused=focused,
            mask=mask,
            read_only=read_only,
        )
        self._prompt_style = self.pick(prompt_style, self._theme.content.accent)
        self.prompt = prompt  # the prompt's width is the buffer's row indent

    # -- buffer views -----------------------------------------------------------

    @property
    def prompt(self) -> str:
        """The first row's prompt; its width is the buffer's row indent."""
        return self._prompt

    @prompt.setter
    def prompt(self, value: str) -> None:
        self._prompt = value
        self._buf.indent = visible_width(value)

    @property
    def cursor(self) -> tuple[int, int]:
        """The cursor as ``(row, col)``: a single-line field reports row 0.

        ``col`` is the flat character offset into :attr:`text` -- the
        single-line view of the buffer position.  A paste is folded to one
        space per newline run at :meth:`handle`, so only an explicit
        ``insert("\\n")`` can keep a newline in the buffer.
        """
        return 0, self._buf.offset

    # -- routing ----------------------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Consume an event; a paste's newline runs fold into single spaces.

        The one policy this shell adds over the shared routing: a
        :class:`~motui.kernel.events.PasteEvent` entering a single-line field
        has every run of ``\\r\\n`` / ``\\r`` / ``\\n`` -- consecutive empty
        lines included -- collapsed to one space before the buffer sees it,
        so a multi-line paste is one input row and nothing about it can
        submit.  Everything else routes through the shared shell; the
        editor's paste path and an explicit :meth:`insert` keep their
        newlines.
        """
        if isinstance(event, PasteEvent):
            event = PasteEvent(_NEWLINE_RUN.sub(" ", event.text))
        return super().handle(event)

    # -- rendering ---------------------------------------------------------------

    def _indent(self) -> int:
        return visible_width(self._prompt)

    def _row_prefix(self, index: int, indent: int) -> Segment:
        if index == 0:
            return Segment(self._prompt, self._prompt_style)
        return Segment(" " * indent)


class Editor(_TextField):
    """A multi-line text buffer with a reverse-video block cursor.

    ``text`` seeds the buffer (the cursor parks at its start);
    ``placeholder`` shows dim on the first row of an empty focused editor,
    with no cursor cell riding it -- the block appears with the first typed
    character.  ``focused=False`` renders the text plainly (no cursor, no
    placeholder).
    The cursor is drawn by re-styling the character under it as
    ``style.merge(caret_style)``, or, at a row end, by appending a
    reverse-video space -- skipped when the row is already full so no row
    ever exceeds ``width``.  ``caret_style`` and the placeholder's dim
    style fall back to the theme's ``caret``/``dim`` when not given
    explicitly.  ``max_rows`` (``None`` = unlimited) caps the rendered rows
    with a sliding window that keeps the cursor's visual row visible.
    ``mask`` (``""`` = plain) replaces every rendered character with its own
    glyph while :attr:`~_TextField.text` stays plain -- the display-only
    secret field, set at construction.  ``hover`` is the pointer tier's
    block-level band: while it is ``True`` every rendered row merges the
    theme's ``hover``; there is no row-level ``hover_at``.  The class
    declares ``cursor_shape = "beam"``: a text buffer reads best with the
    terminal's bar cursor, and the host reads the attribute off the focused
    leaf and passes it to :meth:`~motui.app.TUI.set_cursor_shape`.
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
        style: Style | None = None,
        caret_style: Style | None = None,
        theme: Theme | None = None,
        keymap: Keymap | None = None,
        focused: bool = True,
        max_rows: int | None = None,
        read_only: bool = False,
    ) -> None:
        super().__init__(
            text,
            placeholder=placeholder,
            style=style,
            caret_style=caret_style,
            theme=theme,
            keymap=keymap if keymap is not None else DEFAULT_EDITOR_KEYMAP,
            focused=focused,
            mask=mask,
            read_only=read_only,
        )
        self.max_rows = max_rows

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
