"""The layout page: the containers -- and the two live ones.

``Panel``, ``Row``/``Column``, ``Padding``, ``Spacer`` and ``Divider``: layout
is a component too, each through the same ``render(width)`` protocol and
each routing a click down to its child.  The ``Collapsible`` is the ring
target; the three ``Notice`` levels stand side by side below it."""

from __future__ import annotations

from motui import FocusRing, Text
from motui.kernel import DIM
from motui.widgets import Collapsible, Column, Divider, Notice, Padding, Panel, Row, Spacer

from ..page import PageBody, api_note, header, section, try_line


def page(session) -> PageBody:
    """The containers, one exhibit per part; a foldable section closes the page."""
    theme = session.theme
    options = Collapsible(
        "Collapsible -- click this title row, or tab + enter, to fold the body away",
        Column([
            Text("The body is any component: this one is a Column of Text rows, inset by "
                 "the marker's width and re-rendered while open.", style=DIM),
            Panel(Text("even a Panel nests here", style=DIM), title="nested", theme=theme),
        ]),
        theme=theme,
    )
    return PageBody([
        *header("layout",
                "Panel, Row, Column, Padding, Spacer and Divider -- the geometry, all of it "
                "plain components -- plus the Collapsible and the Notice levels.", theme),
        try_line("read the boxes below: every frame here is one call, and every child renders "
                 "through the same render(width) protocol", theme),
        section("Panel -- a child in a single-line box", theme),
        Row(
            [Panel(Text("a Panel around Text", style=DIM), title="Panel", theme=theme),
             Panel(Panel(Text("a Panel around a Panel", style=DIM), title="inner", theme=theme),
                   title="outer", theme=theme)],
            widths=[40, None],
        ),
        section("Row / Column -- fixed and flexible widths, gaps", theme),
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
        section("Padding -- a child inset over a filled band", theme),
        Padding(Text("Padding: inset text over a filled band"), left=2, top=1,
                fill_style=theme.selection),
        section("Spacer -- blank rows, and Divider -- the rule", theme),
        Text("above the spacer", style=theme.dim),
        Spacer(2),
        Text("below two blank rows", style=theme.dim),
        Divider(theme=theme),
        api_note("Row(children, widths=[\u2026]) / Column(children, gap=\u2026) / Padding(child, \u2026)",
                 theme),
        section("Collapsible -- a titled section that folds its body away", theme),
        options,
        api_note("Collapsible(title, body, open=...) -- click / activate flip it; the new state is the pick",
                 theme),
        section("Notice -- the three levels standing still", theme),
        Notice("an info Notice: nothing to worry about", level="info", theme=theme),
        Notice("a warn Notice: mind the gap", level="warn", theme=theme),
        Notice("an error Notice: something broke", level="error", theme=theme),
        api_note('Notice(text, level="info" | "warn" | "error") -- one row, never wrapped', theme),
    ], focus=FocusRing([options]))
