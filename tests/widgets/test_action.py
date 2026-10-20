"""Button, Checkbox and Link: the minimal clickable units and their bands."""

from dataclasses import replace

import pytest

from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Button, Checkbox, Link, Option, Select, Table, Tabs, Tree, TreeNode

from tests.testing import texts


def test_button_renders_one_fitted_row_in_the_accent_band():
    button = Button("Run")
    row = button.render(20)[0]
    assert row.text == " Run "
    assert row.segments[0].style == DEFAULT_THEME.accent
    assert button.render(3)[0].text == " R\u2026"


def test_button_hover_and_focus_merge_their_bands():
    button = Button("Run")
    button.hover = True
    assert button.render(20)[0].segments[0].style == DEFAULT_THEME.accent.merge(
        DEFAULT_THEME.hover
    )
    button.hover = False
    button.focused = True
    assert button.render(20)[0].segments[0].style == DEFAULT_THEME.accent.merge(
        DEFAULT_THEME.focus
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
    button = Button("Run", disabled=True, disabled_style=Style(italic=True))
    assert button.click(0, 0) is False and button.activate() is False
    assert button.take_result() is None
    assert button.render(20)[0].segments[0].style == Style(italic=True)


def test_explicit_styles_beat_the_theme_fields():
    theme = replace(DEFAULT_THEME, accent=Style(fg="#ff0000"), hover=Style(bg="#00ff00"))
    button = Button("x", style=Style(underline=True), hover_style=Style(italic=True), theme=theme)
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


def test_checkbox_takes_a_custom_mark_pair_and_its_style_surface():
    box = Checkbox("Bold", mark_pair=("(x)", "( )"), style=Style(underline=True))
    assert box.render(20)[0].text == "( ) Bold"
    box.checked = True
    assert box.render(20)[0].text == "(x) Bold"
    assert box.render(20)[0].segments[0].style == Style(underline=True)


def test_a_disabled_checkbox_refuses_both_doors():
    box = Checkbox("Bold", disabled=True)
    assert box.activate() is False and box.click(0, 0) is False
    assert box.checked is False and box.take_result() is None


def test_link_follows_a_click_and_wears_the_link_band():
    link = Link("docs/COMPONENTS.md")
    assert link.render(30)[0].text == "docs/COMPONENTS.md"
    assert link.render(30)[0].segments[0].style == DEFAULT_THEME.link
    assert link.take_result() is None
    assert link.click(0, 3) is True and link.take_result() is True
    assert link.take_result() is None


def test_link_focus_and_disabled_flags_shape_the_row():
    link = Link("docs", focus_style=Style(bold=True), disabled_style=Style(italic=True))
    link.focused = True
    assert link.render(20)[0].segments[0].style == DEFAULT_THEME.link.merge(Style(bold=True))
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
    component = build(replace(DEFAULT_THEME, hover=Style(underline=True)))
    plain = texts(component, 30)
    assert component.hover_at(row, col) is True
    assert any(
        seg.style.underline for line in component.render(30) for seg in line.segments
    )
    assert component.hover_at(row, col) is False
    assert component.hover_at(-1, -1) is True
    assert texts(component, 30) == plain


def test_the_action_hints_default_to_no_tooltip():
    assert Button("x").hint == ""
    assert Checkbox("x").hint == ""
    assert Link("x").hint == ""
