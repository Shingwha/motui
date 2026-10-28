"""The public-surface snapshot: what each facade exports, and with what shape.

The snapshot is one line per exported name, plus selected public methods::

    <module>\t<name>\t<class|function|module|value|method>\t<signature>

``signature`` is :func:`inspect.signature`'s rendering, with any memory
address scrubbed so the file is stable across processes; a value that has no
signature contributes its stable ``repr`` instead.

Three modes:

* ``--update`` writes the snapshot to ``tools/api-2.1.txt``;
* ``--check`` compares it line for line and exits 1 on any difference;
* ``--check --allow-additions`` compares only the ``(module, name)`` keys:
  new names and changed signatures pass (that is what a growth wave does),
  a name that disappeared fails.

The faces are the seven public roots the 2.1 tree ships.  The selected
provisional classes also record their public method signatures, so the
verb vocabulary is pinned, not only the constructor.  A face that does not
exist yet is skipped; regenerate the snapshot in the wave that moves it.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

#: The public facade modules, in the order the toolkit documents them.
FACES = (
    "motui",
    "motui.kernel",
    "motui.pixel",
    "motui.terminal",
    "motui.widgets",
    "motui.app",
    "motui.testing",
)

#: Classes whose public method signatures are part of the provisional pin.
MEMBER_TARGETS = (
    ("motui.pixel", "Raster"),
    ("motui.pixel", "PixelPalette"),
    ("motui.widgets", "PixelCanvas"),
)

#: Where ``--update`` records the surface and ``--check`` reads it.
SNAPSHOT = ROOT / "tools" / "api-2.1.txt"

_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")

#: One-line description for ``--help`` (``__doc__`` is optional to the type checker).
DESCRIPTION = "The public-surface snapshot: what each facade exports, and with what shape."


def _stable(text: str) -> str:
    """``text`` with any ``0x...`` memory address folded to one spelling."""
    return _ADDRESS.sub("0x...", text)


def _kind(obj: object) -> str:
    """The row's kind: ``module``, ``class``, ``function`` or ``value``."""
    if inspect.ismodule(obj):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if callable(obj):
        return "function"
    return "value"


def _signature(obj: object) -> str:
    """The object's signature, or its stable repr when it has none."""
    if callable(obj):
        try:
            return _stable(str(inspect.signature(obj)))
        except (TypeError, ValueError):
            pass
    return _stable(repr(obj))


def _exported(module: ModuleType) -> list[str]:
    """The names a facade publishes: ``__all__`` when present, else public."""
    recorded: object = getattr(module, "__all__", None)
    if isinstance(recorded, (list, tuple)):
        # ``getattr`` erases the element type; the list/tuple check proves the
        # shape, and the cast restores the container type for the loop.
        entries = cast("Sequence[object]", recorded)
        return [name for name in entries if isinstance(name, str)]
    return sorted(name for name in dir(module) if not name.startswith("_"))


def surface() -> list[str]:
    """The snapshot lines, sorted by ``(module, name)``.

    A facade missing from the tree is skipped: the snapshot documents the
    surface that exists, not the one a later wave will add.
    """
    rows: list[tuple[str, str, str, str]] = []
    for face in FACES:
        try:
            module = importlib.import_module(face)
        except ImportError:
            continue
        for name in _exported(module):
            obj: object = getattr(module, name)
            rows.append((face, name, _kind(obj), _signature(obj)))
    for face, class_name in MEMBER_TARGETS:
        module = importlib.import_module(face)
        cls = getattr(module, class_name)
        for name in sorted(dir(cls)):
            if name.startswith("_"):
                continue
            member = getattr(cls, name)
            if inspect.isfunction(member):
                rows.append((face, f"{class_name}.{name}", "method", _signature(member)))
    rows.sort(key=lambda row: (row[0], row[1]))
    return ["\t".join(row) for row in rows]


def parse(lines: list[str]) -> dict[tuple[str, str], tuple[str, str]]:
    """Snapshot lines as ``{(module, name): (kind, signature)}``."""
    recorded: dict[tuple[str, str], tuple[str, str]] = {}
    for line in lines:
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        module, name, kind, signature = parts
        recorded[(module, name)] = (kind, signature)
    return recorded


def _differences(
    recorded: dict[tuple[str, str], tuple[str, str]],
    actual: dict[tuple[str, str], tuple[str, str]],
) -> list[str]:
    """One human-readable line per missing, added or changed name."""
    problems: list[str] = []
    for key in sorted(set(recorded) | set(actual)):
        if key not in actual:
            problems.append(f"- {key[0]}:{key[1]} (missing)")
        elif key not in recorded:
            problems.append(f"+ {key[0]}:{key[1]} (added)")
        elif recorded[key] != actual[key]:
            problems.append(f"~ {key[0]}:{key[1]} (shape changed)")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Run the tool; return the process exit code."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="compare the snapshot")
    mode.add_argument("--update", action="store_true", help="rewrite the snapshot")
    parser.add_argument(
        "--allow-additions",
        action="store_true",
        help="with --check: permit new names and changed signatures",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=SNAPSHOT,
        help=f"snapshot path (default: {SNAPSHOT})",
    )
    args = parser.parse_args(argv)

    lines = surface()
    target: Path = args.snapshot

    if args.update:
        target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"api: {len(lines)} names written to {target}")
        return 0

    if not target.is_file():
        print(f"api: snapshot missing: {target}")
        return 1
    recorded_lines = target.read_text(encoding="utf-8").splitlines()
    recorded = parse(recorded_lines)
    actual = parse(lines)

    if not args.allow_additions:
        if recorded_lines == lines:
            print(f"api: {len(lines)} names match")
            return 0
        problems = _differences(recorded, actual)
        for problem in problems:
            print(problem)
        print(f"api: {len(problems)} differences against {target}")
        return 1

    missing = sorted(key for key in recorded if key not in actual)
    if missing:
        for module, name in missing:
            print(f"- {module}:{name} (missing)")
        print(f"api: {len(missing)} snapshot names disappeared")
        return 1
    added = sorted(key for key in actual if key not in recorded)
    print(
        f"api: {len(recorded)} names present, {len(added)} additions, "
        "signatures unchecked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
