"""The registry: the showcase's pages, and the palette lines derived from them.

``PAGES`` is the table of contents -- one :class:`~showcase.page.Page` per
category, the overview first because it is the page the session opens on.
:func:`page_commands` turns each page into a palette entry; the session adds
its own action commands (``/split``, ``/theme``, ...) and derives the
palette's rows and the ``/help`` reply from the whole list, so a new page is
one line here and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Sequence

from mocode_tui import Option, Table, Text

from . import chat, components, features, styles
from .page import Page, PageBody, header, section

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["PAGES", "Command", "help_text", "page_commands", "palette_options"]


def _overview(session: Showcase) -> PageBody:
    """The landing page: what the showcase is, and the pages it holds."""
    theme = session.theme
    return PageBody([
        *header("mocode-tui showcase",
                "Every component, every style and every feature -- one page per category, "
                "and the shell around them is built from the same library.", theme),
        Text(
            "Type / to open the page menu: \u2191\u2193 move (the ends wrap), enter opens the page. "
            "On a page that can be played with, \u2191\u2193 drive the widget named in the header and "
            "enter activates it; a click does both. The composer below is a real Editor, and "
            "anything you type is answered locally -- no model, no network.",
            style=theme.dim,
        ),
        section("the pages", theme),
        Table(["page", "what it shows"],
              [[f"/{page.name}", page.description] for page in PAGES],
              theme=theme),
    ])


#: The showcase's pages, in palette order.
PAGES: tuple[Page, ...] = (
    Page("overview", "What this showcase is, and how to move around", _overview),
    Page("data", "Text & data -- Table, Markdown, Text, Divider", components.data),
    Page("structure", "Structure & layout -- Panel, Row/Column, Tabs, Tree", components.structure),
    Page("lists", "Lists & menus -- Select, Confirm, Autocomplete", components.lists),
    Page("fields", "Fields -- Input, Editor", components.fields),
    Page("feedback", "Progress & feedback -- bars, spinner, notices", components.feedback),
    Page("styles", "Styles -- themes, colors, attributes", styles.page),
    Page("features", "Features -- panes, scroll, selection, keymaps", features.page),
    Page("markdown", "The Markdown fixture -- every construct", components.markdown),
    Page("chat", "The chat layer -- Message, ToolBlock, EditBlock", chat.page),
)

BY_NAME = {page.name: page for page in PAGES}


@dataclass(frozen=True)
class Command:
    """One palette entry: the name it shows, the description beside it, its run.

    ``run`` is called with the live session and answers whether the session
    continues (``False`` quits).
    """

    name: str
    description: str
    run: Callable[[Showcase], bool]


def open_page(page: Page, session: Showcase) -> bool:
    """A page command: switch to the page; the session always keeps running."""
    session.show(page)
    return True


def page_commands() -> tuple[Command, ...]:
    """The palette entries the page table yields, one per page."""
    return tuple(
        Command(page.name, page.description, partial(open_page, page)) for page in PAGES
    )


def palette_options(commands: Sequence[Command]) -> list[Option]:
    """The palette's rows: ``/name`` with its description in the second column."""
    return [
        Option(f"/{command.name}", value=command.name, description=command.description)
        for command in commands
    ]


def help_text(commands: Sequence[Command]) -> str:
    """The ``/help`` style reply, aligned off the same registry."""
    width = max(len(command.name) for command in commands)
    lines = "\n".join(
        f"  /{command.name:<{width}}  {command.description}" for command in commands
    )
    return (
        f"Commands:\n{lines}\n"
        "Enter sends, c-j breaks a line, a leading / opens the menu, "
        "tab cycles the page's focus (c-o switches pane focus), drag selects "
        "and release copies through OSC 52, Ctrl-C quits."
    )
