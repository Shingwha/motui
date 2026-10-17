"""The content page: ``Text`` and ``Markdown`` -- the primitives that carry it.

Static on purpose: the two components that render the gallery's own copy,
one sample each.  The paragraph is the wrapping proof -- it re-breaks at
whatever width the pane hands it, so a live terminal's resize is the demo --
and the Markdown sample is one of every construct the engine renders.

The sample's ``[link](https://example.invalid)`` is also the wave's exhibit:
a Markdown link is a real hyperlink (the row's bytes carry the OSC 8 pair,
so a terminal's own cmd+click can open it) **and** an application-side
action -- a click on the label lands the url in ``Markdown.chosen``, the
host reads that pick once, and the toast plus this page's echo line answer.
The echo is an empty ``Markdown``: an empty document renders **zero** rows,
so the line exists only after a pick and the page's read-out costs no row
until there is something to report.

**The task list is the wave's second exhibit, and the page is its whole
loop.**  The sample ends with the task items: each renders its bullet as a
``\u2610``/``\u2611`` box -- one action span, ``"todo:<flat index>"`` -- and a
click on a box lands that payload in ``Markdown.chosen`` like a link's url.
The loop the component's docstring documents runs here in :func:`_flip_task`
and :func:`page`'s ``note``: the host reads the pick once, rewrites *its
own* ``text`` (the i-th task marker, the flat index counting the markers in
source order), assigns it back and the next render shows the flipped box --
the widget never touches the text itself.

**``c-y`` copies the sample's first fence.**  The shell's key (the host's
own gesture again) asks the page's first ``Markdown`` for
``Markdown.fences()`` and puts the first block's code on the clipboard
through ``screen.copy``; the toast names the language and the line count.
"""

from __future__ import annotations

import re

from motui import Markdown, Text
from motui.kernel import DIM
from motui.widgets import Divider

from ..page import PageBody, api_note, header, section, try_line

#: The Markdown sample: one of every construct the engine renders, task
#: items included (the last section is the clickable-box exhibit).
MARKDOWN_SAMPLE = """\
### A Markdown block

Prose with **bold**, *italic*, `inline code` and a [link](https://example.invalid)
-- wrapped to the pane, never past it.

1. numbered items
2. a second one

> A quote, for the record.

```python
def hello(name: str) -> str:
    return f"hello {name}"
```

| column | meaning |
|:-------|--------:|
| rows   | 2       |

### Task items

- [ ] click a box -- the host flips the source
- [x] and this one is already done
"""

#: The wrapping exhibit: one long paragraph, broken on the pane's edge.
PARAGRAPH = (
    "Plain Text is the kernel's simplest component: one logical line per "
    "\\n, each word-wrapped to the width its parent hands it, every row fit "
    "back to that width. The pane you are reading is a Viewport window over "
    "one document; the scrollbar on the right maps the part above and below "
    "the fold."
)

# Task marker lines in source order: the flat index counts these, exactly
# the order the rendered rows carry their ``todo:<i>`` payloads.
_TASK_LINE = re.compile(r"^(\s*[-*]\s+)\[([ xX])\](.*)$")


def _flip_task(text: str, index: int) -> str:
    """The host's own rewrite: flip the ``index``-th task marker in ``text``.

    The documented loop's middle step, as a function a host can copy: the
    payload ``"todo:<i>"`` counts the document's task markers in source
    order (what the rendered rows' flat ordinals are), so this scans the
    lines for ``- [ ]`` / ``- [x]`` markers, counts them as it goes and
    flips the ``i``-th one -- the other lines come back untouched.  An
    index past the last marker returns the text unchanged.
    """
    out: list[str] = []
    count = 0
    for line in text.split("\n"):
        matched = _TASK_LINE.match(line)
        if matched is not None:
            if count == index:
                box = " " if matched.group(2) in "xX" else "x"
                line = f"{matched.group(1)}[{box}]{matched.group(3)}"
            count += 1
        out.append(line)
    return "\n".join(out)


def page(gallery) -> PageBody:
    """The two content primitives, one sample each, and the pick echoes."""
    theme = gallery.theme
    # The link echo: empty until a pick lands, so the line appears exactly
    # when there is something to report (and the page renders identically
    # before the first click).
    echo = Markdown("", theme=theme)
    sample = Markdown(MARKDOWN_SAMPLE, theme=theme)

    def note(text: str) -> None:
        """One pick was reported: echo it, and run the task loop on a box.

        The host reports ``chosen: <value>`` -- the sample's link url or a
        task box's ``'todo:<i>'`` -- so the page echoes the report it was
        handed, beside the exhibit the click was on.  A ``todo:`` pick is
        the one the page *acts* on: the host reads it once (the session did)
        and rewrites the sample's own text, so the box flips on the next
        frame.  The widget never touches ``text``.
        """
        echo.text = f"echo \u25b8 {text}"
        pick = text.removeprefix("chosen: ").strip("'")
        if pick.startswith("todo:"):
            sample.text = _flip_task(sample.text, int(pick.removeprefix("todo:")))

    return PageBody([
        *header("content",
                "Text and Markdown -- the primitives that carry content, and the one that "
                "renders it.", theme),
        try_line("click the sample's link label, or a task box to flip it -- c-y copies the "
                 "sample's first code fence", theme),
        section("Markdown -- one sample of every construct", theme),
        sample,
        api_note("Markdown(text) -- a rule-registry engine; fences, tables, task items and "
                 "inline rules", theme),
        # The row the sample's picks echo on (a toast reports them too).
        echo,
        api_note("Markdown.click(row, col) -> chosen: a link's url, a task box's 'todo:<i>' "
                 "-- the host reads it once and rewrites the text", theme),
        section("Text -- one paragraph, word-wrapped to the pane", theme),
        Text(PARAGRAPH, style=DIM),
        api_note("Text(text, style=\u2026) -- one logical line, wrapped by the renderer", theme),
        section("Divider -- three ways", theme),
        Divider(theme=theme),
        Divider(theme=theme, label="a labelled rule"),
        Divider(theme=theme, char="\u00b7", max_width=40),
        api_note("Divider(label=\u2026, char=\u2026, max_width=\u2026)", theme),
    ], note=note)
