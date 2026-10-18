"""The shell page: the demo's own materials -- panes, overlays, the probe, the bands.

Every exhibit is the demo's own machinery, and the page's hooks are the
frame's: ``enter`` opens a right pane of the page's own and ``leave`` closes
it again (they are page hooks, not routing glue, so the kit's ``enter`` /
``leave`` fields carry them verbatim).  The **split panes** come first, then
the tiers the session owns -- the **Find** search and the copy gesture's
**selection** -- the **Toasts** the retired feedback page raised (its level
selector's pick *is* the sentence the host shows) and the **Tooltip** band
whose hint the hovered leaf carries, the **live bars** that keep the page's
beat (three fixed fractions and one growing, a spinner's frames and the one
that moves), and finally the **Scrollbar**, the **Stats** box ``c-g`` mounts
and the **hit-test probe**, whose live row resolves the pointer's cell
through ``TUI.hit_component`` -- the same walk a click takes.  The
``Palette`` exhibit left for the modals page: it is a panel over the frame's
scrim, and the shell is about what the frame does while no panel covers it.
"""

from __future__ import annotations

from motui import Button, Checkbox, Link, Option, Select, Text
from motui.kernel import DIM
from motui.widgets import Column, Divider, ProgressBar, Row, Spinner

from ..kit import Exhibit
from ..page import PageBody

#: What each selector row raises: ``(level, the sentence its payload carries)``.
LEVELS = (
    ("info", "an info notice: nothing to worry about"),
    ("warn", "a warn notice: mind the gap"),
    ("error", "an error notice: something broke"),
)

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
    """The pane, the overlays, the chrome three, the live bars, the probe."""
    theme = session.theme
    exhibit = Exhibit(
        session,
        title="shell",
        blurb="Panes, the scrollbar, the stats box, toasts, the tooltip band, find, "
              "selection copy and a hit-test probe -- the shell's own materials, "
              "mounted from a page.",
        echo_label="last raised",
    )
    # The live rows start as placeholders: with no loop (--pages) they stay
    # these, and the tick below is what moves them.
    rate = Text("frames painted: -- (the painter's own counter)", style=theme.dim)
    events = Text("events: -- (c-g mounts the overlay that counts them)", style=theme.dim)
    probe = Text("hit (pointer cell): -- move the pointer over the probe rows below", style=theme.dim)
    levels = Select(
        [Option(level, value=sentence, description=f"raises a {level} toast")
         for level, sentence in LEVELS],
        theme=theme,
    )
    hinted = Button("hover me -- my hint is the tooltip band")
    live = ProgressBar(0.0, label="live", width_chars=20, theme=theme)
    spinner = Spinner("live")
    frame = Text("", style=theme.accent)
    one = Button("probe one -- a Button")
    two = Checkbox("probe two -- a Checkbox")
    three = Link("probe three -- a Link")

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
        """Give the pane's cells back: the visit's resource retires with it."""
        s.close_aside()

    def tick() -> None:
        """One beat: step the live pair, then republish the session's own rows."""
        spinner.advance()
        live.fraction = (live.fraction + 0.02) % 1.0
        frame.text = f"{spinner.frame} {spinner.text}"
        rate.text = f"frames painted: {session.tui.painter.frames} -- the painter's count"
        if session.stats is None:
            events.text = "events: -- the overlay is off; c-g mounts it"
        else:
            events.text = (
                f"events: {session.stats.events} counted, "
                f"last {session.stats.last or '--'} (c-g unmounts)"
            )
        probe.text = _hit_line(session)

    # The arrival frame: the spinner's first step, so the pair is live on the
    # first paint (the retired feedback page's own reading).
    spinner.advance()
    frame.text = f"{spinner.frame} {spinner.text}"

    exhibit.enter = enter
    exhibit.leave = leave
    exhibit.tick = tick
    exhibit.section("toasts -- the pick is the sentence the shell raises",
                    caption="info \u00b7 warn \u00b7 error", draft=True)
    exhibit.show(exhibit.echo)
    exhibit.show(levels, note="last raised").focus()
    exhibit.section("tooltip -- the hovered leaf's own hint, beside the pointer",
                    caption="the band reads the leaf's own hint", draft=True)
    exhibit.show(hinted,
                 hint="the Tooltip tier reads this attribute off the leaf under the pointer")
    exhibit.section("progressbar -- three fixed fractions and one live bar",
                    Row([ProgressBar(0.25, label="25%", width_chars=16, theme=theme),
                         ProgressBar(0.5, label="50%", width_chars=16, theme=theme),
                         ProgressBar(1.0, label="done", width_chars=16, theme=theme)]),
                    caption="25% \u00b7 50% \u00b7 100% \u00b7 one streamed", draft=True)
    exhibit.show(live)
    exhibit.section("spinner -- every frame at rest, then one live",
                    Text("  ".join(Spinner("").frames), style=theme.accent),
                    caption="every frame, then one advancing", draft=True)
    exhibit.show(frame)
    exhibit.section("live readouts -- the session's own fields, no new clock",
                    rate, events, probe,
                    caption="frames \u00b7 events \u00b7 the hit-test probe", draft=True)
    exhibit.section("the hit-test probe -- three hoverable leaves, one block each",
                    caption="a Button, a Checkbox and a Link under the pointer", draft=True)
    exhibit.show(one).focus()
    exhibit.show(two).focus()
    exhibit.show(three)
    return exhibit.build()
