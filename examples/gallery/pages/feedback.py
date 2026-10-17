"""The feedback page: bars, the spinner's frames, the notice levels.

One determinate ``ProgressBar`` and one ``Spinner`` keep the page's ``tick``
-- the gallery's own beat, run only while the page is on screen -- so the
animation is the page's own state moved by the host's clock, never a
component reading time.  The level selector is the page's one ``Activable``:
each row carries the sentence it raises, the host reads the pick once, and
the toast is exactly that sentence -- the read-once road the palette also
travels, shown end to end.  The three ``Notice`` levels stand still below:
they are the half a toast cannot show, all levels side by side.
"""

from __future__ import annotations

from motui import FocusRing, Notice, Option, ProgressBar, Row, Select, Spinner, Text

from ..page import PageBody, api_note, header, section, try_line

#: What each selector row raises: ``(level, the sentence its payload carries)``.
LEVELS = (
    ("info", "an info notice: nothing to worry about"),
    ("warn", "a warn notice: mind the gap"),
    ("error", "an error notice: something broke"),
)


def page(gallery) -> PageBody:
    """The live pair, the toast selector, the three notices."""
    theme = gallery.theme
    levels = Select(
        [Option(level, value=sentence, description=f"raises a {level} toast")
         for level, sentence in LEVELS],
        theme=theme,
    )
    live = ProgressBar(0.0, label="live", width_chars=20, theme=theme)
    spinner = Spinner("live")
    frame = Text("", style=theme.accent)
    echo = Text("last raised: --", style=theme.dim)

    def tick() -> None:
        """One page beat: step the spinner and advance the live bar."""
        spinner.advance()
        live.fraction = (live.fraction + 0.02) % 1.0
        frame.text = f"{spinner.frame} {spinner.text}"

    def note(text: str) -> None:
        """One activation was reported: keep the sentence on the echo line."""
        echo.text = "last raised: " + text.removeprefix("chosen: ").strip("'\"")

    tick()
    return PageBody([
        *header("feedback",
                "Determinate bars, a spinner, the three notice levels -- and a selector that "
                "raises a real toast.", theme),
        try_line("activate a row of the level selector below -- the toast that appears is the "
                 "row's own payload", theme),
        echo,
        levels,
        api_note("Toasts.show(text) -- the row's value is the sentence the host shows", theme),
        section("ProgressBar -- three fixed fractions and one live bar", theme),
        Row([ProgressBar(0.25, label="25%", width_chars=16, theme=theme),
             ProgressBar(0.5, label="50%", width_chars=16, theme=theme),
             ProgressBar(1.0, label="done", width_chars=16, theme=theme)]),
        live,
        api_note("ProgressBar.fraction -- set it and the bar repaints; the page's tick moves it", theme),
        section("Spinner -- every frame at rest, then one live", theme),
        Text("  ".join(Spinner("").frames), style=theme.accent),
        frame,
        api_note("Spinner.advance() -- the page's tick, not a clock inside the component", theme),
        section("Notice -- the three levels standing still", theme),
        Notice("an info Notice: nothing to worry about", level="info", theme=theme),
        Notice("a warn Notice: mind the gap", level="warn", theme=theme),
        Notice("an error Notice: something broke", level="error", theme=theme),
        api_note('Notice(text, level="info" | "warn" | "error")', theme),
        Text("Toasts are an overlay, not a block: they float over the composed frame in the "
             "top-right corner and expire on the pump's clock -- /fps toggles the readout that "
             "shows that clock ticking.",
             style=theme.dim),
    ], focus=FocusRing([levels]), hint="the level selector", note=note, tick=tick)
