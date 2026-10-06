"""The registry: the showcase's pages, and the palette lines derived from them.

``PAGES`` is the table of contents -- one :class:`~showcase.page.Page` per
category, the overview first because it is the page the session opens on --
and it is read twice: :func:`page_commands` turns each page into a palette
entry, and the banner's tab strip renders each page's ``nav`` label.  The
session adds its own action commands (``/split``, ``/theme``, ...) and derives
the palette's rows and the ``/help`` reply from the whole list, so a new page
is one line here and nothing else.
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


#: The showcase's pages, in palette (and tab-strip) order.
PAGES: tuple[Page, ...] = (
    Page("overview", "over", "What this showcase is, and the index of its exhibits", _overview),
    Page("text", "text", "Text, Markdown, Table, Divider -- the content primitives, live",
         components.text),
    Page("structure", "struct", "Panel, Row/Column, Tabs, Tree -- boxes you can click and focus",
         components.structure),
    Page("lists", "menus", "Select, Confirm, Autocomplete -- the menu kernel the palette runs on",
         components.lists),
    Page("fields", "fields", "Input and Editor -- click a cell and the caret lands there",
         components.fields),
    Page("feedback", "feed", "ProgressBar, Spinner, Notice -- and where a toast comes from",
         components.feedback),
    Page("styles", "styles", "Themes, colors, style attributes -- the shell's whole skin",
         styles.page),
    Page("features", "shell", "Panes, scrollback, selection, keymaps -- the shell's engineering",
         features.page),
    Page("streaming", "stream", "a long Markdown document -- every construct", components.markdown),
    Page("chat", "chat", "Message, ToolBlock, EditBlock, StatusLine -- plus a live turn",
         chat.page),
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
