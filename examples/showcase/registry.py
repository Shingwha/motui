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

from mocode_tui import FocusRing, Option, Select, Text

from . import chat, components, features, interaction, keys, styles
from .page import Page, PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["PAGES", "Command", "help_text", "page_commands", "palette_options"]


def _overview(session: Showcase) -> PageBody:
    """The landing page: what the showcase is, and a live index of its pages.

    The index is the live one the palette itself is built on: a ``Select``
    whose rows are the pages, activated with ``enter`` or a click.  The host
    reads the pick once and switches to the page it names, so the landing
    page is a table of contents you can walk -- the static table it replaced
    only described one.
    """
    theme = session.theme
    index = Select(
        [Option(f"/{page.name}", value=page.name, description=page.description)
         for page in PAGES],
        max_rows=None,  # the index shows every exhibit, the way a contents page does
        theme=theme,
    )
    return PageBody([
        *header("mocode-tui showcase",
                "Every component, every style and every feature -- one page per category, "
                "and the shell around them is built from the same library.", theme),
        try_line("click a row below -- or move with \u2191\u2193 and press enter -- to open "
                 "that exhibit", theme),
        section("the exhibits", theme),
        index,
        api_note("Select.activate() -> chosen, read once by the host", theme),
        Text(
            "The strip above is the same index, always on screen: a click on a tab opens "
            "that exhibit and c-n / c-p step through them; / opens the list as a menu. On a "
            "page that can be played with, \u2191\u2193 drive its widget and enter activates "
            "it -- a click does both. The composer below is a real Editor, and anything you "
            "type is answered locally: no model, no network.",
            style=theme.dim,
        ),
    ], focus=FocusRing([index]), hint="pages")


#: The showcase's pages, in palette (and tab-strip) order.
PAGES: tuple[Page, ...] = (
    Page("overview", "over", "What this showcase is, and the index of its exhibits", _overview),
    Page("text", "text", "Text, Markdown, Table, Divider -- the content primitives, live",
         components.text),
    Page("structure", "struct",
         "Boxes, columns, a tab strip and a tree -- click one; the focus left behind dims",
         components.structure),
    Page("lists", "menus",
         "Select, Confirm, Autocomplete -- activate one; the toast and the echo line report the pick",
         components.lists),
    Page("fields", "fields", "Input and Editor -- click any cell and the block cursor lands there",
         components.fields),
    Page("feedback", "feed",
         "ProgressBar, Spinner, Notice -- and a level selector that raises a real toast",
         components.feedback),
    Page("styles", "styles",
         "A theme picker, the colors, the style attributes -- activate one and the shell re-skins",
         styles.page),
    Page("keys", "keys",
         "The three shipped keymaps, key by key -- and the one-line rebinding story",
         keys.page),
    Page("features", "shell",
         "Panes, scrollback, selection, and the three commands that need no terminal",
         features.page),
    Page("interaction", "interact",
         "The focus ring, the click policy, the placement -- the interaction model, live",
         interaction.page),
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
