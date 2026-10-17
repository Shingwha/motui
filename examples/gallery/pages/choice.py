"""The choice page: ``Select``, ``Radio``, ``Confirm``, ``Autocomplete`` -- the menus.

The kernel the palette itself runs on.  Every menu is a ring target, so
``tab`` walks the five widgets, the arrows move the cursor under the focus
and ``enter`` takes the option; a click does both -- the first focuses, the
second activates.  Every activation's pick is read once by the host (the
toast) and echoed on the page's own line, which is what the ``note`` hook is
for: one activation, one report, one visible echo.  ``Radio`` is the same
choice in its single-row shape: one ``(•)`` marker, and a step already is
the selection -- the arrows (or a click) write the pick as they move it.
"""

from __future__ import annotations

from motui import Autocomplete, Confirm, FocusRing, Option, Radio, Select, Text

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """A windowed menu, a radio group, two confirms, a filter -- all with an echo line."""
    theme = gallery.theme
    menu = Select(
        [Option(f"option {i:02d}", value=f"option {i:02d}",
                description=f"the description of row {i}")
         for i in range(1, 21)],
        max_rows=6,
        theme=theme,
    )
    menu.index = 11  # mid-list: the window and its (12/20) counter both show
    radio = Radio(["fast", "balanced", "thorough"], index=1, theme=theme)
    danger = Confirm("delete the project?", danger=True, theme=theme)
    plain = Confirm("and a plain confirmation?", theme=theme)
    filtered = Autocomplete(
        options=[Option("/help", value="/help", description="this command list"),
                 Option("/theme", value="/theme", description="the next theme variant"),
                 Option("/split", value="/split", description="the live preview pane"),
                 Option("/quit", value="/quit", description="leave the gallery")],
        theme=theme,
    )
    filtered.set_query("/s")

    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """Write one reported activation onto the echo line (the last one only).

        The host reports ``chosen: <repr of the value>``; the echo keeps the
        value half, so the line reads the same shape for every menu here.
        """
        echo.text = f"last pick: {text.removeprefix('chosen: ')}"

    return PageBody([
        *header("choice",
                "The kernel the palette itself runs on: a windowed Select, a radio group, "
                "a filtered list, two Confirm pairs.", theme),
        try_line("click a row to move the cursor there; enter activates it -- watch the toast "
                 "and the echo line", theme),
        echo,
        section("Select -- 20 rows, 6 visible, a counter under the window", theme),
        menu,
        api_note("Select.chosen -- the host reads the pick once, then resets it", theme),
        section("Radio -- one selection; a step or a click is the pick", theme),
        radio,
        api_note("Radio(labels, index=\u2026) -- move / click / activate land the pick in chosen", theme),
        section("Confirm -- a dangerous one and a plain one", theme),
        danger,
        plain,
        api_note('Confirm -- a Yes/No pair of Option("Yes", True) / Option("No", False)', theme),
        section("Autocomplete -- the same rows, narrowed by a query", theme),
        filtered,
        api_note("Autocomplete -- enter takes the matching row into chosen; an empty match takes None",
                 theme),
    ], focus=FocusRing([menu, radio, danger, plain, filtered]), hint="menus, confirms", note=note)
