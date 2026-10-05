"""Tests for mocode_tui.core.style.

Contracts (COMPONENTS.md palette section + the Style docstring): ``prefix()``
emits SGR parameters -- attributes first, then fg, then bg; a color is a named
16-color (unknown names raise ``KeyError``), a ``#rrggbb`` string, or an
``(r, g, b)`` tuple (the latter two emit 24-bit truecolor); ``merge`` ORs
attributes and passes ``None`` fields through; ``Style`` is frozen and
hashable so ``prefix()`` is memoizable.
"""

import dataclasses

import pytest

from mocode_tui.core.style import (
    HEADING,
    INLINE_CODE,
    LINK,
    LIST_MARKER,
    RESET,
    Style,
)


def test_empty_style_prefix_is_empty():
    assert Style().prefix() == ""
    assert Style(bold=False).prefix() == ""


def test_named_colors_and_attribute_codes():
    assert Style(fg="red").prefix() == "\x1b[31m"
    assert Style(bg="blue").prefix() == "\x1b[44m"  # fg code + 10
    assert Style(dim=True).prefix() == "\x1b[2m"
    assert Style(reverse=True).prefix() == "\x1b[7m"


def test_code_order_is_attributes_then_fg_then_bg():
    style = Style(fg="cyan", bg="magenta", bold=True, italic=True, underline=True)
    assert style.prefix() == "\x1b[1;3;4;36;45m"


def test_truecolor_forms_and_equivalence():
    assert Style(fg="#58a6ff").prefix() == "\x1b[38;2;88;166;255m"
    assert Style(fg=(88, 166, 255)).prefix() == Style(fg="#58a6ff").prefix()
    assert Style(bg=(22, 40, 28)).prefix() == "\x1b[48;2;22;40;28m"
    assert Style(fg="#58a6ff", bold=True).prefix() == "\x1b[1;38;2;88;166;255m"
    assert Style(fg="cyan", bg="#16281c").prefix() == "\x1b[36;48;2;22;40;28m"


def test_unknown_color_name_raises_key_error():
    with pytest.raises(KeyError):
        Style(fg="chartreuse").prefix()
    with pytest.raises(KeyError):
        Style(bg="not-a-color").prefix()


def test_style_is_frozen_and_hashable():
    assert hash(Style(fg="red")) == hash(Style(fg="red"))
    assert Style(fg=(1, 2, 3)) == Style(fg=(1, 2, 3))
    assert Style(fg=(1, 2, 3)) != Style(fg=(1, 2, 4))
    assert len({Style(fg="red"), Style(fg="red"), Style()}) == 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        Style(fg="red").fg = "blue"  # type: ignore[misc]


def test_merge_none_passthrough_and_ored_attributes():
    base = Style(fg="red", bg="blue", bold=True)
    assert base.merge(Style()) == base  # None fields pass through
    merged = Style(fg="red", bg="blue").merge(Style(fg="green"))
    assert (merged.fg, merged.bg) == ("green", "blue")  # colors override
    both = Style(bold=True).merge(Style(dim=True))
    assert both.bold is True and both.dim is True  # attributes OR
    # Neither operand is mutated.
    other = Style(fg="green")
    assert base.merge(other) is not base and base.merge(other) is not other
    assert base == Style(fg="red", bg="blue", bold=True)
    assert other == Style(fg="green")


def test_reset_constant():
    assert RESET == "\x1b[0m"


def test_markdown_palette_constants():
    """One hue per Markdown construct; none of them is bold (bold stays
    reserved for the **...** syntax), and only the link is underlined."""
    assert HEADING == Style(fg="#e3b341")
    assert LINK == Style(fg="#58a6ff", underline=True)
    assert INLINE_CODE == Style(fg="#f778ba")
    assert LIST_MARKER == Style(fg="#bc8cff")
    for style in (HEADING, LINK, INLINE_CODE, LIST_MARKER):
        assert not style.bold
    assert not HEADING.underline and not INLINE_CODE.underline
    assert HEADING.prefix() == "\x1b[38;2;227;179;65m"
    assert LINK.prefix() == "\x1b[4;38;2;88;166;255m"
    assert INLINE_CODE.prefix() == "\x1b[38;2;247;120;186m"
    assert LIST_MARKER.prefix() == "\x1b[38;2;188;140;255m"
