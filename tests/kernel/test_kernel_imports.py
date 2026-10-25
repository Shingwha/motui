"""The kernel package surface and its isolation from the I/O layers.

A bare ``import motui.kernel`` executes ``motui/__init__.py`` first, and that
facade eagerly imports the terminal, widgets, app and testing layers -- so
the literal "no ``motui.kernel`` in ``sys.modules``" check cannot hold for a
normal import.  The invariant that matters is the one the kernel owns:
importing the kernel package must not pull any of those layers in.  The
isolation test therefore imports ``motui.kernel`` in a fresh interpreter
whose ``motui`` root package is a bare stub (its ``__path__`` points at the
real package directory), which exercises the kernel's own dependency graph.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import motui
import motui.kernel as kernel

#: The package surface W1 publishes; W2 may extend it but nothing may leak
#: in by accident.
EXPECTED = {
    "Axis",
    "Border",
    "Cell",
    "Chrome",
    "Color",
    "ColorMode",
    "ColorPalette",
    "Component",
    "Constraints",
    "DEFAULT_EDITOR_KEYMAP",
    "DEFAULT_INPUT_KEYMAP",
    "DEFAULT_THEME",
    "Document",
    "EDITOR_SUBMIT_KEYMAP",
    "ELLIPSIS",
    "Event",
    "EventSource",
    "FG_CODES",
    "FocusEvent",
    "Frame",
    "GLYPHS",
    "Glyphs",
    "Hit",
    "KeyEvent",
    "Keymap",
    "Line",
    "MouseEvent",
    "NONE",
    "Overlay",
    "Pane",
    "PasteEvent",
    "Pos",
    "RESET",
    "Rect",
    "ResizeEvent",
    "RowRange",
    "ScreenLayout",
    "Scroll",
    "ScrollAxis",
    "Section",
    "Segment",
    "Selection",
    "Separator",
    "Size",
    "Split",
    "Style",
    "Styles",
    "Surface",
    "Theme",
    "Viewport",
    "WrapMode",
    "action_at",
    "cut_line",
    "ellipsize_tail",
    "extract",
    "highlight",
    "sgr_prefix",
    "slice_line",
    "visible_width",
    "wrap_line",
    "wrap_text",
}


def test_package_exports_exactly_the_documented_names() -> None:
    assert set(kernel.__all__) == EXPECTED
    assert len(kernel.__all__) == len(EXPECTED)  # no duplicates
    for name in EXPECTED:
        assert getattr(kernel, name) is not None
    assert hasattr(kernel, "Style")  # the real style moved into the kernel


def test_kernel_import_pulls_in_no_other_motui_layer() -> None:
    package_dir = Path(motui.__file__).resolve().parent
    script = textwrap.dedent(
        """
        import sys
        import types

        root = types.ModuleType("motui")
        root.__path__ = [sys.argv[1]]
        sys.modules["motui"] = root

        import motui.kernel

        forbidden = ("motui.widgets", "motui.app", "motui.terminal", "motui.testing")
        loaded = sorted(
            name for name in sys.modules if name == "motui" or name.startswith("motui.")
        )
        leaked = [name for name in forbidden if name in sys.modules]
        if leaked:
            raise SystemExit(f"kernel imported forbidden layers: {leaked}")
        expected = [
            "motui",
            "motui.kernel",
            "motui.kernel.cell",
            "motui.kernel.document",
            "motui.kernel.events",
            "motui.kernel.frame",
            "motui.kernel.geom",
            "motui.kernel.glyphs",
            "motui.kernel.hit",
            "motui.kernel.keymap",
            "motui.kernel.layout",
            "motui.kernel.overlay",
            "motui.kernel.selection",
            "motui.kernel.style",
            "motui.kernel.text",
            "motui.kernel.theme",
        ]
        if loaded != expected:
            raise SystemExit(f"unexpected motui modules: {loaded}")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(package_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
