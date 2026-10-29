"""The 2.0 token contract: every role value is frozen, slotted and
keyword-only with defaults, ``Theme()`` is the shipped default, and the
constructors and band resolvers follow the documented semantics."""

from __future__ import annotations

from dataclasses import MISSING, fields, is_dataclass
from typing import get_type_hints

import pytest

from motui.kernel.style import NONE, Color, Style
from motui.kernel.theme import (
    DARK_PALETTE,
    DEFAULT_THEME,
    LIGHT_PALETTE,
    BorderStyles,
    ChromeStyles,
    ColorPalette,
    ContentStyles,
    ControlStyles,
    OverlayStyles,
    RowStyles,
    StatusStyles,
    SurfaceStyles,
    SyntaxStyles,
    TextStyles,
    Theme,
)

TOKEN_CLASSES = (
    ColorPalette,
    TextStyles,
    SurfaceStyles,
    BorderStyles,
    ControlStyles,
    RowStyles,
    StatusStyles,
    ContentStyles,
    ChromeStyles,
    OverlayStyles,
    SyntaxStyles,
    Theme,
)


def test_token_values_are_frozen_slotted_keyword_only_with_defaults():
    for cls in TOKEN_CLASSES:
        assert is_dataclass(cls)
        params = cls.__dataclass_params__
        assert params.frozen is True, cls.__name__
        assert params.slots is True, cls.__name__
        assert all(field.kw_only for field in fields(cls)), cls.__name__
        for field in fields(cls):
            assert field.default is not MISSING or field.default_factory is not MISSING, (
                f"{cls.__name__}.{field.name} has no default"
            )
        assert isinstance(cls(), cls)
        with pytest.raises(TypeError):
            cls(Style(fg="#ff0000"))  # type: ignore[misc]


def test_every_theme_field_is_a_role_group():
    hints = get_type_hints(Theme)
    assert fields(Theme)
    for field in fields(Theme):
        assert hints[field.name] in TOKEN_CLASSES


def test_default_theme_is_theme_and_the_dark_visual():
    assert isinstance(DEFAULT_THEME, Theme)
    assert Theme() == DEFAULT_THEME
    assert hash(Theme()) == hash(DEFAULT_THEME)
    assert DEFAULT_THEME.text.base == NONE
    assert DEFAULT_THEME.surfaces.base == NONE
    assert DEFAULT_THEME.rows.active == DARK_PALETTE.surface_active
    assert DEFAULT_THEME.overlays.toast == DARK_PALETTE.surface_raised


def test_dark_light_and_flat_are_built_from_the_palettes():
    assert Theme.dark() == Theme.from_palette(DARK_PALETTE)
    assert Theme.light() == Theme.from_palette(LIGHT_PALETTE)
    assert Theme.dark() == Theme()
    assert Theme.light() != Theme()
    assert Theme.light().text.inverse == Style(fg="#ffffff")
    assert Theme.dark().text.inverse == Style(fg="#0d1117")

    flat = Theme.flat()
    assert flat.surfaces == SurfaceStyles(
        base=NONE,
        raised=NONE,
        hover=NONE,
        active=NONE,
        selected=NONE,
        control=NONE,
        accent=NONE,
        danger=NONE,
        inactive=NONE,
    )
    assert flat.controls == ControlStyles(
        hover=Style(underline=True),
        focus=Style(bold=True, underline=True),
        active=Style(reverse=True, underline=True),
        disabled=Style(dim=True),
    )
    assert flat.rows.active == Style(reverse=True)
    assert flat.rows.inactive == Style(dim=True)
    assert flat.rows.hover == Style(underline=True)
    assert flat.rows.selected == Style(reverse=True)
    assert flat.overlays.toast == Style(reverse=True)
    assert flat.overlays.tooltip == Style(reverse=True)
    assert flat.text == Theme.dark().text


def test_from_palette_is_a_pure_derivation():
    assert Theme.from_palette(DARK_PALETTE) == Theme.from_palette(DARK_PALETTE)
    dark = Theme.dark()
    assert dark.content.headings[0] == DARK_PALETTE.heading.merge(
        Style(underline=True)
    )
    assert dark.content.headings[1:] == (DARK_PALETTE.heading,) * 5
    assert dark.syntax.keyword == DARK_PALETTE.accent
    assert dark.chrome.scrollbar == DARK_PALETTE.faint
    assert Theme.light().content.accent == LIGHT_PALETTE.accent
    assert Theme.light().surfaces.control == LIGHT_PALETTE.surface_raised
    assert Theme.light().surfaces.accent == Style(bg=LIGHT_PALETTE.accent.fg)
    assert Theme.light().surfaces.danger == Style(bg=LIGHT_PALETTE.danger.fg)
    assert Theme.light().surfaces.inactive == LIGHT_PALETTE.surface_inactive
    assert DARK_PALETTE != LIGHT_PALETTE


def test_auto_reads_only_the_passed_environment():
    for env, expected in [
        ({}, Theme.dark),
        ({"TERM_BACKGROUND": "light"}, Theme.light),
        ({"TERM_BACKGROUND": "white"}, Theme.light),
        ({"TERM_BACKGROUND": "dark"}, Theme.dark),
        ({"TERM_BACKGROUND": "black"}, Theme.dark),
        ({"COLORFGBG": "15;0"}, Theme.dark),
        ({"COLORFGBG": "0;7"}, Theme.light),
        ({"COLORFGBG": "0;8"}, Theme.dark),
        ({"COLORFGBG": "0;9"}, Theme.light),
        ({"COLORFGBG": "0;15"}, Theme.light),
        ({"TERM_BACKGROUND": "unknown"}, Theme.dark),
        ({"COLORFGBG": "no-color"}, Theme.dark),
    ]:
        assert Theme.auto(env) == expected(), env


def test_row_band_precedence_is_exact():
    rows = RowStyles(
        base=Style(fg="red"),
        hover=Style(fg="green"),
        active=Style(fg="blue"),
        inactive=Style(fg="yellow"),
        selected=Style(fg="magenta"),
        marked=Style(fg="cyan"),
        disabled=Style(fg="white"),
    )
    assert rows.band() == rows.base
    assert rows.band(marked=True) == rows.marked
    assert rows.band(selected=True, marked=True) == rows.selected
    assert rows.band(active=True) == rows.active
    assert rows.band(active=True, focused=False) == rows.inactive
    assert rows.band(active=True, focused=False, selected=True) == rows.inactive
    assert rows.band(hovered=True, active=True, selected=True) == rows.hover
    assert rows.band(disabled=True, hovered=True, active=True) == rows.disabled


def test_control_overlay_precedence_is_exact():
    controls = ControlStyles(
        hover=Style(fg="green"),
        focus=Style(fg="blue"),
        active=Style(fg="yellow"),
        disabled=Style(fg="magenta"),
    )
    assert controls.overlay() == NONE
    assert controls.overlay(hovered=True) == controls.hover
    assert controls.overlay(focused=True, hovered=True) == controls.focus
    assert controls.overlay(pressed=True, focused=True) == controls.active
    assert controls.overlay(disabled=True, pressed=True) == controls.disabled


def test_control_overlay_merges_onto_a_base_style():
    controls = ControlStyles(
        hover=Style(underline=True),
        focus=Style(bold=True, reverse=True),
        active=Style(strike=True),
        disabled=Style(dim=True),
    )
    base = Style(fg="red", bg="black")
    merged = base.merge(controls.overlay(focused=True))
    assert merged.fg == "red" and merged.bg == "black"
    assert merged.bold is True and merged.reverse is True
    assert base.merge(controls.overlay()) == base


def test_control_defaults_are_state_overlays_without_a_base_band():
    controls = ControlStyles()
    assert not hasattr(controls, "base")
    assert not hasattr(controls, "band")
    assert controls.overlay() == NONE


def test_the_surface_floor_tokens_default_to_the_dark_roles():
    surfaces = SurfaceStyles()
    assert surfaces.control == DARK_PALETTE.surface_raised
    assert surfaces.accent == Style(bg=Color("#53c8f0", ansi="bright_cyan"))
    assert surfaces.danger == Style(bg=Color("#f2708a", ansi="bright_red"))
    assert surfaces.inactive == DARK_PALETTE.surface_inactive
    # They are plain defaults on the frozen dataclass, not required fields.
    assert SurfaceStyles(control=NONE).accent == surfaces.accent


def test_band_resolvers_are_side_effect_free():
    rows = RowStyles()
    before = rows
    assert rows.band(active=True) == rows.band(active=True)
    assert rows == before
    controls = ControlStyles()
    before = controls
    assert controls.overlay(focused=True) == controls.overlay(focused=True)
    assert controls == before


def test_replace_never_mutates_the_default_theme():
    from dataclasses import replace

    variant = replace(
        DEFAULT_THEME,
        content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff0000")),
    )
    assert variant != DEFAULT_THEME
    assert DEFAULT_THEME.content.accent == Theme().content.accent
