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
        try_text="read the boxes below: every frame here is one call, and every child renders "
                 "through the same render(width) protocol",
        echo_label="echo",
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
    exhibit.section("Panel -- a child in a single-line box")
    exhibit.show(Row(
        [Panel(Text("a Panel around Text", style=DIM), title="Panel", theme=theme),
         Panel(Panel(Text("a Panel around a Panel", style=DIM), title="inner", theme=theme),
               title="outer", theme=theme)],
        widths=[40, None],
    ))
    exhibit.section("Row / Column -- fixed and flexible widths, gaps")
    exhibit.show(Row(
        [Panel(Text("fixed at 24", style=DIM), theme=theme),
         Panel(Text("the rest of the row", style=DIM), theme=theme),
         Panel(Text("and 20 more", style=DIM), theme=theme)],
        widths=[24, None, 20],
    ))
    exhibit.show(Column(
        [Text("Column: stacked, one blank row between neighbours", style=DIM),
         Text("the second row", style=DIM),
         Text("and the third", style=DIM)],
        gap=1,
    ))
    exhibit.section("Padding -- a child inset over a filled band")
    exhibit.show(Padding(Text("Padding: inset text over a filled band"), left=2, top=1,
                         fill_style=theme.selection))
    exhibit.section("Spacer -- blank rows, and Divider -- the rule")
    exhibit.show(Text("above the spacer", style=theme.dim))
    exhibit.show(Spacer(2))
    exhibit.show(Text("below two blank rows", style=theme.dim))
    exhibit.show(Divider(theme=theme))
    exhibit.text("API \u00b7 Row(children, widths=[\u2026]) / Column(children, gap=\u2026) / "
                 "Padding(child, \u2026)")
    exhibit.section("Collapsible -- a titled section that folds its body away")
    exhibit.show(
        options,
        api="Collapsible(title, body, open=...) -- click / activate flip it; the new state "
            "is the pick",
    ).focus()
    exhibit.section("Notice -- the three levels standing still")
    exhibit.show(Notice("an info Notice: nothing to worry about", level="info", theme=theme))
    exhibit.show(Notice("a warn Notice: mind the gap", level="warn", theme=theme))
    exhibit.show(
        Notice("an error Notice: something broke", level="error", theme=theme),
        api='Notice(text, level="info" | "warn" | "error") -- one row, never wrapped',
    )
    exhibit.section("StatusLine -- left text, right text, one row")
    exhibit.show(
        StatusLine(left=("layout",), right=("the footer's own row, on a page",), theme=theme),
        api="StatusLine(left=(\u2026,), right=(\u2026,)) -- updates in place, never wraps",
    )
    return exhibit.build()
