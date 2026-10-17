"""The themes page: the ``Theme`` -- the picker, the swatches, the knobs.

Every semantic style, color by color, plus the attributes a ``Style``
carries and the three color forms it accepts -- and one live control: a
``Select`` of the theme variants whose rows carry the re-skin as kit
``Action``s (``run`` calls ``session.set_theme(i)``), so the page never
depends on the session's theme-name special case.  The line under the picker
names the skin the page is wearing: a re-skin rebuilds the shell *and this
page*, so that row is baked at build time -- which is also why it says
"amber" the moment the pick has landed."""

from __future__ import annotations

from motui import Option, Select, Style, Table, Text, Theme

from ..assets import THEMES
from ..kit import Action, Exhibit
from ..page import PageBody

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
    exhibit = Exhibit(
        session,
        title="themes",
        blurb="Every color, attribute and color form the toolkit renders with -- and a "
              "picker that re-skins the whole shell.",
        try_text="click a theme name below (or \u2191\u2193 + enter): the shell and this page "
                 "re-skin at once",
        echo_label="echo",
    )
    picker = Select(
        # The payload is the row's own action: picking the variant re-skins the
        # session, and the action runs with it (no page-name special case).
        [Option(name, value=Action(name, name, lambda s, i=index: s.set_theme(i)))
         for index, (name, _) in enumerate(THEMES)],
        theme=theme,
    )
    picker.index = session.theme_index  # the cursor starts on the theme the shell wears
    exhibit.section("the picker -- one row per variant")
    exhibit.show(
        picker,
        api="Select.activate() -> chosen -- the row's own Action re-skins the shell",
    ).focus()
    # The skin the page is wearing, baked at build time: a re-skin rebuilds
    # the page, so this row is the fresh one's answer.
    exhibit.show(Text(f"current theme: {THEMES[session.theme_index][0]}", style=theme.dim))
    exhibit.section("the three themes, color by color")
    exhibit.show(_palette(theme, _COLORS))
    exhibit.section("bands and marks")
    exhibit.show(_palette(theme, _BANDS))
    exhibit.text('API \u00b7 Theme -- dataclasses.replace(DEFAULT_THEME, '
                 'accent=Style(fg="#e8a020")) derives a variant')
    exhibit.section("style attributes, and the three color forms")
    exhibit.show(Table(
        ["attribute", "sample"],
        [["bold", ("bold text", Style(bold=True))],
         ["dim", ("dim text", Style(dim=True))],
         ["italic", ("italic text", Style(italic=True))],
         ["underline", ("underlined text", Style(underline=True))],
         ["reverse", ("reversed text", Style(reverse=True))],
         ["strike", ("struck-out text", Style(strike=True))]],
        theme=theme,
    ))
    exhibit.text('API \u00b7 Style(fg="red" | "#58a6ff" | (88, 166, 255)) -- the three '
                 "color forms")
    exhibit.text("Styles resolve once, at construction: explicit parameter > theme field > "
                 "DEFAULT_THEME. Picking a theme here rebuilds the shell and this page; a "
                 "component that resolves per render (a divider's label, an unsealed page block) "
                 "would follow without a rebuild.")
    return exhibit.build()
