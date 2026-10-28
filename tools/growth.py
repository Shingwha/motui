"""The growth probe: prove a defaulted kernel field is a non-breaking change.

The tool copies ``src/``, ``tests/``, ``tools/`` and the release files beside
``pyproject.toml`` (the packaging test reads ``LICENSE`` and ``README.md``)
into a throw-away directory, then uses :mod:`ast` to add one defaulted field
to each of the four value types that grow in 2.0::

    Surface._growth_probe: int = 0
    Constraints._growth_probe: int = 0
    ScrollAxis._growth_probe: int = 0
    Scroll._growth_probe: int = 0

and runs the real gates against that copy:

* ``python -m pytest -q -p no:cacheprovider`` (or ``tests/kernel`` with
  ``--quick``);
* ``python tools/semantic.py --check``;
* ``python tools/api.py --check --allow-additions`` (full runs only).

The repository itself is never touched: every edit happens under
:func:`tempfile.mkdtemp`.  The copied API snapshot is refreshed before pytest
because the suite pins that snapshot, and restored to the unprobed baseline
before the API gate -- the gate's whole point is that the *old* snapshot still
accepts the new signatures (additions pass, deletions would not).

The probe tree is removed on success.  On failure the path is printed; add
``--keep`` to keep it there for inspection.
"""

from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The classes that receive a probe field, as (module file, class name).
PROBES = (
    ("src/motui/kernel/cell.py", "Surface"),
    ("src/motui/kernel/layout.py", "Constraints"),
    ("src/motui/kernel/layout.py", "ScrollAxis"),
    ("src/motui/kernel/layout.py", "Scroll"),
)

#: The probe field: defaulted, so every existing construction keeps working.
PROBE_FIELD = "_growth_probe: int = 0"

#: One-line description for ``--help`` (``__doc__`` is optional to the type checker).
DESCRIPTION = "Grow the kernel values in a throw-away copy and run the real gates there."

#: What the probe copy needs: the package, its tests and the tooling.
COPIED = ("src", "tests", "tools")
#: ``tests/test_packaging.py`` reads these two release files beside the config.
COPIED_FILES = ("pyproject.toml", "LICENSE", "README.md")


def add_probe(source: str, class_name: str) -> str:
    """``source`` with :data:`PROBE_FIELD` added after the class's last field.

    The insertion keeps the field's own indentation and lands before the
    methods, so the class's ``__post_init__`` (or any other method) still
    follows the fields.
    """
    tree = ast.parse(source)
    classes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if not classes:
        raise LookupError(f"class {class_name!r} not found")
    fields = [
        statement
        for statement in classes[0].body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
    ]
    if not fields:
        raise LookupError(f"class {class_name!r} has no annotated fields")
    last = fields[-1]
    if last.end_lineno is None:
        raise LookupError(f"class {class_name!r}: no source position for its fields")
    lines = source.splitlines(keepends=True)
    indent = " " * last.col_offset
    lines.insert(last.end_lineno, f"{indent}{PROBE_FIELD}\n")
    return "".join(lines)


def _copy_tree(target: Path) -> None:
    """Copy the probe's inputs into ``target``."""
    for name in COPIED:
        shutil.copytree(
            ROOT / name,
            target / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for name in COPIED_FILES:
        shutil.copy2(ROOT / name, target / name)


def _apply_probes(target: Path) -> None:
    """Insert the probe field into every class; a file may carry several."""
    for relative, class_name in PROBES:
        path = target / relative
        source = path.read_text(encoding="utf-8")
        path.write_text(add_probe(source, class_name), encoding="utf-8", newline="\n")


def _environment(target: Path) -> dict[str, str]:
    """The subprocess environment: the copy's ``src`` wins over the install."""
    env = dict(os.environ)
    prefix = str(target / "src")
    inherited = env.get("PYTHONPATH")
    env["PYTHONPATH"] = prefix if not inherited else prefix + os.pathsep + inherited
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _imports_the_copy(target: Path, env: dict[str, str]) -> bool:
    """Prove the interpreter resolves ``motui`` inside the probe tree."""
    done = subprocess.run(
        [sys.executable, "-c", "import motui; print(motui.__file__)"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    where = done.stdout.strip()
    print(f"growth: motui under test: {where or done.stderr.strip()}")
    if done.returncode != 0:
        return False
    try:
        return Path(where).resolve().is_relative_to(target.resolve())
    except OSError:
        return False


def _run(label: str, command: list[str], target: Path, env: dict[str, str]) -> bool:
    """Run one gate in the probe tree, streaming its real output."""
    print("growth: $ " + " ".join(command))
    done = subprocess.run(command, cwd=target, env=env, check=False)
    print(f"growth: {label} -> {done.returncode}")
    return done.returncode == 0


def main(argv: list[str] | None = None) -> int:
    """Run the probe; return the process exit code."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="run tests/kernel and the semantic check only",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the probe tree (on success too) and print its path",
    )
    args = parser.parse_args(argv)

    target = Path(tempfile.mkdtemp(prefix="motui-growth-"))
    passed = False
    try:
        _copy_tree(target)
        _apply_probes(target)
        env = _environment(target)
        if not _imports_the_copy(target, env):
            print("growth: the probe tree is not the import source")
            return 1

        snapshot = target / "tools" / "api-2.0.txt"
        baseline = snapshot.read_bytes()
        # The suite's own API test pins the copied snapshot, so refresh it for
        # the probed tree; the gate below compares against the untouched one.
        subprocess.run(
            [sys.executable, "tools/api.py", "--update"],
            cwd=target,
            env=env,
            check=False,
            stdout=subprocess.DEVNULL,
        )

        pytest_args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        if args.quick:
            pytest_args.append("tests/kernel")
        results = [
            ("pytest", _run("pytest", pytest_args, target, env)),
            (
                "semantic",
                _run(
                    "semantic",
                    [sys.executable, "tools/semantic.py", "--check"],
                    target,
                    env,
                ),
            ),
        ]
        if not args.quick:
            snapshot.write_bytes(baseline)
            results.append(
                (
                    "api",
                    _run(
                        "api",
                        [
                            sys.executable,
                            "tools/api.py",
                            "--check",
                            "--allow-additions",
                        ],
                        target,
                        env,
                    ),
                )
            )
        passed = all(result for _, result in results)
        for label, result in results:
            print(f"growth: {label}: {'pass' if result else 'FAIL'}")
        if passed:
            print(f"growth: OK ({'quick' if args.quick else 'full'} probe)")
        else:
            print("growth: FAILED")
        return 0 if passed else 1
    finally:
        if args.keep or not passed:
            print(f"growth: probe tree kept at {target}")
        else:
            shutil.rmtree(target, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
