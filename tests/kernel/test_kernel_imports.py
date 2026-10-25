"""The kernel package surface and its isolation from the 1.x layers.

A bare ``import motui.kernel`` executes ``motui/__init__.py`` first, and that
facade eagerly imports ``core``, ``widgets``, ``app`` and ``testing`` -- so
the literal "no ``motui.core`` in ``sys.modules``" check cannot hold for a
normal import without changing the 1.x facade, which this wave must not
touch.  The invariant that matters is the one the kernel owns: importing the
kernel package must not pull any of those layers in.  The isolation test
therefore imports ``motui.kernel`` in a fresh interpreter whose ``motui``
root package is a bare stub (its ``__path__`` points at the real package
directory), which exercises the kernel's own dependency graph exactly as a
later wave will load it.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import motui
import motui.kernel as kernel

#: The package surface W0a promises; W1 may extend it but nothing may leak
#: in by accident.
EXPECTED = {
    "Axis",
    "Cell",
    "Constraints",
    "Line",
    "Pos",
    "Rect",
    "Scroll",
    "ScrollAxis",
    "Segment",
    "Size",
    "Surface",
    "WrapMode",
}


def test_package_exports_exactly_the_documented_names() -> None:
    assert set(kernel.__all__) == EXPECTED
    assert len(kernel.__all__) == len(EXPECTED)  # no duplicates
    for name in EXPECTED:
        assert getattr(kernel, name) is not None
    assert not hasattr(kernel, "Style")  # the transitional carrier stays private


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

        forbidden = ("motui.core", "motui.widgets", "motui.app", "motui.terminal")
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
            "motui.kernel.geom",
            "motui.kernel.layout",
            "motui.kernel.text",
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
