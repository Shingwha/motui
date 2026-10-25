"""Theme: the frozen value that carries every semantic style default.

The 2.0 theme is a tree of ten **role groups** -- ``text``, ``surfaces``,
``borders``, ``controls``, ``rows``, ``status``, ``content``, ``chrome``,
``overlays`` and ``syntax`` -- each a frozen, keyword-only value whose fields
are :class:`~motui.kernel.style.Style` tokens.  A component reads the token
it paints with (``theme.content.accent``, ``theme.rows.hover`` ...) instead
of a flat palette name, so a role can change without every call site
changing with it.

Two ways to build a variant exist:

* :class:`ColorPalette` -- the brand-colour authoring layer.  It names the
  *creation* colours (ink, muted, surface, accent, success ...), and
  :meth:`Theme.from_palette` derives every role token from them.
  :data:`DARK_PALETTE` and :data:`LIGHT_PALETTE` are the shipped palettes.
* :func:`dataclasses.replace` on a :class:`Theme` -- the surgical route,
  replacing one group or one token (``replace(theme, content=replace(
  theme.content, accent=Style(...)))``).

The shipped :data:`DEFAULT_THEME` is :class:`Theme`'s own default values,
which are the **Ink & Signal dark theme**: ``Theme() == Theme.dark()``.
``Theme.light()`` derives the light palette, ``Theme.flat()`` the same dark
theme with every background surface flattened, and ``Theme.auto()`` picks
between the two shipped themes from the environment.

Every component takes ``style=...`` (an explicit override, which always
wins) plus ``theme=Theme | None`` (default ``None``).  A component resolves
each style it renders as::

    explicit style parameter  >  theme field  >  DEFAULT_THEME field

:class:`Themed` stores the resolved theme once, at construction, and picks
each style with :meth:`Themed.pick`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from .style import Color, NONE, Style

__all__ = [
    "DARK_PALETTE",
    "DEFAULT_THEME",
    "LIGHT_PALETTE",
    "BorderStyles",
    "ChromeStyles",
    "ColorPalette",
    "ContentStyles",
    "ControlStyles",
    "OverlayStyles",
    "RowStyles",
    "StatusStyles",
    "SurfaceStyles",
    "Styles",
    "SyntaxStyles",
    "TextStyles",
    "Theme",
    "Themed",
]


# ---------------------------------------------------------------------------
# ColorPalette: the brand-colour authoring layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ColorPalette:
    """The creation colours a theme is derived from.

    ``value``-style fields pair a truecolor hex with the nearest ANSI name
    (``Color``), so a 16-colour terminal keeps the intended hue.  The
    defaults are :data:`DARK_PALETTE`'s values; ``LIGHT_PALETTE`` overrides
    every one of them.
    """

    ink: Style = NONE
    muted: Style = Style(fg=Color("#8b95a7", ansi="bright_black"))
    faint: Style = Style(fg=Color("#5d6677", ansi="bright_black"))
    line: Style = Style(fg=Color("#4a5568", ansi="bright_black"))
    surface: Style = NONE
    surface_raised: Style = Style(bg=Color("#161d27", ansi="black"))
    surface_hover: Style = Style(bg=Color("#1b2430", ansi="black"))
    surface_active: Style = Style(bg=Color("#1f2937", ansi="black"))
    surface_inactive: Style = Style(bg=Color("#151b24", ansi="black"))
    accent: Style = Style(fg=Color("#53c8f0", ansi="bright_cyan"))
    success: Style = Style(fg=Color("#5bd18b", ansi="bright_green"))
    warning: Style = Style(fg=Color("#f2c14e", ansi="bright_yellow"))
    danger: Style = Style(fg=Color("#f2708a", ansi="bright_red"))
    code: Style = NONE
    heading: Style = Style(fg=Color("#53c8f0", ansi="bright_cyan"))
    link: Style = Style(fg=Color("#53c8f0", ansi="bright_cyan"), underline=True)
    inline_code: Style = Style(fg=Color("#c4b5fd", ansi="magenta"))
    marker: Style = Style(fg=Color("#8b95a7", ansi="bright_black"))


#: The dark authoring palette (also the :class:`ColorPalette` defaults).
DARK_PALETTE = ColorPalette()

#: The light authoring palette.  Every field overrides the dark default.
LIGHT_PALETTE = ColorPalette(
    ink=NONE,
    muted=Style(fg=Color("#5b6472", ansi="bright_black")),
    faint=Style(fg=Color("#8b95a7", ansi="bright_black")),
    line=Style(fg=Color("#b6c0cc", ansi="bright_black")),
    surface=NONE,
    surface_raised=Style(bg=Color("#f1f5f9", ansi="bright_white")),
    surface_hover=Style(bg=Color("#eef3f9", ansi="bright_white")),
    surface_active=Style(bg=Color("#e2e8f0", ansi="bright_white")),
    surface_inactive=Style(bg=Color("#f5f8fb", ansi="bright_white")),
    accent=Style(fg=Color("#0369a1", ansi="cyan")),
    success=Style(fg=Color("#15803d", ansi="green")),
    warning=Style(fg=Color("#b45309", ansi="yellow")),
    danger=Style(fg=Color("#be123c", ansi="red")),
    code=NONE,
    heading=Style(fg=Color("#0369a1", ansi="cyan")),
    link=Style(fg=Color("#0369a1", ansi="cyan"), underline=True),
    inline_code=Style(fg=Color("#7e22ce", ansi="magenta")),
    marker=Style(fg=Color("#5b6472", ansi="bright_black")),
)


def _inverse_for(palette: ColorPalette) -> Style:
    """The text colour that reads on a solid accent/surface.

    The inverse is not derivable from the other palette fields (it is the
    page colour, which ``surface`` leaves transparent), so the two shipped
    palettes name it explicitly: white on the light palette, near-black on
    the dark one.  A custom palette gets the dark answer.
    """
    return Style(fg="#ffffff") if palette == LIGHT_PALETTE else Style(fg="#0d1117")


# ---------------------------------------------------------------------------
# Role groups: every field is a Style token, every group is a frozen value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class TextStyles:
    """Foreground text roles."""

    base: Style = NONE
    muted: Style = DARK_PALETTE.muted
    faint: Style = DARK_PALETTE.faint
    inverse: Style = Style(fg="#0d1117")
    disabled: Style = DARK_PALETTE.faint
    caret: Style = Style(reverse=True)
    selection: Style = Style(reverse=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class SurfaceStyles:
    """Background surfaces, from the resting page to the selected row."""

    base: Style = NONE
    raised: Style = DARK_PALETTE.surface_raised
    hover: Style = DARK_PALETTE.surface_hover
    active: Style = DARK_PALETTE.surface_active
    selected: Style = DARK_PALETTE.surface_active


@dataclass(frozen=True, slots=True, kw_only=True)
class BorderStyles:
    """Frame, grid, focus and danger borders."""

    base: Style = DARK_PALETTE.line
    grid: Style = DARK_PALETTE.line
    focus: Style = DARK_PALETTE.accent
    danger: Style = DARK_PALETTE.danger


@dataclass(frozen=True, slots=True, kw_only=True)
class ControlStyles:
    """Interactive control bands."""

    base: Style = DARK_PALETTE.accent
    hover: Style = DARK_PALETTE.surface_hover
    focus: Style = Style(underline=True)
    active: Style = DARK_PALETTE.surface_active
    disabled: Style = DARK_PALETTE.faint

    def band(
        self,
        *,
        hovered: bool = False,
        focused: bool = False,
        active: bool = False,
        disabled: bool = False,
    ) -> Style:
        """The band a control paints, by precedence.

        ``disabled > active > focused > hovered > base`` -- the exact rule
        the row and control families already apply, in one place.
        """
        if disabled:
            return self.disabled
        if active:
            return self.active
        if focused:
            return self.focus
        if hovered:
            return self.hover
        return self.base


@dataclass(frozen=True, slots=True, kw_only=True)
class RowStyles:
    """Row bands and their state resolution."""

    base: Style = NONE
    hover: Style = DARK_PALETTE.surface_hover
    active: Style = DARK_PALETTE.surface_active
    inactive: Style = DARK_PALETTE.surface_inactive
    selected: Style = DARK_PALETTE.surface_active
    marked: Style = DARK_PALETTE.surface_hover
    disabled: Style = NONE

    def band(
        self,
        *,
        active: bool = False,
        hovered: bool = False,
        focused: bool = True,
        selected: bool = False,
        marked: bool = False,
        disabled: bool = False,
    ) -> Style:
        """The band a row paints, by precedence.

        ``disabled > hovered > (active ? (focused ? active : inactive)) >
        selected > marked > base``.  An active row resolves through its
        focus branch and stops there: a focused cursor row wears ``active``,
        an unfocused one wears ``inactive``.  The pointer's band still wins
        over the cursor (it is the more immediate signal), and a disabled
        row wins over everything.
        """
        if disabled:
            return self.disabled
        if hovered:
            return self.hover
        if active:
            return self.active if focused else self.inactive
        if selected:
            return self.selected
        if marked:
            return self.marked
        return self.base


@dataclass(frozen=True, slots=True, kw_only=True)
class StatusStyles:
    """Outcome colours."""

    success: Style = DARK_PALETTE.success
    warning: Style = DARK_PALETTE.warning
    danger: Style = DARK_PALETTE.danger
    info: Style = DARK_PALETTE.accent


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentStyles:
    """Content roles: links, code, headings and inline emphasis."""

    accent: Style = DARK_PALETTE.accent
    link: Style = DARK_PALETTE.link
    code: Style = DARK_PALETTE.code
    inline_code: Style = DARK_PALETTE.inline_code
    headings: tuple[Style, ...] = (
        DARK_PALETTE.heading.merge(Style(underline=True)),
        *(DARK_PALETTE.heading,) * 5,
    )
    marker: Style = DARK_PALETTE.marker
    quote: Style = DARK_PALETTE.line
    strong: Style = Style(bold=True)
    emphasis: Style = Style(italic=True)
    strike: Style = Style(strike=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class ChromeStyles:
    """The quiet chrome bands: dividers and scrollbars."""

    divider: Style = DARK_PALETTE.line
    scrollbar: Style = DARK_PALETTE.faint
    scrollbar_thumb: Style = DARK_PALETTE.muted


@dataclass(frozen=True, slots=True, kw_only=True)
class OverlayStyles:
    """Scrim, toast and tooltip bands."""

    scrim: Style = Style(dim=True)
    toast: Style = DARK_PALETTE.surface_raised
    tooltip: Style = DARK_PALETTE.surface_raised


@dataclass(frozen=True, slots=True, kw_only=True)
class SyntaxStyles:
    """Token classes for the syntax highlighter."""

    comment: Style = DARK_PALETTE.muted.merge(Style(italic=True))
    keyword: Style = DARK_PALETTE.accent
    string: Style = DARK_PALETTE.success
    number: Style = DARK_PALETTE.warning
    builtin: Style = DARK_PALETTE.inline_code


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Styles:
    """Per-widget role-group overrides, one field per :class:`Theme` group.

    ``None`` inherits the widget's theme group; a value replaces that whole
    group.  A migrated widget accepts this through ``styles=`` instead of
    the per-token ``style`` / ``hover_style`` / ... parameters, and resolves
    the token when it renders, so a theme switch reaches a mounted widget.
    """

    text: TextStyles | None = None
    surfaces: SurfaceStyles | None = None
    borders: BorderStyles | None = None
    controls: ControlStyles | None = None
    rows: RowStyles | None = None
    status: StatusStyles | None = None
    content: ContentStyles | None = None
    chrome: ChromeStyles | None = None
    overlays: OverlayStyles | None = None
    syntax: SyntaxStyles | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    """Every semantic style the toolkit renders with, in ten role groups.

    The fields' **default values are the Ink & Signal dark theme**, so
    ``DEFAULT_THEME`` -- ``Theme()`` -- is ``Theme.dark()``.
    :meth:`light`, :meth:`flat` and :meth:`from_palette` build the other
    shipped variants.

    Instances are frozen: build variants with :func:`dataclasses.replace`
    rather than mutating.  Equality is field-wise, so a custom theme never
    compares equal to :data:`DEFAULT_THEME` unless every group matches.
    """

    text: TextStyles = field(default_factory=TextStyles)
    surfaces: SurfaceStyles = field(default_factory=SurfaceStyles)
    borders: BorderStyles = field(default_factory=BorderStyles)
    controls: ControlStyles = field(default_factory=ControlStyles)
    rows: RowStyles = field(default_factory=RowStyles)
    status: StatusStyles = field(default_factory=StatusStyles)
    content: ContentStyles = field(default_factory=ContentStyles)
    chrome: ChromeStyles = field(default_factory=ChromeStyles)
    overlays: OverlayStyles = field(default_factory=OverlayStyles)
    syntax: SyntaxStyles = field(default_factory=SyntaxStyles)

    # -- constructors ------------------------------------------------------

    @classmethod
    def dark(cls) -> "Theme":
        """The shipped dark theme, derived from :data:`DARK_PALETTE`."""
        return cls.from_palette(DARK_PALETTE)

    @classmethod
    def light(cls) -> "Theme":
        """The shipped light theme, derived from :data:`LIGHT_PALETTE`."""
        return cls.from_palette(LIGHT_PALETTE)

    @classmethod
    def flat(cls) -> "Theme":
        """The dark theme with every surface flattened.

        No background surfaces: position reads through attributes instead
        (reverse for the engaged/selected row, underline for hover, dim
        for an unfocused cursor), and the overlays reverse rather than
        paint a raised surface.
        """
        theme = cls.dark()
        return replace(
            theme,
            surfaces=SurfaceStyles(
                base=NONE,
                raised=NONE,
                hover=NONE,
                active=NONE,
                selected=NONE,
            ),
            rows=replace(
                theme.rows,
                active=Style(reverse=True),
                inactive=Style(dim=True),
                hover=Style(underline=True),
                selected=Style(reverse=True),
            ),
            overlays=replace(
                theme.overlays,
                toast=Style(reverse=True),
                tooltip=Style(reverse=True),
            ),
        )

    @classmethod
    def auto(cls, env: Mapping[str, str]) -> "Theme":
        """Pick light or dark from ``env``; unknown falls back to dark.

        ``TERM_BACKGROUND`` (``light``/``white`` or ``dark``/``black``) wins;
        otherwise a numeric ``COLORFGBG`` background slot is read -- ``7``
        or a bright value (``9``..``15``) is a light background, everything
        else is dark.  The environment is an explicit argument: the kernel
        never reads :data:`os.environ`, and
        :func:`motui.terminal.capability.auto_theme` is the convenience that
        passes it.
        """
        background = env.get("TERM_BACKGROUND", "").strip().lower()
        if background in ("light", "white"):
            return cls.light()
        if background in ("dark", "black"):
            return cls.dark()
        colorfgbg = env.get("COLORFGBG", "")
        slot = colorfgbg.split(";")[-1].strip()
        if slot.isdigit():
            index = int(slot)
            return cls.light() if index == 7 or index >= 9 else cls.dark()
        return cls.dark()

    @classmethod
    def from_palette(cls, palette: ColorPalette) -> "Theme":
        """Derive every role token from ``palette`` (a pure function)."""
        heading = palette.heading
        return cls(
            text=TextStyles(
                base=palette.ink,
                muted=palette.muted,
                faint=palette.faint,
                inverse=_inverse_for(palette),
                disabled=palette.faint,
                caret=Style(reverse=True),
                selection=Style(reverse=True),
            ),
            surfaces=SurfaceStyles(
                base=palette.surface,
                raised=palette.surface_raised,
                hover=palette.surface_hover,
                active=palette.surface_active,
                selected=palette.surface_active,
            ),
            borders=BorderStyles(
                base=palette.line,
                grid=palette.line,
                focus=palette.accent,
                danger=palette.danger,
            ),
            controls=ControlStyles(
                base=palette.accent,
                hover=palette.surface_hover,
                focus=Style(underline=True),
                active=palette.surface_active,
                disabled=palette.faint,
            ),
            rows=RowStyles(
                base=NONE,
                hover=palette.surface_hover,
                active=palette.surface_active,
                inactive=palette.surface_inactive,
                selected=palette.surface_active,
                marked=palette.surface_hover,
                disabled=NONE,
            ),
            status=StatusStyles(
                success=palette.success,
                warning=palette.warning,
                danger=palette.danger,
                info=palette.accent,
            ),
            content=ContentStyles(
                accent=palette.accent,
                link=palette.link,
                code=palette.code,
                inline_code=palette.inline_code,
                headings=(heading.merge(Style(underline=True)), *(heading,) * 5),
                marker=palette.marker,
                quote=palette.line,
                strong=Style(bold=True),
                emphasis=Style(italic=True),
                strike=Style(strike=True),
            ),
            chrome=ChromeStyles(
                divider=palette.line,
                scrollbar=palette.faint,
                scrollbar_thumb=palette.muted,
            ),
            overlays=OverlayStyles(
                scrim=Style(dim=True),
                toast=palette.surface_raised,
                tooltip=palette.surface_raised,
            ),
            syntax=SyntaxStyles(
                comment=palette.muted.merge(Style(italic=True)),
                keyword=palette.accent,
                string=palette.success,
                number=palette.warning,
                builtin=palette.inline_code,
            ),
        )

class Themed:
    """Base for components that resolve styles against a theme.

    A themed component stores one resolved theme -- ``theme`` when given,
    :data:`DEFAULT_THEME` otherwise -- and picks each style with
    :meth:`pick`: the explicit style wins, otherwise the fallback token.
    Subclasses resolve their styles in ``__init__`` and keep the stored
    theme for the rare render-time pick (a divider whose label a host
    restyles in place).
    """

    __slots__ = ("_theme",)

    def __init__(self, theme: Theme | None = None) -> None:
        self._theme = theme or DEFAULT_THEME

    def pick(self, explicit: Style | None, fallback: Style) -> Style:
        """``explicit`` when given, else ``fallback``."""
        return explicit if explicit is not None else fallback


#: The shipped theme: what every component falls back to.  ``Theme()`` --
#: the Ink & Signal dark theme, equal to :meth:`Theme.dark`.
DEFAULT_THEME = Theme()
