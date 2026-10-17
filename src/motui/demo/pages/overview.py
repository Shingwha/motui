"""The overview page: what this demo is, and a clickable index of its pages.

The index is a ``Select`` over the registry, and every row carries an
``Action`` whose ``run`` opens the page the row names -- the routing is
data, so the host knows nothing about this page's index."""

from __future__ import annotations

from motui import Option, Select

from ..kit import Action, Exhibit
from ..page import PageBody


def page(session) -> PageBody:
    """What this demo is, and the index of its pages."""
    exhibit = Exhibit(
        session,
        title="motui",
        blurb="Every component, every style and every feature -- one page per category, "
              "and the shell around them is built from the same library.",
        try_text="click a label of the rail on the left -- or a row below, or c-n / c-p -- "
                 "to open that page",
        echo_label="echo",
    )
    index = Select(
        [Option(page.name,
                value=Action(page.name, page.description,
                             lambda s, p=page: s.show(p)),
                description=page.description)
         for page in session.pages],
        max_rows=None,  # the index shows every page, the way a contents page does
        theme=session.theme,
    )
    exhibit.section("the pages")
    exhibit.show(index).focus()
    exhibit.text(
        "The rail is a real second pane: click a label to open its page, and a terminal "
        f"too short for all {len(session.pages)} labels scrolls it on its own. On a page that "
        "can be played with, tab cycles the page's focus ring, \u2191\u2193 drive the focused "
        "widget, enter activates it, and the pointer's hover follows the leaf under it. "
        "A drag over any rows selects them; release copies the range through OSC 52."
    )
    return exhibit.build()
