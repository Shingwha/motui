"""The API surface pin: the curated root and every layer facade are locked.

Each curated ``__all__`` is pinned verbatim, every pinned name resolves, the
root hands out the layer objects, the selection mechanism is reachable at the
kernel facade, and no private name leaks.
"""

import importlib

import motui as root
import motui.kernel as kernel

#: The curated root surface: the 31 names one import line hands out.
ROOT_ALL = """
    DEFAULT_THEME
    Button Checkbox Editor FocusRing Input Key Line Link List Markdown MouseEvent
    Option Palette Paste Pointer Scrollbar Segment Select SelectionGesture
    StatusLine Style TUI Table Tabs Text Theme Toasts Tree headless_tui snapshot
""".split()

#: The 41 names the structure ref's table takes off the root this wave --
#: 42 minus ``Confirm``, whose Select-specialized class this wave deletes
#: (the modal layer's ``Dialog`` / ``confirm_dialog`` replaces it).
SHED = """
    ACCENT DIM ERROR MUTED SUCCESS WARNING Block Component Pane Selection extract
    highlight visible_width wrap_text HeadlessScreen ScriptedKeys
    DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP EDITOR_SUBMIT_KEYMAP
    Autocomplete Collapsible Column Diff Divider Notice Padding Panel
    ProgressBar Radio Row ShortcutBar Slider Spacer Spinner TreeNode
    Find copy_on_select Stats Tooltip EveryHandle Hit
""".split()

#: The curated layer facades, keyed by module path.  ``motui.widgets.markdown``
#: publishes its own curated surface too; it is not pinned here, only its
#: names' documented paths are (``DOWN_LISTED``).
LAYER_ALLS = {
    "motui.kernel": """
        ACCENT BORDER CLEAR_LINE CODE CURSOR DEFAULT_THEME DIM ELLIPSIS ERROR ESC
        FG_CODES MORE_BELOW MUTED NONE RESET SELECTION SUCCESS WARNING Activable
        Block BlockState Clickable Component Container CursorWindow Document
        Focusable Frame HeadlessScreen Hoverable Key KeySource Line MarkSet
        MouseEvent Painter Pane Paste Rect Revisioned Screen ScreenLayout
        ScriptedKeys Segment Selection Style TerminalScreen
        Text Theme Viewport action_at clear_screen cursor_position descend
        disable_mouse_tracking ellipsize_tail enable_mouse_tracking enable_vt
        enter_alt_screen extract hide_cursor highlight leave_alt_screen
        mark_prefix show_cursor terminal_size visible_width wrap_line wrap_text
    """.split(),
    "motui.keys": """
        DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP EDITOR_SUBMIT_KEYMAP KeyDecoder
        Keymap RawTerminalKeys
    """.split(),
    "motui.widgets": """
        Autocomplete Button ButtonSpec CheckGroup Checkbox Collapsible Column Dialog Diff Divider
        Editor Input Link List Markdown Notice Option
        Padding Panel ProgressBar Radio Row Select ShortcutBar Slider Spacer
        Spinner StatusLine
        Table Tabs Text Tree TreeNode confirm_dialog
    """.split(),
    "motui.interaction": "Find FocusRing Palette Pointer SelectionGesture copy_on_select".split(),
    "motui.app": "EveryHandle Hit TUI".split(),
    "motui.chrome": "Scrollbar Stats Toasts Tooltip".split(),
    "motui.testing": "headless_tui snapshot".split(),
}

#: The names that stay below the root, each at the documented path it lives at
#: (facade, or defining module).  Every entry starts with the names the cut
#: left off the root; the tail of one is the deeper seam it shares a landing
#: with.
DOWN_LISTED = {
    "motui.app": "EveryHandle Hit".split(),
    "motui.chrome": "Stats Tooltip".split(),
    "motui.interaction": "Find copy_on_select".split(),
    "motui.kernel": """
        ACCENT DIM ERROR MUTED SUCCESS WARNING Block Component Pane Selection extract
        highlight visible_width wrap_text
        BlockState Container Document Hoverable Painter Rect Revisioned Screen ScreenLayout
        TerminalScreen Viewport action_at descend
    """.split(),
    "motui.kernel.events": "KeySource ScriptedKeys".split(),
    "motui.kernel.screen": "HeadlessScreen".split(),
    "motui.kernel.ansi": """
        CLEAR_LINE ESC begin_sync_update clear_screen cursor_position
        cursor_shape disable_focus_events disable_mouse_tracking
        enable_focus_events enable_mouse_tracking enable_vt end_sync_update
        enter_alt_screen hide_cursor leave_alt_screen set_window_title
        show_cursor
    """.split(),
    "motui.kernel.frame": """
        Chrome FrameSpan FrameTable Overlay Pane Rect Split
    """.split(),
    "motui.kernel.lines": "wrap_line".split(),
    "motui.kernel.style": "BORDER CODE CURSOR FG_CODES NONE RESET SELECTION".split(),
    "motui.kernel.text": "ellipsize_tail".split(),
    "motui.keys": """
        DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP EDITOR_SUBMIT_KEYMAP KeyDecoder
        Keymap RawTerminalKeys
    """.split(),
    "motui.widgets": """
        Autocomplete ButtonSpec CheckGroup Collapsible Column Dialog Diff Divider Notice Padding
        Panel ProgressBar Radio Row ShortcutBar Slider Spacer Spinner TreeNode confirm_dialog
    """.split(),
    "motui.widgets.syntax": """
        Highlighter RegexHighlighter default_highlighter highlight
    """.split(),
    "motui.widgets.markdown": """
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
    """The root exports exactly the curated toolkit face (31 names today)."""
    assert root.__all__ == ROOT_ALL
    assert len(root.__all__) == 31


def test_every_layer_facade_all_is_pinned():
    """Each layer facade is exactly its own curated surface."""
    for path, expected in LAYER_ALLS.items():
        module = importlib.import_module(path)
        assert module.__all__ == expected, path


def test_every_pinned_name_resolves_and_the_root_hands_out_the_layer_objects():
    """No name sits in a facade's ``__all__`` without a matching attribute,
    and ``motui.X is motui.<layer>.X`` for every root name."""
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
    for path in [root.__name__, *LAYER_ALLS]:
        module = importlib.import_module(path)
        leaks = [n for n in module.__all__ if n.startswith("_")]
        assert leaks == [], module.__name__


def test_the_selection_mechanism_is_reachable_at_the_kernel_facade():
    """The selection mechanism is one layer-facade import beside the gesture
    tier: ``from motui.kernel import Selection, extract, highlight``."""
    from motui.kernel import Selection, extract, highlight

    assert Selection is kernel.Selection
    assert extract is kernel.extract
    assert highlight is kernel.highlight


def test_down_listed_names_resolve_at_their_documented_submodule_paths():
    """The names that stay below the root resolve where they are documented to
    live (facade or defining module) -- one sweep, not a residue tripwire.

    The sweep carries the cut's own pin as well: the names the structure
    ref's table sheds -- 41 since the old ``Confirm`` left this wave -- all
    of them off the root and each one documented at a landing below it.
    """
    assert len(SHED) == 41
    assert not set(SHED) & set(ROOT_ALL)
    documented = {name for names in DOWN_LISTED.values() for name in names}
    assert set(SHED) <= documented
    missing: list[str] = []
    for path, names in DOWN_LISTED.items():
        module = importlib.import_module(path)
        for name in names:
            if getattr(module, name, None) is None:
                missing.append(f"{path}.{name}")
    assert missing == []
