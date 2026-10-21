"""Form topics: fields, choices, menus, the slider and the form itself."""

from __future__ import annotations

from motui import Button, Checkbox, Input, Modal, Option, Select
from motui.widgets import (
    Autocomplete,
    CheckboxGroup,
    ComboBox,
    Editor,
    Field,
    Form,
    RadioGroup,
    Slider,
)

from ..stage import topic


class _ComboHost:
    """The ComboBox recipe: the combo owns the keys, a Modal paints the list.

    The combo declines mouse reports, so the modal keeps them; the two
    states are synced after every routed event.  The controller also holds
    the pick across the close, so the session's generic read cannot consume
    it before the modal closes.
    """

    __slots__ = ("_result", "combo", "modal")

    def __init__(self, combo: ComboBox, modal: Modal) -> None:
        self.combo = combo
        self.modal = modal
        self._result: object | None = None

    @property
    def is_open(self) -> bool:
        return self.combo.is_open or self.modal.is_open

    def open(self) -> None:
        self._result = None
        self.combo.open()
        self.modal.open()

    def close(self) -> None:
        self.combo.close()
        self.modal.close()

    def detach(self) -> None:
        self.modal.detach()

    def handle(self, event) -> bool:
        if not self.modal.is_open:
            return False
        consumed = self.combo.handle(event)
        if not consumed:
            consumed = self.modal.handle(event)
        value = self.combo.take_result()
        if value is not None:
            self._result = value
        if self.combo.is_open and not self.modal.is_open:
            self.combo.close()  # a click outside closed the panel with it
        if not self.combo.is_open and self.modal.is_open:
            self.modal.close()
        return True

    def take_result(self) -> object | None:
        value, self._result = self._result, None
        return value


def _input(b) -> None:
    first = Input("hello", theme=b.theme)
    second = Input("secret", mask="\u2022", theme=b.theme)
    readonly = Input("read only", read_only=True, theme=b.theme)
    b.preview(first, second)
    b.variants(("read-only", readonly), ("placeholder", Input("", placeholder="type here", theme=b.theme)))
    b.focus(first, second, readonly)


def _editor(b) -> None:
    editor = Editor("line one\nline two\nline three", max_rows=6, theme=b.theme)
    b.preview(editor)
    b.variants(
        ("max_rows=2", Editor("one\ntwo\nthree", max_rows=2, theme=b.theme)),
        ("masked", Editor("hidden", mask="\u2022", max_rows=2, theme=b.theme)),
    )
    b.focus(editor)


def _checkbox(b) -> None:
    ship = Checkbox("Ship it", checked=True, theme=b.theme)
    ship.hint = "flip the toggle"
    notify = Checkbox("Notify me", theme=b.theme)
    b.preview(ship, notify, Checkbox("Disabled", disabled=True, theme=b.theme))
    b.focus(ship, notify)
    echo = b.echo("checked")

    def note(report) -> None:
        if report.source in (ship, notify):
            echo.set(report.value)

    b.note(note)


def _radio_group(b) -> None:
    group = RadioGroup(["Small", "Medium", "Large"], index=1, theme=b.theme)
    b.preview(group)
    b.variants(
        ("disabled item", RadioGroup(["A", "B", "C"], disabled_items=[1], theme=b.theme)),
        ("Option payloads", RadioGroup([Option("A", 1), Option("B", 2)], theme=b.theme)),
    )
    b.focus(group)
    echo = b.echo("selected")

    def note(report) -> None:
        if report.source is group:
            echo.set(report.value)

    b.note(note)


def _checkbox_group(b) -> None:
    group = CheckboxGroup(["Bold", "Italic", "Underline"], marked=[0], theme=b.theme)
    group.take_result()  # a fresh mount reports nothing until the user acts
    all_marked = CheckboxGroup(["One", "Two", "Three"], marked=[0, 1, 2], theme=b.theme)
    all_marked.take_result()
    b.preview(group)
    b.variants(
        ("all marked", all_marked),
        ("disabled item", CheckboxGroup(["One", "Two"], disabled_items=[1], theme=b.theme)),
    )
    b.focus(group)
    echo = b.echo("marked")

    def note(report) -> None:
        if report.source is group:
            echo.set(report.value)

    b.note(note)


def _select(b) -> None:
    options = [Option(f"option {index:02d}", f"value {index:02d}", "a row") for index in range(1, 7)]
    main = Select(options, title="pick one", max_rows=4, theme=b.theme)
    windowed = Select(options, max_rows=3, window=True, theme=b.theme)
    multi = Select(options, multi=True, marked=[1, 3], max_rows=5, theme=b.theme)
    multi.take_result()  # the initial marks are state, not a pick
    b.preview(main)
    b.variants(("windowed max_rows=3", windowed), ("multi + marks", multi))
    b.focus(main, windowed, multi)
    echo = b.echo("picked")

    def note(report) -> None:
        if report.source in (main, windowed, multi):
            echo.set(report.value)

    b.note(note)


def _combobox(b) -> None:
    options = [
        Option("Dialog", "dialog"),
        Option("Palette", "palette"),
        Option("Toasts", "toasts"),
        Option("Tooltip", "tooltip"),
    ]
    combo = ComboBox(options, theme=b.theme, max_rows=4)
    opener = Button("Open dropdown", theme=b.theme)
    opener.hint = "open the combo list"
    modal = Modal(b.session.tui, combo.list, anchor=(7, 4), theme=b.theme)
    host = _ComboHost(combo, modal)
    b.preview(combo, opener)
    b.modal(host)
    b.focus(combo, opener)
    echo = b.echo("picked")

    def note(report) -> None:
        if report.source is opener:
            host.open()
        elif report.source is host:
            echo.set(report.value)

    b.note(note)


def _autocomplete(b) -> None:
    options = [
        Option("Autocomplete", "autocomplete", "query-filtered menu"),
        Option("Dialog", "dialog", "a blocking panel"),
        Option("Diff", "diff", "a unified diff"),
        Option("Find", "find", "the search tier"),
    ]
    field = Autocomplete(options, max_rows=5, theme=b.theme)
    narrowed = Autocomplete(options, max_rows=5, theme=b.theme)
    narrowed.set_query("di")
    b.preview(field)
    b.variants(("query 'di'", narrowed), ("no matches", Autocomplete(options, max_rows=3, theme=b.theme)))
    b.focus(field)
    echo = b.echo("picked")

    def note(report) -> None:
        if report.source is field:
            echo.set(report.value)

    b.note(note)


def _slider(b) -> None:
    slider = Slider(4, minimum=0, maximum=10, theme=b.theme)
    b.preview(slider)
    b.variants(
        ("step=2", Slider(4, minimum=0, maximum=10, step=2, theme=b.theme)),
        ("disabled", Slider(3, minimum=0, maximum=10, disabled=True, theme=b.theme)),
    )
    b.focus(slider)
    echo = b.echo("value")

    def note(report) -> None:
        if report.source is slider:
            echo.set(report.value)

    b.note(note)


def _form(b) -> None:
    form = Form(
        [
            Field(
                "name",
                Input(theme=b.theme),
                label="Name",
                validate=lambda value: None if str(value).strip() else "required",
            ),
            Field(
                "email",
                Input(theme=b.theme),
                label="Email",
                validate=lambda value: None if "@" in str(value) else "needs an @",
            ),
            Field(
                "agree",
                Checkbox("I agree", theme=b.theme),
                validate=lambda value: None if value else "please confirm",
            ),
        ],
        gap=1,
        theme=b.theme,
    )
    invalid = Form(
        [Field("email", Input("nope", theme=b.theme), label="Email", error="needs an @")],
        theme=b.theme,
    )
    b.preview(form)
    b.variants(("field errors", invalid), ("gap=0", Form([Field("name", Input("Ada", theme=b.theme), label="Name")], theme=b.theme)))
    b.focus(form)
    echo = b.echo("submitted")

    def note(report) -> None:
        if report.source is form:
            echo.set(report.value)

    b.note(note)


TOPICS = (
    topic(
        key="input",
        title="Input",
        summary="One-line text field: prompt, placeholder, mask, caret and read-only.",
        group="Forms",
        section="components",
        try_line="type; left/right or home/end; c-a selects all; masked and read-only variants",
        api_line="Input(text='', *, prompt, placeholder, mask, read_only, caret_style, keymap)",
        components=("Input",),
        build=_input,
    ),
    topic(
        key="editor",
        title="Editor",
        summary="Multi-line text buffer with wrapping, a row window and the same keymap seam.",
        group="Forms",
        section="components",
        try_line="type; enter breaks a line; arrows move; max_rows windows the buffer",
        api_line="Editor(text='', *, max_rows, mask, read_only, caret_style, keymap, theme)",
        components=("Editor",),
        build=_editor,
    ),
    topic(
        key="checkbox",
        title="Checkbox",
        summary="One row toggle with a mark pair, hover/focus bands and a one-shot result.",
        group="Forms",
        section="components",
        try_line="enter or click flips the focused box; space activates where toggleable",
        api_line="Checkbox(label, *, checked, disabled, glyphs) · activate/take_result",
        components=("Checkbox",),
        build=_checkbox,
    ),
    topic(
        key="radio-group",
        title="RadioGroup",
        summary="Single choice over a row cursor: move, activate, one value pending.",
        group="Forms",
        section="components",
        try_line="up/down move; enter takes the row; the chosen label lands below",
        api_line="RadioGroup(labels, *, index, disabled_items, active_style, theme) \u00b7 activate()",
        components=("RadioGroup", "Option"),
        build=_radio_group,
    ),
    topic(
        key="checkbox-group",
        title="Checkbox group",
        summary="Multiple choice with marks: the cursor moves, toggle flips the row.",
        group="Forms",
        section="components",
        try_line="up/down move; enter flips the cursor row's mark; the marked set is the result",
        api_line="CheckboxGroup(labels, *, marked, index, disabled_items, theme) \u00b7 toggle()",
        components=("CheckboxGroup", "Option"),
        build=_checkbox_group,
    ),
    topic(
        key="select",
        title="Select",
        summary="One menu over a sequence: cursor, window, marks, commit and a one-shot pick.",
        group="Forms",
        section="components",
        try_line="up/down move; enter takes the row; the windowed and multi variants work too",
        api_line="Select(options, *, title, max_rows, wrap, glyphs, commit, multi, window, theme)",
        components=("Select", "Option"),
        build=_select,
    ),
    topic(
        key="combobox",
        title="ComboBox",
        summary="An editable field over a filtered dropdown; the host paints it with a Modal.",
        group="Forms",
        section="components",
        try_line="click Open dropdown; type to filter; up/down move; enter takes; esc closes",
        api_line="ComboBox(options, *, max_rows, max_drop_rows) + Modal(tui, combo.list)",
        components=("ComboBox", "Modal", "Button", "Option"),
        build=_combobox,
    ),
    topic(
        key="autocomplete",
        title="Autocomplete",
        summary="A Select over query matches: prefix rows first, then substrings.",
        group="Forms",
        section="components",
        try_line="up/down move; enter takes; set_query() narrows the rows",
        api_line="Autocomplete(options, *, max_rows, wrap, theme) \u00b7 set_query(text) \u00b7 take_result()",
        components=("Autocomplete", "Option"),
        build=_autocomplete,
    ),
    topic(
        key="slider",
        title="Slider",
        summary="A stepped numeric control: arrows move on the step grid, enter takes the value.",
        group="Forms",
        section="components",
        try_line="left/right step the value; enter lands it; the disabled variant refuses",
        api_line="Slider(value, *, minimum, maximum, step, disabled, theme) \u00b7 move() \u00b7 take_result()",
        components=("Slider",),
        build=_slider,
    ),
    topic(
        key="form",
        title="Form",
        summary="Labelled fields, its own focus order, validation and one submitted mapping.",
        group="Forms",
        section="components",
        try_line="tab/down move fields; enter validates and submits; empty fields show errors",
        api_line="Form(fields, *, gap, index, on_submit) · Field(name, component, label, validate)",
        components=("Form", "Field", "Input", "Checkbox"),
        build=_form,
    ),
)
