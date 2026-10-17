"""The modal page: ``Dialog`` and ``Modal`` -- a confirm, a prompt and the scrim.

Three triggers, three dialogs, one routing slot: a danger confirm ("delete
the project?"), a one-line prompt and a plain confirm, each opened over the
frame's scrim by the :class:`~motui.interaction.modal.Modal` the page builds
for the visit.  The page's ``modal`` field carries the modal that is open
(the session's ``_modal()`` query already reads that field), the page's
``tick`` reads the result once -- ``escape``, a click outside and the cancel
button all land ``None``, so a value that reaches the echo is the button that
was taken -- and the page's ``leave`` detaches it: a per-visit overlay
retires with the page it was built for.

The three triggers are one :class:`Trigger`, a :class:`~motui.Button`
whose pick carries the dialog's name: the host reads one ``chosen`` per
round, so the pick itself has to say which dialog it means.
"""

from __future__ import annotations

from motui import Button, FocusRing, Modal, Text
from motui.kernel.style import Style
from motui.kernel.theme import Theme
from motui.widgets.dialog import confirm_dialog, prompt_dialog

from ..page import PageBody, api_note, header, section, try_line

#: The page's dialogs by name: what a trigger's pick resolves to in ``note``.
NAMES: tuple[str, ...] = ("delete", "rename", "plain")


class Trigger(Button):
    """A Button whose pick names the dialog it opens (the page's dispatch).

    :attr:`chosen <Button.chosen>` is ``True`` on a plain button; the page's
    three triggers open three different dialogs through one
    ``chosen``-reading host, so this one lands its ``value`` instead -- the
    same narrowing :class:`~motui.widgets.choice.Radio` applies to
    ``Select.chosen``.
    """

    __slots__ = ("value",)

    def __init__(
        self,
        label: str,
        value: str,
        *,
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(label, style=style, theme=theme)
        self.value = value

    def click(self, row: int, col: int) -> bool:
        """Take a click anywhere on the row; the pick is the dialog's name."""
        super().click(row, col)
        self.chosen = self.value
        return True

    def activate(self) -> bool:
        """Take the activation (the Activable verb); the pick is the dialog's name."""
        super().activate()
        self.chosen = self.value
        return True


def page(session) -> PageBody:
    """The three triggers, their dialogs, the scrim and the echo line."""
    theme = session.theme
    tui = session.tui
    delete = Trigger("Delete project", "delete", style=theme.error, theme=theme)
    rename = Trigger("Rename\u2026", "rename", theme=theme)
    plain = Trigger("plain confirm", "plain", theme=theme)
    echo = Text("last result: --", style=theme.dim)
    # The page's own state: the modal built for the visit (``leave`` detaches
    # it) and whether it was open at the last beat the tick saw (the result
    # is read on the open -> closed edge: ``None`` is a legal decision).
    state: dict = {"modal": None, "open": False}

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

    def note(text: str) -> None:
        """One report: a trigger's pick opens its dialog; a result goes on the echo.

        ``body`` is the page's own body, bound below: the routing field the
        session reads has to follow the modal that is open, and the report
        that opens one arrives long after the body was built.
        """
        name = text.removeprefix("chosen: ").strip("'")
        if name not in NAMES:
            echo.text = f"last result: {text}"
            return
        previous = state["modal"]
        if previous is not None:
            previous.detach()  # the last visit's overlay retires
        modal = Modal(tui, dialog(name), theme=theme)
        state["modal"] = modal
        state["open"] = True  # the beat sees the edge even after a quick escape
        body.modal = modal  # the page's routing field follows the open modal
        modal.open()
        echo.text = f"opened {name} -- escape, a click outside or the cancel button closes it"

    def tick() -> None:
        """One beat: a modal that closed hands its result to the page's note."""
        modal = state["modal"]
        opened = modal is not None and modal.is_open
        if state["open"] and not opened:
            result = modal.chosen
            modal.chosen = None  # the host reads the result exactly once
            note("cancel: nothing chosen" if result is None else f"chosen: {result!r}")
        state["open"] = opened

    def leave(s) -> None:
        """The visit's modal is the visit's: its overlay retires with the page."""
        modal = state["modal"]
        if modal is not None:
            modal.detach()
        state["modal"] = None
        state["open"] = False

    # ``body`` is what ``note`` writes the open modal into; the closure reads
    # it at report time, always after this binding.
    body: PageBody = PageBody(
        [
            *header(
                "modal",
                "Dialog and Modal -- a confirm, a prompt and the scrim behind them.",
                theme,
            ),
            try_line(
                "activate one of the three buttons below: the dialog rises over the dimmed "
                "page, tab or the arrows walk its button row, enter takes the focused one",
                theme,
            ),
            echo,
            section("three triggers -- one dialog each", theme),
            delete,
            api_note("confirm_dialog(message, danger=True, confirm_text=\u2026) -- the danger "
                     "pair, focused on the cancel", theme),
            rename,
            api_note("prompt_dialog(title, placeholder=\u2026) -- a Dialog whose body is an "
                     "Input; its enter reaches the buttons", theme),
            plain,
            api_note("confirm_dialog(message) -- the plain pair", theme),
            section("what the Modal owns", theme),
            api_note("Modal(tui, dialog) -- the overlay, the scrim, the placement and the "
                     "whole keyboard", theme),
            Text(
                "The danger dialog opens focused on its cancel -- a stray return never lands "
                "the delete -- and its Delete button still takes enter once the cursor walks "
                "onto it. Escape is always the cancel, and a press outside the box dismisses "
                "with nothing chosen; the result reaches the echo line on the page's own beat.",
                style=theme.dim,
            ),
        ],
        focus=FocusRing([delete, rename, plain]),
        note=note,
        tick=tick,
        leave=leave,
    )
    return body
