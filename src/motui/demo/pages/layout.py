"""The layout page: the containers -- and the two live ones.

``Panel``, ``Row``/``Column``, ``Padding``, ``Spacer``, ``Divider`` and
``StatusLine``: layout is a component too, each through the same
``render(width)`` protocol and each routing a click down to its child.  The
``Collapsible`` is the ring target; the three ``Notice`` levels stand side
by side below it, and the ``StatusLine`` closes the page as the footer's own
row (it moved in from the retired feedback page)."""

from __future__ import annotations

from motui import StatusLine, Text
from motui.kernel import DIM
from motui.widgets import Collapsible, Column, Divider, Notice, Padding, Panel, Row, Spacer

from ..kit import Exhibit
from ..page import PageBody


def page(session) -> PageBody:
    """The containers, one exhibit per part; a foldable section closes the page."""
    theme = session.theme
    exhibit = Exhibit(
        session,
        title="layout",
        blurb="Panel, Row, Column, Padding, Spacer, Divider and StatusLine -- the geometry, "
              "all of it plain components -- plus the Collapsible and the Notice levels.",
    )
    options = Collapsible(
        "Collapsible -- click this title row, or tab + enter, to fold the body away",
        Column([
            Text("The body is any component: this one is a Column of Text rows, inset by "
                 "the marker's width and re-rendered while open.", style=DIM),
            Panel(Text("even a Panel nests here", style=DIM), title="nested", theme=theme),
        ]),
        theme=theme,
    )
    exhibit.section("panel -- a child in a single-line box", Row(
        [Panel(Text("a Panel around Text", style=DIM), title="Panel", theme=theme),
         Panel(Panel(Text("a Panel around a Panel", style=DIM), title="inner", theme=theme),
               title="outer", theme=theme)],
        widths=[40, None],
    ))
    exhibit.section("row / column -- fixed and flexible widths, gaps",
                    Row(
                        [Panel(Text("fixed at 24", style=DIM), theme=theme),
                         Panel(Text("the rest of the row", style=DIM), theme=theme),
                         Panel(Text("and 20 more", style=DIM), theme=theme)],
                        widths=[24, None, 20],
                    ),
                    Column(
                        [Text("Column: stacked, one blank row between neighbours", style=DIM),
                         Text("the second row", style=DIM),
                         Text("and the third", style=DIM)],
                        gap=1,
                    ))
    exhibit.section("padding -- a child inset over a filled band",
                    Padding(Text("Padding: inset text over a filled band"), left=2, top=1,
                            fill_style=theme.selection))
    exhibit.section("spacer -- blank rows, and divider -- the rule",
                    Text("above the spacer", style=theme.dim),
                    Spacer(2),
                    Text("below two blank rows", style=theme.dim),
                    Divider(theme=theme))
    exhibit.section(
        "collapsible -- a titled section that folds its body away",
        options,
        caption="open on arrival \u00b7 a click or enter folds it",
        focus=[options],
        draft=True,
    )
    exhibit.section("notice -- the three levels standing still",
                    Notice("an info Notice: nothing to worry about", level="info", theme=theme),
                    Notice("a warn Notice: mind the gap", level="warn", theme=theme),
                    Notice("an error Notice: something broke", level="error", theme=theme),
                    caption="info \u00b7 warn \u00b7 error",
                    draft=True)
    exhibit.section("statusline -- left text, right text, one row",
                    StatusLine(left=("layout",), right=("the footer's own row, on a page",),
                               theme=theme))
    return exhibit.build()
