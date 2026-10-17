"""The chrome page: the shell's own materials -- panes, scrollbar, stats, palette.

Five exhibits, all of them the demo's own machinery: the **split panes**
(the page's ``enter`` hook opens a right pane of its own; ``leave`` closes
it); the **Palette** as an exhibit -- the shell no longer has a ``/`` panel
(the rail is the nav), so the component stands on its own here, opened from
a row and driven through the page's ``modal``; the **Scrollbar**, the
**Stats** box ``c-g`` mounts and the **Tooltip** band; and the **hit-test
probe**, whose live row resolves the pointer's cell through
``TUI.hit_component`` -- the same walk a click takes.
"""

from __future__ import annotations

from motui import Button, Checkbox, FocusRing, Link, Option, Palette, Select, Text
from motui.kernel import DIM
from motui.widgets import Column, Divider

from ..page import PageBody, api_note, header, section, try_line

def palette_rows(pages) -> list[Option]:
    """The exhibit's rows: every page by name, then one row that only echoes."""
    return [
        *(Option(f"/{page.name}", value=page.name, description=page.description)
          for page in pages),
        Option("/say hello", value="say hello", description="echo this row's pick below"),
    ]


#: The right pane's own copy: the pane half of the story.
PANE_TEXT: tuple[str, ...] = (
    "The page's enter hook opened this pane with tui.split(\"vertical\", ratios=(2, 1)).",
    "c-o cycles the focus; a press focuses the pane it lands in.",
    "The wheel scrolls the pane under the pointer, not the focused one.",
)


def _hit_line(session) -> str:
    """What ``TUI.hit_component`` resolves at the pointer's last cell."""
    pointer = session.pointer
    position = None if pointer is None else pointer.position
    if position is None:
        return "hit (pointer cell): -- move the pointer over the probe rows below"
    hit = session.tui.hit_component(position[0], position[1])
    if hit is None:
        return f"hit ({position[0]}, {position[1]}): -- no block owns that cell"
    component, row, col = hit
    return (f"hit ({position[0]}, {position[1]}): {type(component).__name__} "
            f"-> its own cell ({row}, {col})")


def page(session) -> PageBody:
    """The pane, the palette, the chrome three, the probe and the live rows."""
    theme = session.theme
    # The live rows start as placeholders: with no loop (--pages) they stay
    # these, and the tick below is what moves them.
    rate = Text("frames painted: -- (the painter's own counter)", style=theme.dim)
    events = Text("events: -- (c-g mounts the overlay that counts them)", style=theme.dim)
    probe = Text("hit (pointer cell): -- move the pointer over the probe rows below", style=theme.dim)
    opening = Select(
        [Option("open the palette", value="open the palette",
                description="its query row takes the keyboard; enter takes a row")],
        title="the Palette exhibit",
        theme=theme,
    )
    palette = Palette(palette_rows(session.pages), theme=theme, max_rows=6)
    one = Button("probe one -- a Button")
    two = Checkbox("probe two -- a Checkbox")
    three = Link("probe three -- a Link")
    pal_echo = Text("palette: closed", style=theme.dim)

    def note(text: str) -> None:
        """One report was handed in: open the palette, or echo it."""
        if text.removeprefix("chosen: ").strip("'") == "open the palette":
            palette.open()
            pal_echo.text = "palette: open -- type to filter, enter takes a row"
            return
        pal_echo.text = text

    def enter(s) -> None:
        """The page's own resource: a right pane, filled and parked at its top."""
        pane = s.open_aside()
        pane.document.add(Column([
            Text("a pane of this page's own", style=theme.accent),
            Divider(theme=theme),
            *(Text(line, style=DIM) for line in PANE_TEXT),
            Divider(theme=theme),
            *(Text(f"pane row {i:02d} -- roll the wheel over me", style=DIM)
              for i in range(1, 25)),
        ]))
        pane.viewport.scroll_up(1 << 20)  # a fresh pane opens at its first row

    def leave(s) -> None:
        """Give the pane's cells back: the un-split the next page expects."""
        s.close_aside()

    def tick() -> None:
        """One beat: republish the live rows from the session's own state."""
        rate.text = f"frames painted: {session.tui.painter.frames} -- the painter's count"
        if session.stats is None:
            events.text = "events: -- the overlay is off; c-g mounts it"
        else:
            events.text = (
                f"events: {session.stats.events} counted, "
                f"last {session.stats.last or '--'} (c-g unmounts)"
            )
        probe.text = _hit_line(session)

    return PageBody(
        [
            *header(
                "chrome",
                "Panes, the scrollbar, the stats box, the palette, selection copy and a "
                "hit-test probe -- the shell's own materials, mounted from a page.",
                theme,
            ),
            try_line(
                "press c-o and roll the wheel over the right pane; drag across any rows to "
                "copy them -- or open the palette below and type", theme,
            ),
            section("capabilities -- press it and watch", theme),
            api_note('tui.split("vertical", ratios=(2, 1)) + Scrollbar(tui, pane=\u2026) -- the '
                     "pane's own chrome", theme),
            api_note("Stats(tui, pointer=\u2026) -- c-g mounts it; painter.frames + tui.clock() "
                     "are the whole reading", theme),
            api_note("SelectionGesture(tui, on_end=\u2026) -- release hands the range to the host",
                     theme),
            section("the Palette -- an exhibit now, not the shell's nav", theme),
            opening,
            palette,
            pal_echo,
            api_note("Palette(commands) -- its own query Input; a pick that names a page "
                     "opens it", theme),
            section("live readouts -- the session's own fields, no new clock", theme),
            rate,
            events,
            probe,
            api_note("TUI.hit_component(x, y) -> (component, row, col) | None -- the deepest "
                     "leaf, the click's own walk", theme),
            section("the hit-test probe -- three hoverable leaves, one block each", theme),
            one,
            two,
            three,
        ],
        focus=FocusRing([opening, one, two]),
        note=note,
        enter=enter,
        leave=leave,
        modal=palette,
        tick=tick,
    )
