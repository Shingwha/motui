"""The modals page: ``Dialog``, ``Modal`` and ``Palette`` -- panels over the frame.

Three triggers, three dialogs, one routing slot: a danger confirm ("delete
the project?"), a one-line prompt and a plain confirm, each opened over the
frame's scrim by the :class:`~motui.interaction.modal.Modal` the page builds
for the visit.  The triggers are plain ``Button``s now: each slot carries the
:class:`~motui.demo.kit.Action` that opens its dialog, so which dialog a
button opens is data -- the retired ``Trigger`` subclass (a ``Button`` whose
``chosen`` was narrowed to the dialog's name) has no job left.  The page's
``modal`` field is the panel dispatcher below (the exhibit carries it), the
page's ``tick`` reads the closed dialog's result once -- ``escape``, a click
outside and the cancel button all land ``None``, so a value that reaches the
echo is the button that was taken -- and the page's ``leave`` detaches the
visit's panel: a per-visit overlay retires with the page it was built for.

The ``Palette`` moved in from the retired chrome page and rides the same
slot: its panel is the same ``Modal`` over its own query row.  Its rows that
name a page carry the ``Action`` that opens it (routing is data), so the one
row that only reports itself is the one that does not.
"""

from __future__ import annotations

from motui import Button, Modal, Option, Palette, Select, Text
from motui.widgets.dialog import confirm_dialog, prompt_dialog

from ..kit import Action, Exhibit
from ..page import PageBody

#: The page's dialogs by name: what a trigger's slot action resolves to.
NAMES: tuple[str, ...] = ("delete", "rename", "plain")


def palette_rows(pages) -> list[Option]:
    """The exhibit's rows: every page by name, then one row that only echoes."""
    return [
        *(Option(f"/{page.name}",
                 value=Action(page.name, page.description,
                              lambda s, p=page: s.show(p)),
                 description=page.description)
          for page in pages),
        Option("/say hello", value="say hello", description="echo this row's pick below"),
    ]


class _Panels:
    """The page's ``modal`` slot: whichever panel is open -- a dialog or the palette.

    The two panels have different owners (a ``Modal`` the page builds per
    dialog visit, the ``Palette`` mounted once for the visit) and the
    session routes **one** ``modal`` field: this dispatcher answers for both,
    sends every event to the open one and hands the cursor shape the
    palette's own query row.  ``detach`` is the visit's end: the dialog's
    overlay unregisters and the palette closes (``Palette`` exposes no
    ``detach``; a closed panel paints zero bytes).
    """

    __slots__ = ("dialog", "palette")

    def __init__(self, palette: Palette) -> None:
        self.dialog: Modal | None = None
        self.palette = palette

    @property
    def is_open(self) -> bool:
        return (
            (self.dialog is not None and self.dialog.is_open)
            or self.palette.is_open
        )

    @property
    def input(self):
        """The open panel's field: the palette's query row, when it is up."""
        return self.palette.input if self.palette.is_open else None

    def handle(self, event) -> bool:
        """Route one event to the open panel (the dialog first, then the palette)."""
        if self.dialog is not None and self.dialog.is_open:
            return self.dialog.handle(event)
        if self.palette.is_open:
            return self.palette.handle(event)
        return False

    def detach(self) -> None:
        """Retire the visit's panels: unregister the dialog, close the palette."""
        if self.dialog is not None:
            self.dialog.detach()
            self.dialog = None
        if self.palette.is_open:
            self.palette.close()


def page(session) -> PageBody:
    """The three triggers, their dialogs, the palette, the scrim and the echo."""
    theme = session.theme
    tui = session.tui
    exhibit = Exhibit(
        session,
        title="modal",
        blurb="Dialog and Modal -- a confirm, a prompt, the scrim behind them -- and the "
              "Palette over the same layer.",
        try_text="activate one of the three buttons below: the dialog rises over the dimmed "
                 "page, tab or the arrows walk its button row, enter takes the focused one "
                 "-- or open the palette and type",
        echo_label="last result",
    )
    delete = Button("Delete project", style=theme.error, theme=theme)
    rename = Button("Rename\u2026", theme=theme)
    plain = Button("plain confirm", theme=theme)
    opening = Select(
        [Option("open the palette", value="open the palette",
                description="its query row takes the keyboard; enter takes a row")],
        title="the Palette exhibit",
        theme=theme,
    )
    palette = Palette(tui, palette_rows(session.pages), theme=theme, max_rows=6)
    panels = _Panels(palette)
    exhibit.modal = panels
    # The page's own state: whether a dialog was open at the last beat the
    # tick saw (the result is read on the open -> closed edge: ``None`` is a
    # legal decision).
    state: dict = {"open": False}

    def dialog(name: str):
        """A fresh dialog for ``name`` -- a visit never inherits the last edit."""
        if name == "rename":
            return prompt_dialog("rename", placeholder="new name", theme=theme)
        if name == "plain":
            return confirm_dialog("and a plain confirmation?", theme=theme)
        return confirm_dialog(
            "delete the project?",
            danger=True,
            confirm_text="Delete",
            cancel_text="Cancel",
            theme=theme,
        )

    def open_dialog(name: str) -> None:
        """One trigger's action: raise the dialog for ``name`` over the scrim."""
        previous = panels.dialog
        if previous is not None:
            previous.detach()  # the last visit's overlay retires
        modal = Modal(tui, dialog(name), theme=theme)
        panels.dialog = modal
        state["open"] = True  # the beat sees the edge even after a quick escape
        modal.open()
        exhibit.echo.set(
            f"{name} -- escape, a click outside or the cancel button closes it", "opened")

    def open_palette() -> None:
        """The palette row's action: raise the panel over the scrim."""
        palette.open()
        exhibit.echo.set("open -- type to filter, enter takes a row", "palette")

    def tick() -> None:
        """One beat: a dialog that closed hands its result to the page's echo."""
        modal = panels.dialog
        opened = modal is not None and modal.is_open
        if state["open"] and not opened:
            result = modal.chosen
            modal.chosen = None  # the host reads the result exactly once
            exhibit.echo.set(
                "cancel -- nothing chosen" if result is None else f"chosen: {result!r}",
                "last result",
            )
        state["open"] = opened

    def leave(s) -> None:
        """The visit's panels are the visit's: they retire with the page."""
        panels.detach()
        state["open"] = False

    exhibit.tick = tick
    exhibit.leave = leave
    # The pick readout: the dialog's result and the palette's rows land here.
    exhibit.show(exhibit.echo)
    exhibit.section("three triggers -- one dialog each")
    exhibit.show(
        delete,
        action=Action("delete", "delete the project?", lambda s: open_dialog("delete")),
        api="confirm_dialog(message, danger=True, confirm_text=\u2026) -- the danger pair, "
            "focused on the cancel",
    ).focus()
    exhibit.show(
        rename,
        action=Action("rename", "rename", lambda s: open_dialog("rename")),
        api="prompt_dialog(title, placeholder=\u2026) -- a Dialog whose body is an "
            "Input; its enter reaches the buttons",
    ).focus()
    exhibit.show(
        plain,
        action=Action("plain", "a plain confirmation", lambda s: open_dialog("plain")),
        api="confirm_dialog(message) -- the plain pair",
    ).focus()
    exhibit.section("the Palette -- the same layer over its own query row")
    exhibit.show(
        opening,
        action=Action("open the palette", "the palette", lambda s: open_palette()),
        api="Palette(tui, commands) -- its own query Input over a Modal: opening it raises "
            "the scrim; a pick that names a page opens it",
    ).focus()
    exhibit.show(palette, note="palette")
    exhibit.section("what the Modal owns")
    exhibit.text("API \u00b7 Modal(tui, dialog) -- the overlay, the scrim, the placement and "
                 "the whole keyboard")
    exhibit.text(
        "The danger dialog opens focused on its cancel -- a stray return never lands "
        "the delete -- and its Delete button still takes enter once the cursor walks "
        "onto it. Escape is always the cancel, and a press outside the box dismisses "
        "with nothing chosen; the result reaches the echo line on the page's own beat."
    )
    return exhibit.build()
