"""Theme values and the Themed resolution rule: defaults, replace,
explicit-style precedence and the no-background invariant.

A Theme is one frozen value of semantic tokens with two derived structural
tables.  Components resolve explicit style > theme field > DEFAULT_THEME,
and a default render paints structure and position only -- no background,
no reverse outside the caret cell.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from motui import DEFAULT_THEME, Button, Input, List, Markdown, Text, Theme
from motui.kernel.style import NONE, Style
from motui.widgets import Divider


def test_default_theme_is_the_shipped_frozen_value():
    assert Theme() == DEFAULT_THEME
    assert hash(Theme()) == hash(DEFAULT_THEME)
    with pytest.raises(FrozenInstanceError):
        DEFAULT_THEME.accent = Style(fg="#ff0000")  # type: ignore[misc]


def test_the_band_family_defaults_to_none_with_position_carve_outs():
    assert DEFAULT_THEME.hover == NONE
    assert DEFAULT_THEME.ground == NONE
    assert DEFAULT_THEME.ground_active == NONE
    assert DEFAULT_THEME.caret == Style(reverse=True)
    assert DEFAULT_THEME.focus == Style(reverse=True)
    assert DEFAULT_THEME.selection == Style(reverse=True)


def test_structural_tables_derive_from_the_theme_colors():
    ladder = DEFAULT_THEME.headings
    assert len(ladder) == 6
    assert ladder[0].underline is True
    assert all(style == ladder[1] for style in ladder[1:])
    custom = Theme(heading=Style(fg="#555555"), warning=Style(fg="#999999"))
    assert custom.headings[0] == Style(fg="#555555", underline=True)
    assert custom.notice_levels["warn"] == ("WARNING: ", Style(fg="#999999"))
    assert custom.notice_levels["error"] == ("ERROR: ", DEFAULT_THEME.error)


def test_derived_tables_are_read_only():
    with pytest.raises(TypeError):
        DEFAULT_THEME.notice_levels["info"] = ("INFO: ", NONE)  # type: ignore[index]
    with pytest.raises(TypeError):
        del DEFAULT_THEME.notice_levels["warn"]  # type: ignore[attr-defined]


def test_replace_builds_a_variant_without_mutating_the_default():
    theme = replace(DEFAULT_THEME, accent=Style(fg="#ff0000"))
    assert theme.accent == Style(fg="#ff0000")
    assert theme.border == DEFAULT_THEME.border
    assert theme != DEFAULT_THEME
    assert DEFAULT_THEME.accent == Theme().accent


def test_explicit_style_beats_the_theme_field():
    theme = Theme(border=Style(fg="#001100"))
    row = Divider(style=Style(fg="#ff0000"), theme=theme).render(10)[0]
    assert all(segment.style == Style(fg="#ff0000") for segment in row.segments)
    themed = Divider(theme=theme).render(10)[0]
    assert all(segment.style == Style(fg="#001100") for segment in themed.segments)


def test_components_take_their_styles_from_the_theme():
    theme = Theme(heading=Style(fg="#555555"), code=Style(fg="#666666"))
    markdown = Markdown("# H\n\n```\nx = 1\n```", theme=theme).render(80)
    assert markdown[0].segments[0].style == Style(fg="#555555", underline=True)
    assert markdown[-2].segments[0].style == Style(fg="#666666")


def test_the_default_theme_paints_no_background_and_no_reverse_outside_the_caret():
    components = (
        Button("ok"),
        List(["alpha", "beta"]),
        Markdown("# Title\n\nA paragraph with **bold**."),
        Text("a paragraph of plain text"),
    )
    for component in components:
        rows = component.render(40)
        assert not any(
            segment.style.bg is not None for row in rows for segment in row.segments
        )
        assert not any(
            segment.style.reverse for row in rows for segment in row.segments
        )
    field = Input()
    field.insert("hello")
    rendered = field.render(40)
    assert not any(segment.style.bg for row in rendered for segment in row.segments)
    assert sum(
        segment.style.reverse for row in rendered for segment in row.segments
    ) == 1
