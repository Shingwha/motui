"""The notes page: how to read this demo, as the demo's own Markdown.

The manual is one :class:`~motui.Markdown` block: the rail and the keys,
the mouse and the copy gesture, the pages the rail holds -- spelled from
``session.pages``, so the list is the registry's own and cannot drift --
and the two headless roads (``--pages`` and the piped replay).  Nothing on
the page is interactive: it is the manual, and it doubles as the exhibit of
multi-paragraph Markdown the ``text`` page shows one sample of.
"""

from __future__ import annotations

from motui import Markdown

from ..kit import Exhibit
from ..page import PageBody

#: The manual's opening: the shell's own story -- the rail, the keys, the
#: mouse, the copy gesture and the search tier.
_SHELL = """\
The shell around every page is built from the library it shows off: a
two-pane frame whose left column is the **rail**, a vertical list of this
demo's page names.

Click a rail label to open that page -- or press `c-n` / `c-p` to step
through the families, the ends wrap. `tab` moves the page's focus ring,
the arrows and `enter` drive whatever it focuses, `space` marks the focused
view's cursor row, `c-o` walks the focus into the page's own right pane
(the `shell` page opens one), `c-f` opens the search tier over the page,
`c-g` mounts the developer stats box, and `q` quits.

The mouse works the same way: moving the pointer raises a hover band and
the hovered leaf's own hint in the tooltip line under it; a press and a
release on one cell is a click; the wheel scrolls the pane under the
pointer, not the focused one. A **drag** across any rows selects them, and
the release copies the range through the terminal's OSC 52 -- a toast says
how many lines went to the clipboard."""

#: The manual's reading rules: the ``TRY`` line, and how the hint band relates.
_TRY = """\
Each page opens with a `TRY \u25b8` line: the one thing worth doing on that
page -- `TRY \u25b8 click a task box` on `text`, `TRY \u25b8 press c-o` on
`shell`. The keys the line names are the page's own rows in the hint band
along the bottom of the screen, in front of the shell's global keys."""

#: The two headless roads, verbatim from the README's demo section.
_HEADLESS = """\
There are headless roads as well, for a reader without a terminal:

```
python -m motui              # a real terminal: the full screen
python -m motui < /dev/null  # piped: replays headless, dumps the final screen
python -m motui --pages      # every page as plain text, no terminal needed
```

`--pages` paints every page once and prints it as plain text, and a piped
run replays the scripted tour -- the rail's own click road, every page, a
few plays -- and dumps the final screen. Neither road reads the terminal,
and nothing here reaches the network."""


def manual(session) -> str:
    """The page's Markdown source: the reading guide, the pages from the registry."""
    pages = "\n".join(f"- `{page.name}` -- {page.description}" for page in session.pages)
    return f"""\
### How to read this demo

This page is the manual: the demo built around the exhibits, and what each
page carries under its own heading.

#### The shell

{_SHELL}

#### The pages

{pages}

#### Each page's TRY line

{_TRY}

#### The headless roads

{_HEADLESS}
"""


def page(session) -> PageBody:
    """The manual, one Markdown block -- the demo's own reading guide."""
    theme = session.theme
    exhibit = Exhibit(
        session,
        title="notes",
        blurb="How to read this demo: the rail and the keys, the mouse and the copy "
              "gesture, the pages the rail holds, and the two headless roads.",
        try_text="read the manual below -- the wheel scrolls the rest of it, and c-n / c-p "
                 "walk the pages it describes",
        echo_label="echo",
    )
    exhibit.section("the manual -- the rail, the keys, the mouse, the pages")
    exhibit.show(
        Markdown(manual(session), theme=theme),
        api="Markdown(text) -- the whole guide is one block of the page's own prose",
    )
    return exhibit.build()
