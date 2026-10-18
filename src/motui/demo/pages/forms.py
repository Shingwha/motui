"""The forms page: ``Input``, ``Editor``, ``ComboBox``, ``Autocomplete`` and the menu family.

The fields first, then the menus: a click inside an ``Editor`` docks the
block cursor on the cell the hit test resolved, because a field is written
into rather than activated.  The ComboBox exhibit is the one place the demo
opens a dropdown: the row above the field opens it -- an ``Action`` on its
slot, so the page's routing is data -- and the dropdown itself is painted by
a :class:`~motui.interaction.modal.Modal` over the frame, the recipe the
component's own docstring carries, composed here by :class:`_ComboHost`,
which gives the combo the keyboard before the modal and keeps the two open
states in step (the kit has no vocabulary for a two-tier keyboard, so the
recipe's host stays page-local and only its open/close road is an action).
Below the fields stand the menus the retired choice page brought: a windowed
``Select``, the ``Radio`` and ``CheckGroup`` groups and the form control
``Select(commit=True)``.  The demo keeps no text input of its own: the only
typing happens in the two query rows the shell owns (``c-f``'s search and
the palette's) and in the ComboBox's own field while its dropdown is open."""

from __future__ import annotations

from motui import Editor, Input, Modal, Option, Select
from motui.widgets import Autocomplete, CheckGroup, ComboBox, Radio

from ..kit import Action, Exhibit
from ..page import PageBody

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
    The exhibit's ``modal`` field carries this object; the page's ``Action``
    is what opens it (the old string-named dispatch is gone).
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
    """The fields in their states, the combo's dropdown, then the menu family."""
    theme = session.theme
    exhibit = Exhibit(
        session,
        title="forms",
        blurb="Input, Editor, ComboBox and Autocomplete -- the text fields, and what a click "
              "does to them -- plus the menu family: Select, Radio and CheckGroup.",
        echo_label="last pick",
    )
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
    menu = Select(
        [Option(f"option {i:02d}", value=f"option {i:02d}",
                description=f"the description of row {i}")
         for i in range(1, 21)],
        max_rows=6,
        theme=theme,
    )
    menu.index = 11  # mid-list: the window and its (12/20) counter both show
    radio = Radio(["fast", "balanced", "thorough"], index=1, theme=theme)
    checks = CheckGroup(["the kernel", "the widgets", "the interaction tiers"],
                        marked=[0], theme=theme)  # a visible mark on arrival
    commit = Select(
        [Option(f"commit target {i}", value=f"target {i}") for i in range(1, 4)],
        title="Select(commit=True)",
        commit=True,
        theme=theme,
    )

    def open_combo() -> None:
        """The composer row's action: open the dropdown, and say so on the echo."""
        host.open()
        exhibit.echo.set("open -- type to filter, \u2191\u2193 walk, enter takes the label",
                         "combo")

    def leave(s) -> None:
        """The dropdown is per-visit: its modal retires with the page."""
        host.detach()

    exhibit.modal = host
    exhibit.leave = leave

    exhibit.section(
        "input -- an empty focused one, and a plain one",
        hint_only,
        plain,
        caption="placeholder \u00b7 focused=False renders the text plainly",
        draft=True,
    )
    exhibit.section("input -- mask: the display-only secret field", secret,
                    caption="every rendered character is the mask's glyph", draft=True)
    exhibit.section("combo box -- pick from the dropdown, or type and narrow it")
    # The row opens the dropdown through its slot's action; the echo line under
    # the field answers the open (and every pick the dropdown lands).
    exhibit.show(
        opening,
        action=Action("open the composer", "the composer", lambda s: open_combo()),
    )
    exhibit.show(combo)
    exhibit.show(exhibit.echo)
    exhibit.caption("the dropdown rides a Modal, one row under the field")
    exhibit.section("editor -- \u2191\u2193 move the block cursor, a click places it", editor,
                    caption="a click docks the cursor on the cell it hit", draft=True)
    exhibit.section("editor -- a max_rows window over a twelve-row buffer", windowed,
                    caption="12 rows \u00b7 5 visible", draft=True)
    exhibit.section("autocomplete -- a query narrows the rows; enter takes the match", filtered,
                    caption="query '/h' \u00b7 enter lands the matching row", draft=True)
    exhibit.section("select -- 20 rows, 6 visible, a counter under the window", menu,
                    caption="20 rows \u00b7 6 visible \u00b7 the host reads the pick once",
                    draft=True)
    exhibit.section("radio -- one selection; a step or a click is the pick", radio,
                    caption="fast \u00b7 balanced \u00b7 thorough", draft=True)
    exhibit.section("checkgroup -- the multiple selection: enter flips the cursor row's mark",
                    checks, caption="one row marked on arrival", draft=True)
    exhibit.section("select(commit=True) -- the form control: the cursor is the choice", commit,
                    caption="a step or a click writes the row into chosen", draft=True)
    # The ring, in the old input page's order first: the fields the page opens
    # on (an Editor holds the beam cursor), then the menu family's four.
    exhibit.focus(editor, windowed, filtered, opening, menu, radio, checks, commit)
    return exhibit.build()
