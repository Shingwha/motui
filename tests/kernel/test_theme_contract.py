"""The 2.0 token contract: every role value is frozen, slotted and
keyword-only with defaults, ``Theme()`` is the shipped default, and the
constructors and band resolvers follow the documented semantics."""

from __future__ import annotations

from dataclasses import MISSING, fields, is_dataclass
from typing import get_type_hints

import pytest

from motui.core.style import NONE, Style
from motui.core.theme import (
    DARK_PALETTE,
    DEFAULT_THEME,
    LIGHT_PALETTE,
    BorderStyles,
    ChromeStyles,
    ContentStyles,
    ControlStyles,
    OverlayStyles,
    ColorPalette,
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


@pytest.mark.parametrize("cls", TOKEN_CLASSES, ids=lambda cls: cls.__name__)
def test_token_values_are_frozen_slotted_keyword_only(cls):
    assert is_dataclass(cls)
    params = cls.__dataclass_params__
    assert params.frozen is True
    assert params.slots is True
    assert all(field.kw_only for field in fields(cls))


@pytest.mark.parametrize("cls", TOKEN_CLASSES, ids=lambda cls: cls.__name__)
def test_every_token_field_has_a_default_and_the_value_constructs(cls):
    for field in fields(cls):
        assert field.default is not MISSING or field.default_factory is not MISSING, (
            f"{cls.__name__}.{field.name} has no default"
        )
    assert isinstance(cls(), cls)


@pytest.mark.parametrize("cls", TOKEN_CLASSES, ids=lambda cls: cls.__name__)
def test_token_values_reject_positional_arguments(cls):
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
        base=NONE, raised=NONE, hover=NONE, active=NONE, selected=NONE
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
    assert DARK_PALETTE != LIGHT_PALETTE


@pytest.mark.parametrize(
    ("env", "expected"),
    [
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
    ],
)
def test_auto_reads_only_the_passed_environment(env, expected):
    assert Theme.auto(env) == expected()


def test_auto_does_not_touch_the_process_environment(monkeypatch):
    monkeypatch.setenv("TERM_BACKGROUND", "light")
    assert Theme.auto() == Theme.light()
    monkeypatch.delenv("TERM_BACKGROUND")
    monkeypatch.setenv("COLORFGBG", "15;0")
    assert Theme.auto() == Theme.dark()


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


def test_control_band_precedence_is_exact():
    controls = ControlStyles(
        base=Style(fg="red"),
        hover=Style(fg="green"),
        focus=Style(fg="blue"),
        active=Style(fg="yellow"),
        disabled=Style(fg="magenta"),
    )
    assert controls.band() == controls.base
    assert controls.band(hovered=True) == controls.hover
    assert controls.band(focused=True, hovered=True) == controls.focus
    assert controls.band(active=True, focused=True) == controls.active
    assert controls.band(disabled=True, active=True) == controls.disabled


def test_band_resolvers_are_side_effect_free():
    rows = RowStyles()
    before = rows
    assert rows.band(active=True) == rows.band(active=True)
    assert rows == before
    controls = ControlStyles()
    before = controls
    assert controls.band(focused=True) == controls.band(focused=True)
    assert controls == before


def test_replace_never_mutates_the_default_theme():
    from dataclasses import replace

    variant = replace(
        DEFAULT_THEME,
        content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff0000")),
    )
    assert variant != DEFAULT_THEME
    assert DEFAULT_THEME.content.accent == Theme().content.accent
