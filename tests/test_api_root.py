"""Root-surface tripwire: the package root's export face must not drift.

R5's ratified additions (the text utilities at the root), every
``mocode_tui.__all__`` name resolving via ``getattr``, and the R1-R4
surface: ``Row``/``Column`` are the objects ``mocode_tui.components``
exports, and ``mocode_tui.keys`` still exports its seven public names.
"""

import mocode_tui
import mocode_tui.components as components
import mocode_tui.keys as keys


def test_text_utilities_import_from_the_root():
    """R5: visible_width/wrap_text/ellipsize_tail are root-level names."""
    from mocode_tui import ellipsize_tail, visible_width, wrap_text

    assert visible_width("中x") == 3
    assert wrap_text("a bb ccc", 4) == ["a bb", "ccc"]
    assert ellipsize_tail("abcdef", 4) == "abc…"


def test_every_all_name_resolves_on_the_root():
    """No name may sit in __all__ without a matching root attribute."""
    missing = [n for n in mocode_tui.__all__ if not hasattr(mocode_tui, n)]
    assert missing == []


def test_layout_containers_are_one_object_from_both_faces():
    """R4: Row/Column moved into components/layout.py, re-exported at the root."""
    for name in ("Row", "Column"):
        assert getattr(mocode_tui, name) is getattr(components, name)
        assert name in mocode_tui.__all__ and name in components.__all__


def test_keys_package_exports_the_ratified_seven():
    """R2: the keys/ package re-exports the same seven names as old keys.py."""
    expected = {
        "Key", "KeyDecoder", "KeySource", "MouseEvent",
        "Paste", "RawTerminalKeys", "ScriptedKeys",
    }
    assert expected <= set(keys.__all__)
    for name in expected:
        assert getattr(keys, name) is getattr(mocode_tui, name)
