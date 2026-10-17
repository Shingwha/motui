"""The choice page: ``Select``, ``Confirm``, ``Radio``, ``Checkbox`` -- the menus.

Every menu is a ring target: ``tab`` walks them, the arrows move the
cursor under the focus, ``enter`` takes the option and a click does both --
the first focuses, the second activates.  Every pick is read once by the
host and echoed on the page's own line."""

from __future__ import annotations

from motui import Checkbox, FocusRing, Option, Select, Text
from motui.widgets import Confirm, Radio

from ..page import PageBody, api_note, header, section, try_line


def page(session) -> PageBody:
    """A windowed menu, a radio group, two confirms, a checkbox, an echo line."""
    theme = session.theme
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
    check = Checkbox("Checkbox -- activate flips the mark")
    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """Write one reported activation onto the echo line (the last one only)."""
        echo.text = f"last pick: {text.removeprefix('chosen: ')}"

    return PageBody([
        *header("choice",
                "The menu kernel: a windowed Select, a radio group, two Confirm pairs and a "
                "checkbox.", theme),
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
        section("Checkbox -- activate flips the mark; the new state is the pick", theme),
        check,
        api_note("Checkbox(label, checked=\u2026) -- activate() -> chosen (the new state)", theme),
    ], focus=FocusRing([menu, radio, danger, plain, check]), note=note)
