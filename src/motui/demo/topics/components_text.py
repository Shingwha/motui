"""Text topics: Text, Markdown, Diff and Notice."""

from __future__ import annotations

from dataclasses import replace

from motui import Markdown, Text
from motui.kernel.glyphs import GLYPHS
from motui.widgets import Diff, Notice

from ..stage import topic

_MARKDOWN = """\
# Release notes

motui 2.0 is a contract, not a skin: **events**, **results** and
**focus** gained one vocabulary each. A [link](https://example.invalid)
still opens wherever the host says.

- [ ] click a task box
- [x] the first task is done

```python
from motui import App
App().run()
```
"""


def _flip_task(source: str, index: int) -> str:
    """Flip the ``index``-th task box in a Markdown source."""
    lines = source.split("\n")
    seen = -1
    for position, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith(("- [ ]", "- [x]")):
            continue
        seen += 1
        if seen != index:
            continue
        if "- [ ]" in line:
            lines[position] = line.replace("- [ ]", "- [x]", 1)
        else:
            lines[position] = line.replace("- [x]", "- [ ]", 1)
        break
    return "\n".join(lines)


def _text(b) -> None:
    b.preview(
        Text("Plain Text wraps at the pane width, one row per logical line.", theme=b.theme),
        Text("A styled block keeps its style on every wrapped row.", style=b.theme.text.muted),
    )
    b.variants(
        ("accent style", Text("accent text", style=b.theme.content.accent)),
        ("dim style", Text("dim text", style=b.theme.text.faint)),
    )


def _markdown(b) -> None:
    sample = Markdown(_MARKDOWN, theme=b.theme)
    b.preview(sample)
    b.variants(
        ("gap=0", Markdown("# tight\nfirst\nsecond", gap=0, theme=b.theme)),
        ("task marks", Markdown("- [ ] open\n- [x] done", glyphs=replace(GLYPHS, check_off="\u25a1", check_on="\u25a0"), theme=b.theme)),
    )
    b.focus(sample)
    echo = b.echo("task")

    def note(report) -> None:
        if report.source is sample and str(report.value).startswith("todo:"):
            position = int(str(report.value).split(":", 1)[1])
            sample.text = _flip_task(sample.text, position)
            echo.set(sample.text.count("- [x]"), "checked")

    b.note(note)


def _diff(b) -> None:
    before = "alpha\nbeta\ngamma\ndelta\n"
    after = "alpha\nBETA\ngamma\ndelta\nepsilon\n"
    b.preview(Diff(before, after, numbers=True, theme=b.theme))
    b.variants(
        ("context=1", Diff(before, after, context=1, theme=b.theme)),
        ("numbers=False", Diff(before, after, numbers=False, theme=b.theme)),
    )


def _notice(b) -> None:
    b.preview(
        Notice("All changes are saved.", theme=b.theme),
        Notice("Disk space is running low.", level="warn", theme=b.theme),
        Notice("Connection lost.", level="error", theme=b.theme),
    )
    b.variants(
        ("info", Notice("plain information row", theme=b.theme)),
        ("unknown level degrades to info", Notice("anything else", level="debug", theme=b.theme)),
    )


TOPICS = (
    topic(
        key="text",
        title="Text",
        summary="The plain-text block: mutable text, one style, wrapping at the pane width.",
        group="Text",
        section="components",
        try_line="scroll the stage; drag over the rows to copy them",
        api_line="Text(text='', *, style=None, theme=None) \u00b7 render(width) \u00b7 text is mutable",
        components=("Text",),
        build=_text,
    ),
    topic(
        key="markdown",
        title="Markdown",
        summary="Rule-driven Markdown: headings, lists, fenced code, tables and task boxes.",
        group="Text",
        section="components",
        try_line="click a task box; drag to copy; the source is rewritten live",
        api_line="Markdown(text='', *, block_rules, inline_rules, glyphs, gap, max_width, theme)",
        components=("Markdown",),
        build=_markdown,
    ),
    topic(
        key="diff",
        title="Diff",
        summary="A unified diff between two texts: hunks, context rows and optional numbers.",
        group="Text",
        section="components",
        try_line="scroll the stage; the variants show context and numbering",
        api_line="Diff(before, after, *, context=3, numbers=False) · before/after writable",
        components=("Diff",),
        build=_diff,
    ),
    topic(
        key="notice",
        title="Notice",
        summary="One message row with a semantic level prefix: info, warn or error.",
        group="Text",
        section="components",
        try_line="none -- Notice is a display row; the level is the input",
        api_line="Notice(text, *, level='info'|'warn'|'error', theme=None) \u00b7 one fitted row",
        components=("Notice",),
        build=_notice,
    ),
)
