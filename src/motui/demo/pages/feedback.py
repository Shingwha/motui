"""The feedback page: the live bars, a status row, and a toast selector.

One ``ProgressBar`` and one ``Spinner`` keep the page's ``tick`` -- the
session's own beat -- and the level selector's pick *is* the sentence the
host raises as a toast.  ``StatusLine`` and ``Tooltip`` are on the shelves
beside them."""

from __future__ import annotations

from motui import Button, FocusRing, Option, Select, StatusLine, Text
from motui.widgets import ProgressBar, Row, Spinner

from ..page import PageBody, api_note, header, section, try_line

#: What each selector row raises: ``(level, the sentence its payload carries)``.
LEVELS = (
    ("info", "an info notice: nothing to worry about"),
    ("warn", "a warn notice: mind the gap"),
    ("error", "an error notice: something broke"),
)


def page(session) -> PageBody:
    """The live pair, the toast selector, the status row and the hinted button."""
    theme = session.theme
    levels = Select(
        [Option(level, value=sentence, description=f"raises a {level} toast")
         for level, sentence in LEVELS],
        theme=theme,
    )
    live = ProgressBar(0.0, label="live", width_chars=20, theme=theme)
    spinner = Spinner("live")
    frame = Text("", style=theme.accent)
    hinted = Button("hover me -- my hint is the tooltip band")
    hinted.hint = "the Tooltip tier reads this attribute off the leaf under the pointer"
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
                "Determinate bars, a spinner, a status row and a selector that raises a real "
                "toast.", theme),
        try_line("activate a row of the level selector below -- the toast that appears is the "
                 "row's own payload; hover the button for the tooltip band", theme),
        echo,
        levels,
        api_note("Toasts.show(text) -- the row's value is the sentence the host shows", theme),
        section("ProgressBar -- three fixed fractions and one live bar", theme),
        Row([ProgressBar(0.25, label="25%", width_chars=16, theme=theme),
             ProgressBar(0.5, label="50%", width_chars=16, theme=theme),
             ProgressBar(1.0, label="done", width_chars=16, theme=theme)]),
        live,
        section("Spinner -- every frame at rest, then one live", theme),
        Text("  ".join(Spinner("").frames), style=theme.accent),
        frame,
        section("StatusLine -- left text, right text, one row", theme),
        StatusLine(left=("feedback",), right=("the footer's own row, on a page",), theme=theme),
        api_note("StatusLine(left=(\u2026,), right=(\u2026,)) -- updates in place, never wraps", theme),
        section("Tooltip -- the hovered leaf's own hint, beside the pointer", theme),
        hinted,
        api_note("Tooltip(tui, pointer) -- reads leaf.hint; hover is the Pointer tier's", theme),
        Text("Toasts are an overlay, not a block: they float over the composed frame and "
             "expire on the pump's clock -- no component here reads a clock itself.",
             style=theme.dim),
    ], focus=FocusRing([levels]), note=note, tick=tick)
