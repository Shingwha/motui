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
        blurb="The layout primitives: the containers, two live strips and the static bands.",
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
    exhibit.section("panel", Row(
        [Panel(Text("a Panel around Text", style=DIM), title="Panel", theme=theme),
         Panel(Panel(Text("a Panel around a Panel", style=DIM), title="inner", theme=theme),
               title="outer", theme=theme)],
        widths=[40, None],
    ))
    exhibit.section("row / column",
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
                    ),
                    caption="widths 24 / auto / 20 \u00b7 gap 1")
    exhibit.section("padding",
                    Padding(Text("Padding: inset text over a filled band"), left=2, top=1,
                            fill_style=theme.selection),
                    caption="left 2 \u00b7 top 1")
    exhibit.section("spacer",
                    Text("above the spacer", style=theme.dim),
                    Spacer(2),
                    Text("below two blank rows", style=theme.dim),
                    caption="2 blank rows")
    exhibit.section(
        "divider",
        Divider(theme=theme),
        Divider(theme=theme, label="a labelled rule"),
        caption="plain \u00b7 labelled",
    )
    exhibit.section(
        "collapsible",
        options,
        caption="open on arrival \u00b7 a click or enter flips it",
        focus=[options],
    )
    exhibit.section("notice",
                    Notice("an info Notice: nothing to worry about", level="info", theme=theme),
                    Notice("a warn Notice: mind the gap", level="warn", theme=theme),
                    Notice("an error Notice: something broke", level="error", theme=theme),
                    caption="info \u00b7 warn \u00b7 error")
    exhibit.section("statusline",
                    StatusLine(left=("layout",), right=("the footer's own row, on a page",),
                               theme=theme),
                    caption="left \u00b7 right \u00b7 one row")
    return exhibit.build()
