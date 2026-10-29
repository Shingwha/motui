"""Button, Checkbox and Link: the minimal clickable units and their bands."""

from dataclasses import replace

import pytest

from motui.kernel.cell import Surface
from motui.kernel.geom import Pos
from motui.kernel.glyphs import GLYPHS
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import (
    Button,
    ButtonKind,
    Checkbox,
    Link,
    Option,
    Select,
    Table,
    Tabs,
    Tree,
    TreeNode,
)
from motui.widgets.action import action_band
from tests.testing import texts


def test_button_renders_one_fitted_row_on_the_control_floor():
    button = Button("Run")
    row = button.render(Constraints(width=20))[0]
    assert row.text == " Run "
    assert row.segments[0].style == DEFAULT_THEME.surfaces.control.merge(
        DEFAULT_THEME.text.base
    )
    assert button.render(Constraints(width=3))[0].text == " R\u2026"


def test_the_four_button_kinds_paint_their_own_floors():
    for kind, expected in [
        (
            ButtonKind.NEUTRAL,
            DEFAULT_THEME.surfaces.control.merge(DEFAULT_THEME.text.base),
        ),
        (
            ButtonKind.PRIMARY,
            DEFAULT_THEME.surfaces.accent.merge(DEFAULT_THEME.text.inverse),
        ),
        (ButtonKind.GHOST, DEFAULT_THEME.content.accent),
        (
            ButtonKind.DANGER,
            DEFAULT_THEME.surfaces.danger.merge(DEFAULT_THEME.text.inverse),
        ),
    ]:
        button = Button("Run", kind=kind)
        assert button.render(Constraints(width=20))[0].segments[0].style == expected


def test_button_accepts_a_string_kind_and_normalizes_it():
    button = Button("Run", kind="primary")
    assert button.kind is ButtonKind.PRIMARY
    assert (
        button.render(Constraints(width=20))[0].segments[0].style
        == DEFAULT_THEME.surfaces.accent.merge(DEFAULT_THEME.text.inverse)
    )
    with pytest.raises(ValueError):
        Button("Run", kind="bogus")


def test_action_band_composes_the_floor_and_the_overlay():
    theme = DEFAULT_THEME
    assert action_band("ghost", theme) == theme.content.accent
    assert action_band("ghost", theme, hovered=True) == theme.content.accent.merge(
        theme.controls.hover
    )
    assert action_band("ghost", theme, focused=True) == theme.content.accent.merge(
        theme.controls.focus
    )
    assert action_band("primary", theme, pressed=True) == (
        theme.surfaces.accent.merge(theme.text.inverse).merge(theme.controls.active)
    )


def test_button_hover_and_focus_merge_the_control_overlay():
    button = Button("Run")
    base = DEFAULT_THEME.surfaces.control.merge(DEFAULT_THEME.text.base)
    button.hover = True
    style = button.render(Constraints(width=20))[0].segments[0].style
    assert style == base.merge(DEFAULT_THEME.controls.hover)
    button.hover = False
    button.focused = True
    style = button.render(Constraints(width=20))[0].segments[0].style
    assert style == base.merge(DEFAULT_THEME.controls.focus)
    assert button.render(Constraints(width=20))[0].text == " Run "


def test_button_click_and_activate_land_in_the_one_shot_result():
    button = Button("Run")
    assert button.take() is None
    assert button.on_click(Pos(x=0, y=0)) is True and button.take() is True
    assert button.take() is None
    assert button.on_action("activate") is True and button.take() is True
    assert button.on_click(Pos(x=40, y=9)) is True and button.take() is True


def test_a_disabled_button_refuses_its_doors_and_paints_the_disabled_floor():
    button = Button(
        "Run",
        disabled=True,
        styles=Styles(text=replace(DEFAULT_THEME.text, faint=Style(italic=True))),
    )
    assert button.on_click(Pos(x=0, y=0)) is False and button.on_action("activate") is False
    assert button.take() is None
    expected = (
        DEFAULT_THEME.surfaces.control.merge(Style(italic=True))
        .merge(DEFAULT_THEME.controls.disabled)
    )
    assert button.render(Constraints(width=20))[0].segments[0].style == expected


def test_explicit_styles_beat_the_theme_fields():
    theme = replace(
        DEFAULT_THEME,
        surfaces=replace(DEFAULT_THEME.surfaces, control=Style(fg="#ff0000")),
        controls=replace(DEFAULT_THEME.controls, hover=Style(bg="#00ff00")),
    )
    button = Button(
        "x",
        styles=Styles(
            surfaces=replace(theme.surfaces, control=Style(underline=True)),
            controls=replace(theme.controls, hover=Style(italic=True)),
        ),
        theme=theme,
    )
    assert button.render(Constraints(width=20))[0].segments[0].style == Style(underline=True)
    button.hover = True
    assert button.render(Constraints(width=20))[0].segments[0].style == Style(underline=True).merge(
        Style(italic=True)
    )


def test_checkbox_flips_its_mark_and_leaves_the_new_state_pending():
    box = Checkbox("Bold")
    assert box.render(Constraints(width=20))[0].text == "[ ] Bold"
    assert box.on_action("activate") is True
    assert (box.checked, box.take()) == (True, True)
    assert box.render(Constraints(width=20))[0].text == "[x] Bold"
    assert box.on_click(Pos(x=0, y=0)) is True
    assert (box.checked, box.take()) == (False, False)


def test_checkbox_takes_a_custom_glyph_pair_and_its_style_surface():
    underline = Style(underline=True)
    box = Checkbox(
        "Bold",
        glyphs=replace(GLYPHS, check_on="(x)", check_off="( )"),
        styles=Styles(
            content=replace(DEFAULT_THEME.content, accent=underline),
            text=replace(DEFAULT_THEME.text, base=underline),
        ),
    )
    assert box.render(Constraints(width=20))[0].text == "( ) Bold"
    box.checked = True
    assert box.render(Constraints(width=20))[0].text == "(x) Bold"
    assert box.render(Constraints(width=20))[0].segments[0].style == underline


def test_a_disabled_checkbox_refuses_both_doors():
    box = Checkbox("Bold", disabled=True)
    assert box.on_action("activate") is False and box.on_click(Pos(x=0, y=0)) is False
    assert box.checked is False and box.take() is None


def test_link_follows_a_click_and_wears_the_link_band():
    link = Link("docs/COMPONENTS.md")
    assert link.render(Constraints(width=30))[0].text == "docs/COMPONENTS.md"
    assert link.render(Constraints(width=30))[0].segments[0].style == DEFAULT_THEME.content.link
    assert link.take() is None
    assert link.on_click(Pos(x=3, y=0)) is True and link.take() is True
    assert link.take() is None


def test_link_focus_and_disabled_flags_shape_the_row():
    link = Link(
        "docs",
        styles=Styles(
            controls=replace(DEFAULT_THEME.controls, focus=Style(bold=True)),
            text=replace(DEFAULT_THEME.text, faint=Style(italic=True)),
        ),
    )
    link.focused = True
    style = link.render(Constraints(width=20))[0].segments[0].style
    assert style == DEFAULT_THEME.content.link.merge(Style(bold=True))
    link.focused = False
    link.hover = True
    style = link.render(Constraints(width=20))[0].segments[0].style
    assert style == DEFAULT_THEME.content.link.merge(DEFAULT_THEME.controls.hover)
    link.hover = False
    link.disabled = True
    assert link.on_action("activate") is False
    assert link.render(Constraints(width=20))[0].segments[0].style == (
        DEFAULT_THEME.content.link.merge(Style(italic=True)).merge(
            DEFAULT_THEME.controls.disabled
        )
    )


def test_checkbox_hover_focus_and_disabled_use_the_shared_overlay():
    box = Checkbox("Bold")
    forced = replace(
        DEFAULT_THEME,
        controls=replace(
            DEFAULT_THEME.controls,
            hover=Style(fg="#111111"),
            focus=Style(fg="#222222"),
            disabled=Style(fg="#333333"),
        ),
    )
    box.theme = forced
    box.hover = True
    segments = box.render(Constraints(width=20))[0].segments
    assert segments[0].style == DEFAULT_THEME.content.accent.merge(Style(fg="#111111"))
    assert segments[1].style == DEFAULT_THEME.text.base.merge(Style(fg="#111111"))
    box.hover = False
    box.focused = True
    segments = box.render(Constraints(width=20))[0].segments
    assert segments[0].style == DEFAULT_THEME.content.accent.merge(Style(fg="#222222"))
    box.focused = False
    box.disabled = True
    segments = box.render(Constraints(width=20))[0].segments
    assert segments[0].style == (
        DEFAULT_THEME.content.accent.merge(DEFAULT_THEME.text.faint).merge(
            Style(fg="#333333")
        )
    )
    assert segments[1].style == (
        DEFAULT_THEME.text.base.merge(DEFAULT_THEME.text.faint).merge(
            Style(fg="#333333")
        )
    )


def test_hover_at_marks_and_clears_one_row_across_components():
    hover = Style(underline=True)
    theme = replace(
        DEFAULT_THEME,
        surfaces=replace(DEFAULT_THEME.surfaces, hover=hover),
        rows=replace(DEFAULT_THEME.rows, hover=hover),
    )
    for build, row, col in [
        (lambda theme: Select([Option("one"), Option("two"), Option("three")], theme=theme), 2, 0),
        (lambda theme: Tabs(["one", "two"], theme=theme), 0, 8),
        (lambda theme: Tree([TreeNode("a"), TreeNode("b")], theme=theme), 1, 0),
        (lambda theme: Table([["a"], ["b"]], headers=["h"], theme=theme), 5, 0),
    ]:
        component = build(theme)
        plain = texts(component, 30)
        assert component.on_hover(Pos(x=col, y=row)) is True
        assert any(
            seg.style.underline
            for line in component.render(Constraints(width=30))
            for seg in line.segments
        )
        assert component.on_hover(Pos(x=col, y=row)) is False
        assert component.on_hover(None) is True
        assert texts(component, 30) == plain


def test_the_action_hints_default_to_no_tooltip():
    assert Button("x").hint == ""
    assert Checkbox("x").hint == ""
    assert Link("x").hint == ""


# -- the 2.0 render contract -------------------------------------------------


def test_the_action_primitives_render_into_clipped_surfaces():
    button = Button("Run")
    assert isinstance(button.render(Constraints(width=20)), Surface)
    assert button.render(Constraints(width=20)) == button.render(Constraints(width=20))
    assert [row.text for row in button.render(Constraints(width=3))] == [" R\u2026"]

    box = Checkbox("Bold")
    assert isinstance(box.render(Constraints(width=20)), Surface)
    assert box.render(Constraints(width=20)) == box.render(Constraints(width=20))

    link = Link("docs/COMPONENTS.md")
    assert isinstance(link.render(Constraints(width=30)), Surface)
    assert link.render(Constraints(width=30)) == link.render(Constraints(width=30))

