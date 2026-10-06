"""Input component: a prompt-led text field rendered as rows.

The editing state -- the text, the cursor, the keymap routing, the
wrapped-row geometry -- lives in one
:class:`~mocode_tui.widgets.textbuf.TextBuffer`, and the shared editing
shell -- buffer composition, event routing, the render trunk -- in
:class:`~mocode_tui.widgets.field._TextField`; this module is the policy
shell: the prompt, the placeholder, the focused flag and the resolved
styles.  The prompt is shown on the first visual row only; continuation
rows are indented by the prompt's width, so the text area wraps at
``width - visible_width(prompt)``.

No key is read here: the host feeds events to :meth:`Input.handle`,
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

from ..core.lines import Segment
from ..core.style import Style
from ..core.text import visible_width
from ..core.theme import Theme
from ..keys.keymap import DEFAULT_INPUT_KEYMAP, Keymap
from .field import _TextField

__all__ = ["Input"]


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
    > :data:`~mocode_tui.core.theme.DEFAULT_THEME`.  ``keymap`` (default
    :data:`~mocode_tui.keys.keymap.DEFAULT_INPUT_KEYMAP`) is the table
    :meth:`handle` routes through; it carries no ``enter`` binding, so
    the return key reaches the host untouched.
    """

    __slots__ = ("_prompt", "_prompt_style")

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
        single-line view of the buffer position (a pasted newline stays in
        the text but adds no row to the field's line).
        """
        return 0, self._buf.offset

    # -- rendering ---------------------------------------------------------------

    def _indent(self) -> int:
        return visible_width(self._prompt)

    def _row_prefix(self, index: int, indent: int) -> Segment:
        if index == 0:
            return Segment(self._prompt, self._prompt_style)
        return Segment(" " * indent)
