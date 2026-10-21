"""Button, Checkbox and Link: the minimal clickable units and their bands."""

from dataclasses import replace

import pytest

from motui.core.glyphs import GLYPHS
from motui.core.style import Style
from motui.core.theme import DEFAULT_THEME, Styles
from motui.widgets import Button, Checkbox, Link, Option, Select, Table, Tabs, Tree, TreeNode

from tests.testing import texts


def test_button_renders_one_fitted_row_in_the_accent_band():
    button = Button("Run")
    row = button.render(20)[0]
    assert row.text == " Run "
    assert row.segments[0].style == DEFAULT_THEME.content.accent
    assert button.render(3)[0].text == " R\u2026"


def test_button_hover_and_focus_merge_their_bands():
    button = Button("Run")
    button.hover = True
    assert button.render(20)[0].segments[0].style == DEFAULT_THEME.content.accent.merge(
        DEFAULT_THEME.surfaces.hover
    )
    button.hover = False
    button.focused = True
    assert button.render(20)[0].segments[0].style == DEFAULT_THEME.content.accent.merge(
        DEFAULT_THEME.controls.focus
    )
    assert button.render(20)[0].text == " Run "


def test_button_click_and_activate_land_in_the_one_shot_result():
    button = Button("Run")
    assert button.take_result() is None
    assert button.click(0, 0) is True and button.take_result() is True
    assert button.take_result() is None
    assert button.activate() is True and button.take_result() is True
    assert button.click(9, 40) is True and button.take_result() is True


def test_a_disabled_button_refuses_its_doors_and_paints_the_disabled_band():
    button = Button(
        "Run",
        disabled=True,
        styles=Styles(text=replace(DEFAULT_THEME.text, faint=Style(italic=True))),
    )
    assert button.click(0, 0) is False and button.activate() is False
    assert button.take_result() is None
    assert button.render(20)[0].segments[0].style == Style(italic=True)


def test_explicit_styles_beat_the_theme_fields():
    theme = replace(
        DEFAULT_THEME,
        controls=replace(DEFAULT_THEME.controls, base=Style(fg="#ff0000")),
        surfaces=replace(DEFAULT_THEME.surfaces, hover=Style(bg="#00ff00")),
    )
    button = Button(
        "x",
        styles=Styles(
            controls=replace(theme.controls, base=Style(underline=True)),
            surfaces=replace(theme.surfaces, hover=Style(italic=True)),
        ),
        theme=theme,
    )
    assert button.render(20)[0].segments[0].style == Style(underline=True)
    button.hover = True
    assert button.render(20)[0].segments[0].style == Style(underline=True).merge(
        Style(italic=True)
    )


def test_checkbox_flips_its_mark_and_leaves_the_new_state_pending():
    box = Checkbox("Bold")
    assert box.render(20)[0].text == "[ ] Bold"
    assert box.activate() is True
    assert (box.checked, box.take_result()) == (True, True)
    assert box.render(20)[0].text == "[x] Bold"
    assert box.click(0, 0) is True
    assert (box.checked, box.take_result()) == (False, False)


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
    assert box.render(20)[0].text == "( ) Bold"
    box.checked = True
    assert box.render(20)[0].text == "(x) Bold"
    assert box.render(20)[0].segments[0].style == underline


def test_a_disabled_checkbox_refuses_both_doors():
    box = Checkbox("Bold", disabled=True)
    assert box.activate() is False and box.click(0, 0) is False
    assert box.checked is False and box.take_result() is None


def test_link_follows_a_click_and_wears_the_link_band():
    link = Link("docs/COMPONENTS.md")
    assert link.render(30)[0].text == "docs/COMPONENTS.md"
    assert link.render(30)[0].segments[0].style == DEFAULT_THEME.content.link
    assert link.take_result() is None
    assert link.click(0, 3) is True and link.take_result() is True
    assert link.take_result() is None


def test_link_focus_and_disabled_flags_shape_the_row():
    link = Link(
        "docs",
        styles=Styles(
            controls=replace(DEFAULT_THEME.controls, focus=Style(bold=True)),
            text=replace(DEFAULT_THEME.text, faint=Style(italic=True)),
        ),
    )
    link.focused = True
    assert link.render(20)[0].segments[0].style == DEFAULT_THEME.content.link.merge(Style(bold=True))
    link.disabled = True
    assert link.activate() is False
    assert link.render(20)[0].segments[0].style == Style(italic=True)


@pytest.mark.parametrize(
    "build, row, col",
    [
        (lambda theme: Select([Option("one"), Option("two"), Option("three")], theme=theme), 2, 0),
        (lambda theme: Tabs(["one", "two"], theme=theme), 0, 8),
        (lambda theme: Tree([TreeNode("a"), TreeNode("b")], theme=theme), 1, 0),
        (lambda theme: Table(["h"], [["a"], ["b"]], theme=theme), 5, 0),
    ],
)
def test_hover_at_marks_and_clears_one_row_across_components(build, row, col):
    hover = Style(underline=True)
    theme = replace(
        DEFAULT_THEME,
        surfaces=replace(DEFAULT_THEME.surfaces, hover=hover),
        rows=replace(DEFAULT_THEME.rows, hover=hover),
    )
    component = build(theme)
    plain = texts(component, 30)
    assert component.hover_at(row, col) is True
    assert any(
        seg.style.underline for line in component.render(30) for seg in line.segments
    )
    assert component.hover_at(row, col) is False
    assert component.hover_at(-1, -1) is True
    assert texts(component, 30) == plain


def test_a_theme_assignment_repaints_the_next_render():
    button = Button("Run")
    assert button.render(20)[0].segments[0].style == DEFAULT_THEME.controls.base
    other = replace(
        DEFAULT_THEME,
        controls=replace(DEFAULT_THEME.controls, base=Style(fg="#ff0000")),
    )
    button.theme = other
    assert button.render(20)[0].segments[0].style == Style(fg="#ff0000")


def test_the_action_hints_default_to_no_tooltip():
    assert Button("x").hint == ""
    assert Checkbox("x").hint == ""
    assert Link("x").hint == ""
