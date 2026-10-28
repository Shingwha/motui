"""The public surface: every curated name resolves and no private name leaks.

The exact name lists are a release decision, not a test fixture: adding or
removing a public name must not require editing this file.  What is pinned is
structural -- the facades publish public names, every name resolves, and the
root is a curated subset of the layers.
"""

from __future__ import annotations

import importlib

import pytest

FACADES = (
    "motui",
    "motui.kernel",
    "motui.pixel",
    "motui.terminal",
    "motui.widgets",
    "motui.app",
    "motui.testing",
)


@pytest.mark.parametrize("path", FACADES)
def test_each_facade_publishes_resolvable_public_names(path):
    module = importlib.import_module(path)
    names = module.__all__
    assert names, path
    assert names == list(dict.fromkeys(names)), f"{path}: duplicate name"
    assert [name for name in names if name.startswith("_")] == [], path
    assert [name for name in names if not hasattr(module, name)] == [], path


def test_every_root_name_has_a_layer_home():
    root = importlib.import_module("motui")
    layers = {
        path: set(importlib.import_module(path).__all__)
        for path in FACADES[1:]
    }
    orphans = [
        name
        for name in root.__all__
        if not any(name in names for names in layers.values())
    ]
    assert orphans == [], f"root names with no layer home: {orphans}"

