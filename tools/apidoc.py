"""docs/API.md: the facades' curated names, rendered from the modules.

Run it from the repository root::

    uv run python tools/apidoc.py            # the gate's line: --check
    uv run python tools/apidoc.py --check    # compare docs/API.md
    uv run python tools/apidoc.py --write    # regenerate the page

The page is generated, never edited: for every facade -- the package root
and each layer's ``__init__`` -- every name in its ``__all__``, in the
facade's own curated order (the order ``tests/test_api_root.py`` pins), as
``### name`` plus the name's signature where it is callable (a class's is
its constructor's), the first paragraph of its docstring where it has one
of its own, and the module that defines it.  A module is resolved by
following the facade's own ``from ... import ...`` lines through the
re-export chain to the last module that curates the name -- the root's
``ACCENT`` is named ``motui.kernel.style``, not ``motui.kernel``.  A
constant has no docstring and no signature -- its type (and a scalar's
value) is the whole story.

The signature text is assembled from ``inspect.signature``'s
:class:`~inspect.Signature` by hand rather than taken from ``str()``, on
purpose: every module here carries ``from __future__ import annotations``,
so annotations arrive as the source's own strings, and printing those raw
keeps the page identical across interpreter versions (``repr`` would add
its quotes, and a version that renders signatures differently would move
the page on a machine that changed nothing).  A default follows the same
rule: scalars by ``repr``, a routine by its qualified name, anything else
by its type -- ``theme: Theme = Theme(...)`` -- so no memory address and no
half-screen repr ever enters the page.

``--check`` re-renders and compares against ``docs/API.md`` (read with
universal newlines, so a checkout's CRLF reads as the LF it stands for --
this page is prose, not a byte-pinned frame), prints a diff summary and
exits 1 when they differ.  ``--write`` rewrites the page as LF text.
"""

from __future__ import annotations

import ast
import difflib
import importlib
import inspect
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

#: The facades, in the page's fixed order: the curated root first, then
#: each layer's own import face.
FACADES: tuple[str, ...] = (
    "motui",
    "motui.kernel",
    "motui.keys",
    "motui.widgets",
    "motui.widgets.markdown",
    "motui.app",
    "motui.interaction",
    "motui.interaction.modal",
    "motui.interaction.overlays",
    "motui.interaction.palette",
    "motui.interaction.scrollbar",
    "motui.testing",
)

#: The page; ``--write`` writes it, ``--check`` compares it.
OUTPUT = ROOT / "docs" / "API.md"

#: How many diff lines ``main`` prints around a drift before summarizing.
DIFF_HEAD = 30

#: A non-scalar default longer than this prints as ``Type(...)``: the repr
#: of a ``Theme`` is two and a half thousand characters, and its contents
#: are the Theme page's story, not a signature's.
MAX_DEFAULT = 60

HEADER = """\
# API

> **Generated** by [`tools/apidoc.py`](../tools/apidoc.py): `uv run python
> tools/apidoc.py --check` (the same assertion as `tests/test_api_doc.py`)
> fails when this page drifts from the code.  Do not edit it by hand.

Every facade -- the package root and each layer's `__init__` -- and every
name in its `__all__`, in the facade's own curated order: the name, its
signature where it is callable (a class's is its constructor's), the first
paragraph of its docstring where it has one of its own, and the module that
defines it.
"""


def _annotation_text(annotation: object) -> str:
    """An annotation as the source spells it, never as a repr writes it."""
    if isinstance(annotation, str):
        return annotation
    return inspect.formatannotation(annotation)


def _default_text(value: object) -> str:
    """A default's spelling: scalars by repr, a routine by name, an instance by type.

    Never a bare object's ``repr``: a function's carries a memory address
    (the page would move between two runs of the same code) and a
    ``Style``'s is half a screen wide.  Scalars, the empty tuple and the
    dataclasses ``<factory>`` sentinel come through verbatim -- for them the
    repr *is* the value.
    """
    if value is None or isinstance(value, (str, int, float, bool, complex, bytes)):
        return repr(value)
    if inspect.isroutine(value):
        return getattr(value, "__qualname__", None) or repr(value)
    text = repr(value)
    if " at 0x" in text or len(text) > MAX_DEFAULT:
        return f"{type(value).__name__}(...)"
    return text


def _param_text(param: inspect.Parameter) -> str:
    """One parameter: name, annotation, default -- ``inspect``'s own rule."""
    text = param.name
    annotated = param.annotation is not inspect.Parameter.empty
    if annotated:
        text = f"{text}: {_annotation_text(param.annotation)}"
    if param.default is not inspect.Parameter.empty:
        default = _default_text(param.default)
        text = f"{text} = {default}" if annotated else f"{text}={default}"
    if param.kind is inspect.Parameter.VAR_POSITIONAL:
        return f"*{text}"
    if param.kind is inspect.Parameter.VAR_KEYWORD:
        return f"**{text}"
    return text


def _signature_text(obj: object) -> str | None:
    """``inspect.signature``'s answer as one line, or ``None`` when there is none.

    The ``/`` and ``*`` markers come from the parameter kinds exactly as
    :meth:`inspect.Signature.__str__` places them; the return annotation
    rides along for a callable, and is left off for a class (a constructor
    has no return the caller spells).
    """
    try:
        signature = inspect.signature(obj, eval_str=False)
    except (TypeError, ValueError):
        return None
    parts: list[str] = []
    positional_only = False
    keyword_only = True
    for param in signature.parameters.values():
        kind = param.kind
        if kind is inspect.Parameter.POSITIONAL_ONLY:
            positional_only = True
        elif positional_only:
            parts.append("/")
            positional_only = False
        if kind is inspect.Parameter.VAR_POSITIONAL:
            keyword_only = False
        elif kind is inspect.Parameter.KEYWORD_ONLY and keyword_only:
            parts.append("*")
            keyword_only = False
        parts.append(_param_text(param))
    text = "(" + ", ".join(parts) + ")"
    if not inspect.isclass(obj) and signature.return_annotation is not inspect.Signature.empty:
        text += f" -> {_annotation_text(signature.return_annotation)}"
    return text


def _first_paragraph(obj: object) -> str:
    """The docstring's first paragraph as one line, or ``""`` without one.

    Only an object's *own* docstring counts: a constant's ``__doc__`` is its
    type's (``dict() -> new empty dictionary`` is not the keymap's story),
    so values get none.
    """
    if not (inspect.isclass(obj) or inspect.isroutine(obj)):
        return ""
    doc = inspect.getdoc(obj)
    if not doc:
        return ""
    head = doc.split("\n\n", 1)[0]
    return " ".join(head.split())


def _value_line(name: str, obj: object) -> str:
    """A non-callable's line: its type, and a scalar's value."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return f"{name}: {type(obj).__name__} = {obj!r}"
    return f"{name}: {type(obj).__name__}"


def _import_origins(source: Path, package: str) -> dict[str, str]:
    """``name -> the absolute module`` the facade line imports it from.

    Read off the facade's own ``from .module import name`` statements, so a
    constant -- which has no ``__module__`` -- is still named by the deep
    module that defines it.  ``name`` is the name as bound (an ``as`` alias
    wins), and the relative level is resolved against the facade's package.
    """
    origins: dict[str, str] = {}
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module == "__future__":
            continue
        base = package
        for _ in range(node.level - 1):
            base = base.rsplit(".", 1)[0]
        module = f"{base}.{node.module}" if node.module else base
        for alias in node.names:
            if alias.name.startswith("_"):
                continue
            origins[alias.asname or alias.name] = module
    return origins


def _origins_of(module_name: str, cache: dict[str, dict[str, str]]) -> dict[str, str]:
    """The module's own ``from ... import name`` map, parsed once per run."""
    if module_name not in cache:
        cache[module_name] = {}
        module = importlib.import_module(module_name)
        path = getattr(module, "__file__", None)
        if path is not None:
            source = Path(path)
            if source.is_relative_to(ROOT / "src"):
                cache[module_name] = _import_origins(source, module.__package__ or module_name)
    return cache[module_name]


def _origin_of(name: str, facade: str, cache: dict[str, dict[str, str]]) -> str:
    """Follow the re-export hops to the module that really defines ``name``.

    The root's ``ACCENT`` arrives through ``motui.kernel``, which imports
    it from ``motui.kernel.style``: the page names the last module in the
    chain.  A hop is only taken while the module on it curates the name
    (``__all__``, where the module has one) -- an import for internal use is
    not a re-export.
    """
    module = facade
    seen: set[str] = set()
    while module not in seen:
        seen.add(module)
        published = getattr(sys.modules[module], "__all__", None)
        if published is not None and name not in published:
            return module
        following = _origins_of(module, cache).get(name)
        if not following or following == module:
            return module
        module = following
    return module


def _entry(name: str, obj: object, origin: str) -> list[str]:
    """One ``### name`` block: heading, signature or type, doc, origin."""
    lines = [f"### {name}", ""]
    signature = _signature_text(obj) if callable(obj) else None
    lines += ["```python", f"{name}{signature}" if signature else _value_line(name, obj), "```", ""]
    paragraph = _first_paragraph(obj)
    if paragraph:
        lines += [paragraph, ""]
    lines += [f"*defined in* `{origin}`", ""]
    return lines


def entry_count() -> int:
    """How many names the page carries: every facade's ``__all__``, summed."""
    return sum(
        len(importlib.import_module(facade).__all__) for facade in FACADES
    )


def render() -> str:
    """The whole page: the header, then every facade and name, LF-terminated."""
    lines = [HEADER.rstrip("\n"), ""]
    origins: dict[str, dict[str, str]] = {}
    for facade in FACADES:
        module: ModuleType = importlib.import_module(facade)
        lines += [f"## {facade}", ""]
        for name in module.__all__:
            obj = getattr(module, name)
            origin = _origin_of(name, facade, origins)
            lines += _entry(name, obj, origin)
    return "\n".join(lines).rstrip("\n") + "\n"


def check(path: Path | None = None) -> list[str]:
    """Compare the page against a fresh render; one line per problem.

    ``"<name>: missing"`` for a page with no file, ``"<name>: differs"``
    when the render moved.  An empty list is the gate's pass.
    """
    where = OUTPUT if path is None else Path(path)
    if not where.is_file():
        return [f"{where.name}: missing"]
    if where.read_text(encoding="utf-8") != render():
        return [f"{where.name}: differs"]
    return []


def diff_summary(recorded: str, expected: str, limit: int = DIFF_HEAD) -> str:
    """A drift's first diff lines plus the added/removed counts."""
    diff = list(
        difflib.unified_diff(
            recorded.splitlines(),
            expected.splitlines(),
            "docs/API.md (as committed)",
            "docs/API.md (regenerated)",
            lineterm="",
        )
    )
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    head = diff[:limit]
    more = "" if len(diff) <= limit else f"\n... {len(diff) - limit} more diff line(s)"
    return f"{added} added, {removed} removed\n" + "\n".join(head) + more


def write(path: Path | None = None) -> None:
    """Record the page afresh: LF text, one trailing newline."""
    where = OUTPUT if path is None else Path(path)
    where.parent.mkdir(parents=True, exist_ok=True)
    with where.open("w", encoding="utf-8", newline="\n") as sink:
        sink.write(render())


def main(argv: list[str] | None = None) -> int:
    """``--check`` (the default) or ``--write``; the exit code is the answer."""
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) > 1 or (args and args[0] not in ("--check", "--write")):
        print(f"usage: python {Path(sys.argv[0]).name} [--check | --write]")
        return 2
    mode = args[0] if args else "--check"
    if mode == "--write":
        write()
        where = OUTPUT.relative_to(ROOT) if OUTPUT.is_relative_to(ROOT) else OUTPUT
        print(f"apidoc: wrote {where} ({entry_count()} entries)")
        return 0
    problems = check()
    for problem in problems:
        print(f"apidoc: {problem}")
    if problems:
        if OUTPUT.is_file():
            print(diff_summary(OUTPUT.read_text(encoding="utf-8"), render()))
        print("apidoc: record it with --write when the page is behind the code")
        return 1
    print(f"apidoc: {OUTPUT.name} matches the facades ({entry_count()} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
