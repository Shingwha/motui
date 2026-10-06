"""The styles page: the theme picker, the semantic colors, the knobs.

Four tables carry the whole look of the toolkit: the **themes** side by side
(every semantic color as a swatch patch), the **attributes** a style can
carry, the **color forms** a ``Style`` accepts, and the Markdown palette --
and one live control carries the look itself: a ``Select`` of the theme
variants, the page's one ``Activable``.  Activating a row lands the theme's
name in ``chosen``; the host reads that name once and calls
:meth:`~showcase.session.Showcase.set_theme`, which rebuilds the footer, the
banner and this page on the variant picked -- so the column that is live is
the one the shell around it wears.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import FocusRing, Option, Select, Style, Table, Text, Theme

from .content import THEMES
from .page import PageBody, api_note, header, section, try_line

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
    """The theme picker, then the swatches, the attributes and the forms."""
    theme = session.theme
    picker = Select(
        [Option(name, value=name) for name, _ in THEMES],  # the payload is the variant's name
        theme=theme,
    )
    picker.index = session.theme_index  # the cursor starts on the theme the shell wears
    return PageBody([
        *header("styles",
                "Every color, attribute and color form the toolkit renders with -- "
                "and a picker that re-skins the whole shell.", theme),
        try_line("click a theme name below (or \u2191\u2193 + enter): the shell and this page "
                 "re-skin at once", theme),
        picker,
        api_note("Select.activate() -> chosen -- the host reads the picked name once", theme),
        section("the three themes, color by color", theme),
        _palette(theme, _COLORS),
        section("bands and marks", theme),
        _palette(theme, _BANDS),
        api_note("Theme -- dataclasses.replace(DEFAULT_THEME, accent=Style(fg=\"#e8a020\")) "
                 "derives a variant", theme),
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
        api_note("Style.merge(other) -- other's set fields win; the booleans or together", theme),
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
             "DEFAULT_THEME. Picking a theme here -- or /theme cycling to the next variant -- "
             "rebuilds the shell and this page; blocks already in a page keep the theme they "
             "were built with.",
             style=theme.dim),
    ], focus=FocusRing([picker]), hint="themes")
