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
"""

from __future__ import annotations

from mocode_tui import DIM, Divider, Markdown, Text

from ..page import PageBody, api_note, header, section, try_line

#: The Markdown sample: one of every construct the engine renders.
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
"""

#: The wrapping exhibit: one long paragraph, broken on the pane's edge.
PARAGRAPH = (
    "Plain Text is the kernel's simplest component: one logical line per "
    "\\n, each word-wrapped to the width its parent hands it, every row fit "
    "back to that width. The pane you are reading is a Viewport window over "
    "one document; the scrollbar on the right maps the part above and below "
    "the fold."
)


def page(gallery) -> PageBody:
    """The two content primitives, one sample each."""
    theme = gallery.theme
    # The link echo: empty until a pick lands, so the line appears exactly
    # when there is something to report (and the page renders identically
    # before the first click).
    echo = Markdown("", theme=theme)

    def note(text: str) -> None:
        """One pick was reported: keep it on the page's echo line.

        The host reports ``chosen: <value>`` -- for the sample's link, the
        url ``Markdown.click`` landed -- so the page echoes the report it
        was handed, beside the exhibit the click was on.
        """
        echo.text = f"echo \u25b8 {text}"

    return PageBody([
        *header("content",
                "Text and Markdown -- the primitives that carry content, and the one that "
                "renders it.", theme),
        try_line("resize the terminal: every row of this page re-wraps to the new width", theme),
        section("Markdown -- one sample of every construct", theme),
        Markdown(MARKDOWN_SAMPLE, theme=theme),
        api_note("Markdown(text) -- a rule-registry engine; fences, tables and inline rules", theme),
        # The row the sample's link echoes its pick on (a toast reports it too).
        echo,
        section("Text -- one paragraph, word-wrapped to the pane", theme),
        Text(PARAGRAPH, style=DIM),
        api_note("Text(text, style=\u2026) -- one logical line, wrapped by the renderer", theme),
        section("Divider -- three ways", theme),
        Divider(theme=theme),
        Divider(theme=theme, label="a labelled rule"),
        Divider(theme=theme, char="\u00b7", max_width=40),
        api_note("Divider(label=\u2026, char=\u2026, max_width=\u2026)", theme),
    ], note=note)
