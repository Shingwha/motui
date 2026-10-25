"""Pattern topics: streaming Markdown, validation, the palette and a shell."""

from __future__ import annotations

from motui import Button, Checkbox, Editor, Input, Markdown, Table
from motui.widgets import Column, Divider, Field, Form, Notice, ShortcutBar, StatusLine

from ..assets import blocks_of, fixture_text
from ..stage import topic

_CHUNKS = blocks_of(fixture_text())


def _streaming_markdown(b) -> None:
    stream = Markdown("".join(_CHUNKS[:2]), theme=b.theme)
    state = {"next": 2}
    b.preview(stream)
    b.focus(stream)

    def tick() -> None:
        position = state["next"]
        if position >= len(_CHUNKS):
            stream.text = "".join(_CHUNKS[:2])
            state["next"] = 2
            return
        stream.text += _CHUNKS[position]
        state["next"] = position + 1

    b.tick(tick)


def _form_validation(b) -> None:
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
    b.preview(form)
    b.focus(form)
    echo = b.echo("submitted")

    def note(report) -> None:
        if report.source is form:
            echo.set(report.value)

    b.note(note)


def _command_palette(b) -> None:
    commands = list(b.session.commands)[:6]
    rows = [[command.name, command.description] for command in commands]
    rows.append([f"\u2026 {len(b.session.commands)} commands total", "press / or c-k"])
    table = Table(["command", "group"], rows, theme=b.theme)
    opener = Button("Open the / palette", theme=b.theme)
    opener.hint = "the same registry the global palette reads"
    b.preview(table, opener)
    b.focus(opener)

    def note(report) -> None:
        if report.source is opener:
            b.session.open_palette()

    b.note(note)


def _own_shell(b) -> None:
    editor = Editor("type here", max_rows=3, theme=b.theme)
    bar = ShortcutBar([("enter", "submit"), ("esc", "cancel")], theme=b.theme)
    status = StatusLine(left=("ready",), right=("own shell",), theme=b.theme)
    b.preview(
        Column(
            [
                editor,
                Divider(theme=b.theme),
                bar,
                status,
                Notice("These are ordinary components; the footer dock is the shell's choice.", theme=b.theme),
            ],
            gap=0,
        )
    )
    b.focus(editor)


TOPICS = (
    topic(
        key="streaming-markdown",
        title="Streaming Markdown",
        summary="A Markdown document that grows one block per beat, appended in place.",
        group="Live",
        section="patterns",
        try_line="watch the interactive beat append fixture blocks; scroll to follow the tail",
        api_line="app.every(0.12, tick) \u00b7 markdown.text += block \u00b7 the tail re-renders",
        components=("Markdown",),
        build=_streaming_markdown,
    ),
    topic(
        key="form-validation",
        title="Form validation",
        summary="Validate on submit: errors land under their fields; a valid form leaves a mapping.",
        group="Live",
        section="patterns",
        try_line="tab/down move fields; enter validates; empty fields show errors",
        api_line="Form([Field(name, component, validate=...)]) \u00b7 handle() \u00b7 take()",
        components=("Form", "Field", "Input", "Checkbox"),
        build=_form_validation,
    ),
    topic(
        key="command-palette",
        title="Command palette",
        summary="CommandRegistry is one ordered collection; the palette is its options() view.",
        group="Composition",
        section="patterns",
        try_line="click Open the / palette, type a section or topic, enter jumps there",
        api_line="CommandRegistry([Command(name=..., description=..., group=..., handler=...)]) \u00b7 options() \u00b7 match(query)",
        components=("CommandPalette", "Table", "Button"),
        build=_command_palette,
    ),
    topic(
        key="own-shell",
        title="Own shell",
        summary="A footer dock is a Document: editor, shortcut bar and status row, ordinary components.",
        group="Composition",
        section="patterns",
        try_line="type in the editor; the rows under it are the shell's own footer",
        api_line="app.dock(footer, placement=Placement.BOTTOM, size=2) \u00b7 ShortcutBar \u00b7 StatusLine",
        components=("Editor", "ShortcutBar", "StatusLine", "Divider", "Notice"),
        build=_own_shell,
    ),
)
