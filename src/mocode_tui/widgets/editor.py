"""Editor component: a multi-line, cursor-editable text buffer rendered as rows.

The editing state -- the ``list[str]`` logical lines, the cursor, the
keymap routing, the wrapped-row geometry -- lives in one
:class:`~mocode_tui.widgets.textbuf.TextBuffer`, and the shared editing
shell -- buffer composition, event routing, the render trunk -- in
:class:`~mocode_tui.widgets.field._TextField`; this module is the policy
shell: the placeholder, the ``max_rows`` sliding window, the per-component
default keymap and the resolved styles.  Unlike
:class:`~mocode_tui.widgets.input.Input`, the editor renders no prompt --
every visual row is a full-width wrap of its logical line -- and
``max_rows`` caps the rendered rows with a sliding window centred on the
cursor's visual row, so the block cursor never scrolls out of view.

The visual geometry is recomputed from the text with the very same wrap
rule the kernel uses (:func:`mocode_tui.core.text.wrap_spans`, shared
with :func:`mocode_tui.core.lines.wrap_line`), so up/down cursor movement
follows the wrapped rows the user actually sees.

Keys are routed by :meth:`handle` through the component's
:attr:`keymap` -- :data:`~mocode_tui.keys.keymap.DEFAULT_EDITOR_KEYMAP` by
default, which binds ``enter`` to ``newline``: **the editor itself consumes
the return key**.  A submit gesture is not a library binding; the host wires
one on an event the editor leaves unconsumed (``handle`` returns
``False`` for it), e.g. ``c-enter`` or ``escape``.

Styles resolve once, at construction, as explicit parameter > theme field
> :data:`~mocode_tui.core.theme.DEFAULT_THEME`, the same rule every
component follows.
"""

from __future__ import annotations

from ..core.style import Style
from ..core.theme import Theme
from ..keys.keymap import DEFAULT_EDITOR_KEYMAP, Keymap
from .field import _TextField

__all__ = ["Editor"]


class Editor(_TextField):
    """A multi-line text buffer with a reverse-video block cursor.

    ``text`` seeds the buffer (the cursor parks at its start);
    ``placeholder`` shows dim on the first row of an empty focused editor,
    with the cursor block trailing the hint exactly as on a typed row.
    ``focused=False`` renders the text plainly (no cursor, no placeholder).
    The cursor is drawn by re-styling the character under it as
    ``style.merge(cursor_style)``, or, at a row end, by appending a
    reverse-video space -- skipped when the row is already full so no row
    ever exceeds ``width``.  ``cursor_style`` and the placeholder's dim
    style fall back to the theme's ``cursor``/``dim`` when not given
    explicitly.  ``max_rows`` (``None`` = unlimited) caps the rendered rows
    with a sliding window that keeps the cursor's visual row visible.
    """

    __slots__ = ("max_rows",)

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
        super().__init__(
            text,
            placeholder=placeholder,
            style=style,
            cursor_style=cursor_style,
            theme=theme,
            keymap=keymap if keymap is not None else DEFAULT_EDITOR_KEYMAP,
            focused=focused,
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

    # -- rendering ---------------------------------------------------------------

    def _placeholder_column(self) -> int:
        """The cursor trails the hint; it does not paint over its first char."""
        return len(self.placeholder)

    def _placeholder_trail_style(self) -> Style:
        """The trailing cursor space shares the row's text style."""
        return self._style
