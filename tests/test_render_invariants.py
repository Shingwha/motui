"""Rendering invariants: every public component, at every awkward width.

The wave's second invariant battery (D12): a fixed component matrix is
rendered at widths ``0, 1, 2, 3, 7, 20, 80`` and three properties are pinned
for each pair, with no sleeps and no new dependency:

* **idempotent** -- two ``render(w)`` calls answer equal rows;
* **bounded** -- every row's display width is at most ``w`` (``Line.width``
  and the concatenated ``line.text`` measured through ``visible_width``),
  so nothing a component returns can paint past its pane;
* **stateless drift-free** -- rendering at another width in between (the
  pane resize a host really does) must not change what ``w`` renders: the
  rows come back exactly equal to the first call's.

The matrix is the components that exist this wave -- the widgets, the
action primitives, the layout containers, the assembly-level rows
(``Palette`` / ``StatusLine``) and ``Text`` / ``Markdown`` -- each freshly
built per case so one case's state can never leak into another's.
"""

import pytest

from motui import (
    Button,
    Checkbox,
    Editor,
    Input,
    Link,
    List,
    Markdown,
    NavList,
    Option,
    Palette,
    Select,
    StatusLine,
    Table,
    Tabs,
    Text,
    Tree,
)
from motui.kernel import visible_width
from motui.testing import headless_tui
from motui.widgets.dialog import confirm_dialog
from motui.widgets import (
    Autocomplete,
    Collapsible,
    Column,
    Diff,
    Divider,
    Dialog,
    Notice,
    Padding,
    Panel,
    ProgressBar,
    Radio,
    Row,
    ShortcutBar,
    Slider,
    Spacer,
    TreeNode,
)

#: The widths every component must survive: the degenerate ones a squeezed
#: pane really hands out -- the zero-width collapse first, the narrowest
#: non-zero widths after it -- one narrow-but-plausible width, and a full
#: pane.
WIDTHS = (0, 1, 2, 3, 7, 20, 80)

#: Long content with wide characters on purpose: wrapping and truncation
#: must stay inside the width even when clusters measure wider than ``len``.
_WIDE = "a long line with 中文 wide characters and words longer than any tiny width"

def _input_with_text() -> Input:
    """An ``Input`` with content: the caret and the wrap geometry engaged."""
    field = Input(placeholder="type here")
    field.insert("hello 中 world")
    return field


#: One builder per component: ``(name, factory)``, the factory fresh each time
#: so no case inherits another's state.  ``Spinner`` is not here: it renders
#: no rows of its own (a host puts ``spinner.frame`` in a ``Text``), so it is
#: not a ``Component``.
CASES = (
    ("Text", lambda: Text(_WIDE)),
    (
        "Markdown",
        lambda: Markdown(
            "# Title\n\nA paragraph with **bold**, `code` and 中文 wide text.\n\n"
            "- item one\n- item two\n\n> quoted\n\n```python\nx = 1\n```\n"
        ),
    ),
    ("Markdown table", lambda: Markdown("| a | b |\n| --- | --- |\n| 1 | 2 |\n")),
    ("Table", lambda: Table(["name", "value"], [["alpha", "1"], ["beta", "2"]])),
    (
        "Table wide cells",
        lambda: Table(["名", "值"], [["中文字符很长的单元格名字", "1"], ["beta", "2"]]),
    ),
    (
        "List",
        lambda: List(["alpha", _WIDE, "gamma", "delta", "epsilon", "zeta"], window=4),
    ),
    ("List empty", lambda: List()),
    ("Diff", lambda: Diff("a\nb\nc\nd", "a\nB\nc\nd\ne")),
    ("Diff no change", lambda: Diff("same", "same")),
    ("Diff numbers", lambda: Diff("a\nb\nc\nd", "a\nB\nc\nd\ne", numbers=True)),
    (
        "Tree",
        lambda: Tree([TreeNode("root", [TreeNode("child"), TreeNode("leaf")], expanded=True)]),
    ),
    ("Tabs", lambda: Tabs(["one", "two", "three"])),
    ("NavList", lambda: NavList(["one", "two", "three"])),
    ("NavList empty", lambda: NavList([])),
    ("Select", lambda: Select([Option("one"), Option("two")], title="pick")),
    ("Dialog", lambda: confirm_dialog("Proceed?")),
    ("Autocomplete", lambda: Autocomplete(options=[Option("alpha"), Option("beta")])),
    ("Input", lambda: Input(placeholder="type here")),
    ("Input with text", _input_with_text),
    ("Editor", lambda: Editor(text="line one\nline two")),
    ("Button", lambda: Button("Ship it")),
    ("Checkbox", lambda: Checkbox("Trace")),
    ("Link", lambda: Link("Read the README")),
    ("Radio", lambda: Radio(["one", _WIDE, "three"])),
    ("Slider", lambda: Slider(4, minimum=0, maximum=10)),
    ("Collapsible", lambda: Collapsible("a foldable section", Text(_WIDE))),
    ("ShortcutBar", lambda: ShortcutBar([("c-n", "next"), ("c-p", "prev")])),
    ("Notice", lambda: Notice("something happened", level="error")),
    ("Divider", lambda: Divider(label="section")),
    ("Panel", lambda: Panel(Text("inner content"), title="box")),
    ("Padding", lambda: Padding(Text("inner content"), left=2, right=2, top=1)),
    ("Column", lambda: Column([Text("a"), Text("b")], gap=1)),
    ("Row", lambda: Row([Text("a"), Text("b")], gap=1)),
    ("Spacer", lambda: Spacer(2)),
    ("ProgressBar", lambda: ProgressBar(0.4, label="work")),
    ("StatusLine", lambda: StatusLine(left=("ready",), right=("60 fps",))),
    (
        "Palette",
        lambda: Palette(
            headless_tui(80, 8), [Option("/one", description="first"), Option("/two")]
        ),
    ),
)


def test_the_matrix_covers_the_promised_widths_and_a_broad_set():
    """The table really holds every width, and the component set is broad."""
    assert WIDTHS == (0, 1, 2, 3, 7, 20, 80)
    assert len(CASES) >= 20
    assert len({name for name, _ in CASES}) == len(CASES)  # distinct names


@pytest.mark.parametrize("name,factory", CASES, ids=[name for name, _ in CASES])
@pytest.mark.parametrize("width", WIDTHS)
def test_render_is_idempotent_bounded_and_drift_free(name, factory, width):
    """The three invariants, for one component at one width."""
    component = factory()
    first = component.render(width)

    for row in first:  # bounded: never wider than the pane it was rendered for
        assert row.width <= width, f"{name}@{width}: row.width {row.width}"
        assert visible_width(row.text) <= width, f"{name}@{width}: text too wide"

    again = component.render(width)  # idempotent: a second call is the same rows
    assert again == first, f"{name}@{width}: render is not idempotent"

    other = 80 if width != 80 else 1  # a resize in between must not drift
    component.render(other)
    assert component.render(width) == first, f"{name}@{width}: state drifted"
