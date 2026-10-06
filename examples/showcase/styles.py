"""The styles page: the theme variants, the semantic colors, the knobs.

Three tables carry the whole look of the toolkit: the **themes** side by side
(every semantic color as a swatch patch), the **attributes** a style can
carry, and the **color forms** a ``Style`` accepts.  A fourth table shows the
Markdown palette.  The page is built from the session's *current* theme and
the session rebuilds it on ``/theme``, so the variants column that is live is
the one the shell around it wears.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import Style, Table, Text, Theme

from .content import THEMES
from .page import PageBody, header, section

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["page"]

#: Foreground colors: a solid block painted in the color itself.
_COLORS = ("accent", "success", "error", "warning", "heading", "link",
           "inline_code", "list_marker", "muted", "code", "dim")

#: Bands and marks: a background patch, or a reversed block.
_BANDS = ("user_bg", "tool_bg", "code_bg", "toast", "border", "table_border",
          "cursor", "selection")


def _swatch(style: Style) -> tuple[str, Style]:
    """A six-cell patch: blocks for a foreground, a label over a background."""
    if style.bg is not None and style.fg is None:
        return " a band ", style
    return "\u2588" * 6, style


def _palette(theme: Theme, names: tuple[str, ...]) -> Table:
    """One row per style name, one column per theme variant."""
    return Table(
        ["style", *(name for name, _ in THEMES)],
        [[name, *(_swatch(getattr(variant, name)) for _, variant in THEMES)]
         for name in names],
        theme=theme,
    )


def page(session: Showcase) -> PageBody:
    """The style showcase, built from the session's current theme."""
    theme = session.theme
    return PageBody([
        *header("styles",
                "Every color, attribute and color form the toolkit renders with. "
                "/theme cycles the live theme -- this page and the footer rebuild on it.", theme),
        section("the three themes, color by color", theme),
        _palette(theme, _COLORS),
        section("bands and marks", theme),
        _palette(theme, _BANDS),
        section("style attributes", theme),
        Table(
            ["attribute", "sample"],
            [["bold", ("bold text", Style(bold=True))],
             ["dim", ("dim text", Style(dim=True))],
             ["italic", ("italic text", Style(italic=True))],
             ["underline", ("underlined text", Style(underline=True))],
             ["reverse", ("reversed text", Style(reverse=True))],
             ["strike", ("struck-out text", Style(strike=True))]],
            theme=theme,
        ),
        section("the three color forms", theme),
        Table(
            ["form", "written", "sample"],
            [["named 16-color", '"red" / "bright_blue"', ("named", Style(fg="red"))],
             ["hex truecolor", '"#58a6ff"', ("hex", Style(fg="#58a6ff"))],
             ["rgb truecolor", "(88, 166, 255)", ("rgb", Style(fg=(88, 166, 255)))]],
            theme=theme,
        ),
        section("the Markdown palette", theme),
        Table(
            ["construct", "sample"],
            [["heading", ("# a heading", theme.headings[0])],
             ["link", ("[a link](https://example.invalid)", theme.link)],
             ["inline code", ("`inline code`", theme.inline_code)],
             ["list marker", ("- a list item", theme.list_marker)],
             ["quote", ("> a quote", theme.dim)]],
            theme=theme,
        ),
        Text("Styles resolve once, at construction: explicit parameter > theme field > "
             "DEFAULT_THEME. /theme rebuilds the shell and this page on the next variant; "
             "blocks already in a page keep the theme they were built with.",
             style=theme.dim),
    ])
