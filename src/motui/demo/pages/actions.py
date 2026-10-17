"""The actions page: ``Button``, ``Link``, ``Checkbox`` and ``Slider`` -- the action primitives.

The page where the **hover** contract is at its plainest: each row is
``Hoverable`` and carries a ``hint`` the session's tooltip band raises.
``Button``, ``Checkbox`` and ``Slider`` are ring targets; ``Link`` is
mouse-only, so its pick is read by the host's round scan like any other
``chosen``.  Every pick -- a button's ``True``, a checkbox's new state, a
slider's number -- is a bare value the kit reports: the toast carries it and
the page's echo line writes it through the kit's own ``Echo``.  The
``Checkbox`` moved in from the retired choice page: it is the family's
toggle, not a menu."""

from __future__ import annotations

from motui import Button, Checkbox, Link
from motui.widgets import Slider

from ..kit import Exhibit
from ..page import PageBody


def page(session) -> PageBody:
    """The four primitives, one section each, with a pick echo and a hint."""
    theme = session.theme
    exhibit = Exhibit(
        session,
        title="actions",
        blurb="Button, Link, Checkbox and Slider -- the action primitives, each one block, "
              "each with a hover.",
        try_text="move the pointer across the rows below: the hover band follows and each "
                 "leaf's own hint rises as a tooltip; click one -- or tab to it and press "
                 "enter -- to take it",
        echo_label="last pick",
    )
    ship = Button("Ship")
    docs = Link("Read the README")
    box = Checkbox("Checkbox -- activate flips the mark")
    level = Slider(4, minimum=0, maximum=10, theme=theme)
    # The pick readout: empty until something lands, so the page carries it
    # the way the text page does -- nothing renders before the first pick.
    exhibit.show(exhibit.echo)
    exhibit.section("Button -- a one-row action; click and activate are the same door")
    exhibit.show(
        ship,
        note="last pick",
        hint="click to ship: the pick lands on the echo line below",
        api="Button(label) -- Hoverable + Clickable + Focusable + Activable; chosen is read once",
    ).focus()
    exhibit.section("Link -- mouse-only: no focus, no activation, just the click")
    exhibit.show(docs, note="last pick",
                 hint="mouse-only: a click lands the url, no focus")
    exhibit.section("Checkbox -- activate flips the mark; the new state is the pick")
    exhibit.show(
        box,
        note="last pick",
        api="Checkbox(label, checked=\u2026) -- activate() -> chosen (the new state)",
    ).focus()
    exhibit.section("Slider -- a stepped value; \u2190\u2192 step it, a cell of the track sets it")
    exhibit.show(
        level,
        note="last pick",
        api="Slider(value, minimum=0, maximum=10) -- activate confirms the value into chosen",
    ).focus()
    exhibit.text("Hover is the Pointer tier's: the demo opens DECSET 1003 with TUI(hover=True), "
                 "and the pointer resolves the cell through the frame. The band beside the pointer "
                 "is the Tooltip -- the leaf's own hint.")
    return exhibit.build()
