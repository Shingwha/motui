"""Input component: a prompt-led text field rendered as rows.

The editing state -- the text, the cursor, the keymap routing, the
wrapped-row geometry -- lives in one
:class:`~mocode_tui.widgets.textbuf.TextBuffer`; this module is the policy
shell: the prompt, the placeholder, the focused flag and the resolved
styles.  The prompt is shown on the first visual row only; continuation
rows are indented by the prompt's width, so the text area wraps at
``width - visible_width(prompt)``.

No key is read here: the host feeds events to :meth:`Input.handle_key`,
which routes them through the component's :attr:`keymap`
(:data:`~mocode_tui.keys.keymap.DEFAULT_INPUT_KEYMAP` unless overridden) and
returns ``False`` for every key it leaves to the host's own routing.  The
wrap geometry comes from the width of the last :meth:`render` call (80
before the first render), so up/down cursor movement follows the wrapped
rows the user sees.  A pure :meth:`Input.cursor_position` reports where
the block cursor sits in the rendered rows, for hosts that park the
terminal cursor there (an IME anchor on a real console).
"""

from __future__ import annotations

from ..core.events import Key, Paste
from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import visible_width
from ..core.theme import DEFAULT_THEME, Theme
from ..keys.keymap import DEFAULT_INPUT_KEYMAP, Keymap
from .textbuf import TextBuffer

__all__ = ["Input"]


class Input:
    """A prompt-led text field with a reverse-video block cursor.

    ``focused=False`` renders the text plainly (no cursor); an empty focused
    field shows ``placeholder`` in a dim style.  The cursor is drawn by
    re-styling the character under it as ``style.merge(cursor_style)``, or,
    at a row end, by appending a reverse-video space -- skipped when the row
    is already full so no row ever exceeds ``width``.  ``prompt_style``,
    ``cursor_style`` and the placeholder's dim style resolve once, at
    construction, as explicit > theme field (``accent``/``cursor``/``dim``)
    > :data:`~mocode_tui.core.theme.DEFAULT_THEME`.  ``keymap`` (default
    :data:`~mocode_tui.keys.keymap.DEFAULT_INPUT_KEYMAP`) is the table
    :meth:`handle_key` routes through; it carries no ``enter`` binding, so
    the return key reaches the host untouched.
    """

    __slots__ = (
        "_buf",
        "_cursor_style",
        "_dim",
        "_prompt_style",
        "_style",
        "cursor_style",
        "focused",
        "placeholder",
        "prompt",
        "prompt_style",
        "style",
        "theme",
    )

    def __init__(
        self,
        *,
        prompt: str = "\u276e ",
        placeholder: str = "",
        style: Style | None = None,
        prompt_style: Style | None = None,
        cursor_style: Style | None = None,
        focused: bool = True,
        theme: Theme | None = None,
        keymap: Keymap | None = None,
    ) -> None:
        self.prompt = prompt
        self.placeholder = placeholder
        self.style = style
        self.prompt_style = prompt_style
        self.cursor_style = cursor_style
        self.focused = focused
        self.theme = theme
        self._buf = TextBuffer(keymap=keymap if keymap is not None else DEFAULT_INPUT_KEYMAP)
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        base = theme or DEFAULT_THEME
        self._style = style if style is not None else NONE
        self._prompt_style = prompt_style if prompt_style is not None else base.accent
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
    def text(self) -> str:
        """The whole field text (a multi-line paste keeps its newlines)."""
        return self._buf.value

    @property
    def cursor(self) -> int:
        """The cursor as a character offset into :attr:`text`."""
        return self._buf.offset

    @cursor.setter
    def cursor(self, value: int) -> None:
        self._buf.offset = value

    # -- editing --------------------------------------------------------------

    def handle_key(self, key: Key | Paste) -> bool:
        """Route one event through :attr:`keymap`; ``True`` when consumed.

        Same routing as the engine: a
        :class:`~mocode_tui.core.events.Paste` inserts its text, a printable
        :class:`~mocode_tui.core.events.Key` inserts its ``char`` directly,
        and any other event's ``name`` is looked up in :attr:`keymap` and
        runs the same-named editing method.  The wrap geometry
        ``move_up``/``move_down`` follow comes from the width of the last
        :meth:`render` call (80 before the first render), not from this
        call, so a host that never rendered yet moves inside a
        default-width geometry.

        Returns ``False`` for every event the field does not consume (a
        name unbound in the keymap, ``enter`` included): the host then
        routes it -- submit, palette, quit -- itself.
        """
        return self._buf.handle_key(key, visible_width(self.prompt))

    def insert(self, text: str) -> None:
        """Insert ``text`` (may contain newlines) at the cursor."""
        self._buf.insert(text)

    def backspace(self) -> bool:
        """Delete the character before the cursor; False at the start."""
        return self._buf.backspace()

    def delete(self) -> bool:
        """Delete the character at the cursor; False at the end."""
        return self._buf.delete()

    def clear(self) -> None:
        """Drop all text and park the cursor at the start."""
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
        return self._buf.move_up(visible_width(self.prompt))

    def move_down(self) -> bool:
        """Move to the next visual row, keeping the inner column."""
        return self._buf.move_down(visible_width(self.prompt))

    # -- visual geometry -------------------------------------------------------

    def cursor_position(self, width: int) -> tuple[int, int]:
        """The cursor cell as ``(visual_row, col)`` of a ``render(width)``.

        The geometry comes from the same wrap rule the render uses, so the
        reported cell is exactly the cell the render paints as the block
        cursor: the character under the cursor, or the reverse-video space
        at a row end.

        ``col`` is the 0-based cell offset from the row's left edge -- row 0
        counts the prompt's width, continuation rows indent by it.  An empty
        field reports the prompt-width column (where the cursor space is
        painted).  A row that is exactly full has no cell past its edge, so
        the cursor clamps to the row's last cell.  The result always lands
        inside ``render(width)``: ``0 <= visual_row < len(render(width))`` and
        ``0 <= col < max(1, width)``.

        Pure query: no state changes, no rendering.
        """
        return self._buf.cursor_position(width, visible_width(self.prompt))

    # -- rendering ---------------------------------------------------------------

    def render(self, width: int) -> list[Line]:
        self._buf.last_width = width
        prompt_width = visible_width(self.prompt)
        rows = self._buf.visual_rows(width, prompt_width)
        cursor_index, cursor_column = self._buf.locate(rows)
        inner = max(0, width - prompt_width)
        placeholder_mode = self._buf.empty and self.focused
        out: list[Line] = []
        for index, row in enumerate(rows):
            if index == 0:
                prefix = Segment(self.prompt, self._prompt_style)
            else:
                prefix = Segment(" " * prompt_width)
            if placeholder_mode:  # empty + focused: the first row is unique
                body = self._buf.placeholder_body(
                    0, inner, self.placeholder, self._dim, self._cursor_style, self._dim
                )
            elif self.focused and index == cursor_index:
                body = self._buf.cursor_body(
                    row.text, cursor_column, inner, self._style, self._cursor_style
                )
            else:
                body = [Segment(row.text, self._style)] if row.text else []
            out.append(Line((prefix, *body)).fit(width))
        return out

    def __repr__(self) -> str:
        return f"Input({self._buf.value!r}, cursor={self._buf.offset})"
