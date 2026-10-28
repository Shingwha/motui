"""Cross-widget contracts: one test, every family that shares the verb."""

from __future__ import annotations

from dataclasses import replace

import pytest

from motui.kernel.layout import Constraints
from motui.kernel.style import Style
from motui.kernel.theme import DEFAULT_THEME
from motui.widgets import Button, Checkbox, ComboBox, Form, List, Option, Select

from tests.testing import key

THREE = [Option("one"), Option("two"), Option("three")]
OPTIONS = [
    Option("Autocomplete", value="autocomplete"),
    Option("Checkbox", value="checkbox"),
]


def _pick_combo(combo: ComboBox) -> bool:
    combo.open()
    return combo.on_key(key("enter"))


@pytest.mark.parametrize(
    ("build", "activate", "expected"),
    [
        (lambda: Select(THREE), lambda widget: widget.on_action("activate"), Option("one")),
        (lambda: List(["a"]), lambda widget: widget.on_action("activate"), "a"),
        (lambda: Form([]), lambda widget: widget.on_action("activate"), {}),
        (lambda: ComboBox(OPTIONS), _pick_combo, "autocomplete"),
    ],
    ids=["select", "list", "form", "combobox"],
)
def test_take_reads_the_result_once(build, activate, expected):
    widget = build()
    assert widget.take() is None
    assert activate(widget) is True
    assert widget.take() == expected
    assert widget.take() is None
    assert activate(widget) is True
    assert widget.take() == expected


@pytest.mark.parametrize(
    "build",
    [
        lambda: Button("Run"),
        lambda: Checkbox("Bold"),
        lambda: Select(THREE),
    ],
    ids=["button", "checkbox", "select"],
)
def test_a_theme_assignment_repaints_the_next_render(build):
    widget = build()
    plain = widget.render(Constraints(width=20))
    mark = Style(underline=True)
    other = replace(
        DEFAULT_THEME,
        text=replace(DEFAULT_THEME.text, base=mark),
        content=replace(DEFAULT_THEME.content, accent=mark),
        controls=replace(DEFAULT_THEME.controls, base=mark),
        rows=replace(DEFAULT_THEME.rows, inactive=mark),
    )
    widget.theme = other
    assert widget.render(Constraints(width=20)) != plain
