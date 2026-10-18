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
    exhibit.section("the pages", index,
                    caption="click a row, or \u2191\u2193 and enter, to open that page",
                    focus=[index], draft=True)
    return exhibit.build()
