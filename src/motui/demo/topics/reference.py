"""Reference topics: the layer map, the keymap, the protocol matrix, non-goals."""

from __future__ import annotations

from motui import Table
from motui.widgets import Column, Notice

from ..stage import topic

_LAYER_ROWS = [
    ["kernel", "motui.kernel", "rows, styles, events, frame, selection, clipboard", "stdlib + wcwidth"],
    ["keys", "motui.keys", "byte decoder, keymaps, terminal sources", "kernel"],
    ["widgets", "motui.widgets", "every component and the Markdown engine", "kernel, keys.keymap"],
    ["interaction", "motui.interaction", "focus, pointer, gesture, find, modal, overlays", "kernel + Host"],
    ["app", "motui.app", "TUI driver and composition root", "everything above"],
]

_KEY_ROWS = [
    ["c-1 .. c-6", "switch to a section", "demo"],
    ["c-n / c-p", "next / previous topic in the section", "demo"],
    ["[ / ]", "previous / next section", "demo"],
    ["tab", "cycle the focus ring (or the form's fields)", "demo / FocusManager"],
    ["arrows", "move the focused cursor or scroll a view", "FocusManager"],
    ["enter", "activate the focused component", "FocusManager"],
    ["space", "toggle the focused row's mark", "demo"],
    ["/ or c-k", "open the command palette", "demo"],
    ["c-f", "open Find over the stage", "Find"],
    ["c-t", "cycle the theme", "demo"],
    ["c-g", "mount / unmount Stats", "demo"],
    ["esc", "close the panel or focus the catalog", "modal / demo"],
    ["q", "quit (a focused text field keeps q)", "demo"],
]

_MATRIX_ROWS = [
    ["Text", "inline actions", "-", "-", "inline payload"],
    ["Markdown", "task boxes", "-", "-", "todo index"],
    ["Input / Editor", "-", "-", "yes", "-"],
    ["Button / Link", "yes", "yes", "-", "true"],
    ["Checkbox", "yes", "yes", "-", "new state"],
    ["Select / Autocomplete", "yes", "yes", "-", "option"],
    ["RadioGroup / CheckboxGroup", "yes", "yes", "-", "value(s)"],
    ["ComboBox", "field", "yes", "yes", "option value"],
    ["Slider", "yes", "yes", "-", "number"],
    ["List", "yes", "yes", "yes", "item"],
    ["Table", "yes", "yes", "-", "row index"],
    ["Tree", "yes", "yes", "-", "no result"],
    ["Tabs / NavList / MenuBar", "yes", "menu bar", "-", "menu label"],
    ["Collapsible", "yes", "yes", "-", "open state"],
    ["Form", "-", "yes", "yes", "mapping"],
    ["Dialog", "yes", "buttons", "yes", "button value"],
    ["Modal / Palette", "routed", "routed", "routed", "panel result"],
]

_NON_GOALS = [
    ["retained widget tree / message bus / CSS layout", "the library is a document of components plus host policy"],
    ["charts, date or colour pickers", "hosts compose them from the primitives"],
    ["grid layout, draggable split dividers", "split ratios are a frame decision"],
    ["cross-pane selection, horizontal wheel scroll", "selection is one document wide"],
    ["full UAX #29 grapheme segmentation", "display columns are wcwidth's"],
    ["backward-compatibility shims", "a removed name is deleted with its last consumer"],
]


def _api_layers(b) -> None:
    b.preview(Table(["layer", "import", "owns", "depends on"], _LAYER_ROWS, theme=b.theme))


def _keymap(b) -> None:
    b.preview(
        Column(
            [
                Table(["key", "action", "owner"], _KEY_ROWS, theme=b.theme),
                Notice("The library binds no global key: the host routes tab and everything above.", theme=b.theme),
            ]
        )
    )


def _component_matrix(b) -> None:
    b.preview(
        Table(
            ["component", "click", "activate", "handle", "result"],
            _MATRIX_ROWS,
            theme=b.theme,
        )
    )


def _non_goals(b) -> None:
    b.preview(Table(["non-goal", "the ruling"], _NON_GOALS, theme=b.theme))


TOPICS = (
    topic(
        key="api-layers",
        title="API layers",
        summary="Five layers, one dependency direction: kernel, keys, widgets, interaction, app.",
        group="Facts",
        section="reference",
        try_line="none -- a static table; scroll if the stage is short",
        api_line="motui / motui.kernel / motui.keys / motui.widgets / motui.interaction / motui.app",
        components=("Table",),
        build=_api_layers,
    ),
    topic(
        key="keymap",
        title="Keymap",
        summary="The demo's keys on the left, their owner on the right.",
        group="Facts",
        section="reference",
        try_line="try the keys above; q quits only when no text field owns it",
        api_line="DEFAULT_INPUT_KEYMAP / DEFAULT_EDITOR_KEYMAP / EDITOR_SUBMIT_KEYMAP",
        components=("Table", "Notice"),
        build=_keymap,
    ),
    topic(
        key="component-matrix",
        title="Component matrix",
        summary="What every component answers: click, activate, handle and take_result.",
        group="Facts",
        section="reference",
        try_line="none -- a static protocol matrix; scroll the stage",
        api_line="Clickable \u00b7 Activable \u00b7 Controller \u00b7 Resultful \u00b7 Container \u00b7 Revisioned",
        components=("Table",),
        build=_component_matrix,
    ),
    topic(
        key="non-goals",
        title="Non-goals",
        summary="What motui 1.2 deliberately does not build, and the ruling behind each.",
        group="Facts",
        section="reference",
        try_line="none -- the contract's non-goal list, kept where the demo can show it",
        api_line="docs/CONTRACT.md \u00a710 (non-goals) is the normative list",
        components=("Table",),
        build=_non_goals,
    ),
)
