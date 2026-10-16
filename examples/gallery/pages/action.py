"""The action page: ``Button``, ``Checkbox``, ``Link`` -- the new primitives.

This is the home of the three minimal action components the base-components
wave added, and the page where the **hover** contract is at its plainest:
each of the three is ``Hoverable``, so the pointer tier flips its ``hover``
flag as the pointer crosses it and the row renders the theme's ``hover``
band on top of its own style -- no callback, no event bus, just a state the
render reads.

The two keyboard-capable primitives are ring targets (``Button`` and
``Checkbox`` are ``Focusable + Activable``; ``enter`` runs the focused one's
verb, and the click policy focuses on the first click and activates on the
second).  ``Link`` is deliberately neither focusable nor activable -- it is
the mouse-only leaf -- so its pick is read by the host's round scan like any
other ``chosen``.  Every pick is read once and echoed below.
"""

from __future__ import annotations

from mocode_tui import Button, Checkbox, FocusRing, Link, Text

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """The three primitives, one section each, with a pick echo."""
    theme = gallery.theme
    ship = Button("Ship")
    trace = Checkbox("Trace")
    docs = Link("Read the README")
    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """Write one reported activation onto the echo line."""
        echo.text = f"last pick: {text.removeprefix('chosen: ')}"

    return PageBody([
        *header("action",
                "Button, Checkbox and Link -- the minimal action primitives, each one block, "
                "each with a hover.", theme),
        try_line("move the pointer across the three rows below: the hover band follows; click "
                 "one -- or tab to it and press enter -- to take it", theme),
        echo,
        section("Button -- a one-row action; click and activate are the same door", theme),
        ship,
        api_note("Button(label) -- Hoverable + Clickable + Focusable + Activable; chosen is read once",
                 theme),
        section("Checkbox -- activate flips the mark; the new state is the pick", theme),
        trace,
        api_note("Checkbox(label, checked=\u2026) -- activate() -> chosen (the new state)", theme),
        section("Link -- mouse-only: no focus, no activation, just the click", theme),
        docs,
        api_note("Link(text) -- Hoverable + Clickable; rendered in the theme's link band", theme),
        Text("Hover is the Pointer tier's: the gallery opens DECSET 1003 with TUI(hover=True), "
             "the pointer resolves the cell through the frame and flips the leaf's hover flag; "
             "only the leaf changes, and a motion that changes nothing repaints nothing.",
             style=theme.dim),
    ], focus=FocusRing([ship, trace]), hint="button, checkbox", note=note)
