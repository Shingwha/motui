"""Decor, layout, padding and the foldable section."""

from dataclasses import replace

import pytest

from motui.kernel.cell import Line, Surface
from motui.kernel.document import descend
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME, Styles
from motui.widgets import (
    Align,
    Button,
    Canvas,
    Collapsible,
    Column,
    Divider,
    Padding,
    Panel,
    Row,
    Spacer,
    Stack,
)
from motui.widgets.base import Container, Widget
from motui.widgets.text import Text
from tests.testing import Rows, texts

# -- Divider ------------------------------------------------------------------


@pytest.mark.parametrize("width, expected", [(5, "\u2500" * 5)])
def test_a_divider_fills_the_width_with_one_repeated_char(width, expected):
    assert texts(Divider(), width) == [expected]


def test_a_divider_embeds_a_label_between_rule_segments():
    divider = Divider(label="load")
    assert texts(divider, 20) == ["\u2500\u2500 load " + "\u2500" * 12]
    divider.label = "x"
    assert texts(divider, 20)[0].startswith("\u2500\u2500 x ")


def test_a_divider_cap_shortens_the_span_and_ellipsizes_the_label():
    assert texts(Divider(max_width=6), 20) == ["\u2500" * 6]
    narrow = texts(Divider(label="a long label", max_width=8), 20)[0]
    assert len(narrow) == 8 and narrow.startswith("\u2500\u2500 ")


# -- Panel --------------------------------------------------------------------


def test_a_panel_frames_the_child_with_a_title():
    rows = Panel(Rows("body"), title="T").render(Constraints(width=10))
    assert [row.text for row in rows] == [
        "\u250c\u2500 T \u2500\u2500\u2500\u2500\u2510",
        "\u2502 body   \u2502",
        "\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518",
    ]


def test_a_panel_below_four_columns_degrades_to_the_bare_child():
    assert texts(Panel(Rows("body")), 3) == ["bo\u2026"]


def test_a_borderless_panel_keeps_the_inset_and_drops_the_title():
    panel = Panel(Rows("body"), title="T", frame=False)
    assert texts(panel, 8) == [" body   "]


def test_a_borderless_panel_style_is_its_ground_under_the_child():
    ground = Style(fg="#101010")
    row = Panel(
        Rows("body"),
        frame=False,
        styles=Styles(surfaces=replace(DEFAULT_THEME.surfaces, base=ground)),
    ).render(Constraints(width=8))[0]
    assert all(seg.style == ground for seg in row.segments)
    themed = Panel(
        Rows("body"),
        frame=False,
        theme=replace(
            DEFAULT_THEME, borders=replace(DEFAULT_THEME.borders, base=ground)
        ),
    ).render(Constraints(width=8))[0]
    assert all(seg.style == Style() for seg in themed.segments)


# -- Row / Column -------------------------------------------------------------


def test_a_row_lays_out_fixed_and_flexible_columns():
    row = Row([Rows("a", "b"), Rows("x")], widths=[2, None], gap=1)
    assert texts(row, 10) == ["a  x      ", "b         "]


def test_a_column_stacks_children_with_gaps():
    column = Column([Rows("a", "b"), Rows("c")], gap=1)
    assert texts(column, 5) == ["a", "b", "", "c"]


def test_containers_nest_one_level():
    nested = Row([Column([Rows("a"), Rows("b")]), Rows("x")], widths=[2, None], gap=1)
    assert texts(nested, 8) == ["a  x    ", "b       "]


# -- Stack --------------------------------------------------------------------


def test_a_stack_paints_children_bottom_to_top():
    assert texts(Stack([Rows("abc"), Rows(" X ")]), 5) == ["aXc  "]
    # A blank top row is transparent: the layer below shows through.
    assert texts(Stack([Rows("abc"), Rows("   ")]), 5) == ["abc  "]


def test_a_stack_merges_the_lower_style_under_a_top_cell():
    depth = Style(fg="#123456")
    tint = Style(bg="#654321")
    stacked = Stack([Text("abc", style=depth), Text("X", style=tint)])
    row = stacked.render(Constraints(width=3))[0]
    assert row.text == "Xbc"
    assert row.segments[0].style == depth.merge(tint)
    assert row.segments[1].style == depth


def test_a_stack_routes_hits_to_the_first_interactive_layer_top_down():
    background = Canvas(width=5, height=1)
    button = Button("go")
    # A non-interactive Canvas on top is not a click target: the Button
    # below it takes the cell.
    under_canvas = Stack([button, background])
    under_canvas.render(Constraints(width=5, max_height=1))
    assert under_canvas.child_at(0, 0) == (button, 0, 0)
    # The same holds with the Button on top (the ordinary z-order case).
    over_canvas = Stack([background, button])
    over_canvas.render(Constraints(width=5, max_height=1))
    assert over_canvas.child_at(0, 0) == (button, 0, 0)


def test_a_stack_finds_a_nested_interactive_child_through_padding():
    button = Button("go")
    padded = Padding(button, left=1)
    stack = Stack([padded])
    stack.render(Constraints(width=8, max_height=1))
    # The Stack answers the Padding layer (its child_at keeps descending)...
    assert stack.child_at(0, 1) == (padded, 0, 1)
    # ...and the chain reaches the Button, which is the interactive node.
    assert descend(stack, 0, 1) == (button, 0, 0)


def test_a_stack_hit_falls_back_to_the_topmost_containing_layer():
    bottom, top = Rows("abc"), Rows("xyz")
    stack = Stack([bottom, top])
    stack.render(Constraints(width=5))
    assert stack.child_at(0, 0) == (top, 0, 0)
    assert stack.child_at(1, 0) is None  # below every layer
    assert stack.child_at(0, 9) is None  # past every layer


def test_a_stack_answers_the_blank_frame_and_the_height_budget():
    empty = Stack([])
    assert empty.render(Constraints(width=4)).width == 4
    assert list(empty.render(Constraints(width=4))) == []
    assert [row.text for row in empty.render(Constraints(width=4, max_height=2))] == [
        "",
        "",
    ]
    one = Stack([Rows("a", "b")])
    assert [row.text for row in one.render(Constraints(width=3, max_height=1))] == ["a"]
    assert list(one.render(Constraints(width=3, max_height=0))) == []


def test_a_stack_is_a_container_with_adopted_children():
    first, second = Text("a"), Text("b")
    stack = Stack([first, second])
    assert isinstance(stack, Container)
    assert stack.children == [first, second]
    assert first.parent is stack and second.parent is stack
    assert list(stack.walk()) == [stack, first, second]


# -- Align --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("horizontal", "left"), [("left", 0), ("center", 2), ("right", 4)]
)
@pytest.mark.parametrize(
    ("vertical", "top"), [("top", 0), ("middle", 1), ("bottom", 2)]
)
def test_align_places_the_child_at_each_anchor(horizontal, left, vertical, top):
    aligned = Align(Rows("ab", "cd"), horizontal=horizontal, vertical=vertical)
    rows = aligned.render(Constraints(width=6, max_height=4))
    expected = [" " * 6] * 4
    expected[top] = " " * left + "ab" + " " * (6 - left - 2)
    expected[top + 1] = " " * left + "cd" + " " * (6 - left - 2)
    assert [row.text for row in rows] == expected


def test_align_rejects_unknown_anchors():
    with pytest.raises(ValueError):
        Align(Rows("x"), horizontal="middle")
    with pytest.raises(ValueError):
        Align(Rows("x"), vertical="center")


def test_align_clips_a_child_that_overflows_the_frame():
    assert texts(Align(Rows("abcdef"), horizontal="center"), 4) == ["abcd"]
    assert texts(Align(Rows("abcdef"), horizontal="right"), 4) == ["abcd"]
    # Vertically the frame budget clips the child from the bottom.
    aligned = Align(Rows("a", "b", "c"), horizontal="left", vertical="bottom")
    assert [row.text for row in aligned.render(Constraints(width=3, max_height=2))] == [
        "a  ",
        "b  ",
    ]


def test_align_forwards_child_at_inside_the_painted_rectangle():
    child = Rows("ab", "cd")
    aligned = Align(child, horizontal="right", vertical="bottom")
    aligned.render(Constraints(width=6, max_height=4))
    assert aligned.child_at(0, 0) is None
    assert aligned.child_at(2, 3) is None  # child's own blank padding column
    assert aligned.child_at(2, 4) == (child, 0, 0)
    assert aligned.child_at(3, 5) == (child, 1, 1)
    assert Align(Rows("x")).child_at(0, 0) is None  # nothing rendered yet


def test_align_shows_no_effect_for_a_child_that_fills_the_width():
    assert texts(Align(Rows("abcd"), horizontal="center"), 4) == ["abcd"]


# -- Spacer / Padding ---------------------------------------------------------


def test_a_spacer_renders_blank_rows():
    assert texts(Spacer(3), 10) == ["", "", ""]
    assert list(Spacer(0).render(Constraints(width=10))) == []
    assert list(Spacer(-2).render(Constraints(width=10))) == []


def test_padding_surrounds_the_child_with_plain_spaces():
    padded = Padding(Rows("ab"), left=1, right=1, top=1, bottom=1)
    assert texts(padded, 6) == ["", " ab ", ""]


def test_padding_fill_paints_a_continuous_band_under_the_child():
    fill = Style(fg="#101010")
    row = Padding(
        Rows("ab"),
        left=1,
        right=1,
        styles=Styles(surfaces=replace(DEFAULT_THEME.surfaces, base=fill)),
    ).render(Constraints(width=6))[0]
    assert row.text == " ab   " and row.width == 6
    assert all(seg.style == fill for seg in row.segments)


# -- child_at -----------------------------------------------------------------


def test_a_column_maps_rows_and_owns_its_gaps():
    first, second = Rows("a"), Rows("b", "c")
    column = Column([first, second], gap=1)
    column.render(Constraints(width=5))
    assert column.child_at(0, 0) == (first, 0, 0)
    assert column.child_at(1, 0) is None
    assert column.child_at(3, 0) == (second, 1, 0)
    assert column.child_at(4, 0) is None


def test_a_row_maps_columns_and_owns_gaps_and_filler_rows():
    first, second = Rows("a", "b"), Rows("x")
    row = Row([first, second], widths=[2, None], gap=1)
    row.render(Constraints(width=10))
    assert row.child_at(0, 0) == (first, 0, 0)
    assert row.child_at(0, 2) is None
    assert row.child_at(0, 3) == (second, 0, 0)
    assert row.child_at(1, 3) is None
    assert Row([first]).child_at(0, 0) is None  # nothing rendered yet


def test_padding_declines_its_own_whitespace():
    child = Rows("ab")
    padded = Padding(child, left=2, top=1)
    padded.render(Constraints(width=10))
    assert padded.child_at(0, 2) is None
    assert padded.child_at(1, 1) is None
    assert padded.child_at(1, 2) == (child, 0, 0)
    assert padded.child_at(2, 2) is None


def test_a_panel_maps_only_its_content_cells_to_the_child():
    child = Rows("ab", "cd")
    panel = Panel(child)
    panel.render(Constraints(width=10))
    assert panel.child_at(0, 1) is None
    assert panel.child_at(1, 2) == (child, 0, 0)
    assert panel.child_at(2, 2) == (child, 1, 0)
    assert panel.child_at(3, 1) is None


# -- Collapsible --------------------------------------------------------------


def test_a_collapsible_folds_its_body_away_and_back():
    section = Collapsible(Text("body one\nbody two"), title="options")
    assert texts(section, 20) == ["\u25be options", "  body one", "  body two"]
    section.open = False
    assert texts(section, 20) == ["\u25b8 options"]


def test_click_and_activate_flip_the_section_and_leave_the_state_pending():
    section = Collapsible(Text("body"), title="options")
    assert section.on_action("activate") is True
    assert (section.open, section.take()) == (False, False)
    assert section.on_click(Pos(x=40, y=0)) is True
    assert (section.open, section.take()) == (True, True)
    assert section.on_click(Pos(x=0, y=1)) is False and section.take() is None


def test_the_collapsible_title_takes_hover_and_focus_bands():
    title = Style(fg="#abcdef")
    hover = Style(italic=True)
    focus = Style(underline=True)
    section = Collapsible(
        Text("body"),
        title="options",
        styles=Styles(
            content=replace(DEFAULT_THEME.content, accent=title),
            surfaces=replace(DEFAULT_THEME.surfaces, hover=hover),
            controls=replace(DEFAULT_THEME.controls, focus=focus),
        ),
    )
    plain = section.render(Constraints(width=20))
    assert section.on_hover(Pos(x=1, y=0)) is True
    assert section.render(Constraints(width=20))[0].segments[0].style == title.merge(hover)
    assert section.render(Constraints(width=20))[1] == plain[1]
    section.on_hover(Pos(x=0, y=1))
    section.focused = True
    assert section.render(Constraints(width=20))[0].segments[0].style == title.merge(focus)
    assert section.on_hover(Pos(x=0, y=1)) is False
    assert section.render(Constraints(width=20))[1] == plain[1]


def test_the_collapsible_child_at_maps_the_body_and_owns_the_title():
    section = Collapsible(Text("body one\nbody two"), title="options")
    section.render(Constraints(width=20))
    assert section.child_at(0, 3) is None
    assert section.child_at(1, 3) == (section.body, 0, 1)
    assert section.child_at(2, 2) == (section.body, 1, 0)
    assert section.child_at(3, 0) is None


def test_a_disabled_collapsible_refuses_both_doors_and_nested_content_fits():
    section = Collapsible(Text("body"), title="options", disabled=True)
    assert section.on_action("activate") is False and section.on_click(Pos(x=0, y=0)) is False
    nested = Collapsible(
        Collapsible(Text("a long body line to wrap"), title="inner"), title="outer"
    )
    assert all(row.width <= 12 for row in nested.render(Constraints(width=12)))


# -- the 2.0 render contract -------------------------------------------------


def test_a_row_takes_constraints_and_honours_the_height_budget():
    row = Row([Rows("a", "b"), Rows("x")], widths=[2, None], gap=1)
    surface = row.render(Constraints(width=10, max_height=1))
    assert isinstance(surface, Surface)
    assert [row_.text for row_ in surface] == ["a  x      "]
    assert row.render(Constraints(width=10)) == row.render(Constraints(width=10))


def test_a_column_takes_constraints_and_honours_the_height_budget():
    column = Column([Rows("a", "b"), Rows("c")], gap=1)
    surface = column.render(Constraints(width=5, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["a", "b"]
    assert [row.text for row in column.render(Constraints(width=5))] == ["a", "b", "", "c"]


def test_padding_takes_constraints_and_honours_the_height_budget():
    padded = Padding(Rows("ab"), left=1, right=1, top=1, bottom=1)
    surface = padded.render(Constraints(width=6, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["", " ab "]
    assert all(row.width <= 6 for row in surface)


def test_a_spacer_takes_constraints_and_honours_the_height_budget():
    surface = Spacer(3).render(Constraints(width=10, max_height=2))
    assert isinstance(surface, Surface)
    assert surface.height == 2
    assert all(row == Line() for row in surface)


def test_a_divider_takes_constraints_and_honours_the_height_budget():
    divider = Divider(char="-", label="load")
    surface = divider.render(Constraints(width=10, max_height=1))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == ["-- load --"]
    assert divider.render(Constraints(width=10)) == divider.render(Constraints(width=10))
    assert list(Divider(char="-").render(Constraints(width=5, max_height=0))) == []


def test_a_collapsible_takes_constraints_and_honours_the_height_budget():
    section = Collapsible(Text("body one\nbody two"), title="options")
    assert isinstance(section.render(Constraints(width=20)), Surface)
    assert section.render(Constraints(width=20)) == section.render(Constraints(width=20))
    surface = section.render(Constraints(width=20, max_height=2))
    assert [row.text for row in surface] == ["\u25be options", "  body one"]
    assert list(section.render(Constraints(width=20, max_height=0))) == []
    # The body geometry is the untruncated last render's, like the other
    # W2a containers: the budget shapes the returned rows only.
    assert section.child_at(2, 2) == (section.body, 1, 0)


def test_a_panel_takes_constraints_and_honours_the_height_budget():
    panel = Panel(Rows("body"), title="T")
    surface = panel.render(Constraints(width=10, max_height=2))
    assert isinstance(surface, Surface)
    assert [row.text for row in surface] == [
        "\u250c\u2500 T \u2500\u2500\u2500\u2500\u2510",
        "\u2502 body   \u2502",
    ]
    assert [row.text for row in panel.render(Constraints(width=10))][-1] == (
        "\u2514" + "\u2500" * 8 + "\u2518"
    )


# -- the 2.0 tree -------------------------------------------------------------


def test_the_layout_containers_are_widgets_with_adopted_children():
    first, second = Text("a"), Text("b")
    row = Row([first, second], widths=[2, None], gap=1)

    assert isinstance(row, Container) and isinstance(row, Widget)
    assert row.children == [first, second]
    assert first.parent is row and second.parent is row
    assert list(row.walk()) == [row, first, second]

    child = Text("c")
    column = Column([child], gap=1)
    assert isinstance(column, Container) and isinstance(column, Widget)
    assert column.children == [child] and child.parent is column
    assert list(column.walk()) == [column, child]


def test_panel_and_padding_expose_their_single_child_in_the_tree():
    framed = Text("x")
    panel = Panel(framed, title="T")
    assert panel.children == [framed] and framed.parent is panel
    assert list(panel.walk()) == [panel, framed]

    padded_child = Text("y")
    padded = Padding(padded_child, left=1)
    assert padded.children == [padded_child] and padded_child.parent is padded
    assert list(padded.walk()) == [padded, padded_child]


def test_a_spacer_is_a_childless_widget_and_not_a_container():
    spacer = Spacer(2)

    assert isinstance(spacer, Widget)
    assert not isinstance(spacer, Container)
    assert spacer.children == [] and list(spacer.walk()) == [spacer]
    assert list(Spacer(0).render(Constraints(width=10))) == []


def test_a_divider_is_a_childless_widget():
    divider = Divider(char="-")

    assert isinstance(divider, Widget)
    assert divider.children == [] and list(divider.walk()) == [divider]


def test_the_tree_visits_a_shared_child_once():
    shared = Text("shared")
    row = Row([shared, shared], widths=[6, 6], gap=1)

    assert list(row.walk()) == [row, shared]
    assert shared.parent is row


def test_a_collapsible_adopts_its_body_and_answers_the_toggle_action():
    body = Text("body")
    section = Collapsible(body, title="options")

    assert section.children == [body] and body.parent is section
    assert list(section.walk()) == [section, body]
    assert (
        section.focusable,
        section.clickable,
        section.hoverable,
        section.activatable,
    ) == (True, True, True, True)

    assert section.on_action("unknown") is False
    assert section.on_action("toggle") is True
    assert (section.open, section.take()) == (False, False)
    assert section.on_click(Pos(y=0, x=40)) is True
    assert (section.open, section.take()) == (True, True)
    assert section.on_click(Pos(y=1, x=0)) is False
    assert section.take() is None
