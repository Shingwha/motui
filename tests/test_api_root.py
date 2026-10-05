"""Root-surface tripwire: the curated API is pinned to its terminal state.

W7 finalized the public surface.  The package root is the one-line import
face for a host (``from mocode_tui import TUI, Composer, Transcript, ...``),
re-exporting the driver, the document model, the render core, the keys
layer, every generic widget and every chat component; each layer facade
(``mocode_tui.core`` / ``keys`` / ``widgets`` / ``chat``) is complete for
its own layer, and the driver (``mocode_tui.app``) plus the headless helpers
(``mocode_tui.testing``) sit above the kernel with their own ``__all__``.
This test locks the ``__all__`` lists verbatim, checks every name resolves
to the same object its layer exports, and asserts no ``components`` residue
and no private name leaks into a facade.
"""

import importlib.util

import mocode_tui
import mocode_tui.app as app
import mocode_tui.chat as chat
import mocode_tui.core as core
import mocode_tui.keys as keys
import mocode_tui.testing as testing
import mocode_tui.widgets as widgets

ROOT_ALL = [
    "ACCENT",
    "BORDER",
    "CODE",
    "CURSOR",
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "DEFAULT_THEME",
    "DIM",
    "ERROR",
    "FG_CODES",
    "MUTED",
    "NONE",
    "RESET",
    "SELECTION",
    "SUCCESS",
    "WARNING",
    "Autocomplete",
    "Block",
    "BlockState",
    "Column",
    "Component",
    "Composer",
    "Confirm",
    "Divider",
    "Document",
    "EditBlock",
    "Editor",
    "EveryHandle",
    "HeadlessScreen",
    "Highlighter",
    "Hit",
    "Input",
    "Key",
    "KeyDecoder",
    "KeySource",
    "Keymap",
    "Line",
    "Markdown",
    "Message",
    "MouseEvent",
    "Notice",
    "Option",
    "Padding",
    "Painter",
    "Panel",
    "Paste",
    "ProgressBar",
    "RawTerminalKeys",
    "RegexHighlighter",
    "Row",
    "Screen",
    "ScreenLayout",
    "ScriptedKeys",
    "Segment",
    "Select",
    "SlashPalette",
    "Spacer",
    "Spinner",
    "StatusBar",
    "StatusLine",
    "StatusSegment",
    "StreamHandle",
    "Style",
    "TUI",
    "Table",
    "Tabs",
    "TerminalScreen",
    "Text",
    "Theme",
    "ToolBlock",
    "Transcript",
    "Tree",
    "TreeNode",
    "Viewport",
    "default_highlighter",
    "ellipsize_tail",
    "headless_tui",
    "highlight",
    "snapshot",
    "visible_width",
    "wrap_line",
    "wrap_text",
]

LAYER_ALLS = {
    "mocode_tui.core": [
        "ACCENT",
        "BORDER",
        "CLEAR_LINE",
        "CODE",
        "CURSOR",
        "DEFAULT_THEME",
        "DIM",
        "ELLIPSIS",
        "ERROR",
        "ESC",
        "FG_CODES",
        "MUTED",
        "NONE",
        "RESET",
        "SELECTION",
        "SUCCESS",
        "WARNING",
        "Block",
        "BlockState",
        "Component",
        "Document",
        "HeadlessScreen",
        "Key",
        "KeySource",
        "Line",
        "MouseEvent",
        "Painter",
        "Paste",
        "Screen",
        "ScreenLayout",
        "ScriptedKeys",
        "Segment",
        "Style",
        "TerminalScreen",
        "Text",
        "Theme",
        "Viewport",
        "clear_line",
        "clear_screen",
        "cursor_position",
        "disable_mouse_tracking",
        "ellipsize_tail",
        "enable_mouse_tracking",
        "enable_vt",
        "enter_alt_screen",
        "hide_cursor",
        "leave_alt_screen",
        "show_cursor",
        "terminal_size",
        "visible_width",
        "wrap_line",
        "wrap_text",
    ],
    "mocode_tui.keys": [
        "DEFAULT_EDITOR_KEYMAP",
        "DEFAULT_INPUT_KEYMAP",
        "KeyDecoder",
        "Keymap",
        "RawTerminalKeys",
    ],
    "mocode_tui.widgets": [
        "Autocomplete",
        "Column",
        "Confirm",
        "Divider",
        "Editor",
        "Highlighter",
        "Input",
        "Markdown",
        "Notice",
        "Option",
        "Padding",
        "Panel",
        "ProgressBar",
        "RegexHighlighter",
        "Row",
        "Select",
        "Spacer",
        "Spinner",
        "StatusBar",
        "StatusSegment",
        "Table",
        "Tabs",
        "Text",
        "Tree",
        "TreeNode",
        "default_highlighter",
        "highlight",
    ],
    "mocode_tui.chat": [
        "COMPOSER_KEYMAP",
        "Composer",
        "EditBlock",
        "Message",
        "SlashPalette",
        "StatusLine",
        "StreamHandle",
        "ToolBlock",
        "Transcript",
    ],
    "mocode_tui.app": [
        "EveryHandle",
        "Hit",
        "TUI",
    ],
    "mocode_tui.testing": [
        "headless_tui",
        "snapshot",
    ],
}

#: Names in ``__all__`` that are not a plain word: the one all-caps class.
_ALL_CAPS_CLASSES = {"TUI"}


def _groups(names):
    """Split a facade list into constants / classes / functions, in order."""
    constants = [n for n in names if n.isupper() and n not in _ALL_CAPS_CLASSES]
    rest = [n for n in names if not n.isupper() or n in _ALL_CAPS_CLASSES]
    return constants, rest


# ---------------------------------------------------------------------------
# The pinned lists
# ---------------------------------------------------------------------------


def test_root_all_is_the_curated_terminal_surface():
    """W7: the root exports the whole toolkit for a one-line host import."""
    assert mocode_tui.__all__ == ROOT_ALL


def test_every_layer_facade_all_is_pinned():
    """Each layer facade is exactly its own curated surface."""
    for name, expected in LAYER_ALLS.items():
        module = importlib.import_module(name)
        assert module.__all__ == expected, name


def test_the_restructure_acceptance_one_liner():
    """Spec acceptance: Composer and Theme are importable from the root."""
    assert "Composer" in mocode_tui.__all__ and "Theme" in mocode_tui.__all__
    from mocode_tui import Composer, Theme  # noqa: F401  (the import itself)


# ---------------------------------------------------------------------------
# Resolvability and identity
# ---------------------------------------------------------------------------


def test_every_all_name_resolves_on_its_own_module():
    """No name may sit in a facade's __all__ without a matching attribute."""
    packages = [mocode_tui, core, keys, widgets, chat, app, testing]
    lists = [ROOT_ALL, *LAYER_ALLS.values()]
    for module, expected in zip(packages, lists):
        missing = [n for n in expected if not hasattr(module, n)]
        assert missing == [], module.__name__


def test_root_reexports_the_very_objects_the_layers_export():
    """``mocode_tui.X is mocode_tui.<layer>.X`` for every root name."""
    layers = (core, keys, widgets, chat, app, testing)
    for name in ROOT_ALL:
        owners = [layer for layer in layers if name in layer.__all__]
        assert owners, name  # every root name belongs to a layer
        for layer in owners:
            assert getattr(mocode_tui, name) is getattr(layer, name), name


def test_the_chat_trio_is_exported_at_the_root_from_chat():
    """Lead's ruling: Message/ToolBlock/EditBlock are chat-layer symbols."""
    for name in ("Message", "ToolBlock", "EditBlock"):
        assert name in chat.__all__ and name in mocode_tui.__all__
        assert getattr(mocode_tui, name) is getattr(chat, name)


def test_widgets_no_longer_host_the_chat_components():
    """W6 moved the pi-style blocks out of the generic library."""
    for name in ("Message", "ToolBlock", "EditBlock", "Composer", "Transcript"):
        assert name not in widgets.__all__


# ---------------------------------------------------------------------------
# Hygiene
# ---------------------------------------------------------------------------


def test_no_components_package_residue():
    """The restructure removed the old components/ package; nothing revives it.

    The spec name is assembled rather than spelled so a repo-wide grep for
    the retired package finds no live reference -- the assertion itself is
    what keeps it dead.
    """
    retired = ".".join(("mocode_tui", "components"))
    assert importlib.util.find_spec(retired) is None
    assert not hasattr(mocode_tui, "components")


def test_no_private_names_leak_into_any_facade():
    """A facade exports public API only -- no underscore names."""
    for module in (mocode_tui, core, keys, widgets, chat):
        leaks = [n for n in module.__all__ if n.startswith("_")]
        assert leaks == [], module.__name__


def test_all_lists_keep_the_constants_classes_functions_order():
    """Each list is three sorted groups: constants, classes, functions."""
    lists = [ROOT_ALL, *LAYER_ALLS.values()]
    for names in lists:
        constants, rest = _groups(names)
        assert constants + rest == names
        assert constants == sorted(constants)
        assert rest == sorted(rest)
