"""The showcase's global palettes and their pixel-color bridge."""

from __future__ import annotations

from dataclasses import dataclass

from ..kernel.style import Color, Style
from ..kernel.theme import ColorPalette, Theme
from ..pixel import PixelPalette

__all__ = ["DEMO_THEMES", "DemoTheme", "pixel_palette", "style_rgb"]


@dataclass(frozen=True, slots=True)
class DemoTheme:
    name: str
    label: str
    note: str
    theme: Theme


def _color(value: str, ansi: str) -> Style:
    return Style(fg=Color(value, ansi=ansi))


def _background(value: str, ansi: str = "black") -> Style:
    return Style(bg=Color(value, ansi=ansi))


def _palette(
    *,
    ink: str,
    muted: str,
    faint: str,
    line: str,
    raised: str,
    hover: str,
    active: str,
    inactive: str,
    accent: str,
    success: str,
    warning: str,
    danger: str,
    secondary: str,
    light: bool = False,
) -> ColorPalette:
    foreground = "bright_black" if light else "bright_white"
    return ColorPalette(
        ink=_color(ink, foreground),
        muted=_color(muted, "bright_black"),
        faint=_color(faint, "bright_black"),
        line=_color(line, "bright_black"),
        surface_raised=_background(raised, "bright_white" if light else "black"),
        surface_hover=_background(hover, "bright_white" if light else "black"),
        surface_active=_background(active, "bright_white" if light else "black"),
        surface_inactive=_background(inactive, "bright_white" if light else "black"),
        accent=_color(accent, "cyan" if light else "bright_cyan"),
        success=_color(success, "green" if light else "bright_green"),
        warning=_color(warning, "yellow" if light else "bright_yellow"),
        danger=_color(danger, "red" if light else "bright_red"),
        heading=_color(accent, "cyan" if light else "bright_cyan"),
        link=_color(secondary, "magenta" if light else "bright_magenta"),
        inline_code=_color(secondary, "magenta" if light else "bright_magenta"),
        marker=_color(muted, "bright_black"),
    )


DEMO_THEMES: tuple[DemoTheme, ...] = (
    DemoTheme(
        "signal",
        "Signal / Cyan",
        "electric cyan, ultraviolet and cold ink",
        Theme.from_palette(
            _palette(
                ink="#d8f3f2",
                muted="#8aa8b5",
                faint="#526c7c",
                line="#294657",
                raised="#10232d",
                hover="#15313e",
                active="#194454",
                inactive="#101c26",
                accent="#4de8d2",
                success="#8bea9a",
                warning="#ffd166",
                danger="#ff6b8b",
                secondary="#b7a0ff",
            )
        ),
    ),
    DemoTheme(
        "aurora",
        "Aurora / Violet",
        "violet ionosphere with mint afterglow",
        Theme.from_palette(
            _palette(
                ink="#eee8ff",
                muted="#aaa0ca",
                faint="#665d86",
                line="#493e68",
                raised="#211a35",
                hover="#2c2346",
                active="#3b2c5c",
                inactive="#1b162b",
                accent="#c4a1ff",
                success="#76edc4",
                warning="#ffc47d",
                danger="#ff7eaa",
                secondary="#74d9ff",
            )
        ),
    ),
    DemoTheme(
        "ember",
        "Ember / Coral",
        "warm signal flares against carbon",
        Theme.from_palette(
            _palette(
                ink="#fff0df",
                muted="#c2a18f",
                faint="#80685e",
                line="#5d4038",
                raised="#2d1d1b",
                hover="#402824",
                active="#59352c",
                inactive="#251817",
                accent="#ffad66",
                success="#b8db87",
                warning="#ffd166",
                danger="#ff6f6f",
                secondary="#ff8fa3",
            )
        ),
    ),
    DemoTheme(
        "paper",
        "Paper / Blueprint",
        "technical ink on a warm drafting sheet",
        Theme.from_palette(
            _palette(
                ink="#18313b",
                muted="#526872",
                faint="#7d8f94",
                line="#a8b8b8",
                raised="#f1eee4",
                hover="#e5e9e2",
                active="#d5e4df",
                inactive="#f6f3ea",
                accent="#087f8c",
                success="#38761d",
                warning="#9a6100",
                danger="#b42348",
                secondary="#6651a3",
                light=True,
            )
        ),
    ),
    DemoTheme(
        "mono",
        "Mono / Phosphor",
        "green phosphor, amber warnings, no distraction",
        Theme.from_palette(
            _palette(
                ink="#c8f7c5",
                muted="#83ad80",
                faint="#4b704b",
                line="#355c3a",
                raised="#102416",
                hover="#17331e",
                active="#20472a",
                inactive="#0d1d12",
                accent="#8dff9a",
                success="#8dff9a",
                warning="#ffd166",
                danger="#ff8066",
                secondary="#a6d9ff",
            )
        ),
    ),
)


def style_rgb(style: Style, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    value = style.fg.value if isinstance(style.fg, Color) else style.fg
    if isinstance(value, tuple):
        return value
    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
    return fallback


def pixel_palette(theme: Theme) -> PixelPalette:
    accent = style_rgb(theme.content.accent, (77, 232, 210))
    secondary = style_rgb(theme.content.inline_code, (183, 160, 255))
    success = style_rgb(theme.status.success, (139, 234, 154))
    warning = style_rgb(theme.status.warning, (255, 209, 102))
    danger = style_rgb(theme.status.danger, (255, 107, 139))
    muted = style_rgb(theme.text.muted, (138, 168, 181))
    faint = style_rgb(theme.text.faint, (82, 108, 124))
    pairs = (
        accent,
        secondary,
        success,
        warning,
        danger,
        (235, 250, 255),
        muted,
        faint,
    )
    return PixelPalette(
        slots={
            index + 1: (color, tuple(round(channel * 0.38) for channel in color))
            for index, color in enumerate(pairs)
        }
    )
