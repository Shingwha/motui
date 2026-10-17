"""The input page: ``Input``, ``Editor``, ``ComboBox`` and ``Autocomplete``.

A click inside an ``Editor`` docks the block cursor on the cell the hit
test resolved, because a field is written into rather than activated.  The
ComboBox exhibit is the one place the demo opens a dropdown: the row above
the field opens it and the dropdown itself is painted by a
:class:`~motui.interaction.modal.Modal` over the frame -- the recipe the
component's own docstring carries, composed here by :class:`_ComboHost`,
which gives the combo the keyboard before the modal and keeps the two open
states in step.  The demo keeps no text input of its own: the only typing
happens in the two query rows the shell owns (``c-f``'s search and the
chrome page's palette) and in the ComboBox's own field while its dropdown
is open."""

from __future__ import annotations

from motui import Editor, FocusRing, Input, Modal, Option, Select, Text
from motui.widgets import Autocomplete, ComboBox

from ..page import PageBody, api_note, header, section, try_line

#: The dropdown's candidates: the fields and menus the page is about.
COMBO_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Autocomplete", "the filter layer of the menu family"),
    ("Checkbox", "a toggle that reads as one row"),
    ("ComboBox", "this component"),
    ("Dialog", "the modal's pure component"),
    ("Editor", "the multi-line buffer"),
    ("Input", "the single-line field"),
    ("Select", "the menu base"),
    ("Table", "the data grid"),
)

#: The frame cell the dropdown hangs from: one row under the ComboBox field
#: at the headless geometry both the golden frames and the replay use.
DROP_ANCHOR: tuple[int, int] = (19, 22)


class _ComboHost:
    """The page's ``modal`` slot: the combo's keys first, its modal behind.

    The host half of the ComboBox's documented recipe: the
    :class:`~motui.interaction.modal.Modal` mounted over ``combo.list``
    paints the dropdown under the field, :meth:`handle` gives the combo the
    keyboard first and the modal everything the combo declined (the mouse,
    the click outside, the swallow), and the two open states are kept in
    step -- so a dismissal outside the panel closes the dropdown with it.
    The session routes the page's ``modal`` field, and this object is what
    that field points at.
    """

    __slots__ = ("combo", "modal")

    def __init__(self, tui, combo: ComboBox, anchor: tuple[int, int]) -> None:
        self.combo = combo
        self.modal = Modal(tui, combo.list, anchor=anchor)

    @property
    def input(self):
        """The dropdown's field: the cursor shape an open combo asks for."""
        return self.combo.input

    @property
    def is_open(self) -> bool:
        return self.modal.is_open

    def open(self) -> None:
        """Open the dropdown and its modal together (one visit, both halves)."""
        self.combo.open()
        self.modal.open()

    def handle(self, event) -> bool:
        """The combo first, the modal behind it; the open states synced after."""
        if self.combo.handle(event):
            self._sync()
            return True
        consumed = self.modal.handle(event)
        self._sync()
        return consumed

    def detach(self) -> None:
        """Retire the visit's overlay and close the dropdown with it."""
        self.modal.detach()
        self.combo.close()

    def _sync(self) -> None:
        """Follow whichever half closed: one shut half is one shut dropdown.

        Either half can close itself -- the combo on ``enter``/``escape``,
        the modal on a press outside its panel -- and a dismissal is not a
        reopen: the half that closed takes the other with it.
        """
        if self.combo.is_open and self.modal.is_open:
            return
        self.combo.close()
        self.modal.close()


def page(session) -> PageBody:
    """The fields in their states, the masked one, and the combo's dropdown."""
    theme = session.theme
    hint_only = Input(placeholder="an empty Input: the hint and the cursor block", theme=theme)
    plain = Input(prompt="$ ", theme=theme, focused=False)
    plain.insert("focused=False renders the text plainly, without a cursor")
    secret = Input(mask="\u2022", prompt="password \u276f ", theme=theme)
    secret.insert("s3cret")
    combo = ComboBox(
        [Option(label, description=why) for label, why in COMBO_OPTIONS],
        text="Dia",
        theme=theme,
    )
    host = _ComboHost(session.tui, combo, DROP_ANCHOR)
    opening = Select(
        [Option("open the composer", value="open the composer",
                description="the dropdown rides a Modal")],
        title="the ComboBox exhibit",
        theme=theme,
    )
    combo_echo = Text("combo: closed", style=theme.dim)
    editor = Editor(
        text="the Editor\ncarries a block cursor\nand wraps long lines at the pane edge",
        theme=theme,
    )
    windowed = Editor(text="\n".join(f"row {i:02d}" for i in range(1, 13)), max_rows=5, theme=theme)
    filtered = Autocomplete(
        options=[Option("/help", value="/help", description="this command list"),
                 Option("/theme", value="/theme", description="the next theme variant"),
                 Option("/find", value="/find", description="the search row over the page"),
                 Option("/quit", value="/quit", description="leave the demo")],
        theme=theme,
    )
    filtered.set_query("/h")

    def note(text: str) -> None:
        """One report was handed in: open the dropdown, or echo it."""
        if text.removeprefix("chosen: ").strip("'") == "open the composer":
            host.open()
            combo_echo.text = "combo: open -- type to filter, \u2191\u2193 walk, enter takes the label"
            return
        combo_echo.text = text

    def leave(s) -> None:
        """The dropdown is per-visit: its modal retires with the page."""
        host.detach()

    return PageBody([
        *header("input",
                "Input, Editor, ComboBox and Autocomplete -- the text fields, and what a "
                "click does to them.", theme),
        try_line("click any cell in the two Editor blocks below: the block cursor lands there; "
                 "hover a field and the whole row takes the hover band -- and activate the row "
                 "above the composer to open its dropdown", theme),
        section("Input -- an empty focused one, and a plain one", theme),
        hint_only,
        plain,
        section("Input -- mask: the display-only secret field", theme),
        secret,
        api_note("Input(mask='\u2022') -- every rendered character is the mask's glyph; "
                 ".text stays plain", theme),
        section("ComboBox -- pick from the dropdown, or type and narrow it", theme),
        opening,
        combo,
        combo_echo,
        api_note("ComboBox(options, text=\u2026) -- Modal(tui, combo.list, anchor=\u2026) paints "
                 "the dropdown one row under the field", theme),
        section("Editor -- \u2191\u2193 move the block cursor, a click places it", theme),
        editor,
        api_note("TextBuffer.place(row, col) -- a click docks the cursor on the cell it hit", theme),
        section("Editor -- a max_rows window over a twelve-row buffer, click any row", theme),
        windowed,
        section("Autocomplete -- a query narrows the rows; enter takes the match", theme),
        filtered,
        api_note("Autocomplete -- the host sets the query; enter lands the matching row in chosen",
                 theme),
        Text("The demo's own typing happens in the shell's two query rows -- c-f's search and "
             "the chrome page's palette -- and in the ComboBox above while its dropdown is "
             "open; a keystroke typed at the shell never reaches these fields.", style=theme.dim),
    ], focus=FocusRing([editor, windowed, filtered, opening]), note=note, leave=leave,
       modal=host)
