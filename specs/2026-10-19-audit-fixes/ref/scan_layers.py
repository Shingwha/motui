"""Probe (ref for W5): the layer dependency graph must stay one-way.

AST-scans every module under src/motui (relative imports resolved against
the file's package) and reports the layer -> layer edges. The expected
shape: kernel -> nothing; keys -> kernel; widgets -> kernel, keys;
interaction -> app, kernel, widgets; demo -> interaction, kernel, root,
widgets. The root package re-exports everything by design. Any edge that
points above its source in the order kernel < keys/widgets < interaction,
app < root is a violation (interaction -> app is the documented assembly
seam, not a violation).

Run: uv run python specs/2026-10-19-audit-fixes/ref/scan_layers.py
"""

import ast
import collections
import pathlib

ROOT = pathlib.Path("src/motui")
LAYERS = ["kernel", "keys", "widgets", "interaction", "app"]
ORDER = {name: i for i, name in enumerate(LAYERS)}

graph = collections.defaultdict(set)
for f in ROOT.rglob("*.py"):
    if "__pycache__" in str(f):
        continue
    rel = f.relative_to(ROOT)
    pkg = ["motui"] + list(rel.parts[:-1])
    tree = ast.parse(f.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - (node.level - 1)]
                parts = base + (node.module.split(".") if node.module else [])
            elif node.module and node.module.startswith("motui"):
                parts = node.module.split(".")
            else:
                continue
            src_layer = pkg[1] if len(pkg) > 1 else "root"
            tgt_layer = parts[1] if len(parts) > 1 else "root"
            if tgt_layer != src_layer:
                graph[src_layer].add(tgt_layer)

print("layer dependency edges:")
for src in sorted(graph):
    print(f"  {src:<12} -> {sorted(graph[src])}")

bad = [
    (s, t)
    for s, ts in graph.items()
    if s in ORDER
    for t in ts
    if t in ORDER and ORDER[t] > ORDER[s]
]
print()
print("upward violations:", bad if bad else "NONE - one-way dependency verified")
