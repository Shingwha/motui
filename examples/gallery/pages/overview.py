"""The overview page: what the gallery is, and a clickable index of pages.

The index is the live one the palette itself is built on: a ``Select`` whose
rows are the gallery's pages (``gallery.pages`` -- the controller's own copy
of the registry's table, so this page needs no import of its own).  A pick
carries the page's name, and the host reads it once (the ``chosen``
contract) and opens the page it names -- so the landing page is a table of
contents you can walk, not one you can only read.
"""

from __future__ import annotations

from mocode_tui import FocusRing, Option, Select, Text

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """What this gallery is, and the index of its pages."""
    theme = gallery.theme
    index = Select(
        [Option(f"/{page.name}", value=page.name, description=page.description)
         for page in gallery.pages],
        max_rows=None,  # the index shows every page, the way a contents page does
        theme=theme,
    )
    return PageBody([
        *header("mocode-tui gallery",
                "Every component, every style and every feature -- one page per category, "
                "and the shell around them is built from the same library.", theme),
        try_line("click a row below -- or move with \u2191\u2193 and press enter -- to open "
                 "that page", theme),
        section("the pages", theme),
        index,
        api_note("Select.activate() -> chosen, read once by the host and dispatched by name", theme),
        Text(
            "The strip above is the same index, always on screen: a click on a tab opens that "
            "page, and c-n / c-p step through them. The / key opens a modal palette -- it "
            "carries its own query row and disappears the moment a command is taken; the "
            "gallery has no input box anywhere else. On a page that can be played with, tab "
            "cycles the page's focus ring, \u2191\u2193 drive the focused widget, enter "
            "activates it, and the pointer's hover follows the leaf under it. A drag over any "
            "rows selects them; release copies the range through OSC 52.",
            style=theme.dim,
        ),
    ], focus=FocusRing([index]), hint="pages")
