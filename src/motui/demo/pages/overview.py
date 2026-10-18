"""The overview page: what this demo is, and a clickable index of its pages.

The index is a ``Table`` over the registry -- one row per page, its rail
group and its one-line description -- and the pick is the row **number**:
the page's own ``watch`` opens ``session.pages[row]`` (the table's
``activate``/``chosen`` semantics), so the routing is the page's data and
the host knows nothing about this index."""

from __future__ import annotations

from motui import Table

from ..kit import Exhibit, Pick
from ..page import PageBody

#: The index's description column, in cells: what the replay's 110-column
#: frame leaves the third column once the rail, the grid's own rules and
#: the two named columns are paid.  The pane is 87 cells and the three
#: pinned budgets -- a 9-cell name, an 11-cell group label, this -- land
#: on 83, the pane's own inner budget, so nothing shrinks at the recorded
#: geometry.  Without the pins the table's proportional shrink would
#: ellipsize the page names themselves; a pane narrower than the pinned
#: total falls back to that shrink, the component's documented rule
#: (``Table.set_widths``).
WHAT_WIDTH = 57


def page(session) -> PageBody:
    """What this demo is, and the index of its pages."""
    exhibit = Exhibit(
        session,
        title="motui",
        blurb="Every component, every style and every feature -- one page per category, "
              "and the shell around them is built from the same library.",
    )
    index = Table(
        ["page", "group", "what"],
        [[page.name, page.group, page.description] for page in session.pages],
        theme=session.theme,
    )
    # A page name and a group label are never worth an ellipsis: pin the
    # two columns to their own content and give the description column the
    # rest (the one place a long cell may ellipsize, as it always could).
    index.set_widths([
        max(len(page.name) for page in session.pages),
        max(len(page.group) for page in session.pages),
        WHAT_WIDTH,
    ])
    index.index = 0  # a visible cursor on the page the demo opens with

    def watch(pick: Pick) -> None:
        """One index pick: the chosen row **is** the page to open."""
        row = pick.value
        if isinstance(row, int) and 0 <= row < len(session.pages):
            session.show(session.pages[row])

    exhibit.watch(watch)
    exhibit.section("the pages", index,
                    caption="\u2191\u2193 move the cursor \u00b7 enter opens the row's page",
                    focus=[index], draft=True)
    return exhibit.build()
