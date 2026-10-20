"""The notes page: the manual -- how to play, the tour, the signatures.

The manual is one :class:`~motui.Markdown` block in four parts, and it is the
demo's only prose-dense page: **how to play** (the rail, the keys, the mouse,
the copy gesture, the search tier and the two headless roads, stated once),
**the tour** (the three rail groups, one line each, spelled from
``session.pages``' own ``group`` fields so the list is the registry's and
cannot drift), **the signature quick reference** (every signature the pages
show, by family, in one fenced block -- the signatures W1 swept off the pages
live here, one home) and **the interaction model** (the focus ring, the
pointer tier, the selection and the pick echo, in brief).
Nothing on the page is interactive: it is the manual, and it doubles as the
exhibit of multi-paragraph Markdown the ``text`` page shows one sample of.
"""

from __future__ import annotations

from motui import Markdown

from ..kit import Exhibit
from ..page import PageBody

#: Part one: how to play.  The rail, the page's keys, the mouse, the copy
#: gesture, the search tier and the two headless roads -- everything a reader
#: needs to drive the demo, said once and in full.
_PLAY = """\
The rail is the demo's table of contents: click a label, or press `c-n` /
`c-p` to step through the eleven pages, the ends wrap. The label in the
accent bar is the page you are reading.

Every page is built from the library it shows, and the keys follow the
focus: `tab` walks the page's focus ring, `← / → / ↑ / ↓` move whatever it
focuses, `enter` activates it, `space` marks the focused view's cursor row,
`c-t` cycles the focused view's filter when the page has one.

The mouse works the same way. Moving the pointer raises a hover band and the
hovered leaf's own hint in the tooltip line under it; a press and a release
on one cell is a click; the wheel scrolls the pane under the pointer, not
the focused one. A **drag** across any rows selects them, and the release
copies the range through the terminal's OSC 52 -- a toast says how many
lines went to the clipboard.

`c-f` opens the search row over the page: typing re-addresses the matches,
`enter` steps through them and scrolls the page to the one it landed on,
`escape` closes the row. `c-o` walks the focus into the page's own right
pane, `c-g` mounts the developer stats box, `q` quits -- and `c-c` quits
from anywhere.

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

#: Part three: the signature quick reference.  Every signature the pages
#: show, grouped by family in one fenced block; the seeds are the signature
#: lines W1 swept off the pages (one list, one home).
_SIGNATURES = """\
content -- text
Text(text, style=…) -- one logical line, wrapped by the renderer
Markdown(text) -- a rule-registry engine: fences, tables, task items, inline rules
Markdown.click(row, col) -> chosen -- a link's url, a task box's todo:<i>
Diff(before, after, *, context=3, numbers=True) -- the LCS runs in the constructor
Divider(label=…, char=…, max_width=…) -- plain or labelled
Spacer(rows=…) -- vertical whitespace as a first-class component

layout
Panel(child, title=…, frame=False) -- one child in a box, or inset without one
Row(children, widths=[…]) / Column(children, gap=…) / Padding(child, …)
Collapsible(title, body, open=True) -- a click or enter flips it; the flip is the pick
Tabs(tabs, active=0, disabled=(…)) -- one row; ← / → move, a click selects
Notice(text, level="info" | "warn" | "error") -- one row, never wrapped
StatusLine(left=(…,), right=(…,)) -- updates in place, never wraps

actions
Button(label) -- Hoverable + Clickable + Focusable + Activable; chosen is read once
Link(text) -- mouse-only: a click lands the url, no focus
Checkbox(label, checked=…) -- activate() -> chosen (the new state)
Slider(value, minimum=0, maximum=10) -- activate confirms the value into chosen

forms
Input(mask='•') -- every rendered character is the mask's glyph; .text stays plain
Editor(text, max_rows=…) -- a block cursor; a click places it
TextBuffer.place(row, col) -- a click docks the cursor on the cell it hit
ComboBox(options, text=…) -- Modal(tui, combo.list, anchor=…) paints the dropdown
Autocomplete(options) -- the host sets the query; enter lands the match in chosen
Select.chosen -- the host reads the pick once, then resets it
Select(options, commit=True) -- a step or a click writes the row into chosen
Radio(labels, index=…) -- move / click / activate land the pick in chosen
CheckGroup(labels, marked=[…]) -- chosen is the marked rows' values, in row order

views
Table.index / Table.chosen / Table.sort_by(col) -- the pick is read once
Table.marked + toggle() -- space marks the cursor row; [x] rides the first cell
List(items, window=6) -- six rows and two counter rows whatever the length
List.marked + toggle() -- the mark follows the cursor's marker seat
Tree(root_nodes) -- enter folds; filter(query) is the c-t contract

modals
Dialog(title, body, buttons, frame=False) -- enter takes the focused button's value, escape cancels
confirm_dialog(message, danger=True, confirm_text=…) -- the danger pair, cancel first
prompt_dialog(title, placeholder=…) -- a Dialog whose body is an Input
Modal(tui, dialog, anchor=…) -- the overlay, the scrim, the whole keyboard
Palette(tui, commands) -- a query Input over a Modal; opening it raises the scrim

shell
tui.split("vertical", ratios=(2, 1)) + Scrollbar(tui, pane=…)
Stats(tui, pointer=…) -- c-g mounts it; painter.frames + tui.clock() is the reading
SelectionGesture(tui, on_end=…) -- release hands the range to the host
Find(tui, theme=…) -- c-f opens its query row; enter steps and reveals
Toasts.show(text) -- the row's value is the sentence the host shows
Tooltip(tui, pointer) -- reads leaf.hint; hover is the Pointer tier's
TUI.hit_leaf(x, y) -> (component, row, col) | None -- the click's own walk
ProgressBar(fraction, label=…, width_chars=…) -- one row
Spinner(text) -- every frame at rest, then one advancing

themes and styles
Theme -- dataclasses.replace(DEFAULT_THEME, accent=Style(fg="#e8a020"))
Style(fg="red" | "#58a6ff" | (88, 166, 255)) -- the three color forms
Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME
Select.activate() -> chosen -- the row's own Action re-skins the shell

streaming
markdown.text = … + tui.refresh() -- one chunk appended per beat
tui.every(PAGE_TICK, …) -- the beat MarkdownStream.act("play" | …) rides"""

#: Part four: the interaction model in brief -- the ring, the pointer, the
#: selection and the pick echo.
_MODEL = """\
The **focus ring** is one per page, built from the exhibits the page
registers: `tab` cycles it, the ring flips each target's `focused` flag, and
the arrows fall back to the focused target's own `move` (or its step verbs),
which is why an unfocused strip or view renders its quiet state.

The **pointer tier** watches beside the gesture and never blocks it: it
resolves the cell through the frame's ownership table, raises the hover band
and the leaf's `hint`, and completes a **stationary** click through the ring
(a click on a ring target focuses it first, a second activates it) or, with
no ring, dispatches the deepest clickable leaf itself.

The **selection** is the gesture's: press, motion and release, handed to the
host on release, which extracts the range and copies it through OSC 52.

Every activation ends in a **pick**: a widget writes `chosen`, the host
reads it exactly once per round, raises a toast and hands the page's own
echo line the report. A pick carrying an Action runs it with the session --
which is how a row opens a page or re-skins the shell without the host
knowing any page's name."""


def tour(pages) -> str:
    """The rail groups, one line each: the pages' own ``group`` fields, in rail order."""
    groups: list[tuple[str, list[str]]] = []
    for page in pages:
        if not page.group:
            continue
        if not groups or groups[-1][0] != page.group:
            groups.append((page.group, []))
        groups[-1][1].append(page.name)
    return "\n".join(
        f"- **{name.lower()}** -- " + " \u00b7 ".join(f"`{page}`" for page in names)
        for name, names in groups
    )


def manual(session) -> str:
    """The page's Markdown source: how to play, the tour, the signatures, the model."""
    return f"""\
### How to play

{_PLAY}

### The tour

The rail's three groups, in rail order:

{tour(session.pages)}

### The signature quick reference

Every signature the pages show, by family. The pages themselves carry the
live exhibits only; this is the one home for the signatures.

```
{_SIGNATURES}
```

### The interaction model

{_MODEL}
"""


def page(session) -> PageBody:
    """The manual, one Markdown block -- the demo's own reading guide."""
    theme = session.theme
    exhibit = Exhibit(
        session,
        title="notes",
        blurb="The manual: how to play, the tour, the signatures, the interaction model.",
    )
    exhibit.section("manual",
                    Markdown(manual(session), theme=theme),
                    caption="how to play \u00b7 the tour \u00b7 the signatures \u00b7 the model")
    return exhibit.build()
