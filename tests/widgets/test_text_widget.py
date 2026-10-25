"""Text as a Widget: tree plumbing, capabilities and the typed hooks."""

from dataclasses import replace

from motui.kernel.cell import Line, Segment
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.text import WrapMode
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Column, Text
from motui.widgets.base import Widget


class SpanText(Text):
    """A Text whose one row carries an inline action: the documented seam."""

    def _rows_for(self, width: int) -> list[Line]:
        return [
            Line(
                (Segment("see ", Style()), Segment("docs", Style(), action="open"))
            ).clip(WrapMode.ELLIPSIS, width)
        ]


def test_text_is_a_widget_with_no_children_and_pointer_capabilities():
    text = Text("hi")

    assert isinstance(text, Widget)
    assert text.parent is None and text.children == []
    assert list(text.walk()) == [text]
    assert (text.focusable, text.clickable, text.hoverable, text.activatable) == (
        False,
        True,
        True,
        False,
    )


def test_a_container_adopts_text_and_sets_its_parent():
    text = Text("hi")
    column = Column([text])

    assert column.children == [text]
    assert text.parent is column
    assert list(column.walk()) == [column, text]


def test_on_click_lands_the_payload_and_take_clears_it():
    text = SpanText()
    text.render(Constraints(width=40))

    assert text.on_click(Pos(y=0, x=0)) is False
    assert text.on_click(Pos(y=0, x=5)) is True
    assert text.take() == "open"
    assert text.take() is None

    # The 1.x spellings keep the same answer until W3b3 removes them.
    assert text.on_click(Pos(x=5, y=0)) is True
    assert text.take() == "open"
    assert text.take() is None


def test_on_hover_marks_the_span_and_none_clears_it():
    band = Style(fg="#ff00ff", reverse=True)
    text = SpanText(
        theme=replace(
            DEFAULT_THEME,
            surfaces=replace(DEFAULT_THEME.surfaces, hover=band),
        )
    )
    text.render(Constraints(width=40))

    assert text.on_hover(Pos(y=0, x=5)) is True
    assert text.on_hover(Pos(y=0, x=5)) is False
    hovered = text.render(Constraints(width=40))[0]
    assert hovered.segments[1].style == Style().merge(band)
    assert hovered.segments[1].text == "docs"

    assert text.on_hover(None) is True
    assert text.on_hover(None) is False
    assert text.render(Constraints(width=40))[0].segments[1].style == Style()


def test_plain_text_declines_both_pointer_hooks():
    text = Text("hello")
    text.render(Constraints(width=10))

    assert text.on_click(Pos(y=0, x=0)) is False
    assert text.take() is None
    assert text.on_hover(Pos(y=0, x=0)) is False
    assert text.on_hover(None) is False


def test_text_has_no_action_verb():
    text = Text("hi")

    assert text.on_action("activate") is False
    assert text.on_action("toggle") is False
