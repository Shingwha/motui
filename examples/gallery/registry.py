"""The registry: the gallery's pages, and the palette lines derived from them.

``PAGES`` is the table of contents -- one :class:`~gallery.page.Page` per
category, the overview first because it is the page the gallery opens on --
and it is read twice: :func:`page_commands` turns each page into a palette
entry, and the header's tab strip renders each page's ``nav`` label.  The
session adds its own action commands (``/split``, ``/theme``, ``/fps``,
``/quit``) and derives the palette's rows from the whole list, so a new page
is one line here and nothing else -- one builder module per page, beside
this module.  **Adding a page moves every rendered page's header strip**
(it carries every label) and the overview's index, so the golden frames are
re-recorded whole in the same wave.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Sequence

from mocode_tui import Option

from .page import Page
from .pages import (
    action,
    choice,
    content,
    data,
    devtools,
    feedback,
    features,
    input as input_page,
    navigation,
    overview,
    streaming,
    structure,
    styles,
)

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

#: The gallery's pages, in palette (and tab-strip) order -- thirteen
#: categories, one theme each, the overview first, the developer tools last.
#: ``nav`` labels stay short: all thirteen labels share one row (``Tabs``
#: joins them with ``" | "`` and one space of breathing room), and their sum
#: has to fit the header's content width without truncation.
PAGES: tuple[Page, ...] = (
    Page("overview", "over", "What this gallery is, and a clickable index of its pages",
         overview.page),
    Page("content", "text", "Text and Markdown -- the primitives that carry content",
         content.page),
    Page("data", "data", "Table -- a row cursor, a pick, and hover on the row under the pointer",
         data.page),
    Page("structure", "struct", "Panel, Row, Column, Padding, Spacer, Divider -- read-only layout",
         structure.page),
    Page("input", "input", "Input and Editor -- click a cell and the block cursor lands there",
         input_page.page),
    Page("choice", "choice", "Select, Confirm, Autocomplete -- activate one; the toast echoes it",
         choice.page),
    Page("navigation", "nav", "Tabs and Tree -- click, tab, and watch the row under the pointer",
         navigation.page),
    Page("action", "action", "Button, Checkbox, Link -- hover, click, and a pick for each",
         action.page),
    Page("feedback", "feed", "ProgressBar, Spinner, Notice -- and a selector that raises a toast",
         feedback.page),
    Page("styles", "styles", "A theme picker, the colors, the attributes -- pick one and the shell re-skins",
         styles.page),
    Page("streaming", "stream", "The 346-line Markdown fixture, streamed block by block",
         streaming.page),
    Page("features", "feat", "Panes, scrollback, selection, hover -- with a pane of its own",
         features.page),
    Page("devtools", "dev", "Stats, golden frames, recorded replay -- the developer toolbox and a hit-test probe",
         devtools.page),
)

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
