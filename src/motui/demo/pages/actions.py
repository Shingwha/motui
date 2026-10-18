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
        echo_label="last pick",
    )
    ship = Button("Ship")
    docs = Link("Read the README")
    box = Checkbox("Checkbox -- activate flips the mark")
    level = Slider(4, minimum=0, maximum=10, theme=theme)
    # The pick readout: empty until something lands, so the page carries it
    # the way the text page does -- nothing renders before the first pick.
    exhibit.show(exhibit.echo)
    exhibit.section("button -- a one-row action",
                    caption="click and activate are the same door", draft=True)
    exhibit.show(
        ship,
        note="last pick",
        hint="click to ship: the pick lands on the echo line below",
    ).focus()
    exhibit.section("link -- mouse-only, no focus no activation",
                    caption="a click lands the url", draft=True)
    exhibit.show(docs, note="last pick",
                 hint="mouse-only: a click lands the url, no focus")
    exhibit.section("checkbox -- activate flips the mark",
                    caption="unchecked on arrival \u00b7 the new state is the pick", draft=True)
    exhibit.show(box, note="last pick").focus()
    exhibit.section("slider -- a stepped value; \u2190\u2192 step it, a cell of the track sets it",
                    caption="0 to 10 \u00b7 \u2190\u2192 step \u00b7 a cell of the track sets it",
                    draft=True)
    exhibit.show(level, note="last pick").focus()
    return exhibit.build()
