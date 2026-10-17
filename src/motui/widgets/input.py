"""Input component: a prompt-led text field rendered as rows.

The editing state -- the text, the cursor, the keymap routing, the
wrapped-row geometry -- lives in one
:class:`~motui.widgets.textbuf.TextBuffer`, and the shared editing
shell -- buffer composition, event routing, the render trunk -- in
:class:`~motui.widgets.field._TextField`; this module is the policy
shell: the prompt, the placeholder, the focused flag and the resolved
styles.  The prompt is shown on the first visual row only; continuation
rows are indented by the prompt's width, so the text area wraps at
``width - visible_width(prompt)``.

No key is read here: the host feeds events to :meth:`Input.handle`,
which routes them through the component's :attr:`keymap`
(:data:`~motui.keys.keymap.DEFAULT_INPUT_KEYMAP` unless overridden) and
returns ``False`` for every key it leaves to the host's own routing.  The
wrap geometry comes from the width of the last :meth:`render` call (80
before the first render), so up/down cursor movement follows the wrapped
rows the user sees.  A pure :meth:`Input.cursor_position` reports where
the block cursor sits in the rendered rows, for hosts that park the
terminal cursor there (an IME anchor on a real console).

One policy is the input shell's own: a
:class:`~motui.core.events.Paste` entering a **single-line** field has
every run of newlines folded into one space (:meth:`Input.handle`), so a
pasted paragraph stays one row.  The editor's paste path keeps its
newlines, and so does an explicit :meth:`Input.insert`.
"""

from __future__ import annotations

import re

from ..core.events import Key, Paste
from ..core.lines import Segment
from ..core.style import Style
from ..core.text import visible_width
from ..core.theme import Theme
from ..keys.keymap import DEFAULT_INPUT_KEYMAP, Keymap
from .field import _TextField

__all__ = ["Input"]

#: A run of newlines -- ``\r\n``, ``\r`` or ``\n``, consecutive included --
#: folded into one space when a paste reaches a single-line field.
_NEWLINE_RUN = re.compile(r"(?:\r\n|\r|\n)+")


class Input(_TextField):
    """A prompt-led text field with a reverse-video block cursor.

    ``focused=False`` renders the text plainly (no cursor); an empty focused
    field shows ``placeholder`` in a dim style, with no cursor cell riding it
    -- the block appears with the first typed character.  The cursor is drawn
    by re-styling the character under it as ``style.merge(cursor_style)``, or,
    at a row end, by appending a reverse-video space -- skipped when the row
    is already full so no row ever exceeds ``width``.  ``prompt_style``,
    ``cursor_style`` and the placeholder's dim style resolve once, at
    construction, as explicit > theme field (``accent``/``cursor``/``dim``)
    > :data:`~motui.core.theme.DEFAULT_THEME`.  ``keymap`` (default
    :data:`~motui.keys.keymap.DEFAULT_INPUT_KEYMAP`) is the table
    :meth:`handle` routes through; it carries no ``enter`` binding, so
    the return key reaches the host untouched.  A multi-line ``Paste`` is
    folded into the single line at :meth:`handle`: a paste fills a field,
    and a field whose keymap cannot even bind ``enter`` must not let the
    paste smuggle in a row break.  ``hover`` is the pointer tier's
    block-level band: while it is ``True`` every rendered row (prompt
    included) merges the theme's ``hover``; there is no row-level
    ``hover_at`` -- a text row has no sub-row items to mark.  The class
    declares ``cursor_shape = "beam"``: a text field reads best with the
    terminal's bar cursor, and the host reads the attribute off the focused
    leaf and passes it to :meth:`~motui.app.TUI.set_cursor_shape`.
    """

    __slots__ = ("_prompt", "_prompt_style")

    #: The DECSCUSR shape a focused single-line field asks the host for.
    cursor_shape = "beam"

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
        super().__init__(
            placeholder=placeholder,
            style=style,
            cursor_style=cursor_style,
            theme=theme,
            keymap=keymap if keymap is not None else DEFAULT_INPUT_KEYMAP,
            focused=focused,
        )
        self._prompt_style = self._pick(prompt_style, "accent")
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

    def handle(self, event: Key | Paste) -> bool:
        """Consume an event; a paste's newline runs fold into single spaces.

        The one policy this shell adds over the shared routing: a
        :class:`~motui.core.events.Paste` entering a single-line field
        has every run of ``\\r\\n`` / ``\\r`` / ``\\n`` -- consecutive empty
        lines included -- collapsed to one space before the buffer sees it,
        so a multi-line paste is one input row and nothing about it can
        submit.  Everything else routes through the shared shell; the
        editor's paste path and an explicit :meth:`insert` keep their
        newlines.
        """
        if isinstance(event, Paste):
            event = Paste(_NEWLINE_RUN.sub(" ", event.text))
        return super().handle(event)

    # -- rendering ---------------------------------------------------------------

    def _indent(self) -> int:
        return visible_width(self._prompt)

    def _row_prefix(self, index: int, indent: int) -> Segment:
        if index == 0:
            return Segment(self._prompt, self._prompt_style)
        return Segment(" " * indent)
