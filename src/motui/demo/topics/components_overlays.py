"""Overlay topics: Dialog, Modal, CommandPalette, Toasts, Tooltip and Stats."""

from __future__ import annotations

from motui import (
    Button,
    Option,
    Checkbox,
    Dialog,
    Input,
    Link,
    Modal,
    Text,
)
from motui.app import CommandPalette
from motui.widgets import ButtonSpec, Notice

from ..stage import topic


def _dialog(b) -> None:
    danger = Dialog(
        "Delete project?",
        Text("This cannot be undone."),
        ["Cancel", ButtonSpec("Delete", True, danger=True)],
        danger=True,
        theme=b.theme,
    )
    b.preview(danger)
    b.variants(
        ("plain", Dialog("Rename", Input("demo", theme=b.theme), ["Cancel", "Rename"], theme=b.theme)),
        ("wide", Dialog("About", Text("motui 1.2"), ["OK"], width=36, theme=b.theme)),
    )
    b.focus(danger)
    echo = b.echo("result")

    def note(report) -> None:
        if report.source is danger:
            echo.set(report.value)

    b.note(note)


def _modal(b) -> None:
    dialog = Dialog(
        "Ship the release?",
        Text("The panel centres itself and dims the frame behind it."),
        ["Cancel", ButtonSpec("Ship", "shipped")],
        theme=b.theme,
    )
    modal = Modal(b.session.tui, dialog, theme=b.theme)
    opener = Button("Open modal", theme=b.theme)
    opener.hint = "raise the panel over the scrim"
    b.preview(opener)
    b.modal(modal)
    b.focus(opener)
    echo = b.echo("result")

    def note(report) -> None:
        if report.source is opener:
            modal.open()
        elif report.source is modal:
            echo.set(report.value)

    b.note(note)


def _palette(b) -> None:
    palette = CommandPalette(
        b.session.tui,
        [
            Option("say hello", "say hello"),
            Option("open settings", "open settings"),
            Option("show logs", "show logs"),
            Option("quit demo", "quit demo"),
        ],
        theme=b.theme,
        max_rows=5,
    )
    opener = Button("Open palette", theme=b.theme)
    opener.hint = "a local palette, not the global /"
    b.preview(opener)
    b.modal(palette)
    b.focus(opener)
    echo = b.echo("picked")

    def note(report) -> None:
        if report.source is opener:
            palette.open()
        elif report.source is palette:
            echo.set(report.value)

    b.note(note)


def _toasts(b) -> None:
    info = Button("Info toast", theme=b.theme)
    warn = Button("Warning toast", theme=b.theme)
    error = Button("Error toast", theme=b.theme)
    b.preview(info, warn, error)
    b.focus(info, warn, error)

    def note(report) -> None:
        if report.source is info:
            b.session.toasts.show("saved", style=b.theme.overlays.toast)
        elif report.source is warn:
            b.session.toasts.show("disk almost full", style=b.theme.status.warning)
        elif report.source is error:
            b.session.toasts.show("connection lost", style=b.theme.status.danger)

    b.note(note)


def _tooltip(b) -> None:
    button = Button("Hover me", theme=b.theme)
    button.hint = "a Button's one-line hint"
    link = Link("hover the link", theme=b.theme)
    link.hint = "a Link's hint"
    check = Checkbox("hover the checkbox", theme=b.theme)
    check.hint = "a Checkbox's hint"
    b.preview(button, link, check)
    b.focus(button, link, check)


def _stats(b) -> None:
    opener = Button("Toggle stats", theme=b.theme)
    opener.hint = "or press c-g"
    b.preview(
        opener,
        Notice("The Stats box counts events and shows the pointer cell.", theme=b.theme),
        Text("Mount it with c-g; it rides the frame's overlay layer.", theme=b.theme),
    )
    b.focus(opener)

    def note(report) -> None:
        if report.source is opener:
            b.session.toggle_stats()

    b.note(note)


TOPICS = (
    topic(
        key="dialog",
        title="Dialog",
        summary="A framed panel with a title, a body and a button row; escape cancels.",
        group="Overlays",
        section="components",
        try_line="left/right choose a button; enter takes it; escape cancels with none",
        api_line="Dialog(title, body, buttons, *, danger, width) · handle() · take_result()",
        components=("Dialog", "ButtonSpec", "Button", "Text", "Input"),
        build=_dialog,
    ),
    topic(
        key="modal",
        title="Modal",
        summary="The blocking controller: a scrim, a placed panel and every event routed into it.",
        group="Overlays",
        section="components",
        try_line="click Open modal; choose with arrows/enter; esc or a click outside closes",
        api_line="Modal(tui, dialog, *, anchor, scrim, scrim_style, dismiss_on_click_outside, theme)",
        components=("Modal", "Dialog", "Button"),
        build=_modal,
    ),
    topic(
        key="palette",
        title="CommandPalette",
        summary="A query row over a filtered command list, painted by the modal layer.",
        group="Overlays",
        section="components",
        try_line="click Open palette; type to filter; up/down move; enter picks; esc cancels",
        api_line="CommandPalette(tui, commands, *, max_rows, theme) \u00b7 open() \u00b7 handle() \u00b7 take_result()",
        components=("CommandPalette", "Button"),
        build=_palette,
    ),
    topic(
        key="toasts",
        title="Toasts",
        summary="Transient notification rows in the frame's top-right corner.",
        group="Overlays",
        section="components",
        try_line="activate a button; each raises a toast; the stack auto-dismisses",
        api_line="Toasts(tui, *, ttl, max_shown, corner, style, theme) \u00b7 show(text, style=...)",
        components=("Toasts", "Button"),
        build=_toasts,
    ),
    topic(
        key="tooltip",
        title="Tooltip",
        summary="A one-row hint band under the pointer, read from the leaf's hint attribute.",
        group="Overlays",
        section="components",
        try_line="move the pointer over a row; its hint paints one row under the cell",
        api_line="Tooltip(tui, pointer, *, theme) \u00b7 reads pointer.hovered.hint",
        components=("Tooltip", "Button", "Link", "Checkbox"),
        build=_tooltip,
    ),
    topic(
        key="stats",
        title="Stats",
        summary="The dev readout: frames, events and the pointer cell, in a corner box.",
        group="Overlays",
        section="components",
        try_line="click Toggle stats or press c-g; the box counts every event that round",
        api_line="Stats(tui, *, pointer, theme) \u00b7 handle(event) counts \u00b7 detach() \u00b7 set_theme(theme)",
        components=("Stats", "Button", "Notice"),
        build=_stats,
    ),
)
