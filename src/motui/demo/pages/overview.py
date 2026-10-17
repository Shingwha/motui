"""The overview page: what this demo is, and a clickable index of its pages.

The index is a ``Select`` over the registry; a pick names a page and the
host opens it, so the landing page is a table of contents you can walk."""

from __future__ import annotations

from motui import FocusRing, Option, Select, Text

from ..page import PageBody, header, section, try_line


def page(session) -> PageBody:
    """What this demo is, and the index of its pages."""
    theme = session.theme
    index = Select(
        [Option(page.name, value=page.name, description=page.description)
         for page in session.pages],
        max_rows=None,  # the index shows every page, the way a contents page does
        theme=theme,
    )
    return PageBody([
        *header("motui",
                "Every component, every style and every feature -- one page per category, "
                "and the shell around them is built from the same library.", theme),
        try_line("click a label of the rail on the left -- or a row below, or c-n / c-p -- "
                 "to open that page", theme),
        section("the pages", theme),
        index,
        Text(
            "The rail is a real second pane: click a label to open its page, and a terminal "
            "too short for all eleven labels scrolls it on its own. On a page that can be "
            "played with, tab cycles the page's focus ring, \u2191\u2193 drive the focused "
            "widget, enter activates it, and the pointer's hover follows the leaf under it. "
            "A drag over any rows selects them; release copies the range through OSC 52.",
            style=theme.dim,
        ),
    ], focus=FocusRing([index]))
