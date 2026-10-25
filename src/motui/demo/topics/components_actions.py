"""Action topics: Button, Link, MenuBar and ContextMenu."""

from __future__ import annotations

from dataclasses import replace

from motui import Button, KeyEvent, Link, Modal, Option
from motui.kernel.glyphs import GLYPHS
from motui.widgets import ContextMenu, MenuBar

from ..stage import topic


class _MenuHost:
    """The ContextMenu recipe: the host routes keys, the Modal paints the menu."""

    __slots__ = ("menu", "modal")

    def __init__(self, menu: ContextMenu, modal: Modal) -> None:
        self.menu = menu
        self.modal = modal

    @property
    def is_open(self) -> bool:
        return self.modal.is_open

    def open(self) -> None:
        self.menu.select(0)
        self.modal.open()

    def close(self) -> None:
        self.modal.close()

    def detach(self) -> None:
        self.modal.detach()

    def handle(self, event) -> bool:
        if not self.modal.is_open:
            return False
        if isinstance(event, KeyEvent):
            if event.key == "down":
                self.menu.move(1)
                return True
            if event.key == "up":
                self.menu.move(-1)
                return True
            if event.key == "enter":
                if self.menu.on_action("activate"):
                    self.modal.close(self.menu.take())
                else:
                    self.modal.close()
                return True
            if event.key == "escape":
                self.modal.close()
                return True
        return self.modal.handle(event)

    def take(self) -> object | None:
        return self.modal.take()


def _button(b) -> None:
    ship = Button("Ship", theme=b.theme)
    ship.hint = "land the pending activation"
    plain = Button("Plain", theme=b.theme)
    disabled = Button("Disabled", disabled=True, theme=b.theme)
    b.preview(ship, plain, disabled)
    focused_button = Button("Focused", theme=b.theme)
    focused_button.focused = True
    b.variants(
        ("focused", focused_button),
        ("disabled", Button("Disabled", disabled=True, theme=b.theme)),
    )
    b.focus(ship, plain)
    echo = b.echo("activated")

    def note(report) -> None:
        if report.source in (ship, plain):
            echo.set(report.value)

    b.note(note)


def _link(b) -> None:
    link = Link("https://example.invalid", theme=b.theme)
    link.hint = "follow the pending link"
    b.preview(link, Link("a second link", theme=b.theme))
    focused_link = Link("focused link", theme=b.theme)
    focused_link.focused = True
    b.variants(
        ("focused", focused_link),
        ("disabled", Link("disabled link", disabled=True, theme=b.theme)),
    )
    b.focus(link)
    echo = b.echo("followed")

    def note(report) -> None:
        if report.source is link:
            echo.set(report.value)

    b.note(note)


def _menu_bar(b) -> None:
    menu = MenuBar(["File", "Edit", "View", "Help"], theme=b.theme)
    disabled = MenuBar(["File", "Edit", "View", "Help"], disabled_items=[2], theme=b.theme)
    b.preview(menu)
    b.variants(("disabled item", disabled), ("separator='\u00b7'", MenuBar(["File", "Edit"], glyphs=replace(GLYPHS, vertical_rule="\u00b7"), theme=b.theme)))
    b.focus(menu)
    echo = b.echo("label")

    def note(report) -> None:
        if report.source is menu:
            echo.set(report.value)

    b.note(note)


def _context_menu(b) -> None:
    menu = ContextMenu(
        [
            Option("Open", "open"),
            Option("Rename", "rename"),
            Option("Delete", "delete"),
        ],
        title="Actions",
        theme=b.theme,
    )
    host = _MenuHost(menu, Modal(b.session.tui, menu, anchor=(8, 6), theme=b.theme))
    opener = Button("Open context menu", theme=b.theme)
    opener.hint = "mount the menu over a modal"
    b.preview(menu, opener)
    b.modal(host)
    b.focus(menu, opener)
    echo = b.echo("chosen")

    def note(report) -> None:
        if report.source is opener:
            host.open()
        elif report.source is host or report.source is menu:
            echo.set(report.value)

    b.note(note)


TOPICS = (
    topic(
        key="button",
        title="Button",
        summary="The one-row action: click or activate, with hover and focus bands.",
        group="Actions",
        section="components",
        try_line="enter or click the focused button; the pending result is true",
        api_line="Button(label, *, style, hover_style, focus_style, disabled, focused, hint, theme)",
        components=("Button",),
        build=_button,
    ),
    topic(
        key="link",
        title="Link",
        summary="A clickable, activable text row in the link band with a pending follow.",
        group="Actions",
        section="components",
        try_line="enter or click follows the focused link; the result is true",
        api_line="Link(text, *, style, hover_style, focus_style, disabled, hint, theme)",
        components=("Link",),
        build=_link,
    ),
    topic(
        key="menu-bar",
        title="Menu bar",
        summary="One horizontal strip of section labels with one active label and a clamped cursor.",
        group="Actions",
        section="components",
        try_line="left/right move; enter takes the active label; click a label to select it",
        api_line="MenuBar(items, *, index, glyphs, disabled_items) · activate/take_result",
        components=("MenuBar",),
        build=_menu_bar,
    ),
    topic(
        key="context-menu",
        title="Context menu",
        summary="The Select preset a host mounts at a click with a Modal, one option pending.",
        group="Actions",
        section="components",
        try_line="click Open context menu; up/down move; enter chooses; esc cancels",
        api_line="ContextMenu(options, *, title, max_rows) · Modal(tui, menu, anchor=(y, x))",
        components=("ContextMenu", "Modal", "Button", "Option"),
        build=_context_menu,
    ),
)
