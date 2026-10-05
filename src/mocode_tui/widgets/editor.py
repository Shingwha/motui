"""Editor component: a multi-line, cursor-editable text buffer rendered as rows.

The editing state -- the ``list[str]`` logical lines, the cursor, the
keymap routing, the wrapped-row geometry -- lives in one
:class:`~mocode_tui.widgets.textbuf.TextBuffer`; this module is the policy
shell: the placeholder, the ``max_rows`` sliding window, the per-component
default keymap and the resolved styles.  Unlike
:class:`~mocode_tui.widgets.input.Input`, the editor renders no prompt --
every visual row is a full-width wrap of its logical line -- and
``max_rows`` caps the rendered rows with a sliding window centred on the
cursor's visual row, so the block cursor never scrolls out of view.

The visual geometry is recomputed from the text with the very same wrap
rule the kernel uses (:func:`mocode_tui.core.text._wrap_spans`, shared
with :func:`mocode_tui.core.lines.wrap_line`), so up/down cursor movement
follows the wrapped rows the user actually sees.

Keys are routed by :meth:`handle_key` through the component's
:attr:`keymap` -- :data:`~mocode_tui.keys.keymap.DEFAULT_EDITOR_KEYMAP` by
default, which binds ``enter`` to ``newline``: **the editor itself consumes
the return key**.  A submit gesture is not a library binding; the host wires
one on an event the editor leaves unconsumed (``handle_key`` returns
``False`` for it), e.g. ``c-enter`` or ``escape``.

Styles resolve once, at construction, as explicit parameter > theme field
> :data:`~mocode_tui.core.theme.DEFAULT_THEME`, the same rule every
component follows.
"""

from __future__ import annotations

from ..core.events import Key, Paste
from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import DEFAULT_THEME, Theme
from ..keys.keymap import DEFAULT_EDITOR_KEYMAP, Keymap
from .textbuf import TextBuffer

__all__ = ["Editor"]


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
        "_buf",
        "_cursor_style",
        "_dim",
        "_style",
        "cursor_style",
        "focused",
        "max_rows",
        "placeholder",
        "style",
        "theme",
    )

    def __init__(
        self,
        *,
        text: str = "",
        placeholder: str = "",
        style: Style | None = None,
        cursor_style: Style | None = None,
        theme: Theme | None = None,
        keymap: Keymap | None = None,
        focused: bool = True,
        max_rows: int | None = None,
    ) -> None:
        self.placeholder = placeholder
        self.style = style
        self.cursor_style = cursor_style
        self.theme = theme
        self.focused = focused
        self.max_rows = max_rows
        self._buf = TextBuffer(
            text, keymap=keymap if keymap is not None else DEFAULT_EDITOR_KEYMAP
        )
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        base = theme or DEFAULT_THEME
        self._style = style if style is not None else NONE
        self._cursor_style = cursor_style if cursor_style is not None else base.cursor
        self._dim = base.dim

    # -- buffer views -----------------------------------------------------------

    @property
    def keymap(self) -> Keymap:
        """The table :meth:`handle_key` routes through."""
        return self._buf.keymap

    @keymap.setter
    def keymap(self, value: Keymap) -> None:
        self._buf.keymap = value

    @property
    def value(self) -> str:
        """The full buffer text, logical lines joined by ``"\\n"``."""
        return self._buf.value

    @property
    def lines(self) -> list[str]:
        """The logical lines the buffer is split into."""
        return self._buf.lines

    @lines.setter
    def lines(self, value: list[str]) -> None:
        self._buf.lines = value

    @property
    def row(self) -> int:
        """The cursor's logical line index."""
        return self._buf.row

    @property
    def col(self) -> int:
        """The cursor's character offset inside line :attr:`row`."""
        return self._buf.col

    @property
    def cursor(self) -> tuple[int, int]:
        """The cursor as ``(row, col)``."""
        return self._buf.row, self._buf.col

    # -- editing --------------------------------------------------------------

    def handle_key(self, key: Key | Paste) -> bool:
        """Route one event through :attr:`keymap`; ``True`` when consumed.

        Same routing as :meth:`~mocode_tui.widgets.input.Input.handle_key`:
        a :class:`~mocode_tui.core.events.Paste` inserts its text; a
        :class:`~mocode_tui.core.events.Key` whose ``char`` is set -- a
        printable, ``space`` included -- is inserted directly, so printables
        never need a keymap entry; otherwise the event's ``name`` is looked
        up in :attr:`keymap` and the same-named no-argument editing method
        runs (the default table maps ``enter`` to :meth:`newline`).  The
        wrap geometry ``move_up``/``move_down`` follow comes from the width
        of the last :meth:`render` call (80 before the first render).

        Returns ``False`` for every event the buffer does not consume -- a
        name unbound in the keymap -- leaving the host free to route it.  A
        submit gesture is one such event: no library keymap binds it.
        """
        return self._buf.handle_key(key)

    def insert(self, text: str) -> None:
        """Insert ``text`` (may contain newlines) at the cursor."""
        self._buf.insert(text)

    def backspace(self) -> bool:
        """Delete the character before the cursor; merges the line above."""
        return self._buf.backspace()

    def delete(self) -> bool:
        """Delete the character at the cursor; merges the line below."""
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
        rows = self._buf.visual_rows(width)
        index, _column = self._buf.locate(rows)
        return self._buf.cursor_position(width, 0, self._window_start(len(rows), index))

    # -- rendering ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        self._buf.last_width = width
        rows = self._buf.visual_rows(width)
        cursor_index, cursor_column = self._buf.locate(rows)
        start = self._window_start(len(rows), cursor_index)
        shown = rows if self.max_rows is None else rows[start : start + max(self.max_rows, 0)]
        placeholder_mode = self._buf.empty and self.focused
        out: list[Line] = []
        for offset, row in enumerate(shown):
            index = start + offset
            if placeholder_mode:  # empty + focused: the first row is unique
                body = self._buf.placeholder_body(
                    len(self.placeholder),
                    width,
                    self.placeholder,
                    self._dim,
                    self._cursor_style,
                    self._style,
                )
            elif self.focused and index == cursor_index:
                body = self._buf.cursor_body(
                    row.text, cursor_column, width, self._style, self._cursor_style
                )
            else:
                body = [Segment(row.text, self._style)] if row.text else []
            out.append(Line(body).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Editor({self._buf.value!r}, cursor=({self._buf.row}, {self._buf.col}))"
