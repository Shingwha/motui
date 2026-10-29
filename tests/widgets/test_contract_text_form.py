"""The 2.1.2 contract matrix for the text, form, dialog and indicator families.

The family's share of ``tests/widgets/test_contracts.py``: construction shape,
the state names, the verbs, ``take`` semantics and the one-shot pending rules.
Behaviour beyond the shared contract stays in the per-module test files.
"""

import inspect

import pytest

from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.widgets import (
    ButtonKind,
    ButtonSpec,
    Collapsible,
    Dialog,
    Editor,
    Field,
    Form,
    Input,
    Markdown,
    ProgressBar,
    Slider,
    Text,
)
from tests.testing import Rows, key, texts


def _positional_names(cls) -> list[str]:
    return [
        name
        for name, parameter in inspect.signature(cls).parameters.items()
        if parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]


def _keyword_names(cls) -> list[str]:
    return [
        name
        for name, parameter in inspect.signature(cls).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    ]


@pytest.mark.parametrize(
    "cls, main",
    [
        (Text, "text"),
        (Input, "text"),
        (Editor, "text"),
        (Form, "fields"),
        (Dialog, "body"),
        (Collapsible, "body"),
        (ProgressBar, "value"),
        (Slider, "value"),
    ],
)
def test_the_main_content_is_the_only_positional_parameter(cls, main):
    assert _positional_names(cls) == [main]


def test_the_keyword_tail_follows_the_shared_order():
    dialog = _keyword_names(Dialog)
    assert dialog == [
        "title",
        "buttons",
        "danger",
        "width",
        "align",
        "border",
        "shade",
        "frame",
        "glyphs",
        "theme",
        "styles",
    ]
    for cls in (Collapsible,):
        names = _keyword_names(cls)
        assert names[:4] == ["title", "open", "glyphs", "disabled"]
        assert names.index("theme") < names.index("styles")
    form = _keyword_names(Form)
    assert form[:3] == ["gap", "index", "on_submit"]
    assert form.index("theme") < form.index("styles")
    bar = _keyword_names(ProgressBar)
    assert bar[:2] == ["maximum", "label"]
    assert bar.index("glyphs") < bar.index("theme") < bar.index("styles")
    slider = _keyword_names(Slider)
    assert slider[:3] == ["minimum", "maximum", "step"]
    assert slider.index("glyphs") < slider.index("disabled")
    assert slider.index("theme") < slider.index("styles")
    field = _keyword_names(Input)
    assert field == [
        "prompt",
        "placeholder",
        "mask",
        "glyphs",
        "theme",
        "styles",
        "keymap",
        "read_only",
        "wrap",
    ]
    editor = _keyword_names(Editor)
    assert editor == [
        "placeholder",
        "mask",
        "theme",
        "styles",
        "keymap",
        "max_rows",
        "read_only",
        "wrap",
    ]


def test_text_and_markdown_keep_their_verbatim_state():
    text = Text("a\nb")
    assert texts(text, 10) == ["a", "b"]
    text.text = "c"
    assert texts(text, 10) == ["c"]

    markdown = Markdown("# heading")
    assert markdown.text.startswith("# heading")
    assert markdown.render(Constraints(width=20))[0].text == "heading"


def test_text_inline_action_is_the_one_shot_result():
    markdown = Markdown("[go](target)")
    row = markdown.render(Constraints(width=20))[0]
    assert markdown.on_click(Pos(y=0, x=row.text.index("go"))) is True
    assert markdown.take() == "target"
    assert markdown.take() is None


def test_collapsible_activates_into_toggle_and_emits_the_open_state():
    section = Collapsible(Text("body"), title="options")
    assert section.activate() is True and section.open is False
    assert section.take() is False
    assert section.toggle() is True and section.open is True
    assert section.take() is True
    assert section.on_action("activate") is True and section.open is False
    assert section.take() is False

    dead = Collapsible(Text("body"), disabled=True)
    assert dead.activate() is False
    assert dead.toggle() is False
    assert dead.take() is None


def test_form_selected_is_the_field_and_index_moves_the_focus():
    first, second = Input(), Input()
    form = Form([Field("a", first), Field("b", second)])
    assert form.index == 0
    assert form.selected.name == "a"
    assert form.move(1) is True and form.index == 1 and second.focused is True
    assert form.selected.name == "b"
    assert form.move(1) is False
    assert form.focus("a") is True and first.focused is True
    assert form.focus("missing") is False and form.index == 0
    assert form.index == 0 and form.selected.name == "a"


def test_form_activation_submits_and_movement_clears_the_submission():
    form = Form([Field("a", Input("value"))])
    assert form.activate() is True
    assert form.take() == {"a": "value"}
    assert form.take() is None

    assert form.activate() is True
    assert form.move(1) is False  # already the only field ...
    assert form.take() is None  # ... but a cursor verb still clears the pick


def test_a_failed_form_submission_writes_no_result():
    form = Form([Field("a", Input(), validate=lambda value: "bad")])
    form.activate()
    assert form.fields[0].error == "bad"
    assert form.take() is None
    assert form.on_action("activate") is False


def test_dialog_selected_is_the_button_and_focused_button_agrees():
    dialog = Dialog(Rows("body"), buttons=[ButtonSpec("Go", 7), ("Stop", 0)])
    assert dialog.index == 0
    assert dialog.selected.label == "Go"
    assert dialog.focused_button is dialog.selected
    assert dialog.move(1) is True and dialog.index == 1
    assert dialog.selected.label == "Stop"
    assert dialog.on_key(key("s-tab")) is True and dialog.index == 0


def test_dialog_enter_takes_a_value_and_escape_emits_a_legal_none():
    dialog = Dialog(Rows("body"), buttons=[ButtonSpec("Go", 7), ("Stop", 0)])
    assert dialog.on_key(key("enter")) is True
    assert dialog.take() == 7

    assert dialog.on_key(key("escape")) is True
    made, value = dialog._take_decision()
    assert (made, value) == (True, None)
    assert dialog._take_decision() == (False, None)


def test_a_none_valued_dialog_button_is_a_made_decision():
    dialog = Dialog(Rows("body"), buttons=[ButtonSpec("Cancel", None)])
    assert dialog.activate() is True
    assert dialog._take_decision() == (True, None)


def test_a_buttonless_dialog_declines_activation():
    dialog = Dialog(Rows("body"))
    assert dialog.activate() is False
    assert dialog.on_key(key("enter")) is False
    assert dialog.selected is None and dialog.focused_button is None
    assert dialog.take() is None


def test_button_spec_kind_is_the_fourth_field_and_drives_the_danger_rule():
    spec = ButtonSpec("Go", 7, None, ButtonKind.DANGER)
    assert (spec.label, spec.value, spec.styles, spec.kind) == (
        "Go",
        7,
        None,
        ButtonKind.DANGER,
    )
    assert not hasattr(spec, "danger")
    assert ButtonSpec("Go").kind is ButtonKind.NEUTRAL
    dialog = Dialog(
        Rows("body"),
        buttons=[ButtonSpec("Cancel", None), spec],
        danger=True,
    )
    assert dialog.danger is True
    assert dialog.index == 0  # the danger kind is never the default focus


def test_progress_bar_value_clamps_and_fraction_is_read_only():
    bar = ProgressBar(1.4)
    assert bar.value == 1.0 and bar.maximum == 1.0 and bar.fraction == 1.0
    bar.value = -2
    assert bar.value == 0.0 and bar.fraction == 0.0
    bar.value = 0.5
    assert bar.fraction == 0.5
    with pytest.raises(AttributeError):
        bar.fraction = 0.25  # type: ignore[misc]

    scaled = ProgressBar(5, maximum=10)
    assert scaled.value == 5 and scaled.fraction == 0.5
    scaled.value = 20
    assert scaled.value == 10 and scaled.fraction == 1.0


def test_progress_bar_rejects_a_non_positive_maximum():
    with pytest.raises(ValueError):
        ProgressBar(0.5, maximum=0)
    bar = ProgressBar(0.5)
    with pytest.raises(ValueError):
        bar.maximum = -1


def test_slider_activation_answers_availability_and_keeps_no_result():
    slider = Slider(4)
    assert slider.activate() is True
    assert slider.take() is None
    assert slider.on_action("activate") is True and slider.value == 4
    assert slider.on_action("next") is True and slider.value == 5
    assert slider.on_action("unknown") is False
    assert slider.take() is None
    assert Slider(4, disabled=True).activate() is False
