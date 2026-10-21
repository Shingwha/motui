"""Theme values and the Themed resolution rule: the 2.0 role groups and
the Ink & Signal dark defaults they ship with.

A Theme is one frozen tree of ten role groups.  Its field defaults are the
dark theme (``Theme() == Theme.dark()``), the 1.x flat names are gone, and
components still resolve explicit style > theme token > DEFAULT_THEME.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from motui import DEFAULT_THEME, Button, Input, List, Markdown, Text, Theme
from motui.kernel.style import NONE, Style
from motui.kernel.theme import DARK_PALETTE
from motui.widgets import Divider


def test_default_theme_is_the_shipped_frozen_value():
    assert Theme() == DEFAULT_THEME
    assert hash(Theme()) == hash(DEFAULT_THEME)
    with pytest.raises(FrozenInstanceError):
        DEFAULT_THEME.content = Theme().content  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        DEFAULT_THEME.text = Theme().text  # type: ignore[misc]


def test_default_theme_ships_the_dark_values():
    theme = DEFAULT_THEME
    assert theme == Theme.dark()
    assert theme.text.base == NONE
    assert theme.text.muted == DARK_PALETTE.muted
    assert theme.text.faint == DARK_PALETTE.faint
    assert theme.text.disabled == DARK_PALETTE.faint
    assert theme.content.accent == DARK_PALETTE.accent
    assert theme.content.code == NONE
    assert theme.status.danger == DARK_PALETTE.danger
    assert theme.surfaces.base == NONE
    assert theme.rows.active == DARK_PALETTE.surface_active


def test_the_band_family_defaults_to_the_dark_roles():
    assert DEFAULT_THEME.surfaces.hover == DARK_PALETTE.surface_hover
    assert DEFAULT_THEME.surfaces.base == NONE
    assert DEFAULT_THEME.rows.active == DARK_PALETTE.surface_active
    assert DEFAULT_THEME.text.caret == Style(reverse=True)
    assert DEFAULT_THEME.controls.focus == Style(underline=True)
    assert DEFAULT_THEME.text.selection == Style(reverse=True)


def test_the_flat_1x_names_are_gone():
    theme = DEFAULT_THEME
    for name in (
        "accent",
        "caret",
        "border",
        "code",
        "dim",
        "error",
        "first_column",
        "focus",
        "ground",
        "ground_active",
        "heading",
        "headings",
        "hover",
        "inline_code",
        "link",
        "list_marker",
        "muted",
        "notice_levels",
        "scrollbar",
        "scrollbar_thumb",
        "selection",
        "success",
        "table_border",
        "toast",
        "warning",
    ):
        assert not hasattr(theme, name), name
    with pytest.raises(AttributeError):
        theme.accent = Style(fg="#ff0000")  # type: ignore[attr-defined]


def test_structural_tables_derive_from_the_theme_colors():
    ladder = DEFAULT_THEME.content.headings
    assert len(ladder) == 6
    assert ladder[0].underline is True
    assert all(style == ladder[1] for style in ladder[1:])
    heading = Style(fg="#555555")
    custom = Theme(
        content=replace(
            Theme().content,
            headings=(heading.merge(Style(underline=True)), *(heading,) * 5),
        ),
        status=replace(Theme().status, warning=Style(fg="#999999")),
    )
    assert custom.content.headings[0] == Style(fg="#555555", underline=True)
    assert custom.status.warning == Style(fg="#999999")
    assert custom.status.danger == DEFAULT_THEME.status.danger


def test_replace_builds_a_variant_without_mutating_the_default():
    theme = replace(
        DEFAULT_THEME,
        content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff0000")),
    )
    assert theme.content.accent == Style(fg="#ff0000")
    assert theme.borders.base == DEFAULT_THEME.borders.base
    assert theme != DEFAULT_THEME
    assert DEFAULT_THEME.content.accent == Theme().content.accent


def test_explicit_style_beats_the_theme_field():
    theme = Theme(
        borders=replace(Theme().borders, base=Style(fg="#001100")),
    )
    row = Divider(style=Style(fg="#ff0000"), theme=theme).render(10)[0]
    assert all(segment.style == Style(fg="#ff0000") for segment in row.segments)
    themed = Divider(theme=theme).render(10)[0]
    assert all(segment.style == Style(fg="#001100") for segment in themed.segments)


def test_components_take_their_styles_from_the_theme():
    heading = Style(fg="#555555")
    theme = Theme(
        content=replace(
            Theme().content,
            headings=(heading.merge(Style(underline=True)), *(heading,) * 5),
            code=Style(fg="#666666"),
        ),
    )
    markdown = Markdown("# H\n\n```\nx = 1\n```", theme=theme).render(80)
    assert markdown[0].segments[0].style == Style(fg="#555555", underline=True)
    assert markdown[-2].segments[0].style == Style(fg="#666666")


def test_the_default_theme_is_the_dark_visual():
    assert DEFAULT_THEME == Theme.dark()
    assert DEFAULT_THEME.text.inverse == Style(fg="#0d1117")
    assert DEFAULT_THEME.overlays.toast == DARK_PALETTE.surface_raised
    head = Markdown("# Title").render(40)[0].segments[0].style
    assert head == DARK_PALETTE.heading.merge(Style(underline=True))
    assert Button("ok").render(40)[0].segments[0].style == DARK_PALETTE.accent
    field = Input()
    field.insert("hello")
    assert field.render(40)[0].segments[0].text == "\u276f "
    cursor = List(["alpha"], focused=True).render(40)[0]
    assert any(seg.style.bg == DARK_PALETTE.surface_active.bg for seg in cursor.segments)
