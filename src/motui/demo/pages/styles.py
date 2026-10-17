"""The styles page: the ``Theme`` -- the picker, the swatches, the knobs.

Every semantic style, color by color, plus the attributes a ``Style``
carries and the three color forms it accepts -- and one live control: a
``Select`` of the theme variants whose pick re-skins the whole shell (the
host rebuilds everything that baked its styles at construction)."""

from __future__ import annotations

from motui import FocusRing, Option, Select, Style, Table, Text, Theme

from ..content import THEMES
from ..page import PageBody, api_note, header, section, try_line

#: Foreground colors: a solid block painted in the color itself.
_COLORS = ("accent", "success", "error", "warning", "heading", "link",
           "inline_code", "list_marker", "muted", "code", "dim")

#: Bands and marks: a background patch, a reversed block, a plain surface.
_BANDS = ("selection", "hover", "toast", "border", "table_border", "first_column",
          "cursor", "scrollbar", "scrollbar_thumb")


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


def page(session) -> PageBody:
    """The theme picker, then the swatches, the attributes and the forms."""
    theme = session.theme
    picker = Select(
        [Option(name, value=name) for name, _ in THEMES],  # the payload is the variant's name
        theme=theme,
    )
    picker.index = session.theme_index  # the cursor starts on the theme the shell wears
    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """One activation was reported: keep the variant's name on the echo line."""
        echo.text = "current theme: " + text.removeprefix("chosen: ").strip("'\"")

    return PageBody([
        *header("styles",
                "Every color, attribute and color form the toolkit renders with -- and a "
                "picker that re-skins the whole shell.", theme),
        try_line("click a theme name below (or \u2191\u2193 + enter): the shell and this page "
                 "re-skin at once", theme),
        echo,
        picker,
        api_note("Select.activate() -> chosen -- the host reads the picked name once", theme),
        section("the three themes, color by color", theme),
        _palette(theme, _COLORS),
        section("bands and marks", theme),
        _palette(theme, _BANDS),
        api_note('Theme -- dataclasses.replace(DEFAULT_THEME, accent=Style(fg="#e8a020")) '
                 "derives a variant", theme),
        section("style attributes, and the three color forms", theme),
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
        api_note('Style(fg="red" | "#58a6ff" | (88, 166, 255)) -- the three color forms',
                 theme),
        Text("Styles resolve once, at construction: explicit parameter > theme field > "
             "DEFAULT_THEME. Picking a theme here rebuilds the shell and this page; a "
             "component that resolves per render (a divider's label, an unsealed page block) "
             "would follow without a rebuild.", style=theme.dim),
    ], focus=FocusRing([picker]), note=note)
