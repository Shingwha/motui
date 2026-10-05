"""Root-surface pin: the curated API is locked to its terminal state.

W3b cut the package root to its curated surface -- one import line for a
host (``from mocode_tui import TUI, Composer, Transcript, ...``) -- while
each layer facade (``mocode_tui.core`` / ``keys`` / ``widgets`` /
``chat``) stays complete for its own layer, and the driver
(``mocode_tui.app``) plus the headless helpers (``mocode_tui.testing``)
sit above the kernel with their own ``__all__``.  The names the cut
down-listed stay public at their documented submodule paths
(``mocode_tui.core.Painter``, ``mocode_tui.keys.KeyDecoder``,
``mocode_tui.widgets.syntax.Highlighter``, the Markdown rule registries,
``COMPOSER_KEYMAP``, ...).

This file pins all seven curated ``__all__`` lists verbatim, checks every
pinned name resolves on its own module and that the root hands out the
very objects the layers export, keeps the constants -> classes ->
functions ordering convention, forbids private leaks, and sweeps the
down-listed names for importability at their submodule paths.
"""

import importlib

import mocode_tui
import mocode_tui.app as app
import mocode_tui.chat as chat
import mocode_tui.core as core
import mocode_tui.keys as keys
import mocode_tui.testing as testing
import mocode_tui.widgets as widgets

#: The curated root surface (spec 05, binding).
ROOT_ALL = [
    "ACCENT",
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "DEFAULT_THEME",
    "DIM",
    "ERROR",
    "MUTED",
    "SUCCESS",
    "WARNING",
    "Autocomplete",
    "Block",
    "Column",
    "Component",
    "Composer",
    "Confirm",
    "Divider",
    "EditBlock",
    "Editor",
    "EveryHandle",
    "HeadlessScreen",
    "Hit",
    "Input",
    "Key",
    "KeySource",
    "Keymap",
    "Line",
    "Markdown",
    "Message",
    "MouseEvent",
    "Notice",
    "Option",
    "Padding",
    "Panel",
    "Paste",
    "ProgressBar",
    "RawTerminalKeys",
    "Row",
    "Screen",
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
    "headless_tui",
    "snapshot",
    "visible_width",
    "wrap_text",
]

#: The curated facade surfaces, keyed by module path.
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
        "MORE_BELOW",
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
        "Input",
        "Markdown",
        "Notice",
        "Option",
        "Padding",
        "Panel",
        "ProgressBar",
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

#: The names W3b down-listed from the root, and the documented submodule
#: path each still lives at (facade or defining module).
DOWN_LISTED = {
    "mocode_tui.core": [
        "BlockState",
        "Document",
        "Painter",
        "ScreenLayout",
        "Viewport",
    ],
    "mocode_tui.core.ansi": [
        "CLEAR_LINE",
        "ESC",
        "clear_line",
        "clear_screen",
        "cursor_position",
        "disable_mouse_tracking",
        "enable_mouse_tracking",
        "enable_vt",
        "enter_alt_screen",
        "hide_cursor",
        "leave_alt_screen",
        "show_cursor",
    ],
    "mocode_tui.core.lines": [
        "wrap_line",
    ],
    "mocode_tui.core.style": [
        "BORDER",
        "CODE",
        "CURSOR",
        "FG_CODES",
        "NONE",
        "RESET",
        "SELECTION",
    ],
    "mocode_tui.core.text": [
        "ellipsize_tail",
    ],
    "mocode_tui.keys": [
        "KeyDecoder",
    ],
    "mocode_tui.widgets.syntax": [
        "Highlighter",
        "RegexHighlighter",
        "default_highlighter",
        "highlight",
    ],
    "mocode_tui.widgets.markdown": [
        "BLOCK_RULES",
        "INLINE_RULES",
        "BoldInlineRule",
        "BlockRule",
        "CodeInlineRule",
        "FenceRule",
        "HeadingRule",
        "InlineRule",
        "ItalicInlineRule",
        "LinkInlineRule",
        "ListRule",
        "ParagraphRule",
        "QuoteRule",
        "RenderContext",
        "TableRule",
        "ThematicBreakRule",
        "default_block_rules",
        "inline_segments",
    ],
    "mocode_tui.chat.composer": [
        "COMPOSER_KEYMAP",
    ],
}

#: Names in ``__all__`` that are not a plain word: the one all-caps class.
_ALL_CAPS_CLASSES = {"TUI"}


def _groups(names):
    """Split a facade list into constants / classes+functions, in order."""
    constants = [n for n in names if n.isupper() and n not in _ALL_CAPS_CLASSES]
    rest = [n for n in names if not n.isupper() or n in _ALL_CAPS_CLASSES]
    return constants, rest


# ---------------------------------------------------------------------------
# The pinned lists
# ---------------------------------------------------------------------------


def test_root_all_is_the_curated_surface():
    """The root exports exactly the curated 63-name toolkit face."""
    assert mocode_tui.__all__ == ROOT_ALL
    assert len(mocode_tui.__all__) == 63


def test_every_layer_facade_all_is_pinned():
    """Each layer facade is exactly its own curated surface."""
    for path, expected in LAYER_ALLS.items():
        module = importlib.import_module(path)
        assert module.__all__ == expected, path


# ---------------------------------------------------------------------------
# Resolvability and identity
# ---------------------------------------------------------------------------


def test_every_pinned_name_resolves_and_the_root_hands_out_the_layer_objects():
    """No name sits in a facade's ``__all__`` without a matching attribute,
    and ``mocode_tui.X is mocode_tui.<layer>.X`` for every root name."""
    for path, expected in [(mocode_tui.__name__, ROOT_ALL), *LAYER_ALLS.items()]:
        module = importlib.import_module(path)
        missing = [n for n in expected if not hasattr(module, n)]
        assert missing == [], path
    for name in ROOT_ALL:
        owners = [layer for layer in LAYER_ALLS if name in LAYER_ALLS[layer]]
        assert owners, name  # every root name belongs to a layer
        for path in owners:
            module = importlib.import_module(path)
            assert getattr(mocode_tui, name) is getattr(module, name), name


# ---------------------------------------------------------------------------
# Conventions and hygiene
# ---------------------------------------------------------------------------


def test_all_lists_keep_the_constants_classes_functions_order():
    """Each list is three sorted groups: constants, classes, functions."""
    for names in [ROOT_ALL, *LAYER_ALLS.values()]:
        constants, rest = _groups(names)
        assert constants + rest == names
        assert constants == sorted(constants)
        assert rest == sorted(rest)


def test_no_private_names_leak_into_any_facade():
    """A facade exports public API only -- no underscore names."""
    for module in (mocode_tui, core, keys, widgets, chat):
        leaks = [n for n in module.__all__ if n.startswith("_")]
        assert leaks == [], module.__name__


def test_down_listed_names_resolve_at_their_documented_submodule_paths():
    """The names the cut removed from the root stay importable where they
    are documented to live (facade or defining module) -- one sweep, not a
    residue tripwire."""
    missing: list[str] = []
    for path, names in DOWN_LISTED.items():
        module = importlib.import_module(path)
        for name in names:
            if getattr(module, name, None) is None:
                missing.append(f"{path}.{name}")
    assert missing == []
