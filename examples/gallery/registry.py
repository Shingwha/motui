"""The registry: the gallery's pages, and the palette lines derived from them.

``PAGES`` is the table of contents -- one :class:`~gallery.page.Page` per
category, the overview first because it is the page the gallery opens on --
and it is read twice: :func:`page_commands` turns each page into a palette
entry, and the header's tab strip renders each page's ``nav`` label.  The
session adds its own action commands (``/split``, ``/theme``, ``/fps``,
``/quit``) and derives the palette's rows from the whole list, so a new page
is one line here and nothing else.

The table itself lands with the pages package (one builder module per page,
imported here); this module is the machinery that reads it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Sequence

from mocode_tui import Option

from .page import Page

if TYPE_CHECKING:
    from .session import Gallery

__all__ = [
    "BY_NAME",
    "PAGES",
    "Command",
    "help_text",
    "open_page",
    "page_commands",
    "palette_options",
]

#: The gallery's pages, in palette (and tab-strip) order -- twelve
#: categories, one theme each, the overview first.  ``nav`` labels stay
#: short: all twelve labels share one row (``Tabs`` joins them with
#: ``" | "`` and one space of breathing room), and their sum has to fit the
#: header's content width without truncation.  The builders live in
#: ``gallery/pages/``; the table is filled in as those modules land.
PAGES: tuple[Page, ...] = ()

#: The pages by authoritative name -- the palette dispatch's table.
BY_NAME = {page.name: page for page in PAGES}


@dataclass(frozen=True)
class Command:
    """One palette entry: the name it shows, the description beside it, its run.

    ``run`` is called with the live gallery and answers whether the session
    continues (``False`` quits).
    """

    name: str
    description: str
    run: Callable[[Gallery], bool]


def open_page(page: Page, gallery: Gallery) -> bool:
    """A page command: switch to the page; the session always keeps running."""
    gallery.show(page)
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
    """The aligned command list, for a reader who wants it outside the palette."""
    width = max(len(command.name) for command in commands)
    lines = "\n".join(
        f"  /{command.name:<{width}}  {command.description}" for command in commands
    )
    return f"Commands:\n{lines}"
