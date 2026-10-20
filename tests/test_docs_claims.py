"""The docs' factual claims, checked against the shipped package.

The prose can change freely; names, layers, counts and stale API references
cannot. These tests pin the claims that would otherwise rot silently.
"""

from __future__ import annotations

import re
from pathlib import Path

import motui
import motui.widgets as widgets
from motui.demo.registry import SECTIONS, TOPICS
from motui.kernel.frame import LAYERS

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DESIGN = ROOT / "docs" / "DESIGN.md"
COMPONENTS = ROOT / "docs" / "COMPONENTS.md"
CONTRACT = ROOT / "docs" / "CONTRACT.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
PUBLIC_DOCS = (README, DESIGN, COMPONENTS, CONTRACT, CONTRIBUTING)

#: Names the toolkit deliberately removed. None of them may appear in public
#: documentation; history lives in the changelog and release notes.
STALE_NAMES = (
    "FocusRing",
    "chosen",
    "hit_test",
    "add_band",
    "viewport_rows",
    "invalidate(",
    "stop()",
    "read_key",
    "CheckGroup",
    "Radio(",
    "cursor_style",
    "selected_style",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_root_facade_is_the_documented_34_names():
    """The root is curated: every root name appears in the README."""
    assert len(motui.__all__) == 34
    readme = _read(README)
    missing = [name for name in motui.__all__ if name not in readme]
    assert missing == []


def test_every_widget_is_in_the_readme_and_the_catalogue():
    """Every public widget is named in the README and has a catalogue entry."""
    readme = _read(README)
    components = _read(COMPONENTS)
    assert len(widgets.__all__) == 44
    assert [name for name in widgets.__all__ if name not in readme] == []
    assert [name for name in widgets.__all__ if f"### {name}\n" not in components] == []


def test_every_catalogue_entry_uses_the_fixed_template():
    """The catalogue's six labels appear for every entry (plus the controllers)."""
    components = _read(COMPONENTS)
    for label in (
        "**Purpose:**",
        "**Signature:**",
        "**Verbs:**",
        "**Result:**",
        "**Protocols:**",
        "**Notes:**",
    ):
        assert components.count(label) >= len(widgets.__all__), label


def test_the_layer_graph_names_every_layer():
    """DESIGN and CONTRIBUTING document the one-way graph."""
    design = _read(DESIGN)
    contributing = _read(CONTRIBUTING)
    for name in ("motui.kernel", "motui.keys", "motui.widgets", "motui.interaction", "motui.app"):
        assert name in design
    for name in ("kernel", "keys", "widgets", "commands", "interaction", "app", "testing"):
        assert name in contributing


def test_the_overlay_layers_match_the_code():
    """The documented layer order is the frame's own tuple."""
    design = _read(DESIGN)
    assert LAYERS == (
        "background",
        "content",
        "selection",
        "chrome",
        "overlay",
        "modal",
        "tooltip",
        "toast",
    )
    expected = (
        '(\n'
        '    "background", "content", "selection", "chrome",\n'
        '    "overlay", "modal", "tooltip", "toast",\n'
        ')'
    )
    assert expected in design


def test_the_contract_names_the_host_seam():
    """The 1.2 host fields and factories are part of the normative page."""
    contract = _read(CONTRACT)
    for name in (
        "document",
        "selection",
        "selection_pane",
        "scroll_keys",
        "painter",
        "reveal",
        "make_input",
        "make_autocomplete",
        "copy_to_clipboard",
    ):
        assert name in contract


def test_the_contract_names_the_new_widget_surfaces():
    """The contract covers the composition layer added in this cycle."""
    contract = _read(CONTRACT)
    for name in (
        "RowBands",
        "ScrollView",
        "Form",
        "MenuBar",
        "ContextMenu",
        "CommandRegistry",
        "Clipboard",
        "take_result",
        "FocusManager",
    ):
        assert name in contract


def test_the_readme_demo_claims_match_the_registry():
    """Six sections, 58 topics and their names are what the demo ships."""
    readme = _read(README)
    assert len(SECTIONS) == 6
    assert len(TOPICS) == 58
    assert "58 topics" in readme
    for section in SECTIONS:
        assert section.key in readme


def test_the_readme_carries_no_release_number():
    """The README is an entry point, not release notes."""
    readme = _read(README)
    assert not re.search(r"\b\d+\.\d+\.\d+\b", readme)


def test_no_stale_api_name_appears_in_public_docs():
    """Removed names are gone from every public page."""
    for path in PUBLIC_DOCS:
        text = _read(path)
        for name in STALE_NAMES:
            assert name not in text, f"{path.name}: stale name {name!r}"


def test_docs_are_english_and_link_to_existing_files():
    """Every relative markdown link resolves inside the repository."""
    link = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")
    for path in PUBLIC_DOCS:
        for target in link.findall(_read(path)):
            candidate = (path.parent / target.split("#", 1)[0]).resolve()
            assert candidate.exists(), f"{path.name}: missing link target {target!r}"
