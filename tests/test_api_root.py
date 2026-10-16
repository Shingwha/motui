"""The API surface pin: the curated root and every layer facade are locked.

Each curated ``__all__`` is pinned verbatim, every pinned name resolves, the
root hands out the layer objects, the selection mechanism imports from the
root, and no private name leaks.
"""

import importlib

import mocode_tui as root
import mocode_tui.core as core
import mocode_tui.keys as keys
import mocode_tui.widgets as widgets

#: The curated root surface.
ROOT_ALL = """
    ACCENT DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP DEFAULT_THEME DIM
    EDITOR_SUBMIT_KEYMAP ERROR MUTED
    SUCCESS WARNING Autocomplete Block Button Checkbox Column Component
    Confirm Divider
    Editor EveryHandle Find FocusRing HeadlessScreen Hit Input Key Line Link Markdown
    MouseEvent Notice Option Padding Palette Pane Panel Paste Pointer ProgressBar Row
    ScriptedKeys Scrollbar Segment Select Selection SelectionGesture
    Spacer Spinner StatusLine Style TUI Table Tabs Text Theme
    Toasts Tooltip Tree TreeNode copy_on_select extract headless_tui
    highlight snapshot visible_width wrap_text
""".split()

#: The curated facade surfaces, keyed by module path.
LAYER_ALLS = {
    "mocode_tui.core": """
        ACCENT BORDER CLEAR_LINE CODE CURSOR DEFAULT_THEME DIM ELLIPSIS ERROR ESC
        FG_CODES MORE_BELOW MUTED NONE RESET SELECTION SUCCESS WARNING Activable
        Block BlockState Clickable Component Container Document Focusable Frame
        HeadlessScreen Hoverable Key KeySource Line MouseEvent Painter Pane Paste
        Rect Screen ScreenLayout ScriptedKeys Segment Selection Style TerminalScreen
        Text Theme Viewport action_at clear_screen cursor_position descend
        disable_mouse_tracking ellipsize_tail enable_mouse_tracking enable_vt
        enter_alt_screen extract hide_cursor highlight leave_alt_screen show_cursor
        terminal_size visible_width wrap_line wrap_text
    """.split(),
    "mocode_tui.keys": """
        DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP EDITOR_SUBMIT_KEYMAP KeyDecoder
        Keymap RawTerminalKeys RecordingKeys ReplayKeys
    """.split(),
    "mocode_tui.widgets": """
        Autocomplete Button Checkbox Column Confirm Divider Editor Input Link
        Markdown Notice Option
        Padding Palette Panel ProgressBar Row Select Spacer Spinner StatusLine
        Table Tabs Text Tree TreeNode
    """.split(),
    "mocode_tui.app": "EveryHandle Hit TUI".split(),
    "mocode_tui.chrome": "Scrollbar Toasts Tooltip".split(),
    "mocode_tui.focus": "FocusRing".split(),
    "mocode_tui.gesture": "SelectionGesture copy_on_select".split(),
    "mocode_tui.pointer": "Pointer".split(),
    "mocode_tui.search": "Find".split(),
    "mocode_tui.testing": "headless_tui snapshot".split(),
}

#: The names down-listed from the root, and the documented submodule path
#: each still lives at (facade or defining module).
DOWN_LISTED = {
    "mocode_tui.core": """
        BlockState Container Document Hoverable KeySource Painter Screen ScreenLayout
        TerminalScreen Viewport action_at descend
    """.split(),
    "mocode_tui.core.frame": """
        Chrome FrameSpan FrameTable Overlay Pane Rect Split
    """.split(),
    "mocode_tui.core.ansi": """
        CLEAR_LINE ESC begin_sync_update clear_screen cursor_position
        cursor_shape disable_focus_events disable_mouse_tracking
        enable_focus_events enable_mouse_tracking enable_vt end_sync_update
        enter_alt_screen hide_cursor leave_alt_screen set_window_title
        show_cursor
    """.split(),
    "mocode_tui.core.lines": "wrap_line".split(),
    "mocode_tui.core.style": "BORDER CODE CURSOR FG_CODES NONE RESET SELECTION".split(),
    "mocode_tui.core.text": "ellipsize_tail".split(),
    "mocode_tui.keys": "KeyDecoder Keymap RawTerminalKeys RecordingKeys ReplayKeys".split(),
    "mocode_tui.widgets.syntax": """
        Highlighter RegexHighlighter default_highlighter highlight
    """.split(),
    "mocode_tui.widgets.markdown": """
        BLOCK_RULES INLINE_RULES BoldInlineRule BlockRule CodeInlineRule FenceRule
        HeadingRule InlineRule ItalicInlineRule LinkInlineRule ListRule
        ParagraphRule QuoteRule RenderContext StrikeInlineRule TableRule
        ThematicBreakRule default_block_rules default_inline_rules inline_segments
    """.split(),
}

#: Names in ``__all__`` that are not a plain word: the one all-caps class.
_ALL_CAPS_CLASSES = {"TUI"}


def _groups(names):
    """Split a facade list into constants / classes+functions, in order."""
    constants = [n for n in names if n.isupper() and n not in _ALL_CAPS_CLASSES]
    rest = [n for n in names if not n.isupper() or n in _ALL_CAPS_CLASSES]
    return constants, rest


def test_root_all_is_the_curated_surface():
    """The root exports exactly the curated toolkit face (66 names today)."""
    assert root.__all__ == ROOT_ALL
    assert len(root.__all__) == 66


def test_every_layer_facade_all_is_pinned():
    """Each layer facade is exactly its own curated surface."""
    for path, expected in LAYER_ALLS.items():
        module = importlib.import_module(path)
        assert module.__all__ == expected, path


def test_every_pinned_name_resolves_and_the_root_hands_out_the_layer_objects():
    """No name sits in a facade's ``__all__`` without a matching attribute,
    and ``mocode_tui.X is mocode_tui.<layer>.X`` for every root name."""
    for path, expected in [(root.__name__, ROOT_ALL), *LAYER_ALLS.items()]:
        module = importlib.import_module(path)
        missing = [n for n in expected if not hasattr(module, n)]
        assert missing == [], path
    for name in ROOT_ALL:
        owners = [layer for layer in LAYER_ALLS if name in LAYER_ALLS[layer]]
        assert owners, name  # every root name belongs to a layer
        for path in owners:
            module = importlib.import_module(path)
            assert getattr(root, name) is getattr(module, name), name


def test_all_lists_keep_the_constants_classes_functions_order():
    """Each list is three sorted groups: constants, classes, functions."""
    for names in [ROOT_ALL, *LAYER_ALLS.values()]:
        constants, rest = _groups(names)
        assert constants + rest == names
        assert constants == sorted(constants)
        assert rest == sorted(rest)


def test_no_private_names_leak_into_any_facade():
    """A facade exports public API only -- no underscore names."""
    for module in (root, core, keys, widgets):
        leaks = [n for n in module.__all__ if n.startswith("_")]
        assert leaks == [], module.__name__


def test_the_selection_mechanism_imports_from_the_root():
    """The selection mechanism is one root import beside the gesture tier:
    ``from mocode_tui import Selection, extract, highlight``."""
    from mocode_tui import Selection, extract, highlight

    assert Selection is core.Selection
    assert extract is core.extract
    assert highlight is core.highlight


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
