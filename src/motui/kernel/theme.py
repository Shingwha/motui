"""Theme: the frozen value carrying every semantic style default.

Ten role groups of :class:`Style` tokens; components read a role token
instead of a palette name. Variants come from :class:`ColorPalette`,
``dataclasses.replace``, or the ``dark``/``light``/``flat``/``auto``
constructors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from .style import NONE, Color, Style

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
    "Styles",
    "SurfaceStyles",
    "SyntaxStyles",
    "TextStyles",
    "Theme",
]


# ---------------------------------------------------------------------------
# ColorPalette: the brand-colour authoring layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ColorPalette:
    """The creation colours a theme is derived from; each ``Color`` pairs a
    truecolor value with its ANSI fallback."""

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
    """The text colour that reads on a solid accent or dark surface; it is not
    derivable from the other palette fields."""
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
    """Background surfaces, from the resting page to the control floor;
    ``accent`` and ``danger`` are the solid button floors."""

    base: Style = NONE
    raised: Style = DARK_PALETTE.surface_raised
    hover: Style = DARK_PALETTE.surface_hover
    active: Style = DARK_PALETTE.surface_active
    selected: Style = DARK_PALETTE.surface_active
    control: Style = DARK_PALETTE.surface_raised
    accent: Style = Style(bg=Color("#53c8f0", ansi="bright_cyan"))
    danger: Style = Style(bg=Color("#f2708a", ansi="bright_red"))
    inactive: Style = DARK_PALETTE.surface_inactive


@dataclass(frozen=True, slots=True, kw_only=True)
class BorderStyles:
    """Frame, grid, focus and danger borders."""

    base: Style = DARK_PALETTE.line
    grid: Style = DARK_PALETTE.line
    focus: Style = DARK_PALETTE.accent
    danger: Style = DARK_PALETTE.danger


@dataclass(frozen=True, slots=True, kw_only=True)
class ControlStyles:
    """Interactive control state overlays (no base, no band)."""

    hover: Style = Style(bold=True, underline=True)
    focus: Style = Style(bold=True, underline=True, reverse=True)
    active: Style = Style(reverse=True, underline=True)
    disabled: Style = Style(dim=True)

    def overlay(
        self,
        *,
        hovered: bool = False,
        focused: bool = False,
        pressed: bool = False,
        disabled: bool = False,
    ) -> Style:
        """The state overlay a control merges onto its base style:
        ``disabled > pressed > focused > hovered > NONE``."""
        if disabled:
            return self.disabled
        if pressed:
            return self.active
        if focused:
            return self.focus
        if hovered:
            return self.hover
        return NONE


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
        """The band a row paints: ``disabled > hovered > active (focused ? active :
        inactive) > selected > marked > base``."""
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
    """Per-widget role-group overrides; ``None`` inherits the theme group, a
    value replaces it whole."""

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
    """Every semantic style the toolkit renders with, in ten role groups; the
    field defaults are the Ink & Signal dark theme.

    Frozen: build variants with ``replace`` or the constructors, never by
    mutating."""

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

    def group(self, name: str, styles: Styles | None = None) -> object:
        """The role group ``name``: the ``styles`` override when set, else this
        theme's group."""
        override = getattr(styles, name, None) if styles is not None else None
        return override if override is not None else getattr(self, name)

    # -- constructors ------------------------------------------------------

    @classmethod
    def dark(cls) -> Theme:
        """The shipped dark theme, derived from :data:`DARK_PALETTE`."""
        return cls.from_palette(DARK_PALETTE)

    @classmethod
    def light(cls) -> Theme:
        """The shipped light theme, derived from :data:`LIGHT_PALETTE`."""
        return cls.from_palette(LIGHT_PALETTE)

    @classmethod
    def flat(cls) -> Theme:
        """The dark theme with every surface flattened: position reads through
        attributes (reverse, underline, dim) instead of backgrounds."""
        theme = cls.dark()
        return replace(
            theme,
            surfaces=SurfaceStyles(
                base=NONE,
                raised=NONE,
                hover=NONE,
                active=NONE,
                selected=NONE,
                control=NONE,
                accent=NONE,
                danger=NONE,
                inactive=NONE,
            ),
            controls=replace(
                theme.controls,
                hover=Style(underline=True),
                focus=Style(bold=True, underline=True),
                active=Style(reverse=True, underline=True),
                disabled=Style(dim=True),
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
    def auto(cls, env: Mapping[str, str]) -> Theme:
        """Pick light or dark from ``env``: ``TERM_BACKGROUND`` wins, then
        ``COLORFGBG``; unknown falls back to dark."""
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
    def from_palette(cls, palette: ColorPalette) -> Theme:
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
                control=palette.surface_raised,
                accent=Style(bg=palette.accent.fg),
                danger=Style(bg=palette.danger.fg),
                inactive=palette.surface_inactive,
            ),
            borders=BorderStyles(
                base=palette.line,
                grid=palette.line,
                focus=palette.accent,
                danger=palette.danger,
            ),
            controls=ControlStyles(
                hover=Style(bold=True, underline=True),
                focus=Style(bold=True, underline=True, reverse=True),
                active=Style(reverse=True, underline=True),
                disabled=Style(dim=True),
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

#: The shipped theme: what every component falls back to.  ``Theme()`` --
#: the Ink & Signal dark theme, equal to :meth:`Theme.dark`.
DEFAULT_THEME = Theme()
