"""The action page: ``Button``, ``Link`` and ``Slider`` -- the action primitives.

The page where the **hover** contract is at its plainest: each row is
``Hoverable`` and carries a ``hint`` the session's tooltip band raises.
``Button`` and ``Slider`` are ring targets; ``Link`` is mouse-only, so its
pick is read by the host's round scan like any other ``chosen``."""

from __future__ import annotations

from motui import Button, FocusRing, Link, Text
from motui.widgets import Slider

from ..page import PageBody, api_note, header, section, try_line


def page(session) -> PageBody:
    """The three primitives, one section each, with a pick echo and a hint."""
    theme = session.theme
    ship = Button("Ship")
    docs = Link("Read the README")
    level = Slider(4, minimum=0, maximum=10, theme=theme)
    ship.hint = "click to ship: the pick lands on the echo line below"
    docs.hint = "mouse-only: a click lands the url, no focus"
    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """Write one reported activation onto the echo line."""
        echo.text = f"last pick: {text.removeprefix('chosen: ')}"

    return PageBody([
        *header("action",
                "Button, Link and Slider -- the action primitives, each one block, each with "
                "a hover.", theme),
        try_line("move the pointer across the rows below: the hover band follows and each "
                 "leaf's own hint rises as a tooltip; click one -- or tab to it and press "
                 "enter -- to take it", theme),
        echo,
        section("Button -- a one-row action; click and activate are the same door", theme),
        ship,
        api_note("Button(label) -- Hoverable + Clickable + Focusable + Activable; chosen is read once",
                 theme),
        section("Link -- mouse-only: no focus, no activation, just the click", theme),
        docs,
        section("Slider -- a stepped value; \u2190\u2192 step it, a cell of the track sets it", theme),
        level,
        api_note("Slider(value, minimum=0, maximum=10) -- activate confirms the value into chosen",
                 theme),
        Text("Hover is the Pointer tier's: the demo opens DECSET 1003 with TUI(hover=True), "
             "and the pointer resolves the cell through the frame. The band beside the pointer "
             "is the Tooltip -- the leaf's own hint.", style=theme.dim),
    ], focus=FocusRing([ship, level]), note=note)
