"""The demo's model and registry: the IA cannot drift silently.

These probes pin the section order, the topic keys per section, the
contiguous group rule and the coverage contract: every public widget class
and every interaction tier the browser showcases is named by at least one
topic.  The topic builders themselves are exercised in
``test_demo_topics.py``.
"""

from __future__ import annotations

import inspect

import motui.widgets as widgets

from motui.demo.model import Report, TopicBody
from motui.demo.registry import (
    BY_KEY,
    GROUPS,
    SECTION_BY_KEY,
    SECTIONS,
    TOPICS,
    topics_for,
)

_SECTION_TOPICS = {
    "overview": ["welcome"],
    "components": [
        "text", "markdown", "diff", "notice",
        "input", "editor", "checkbox", "radio-group", "checkbox-group",
        "select", "combobox", "autocomplete", "slider", "form",
        "list", "table", "tree", "tabs", "navlist", "progress", "spinner",
        "row-column", "padding-panel", "divider", "collapsible", "spacer",
        "scroll-view", "delegate",
        "button", "link", "menu-bar", "context-menu",
        "dialog", "modal", "palette", "toasts", "tooltip", "stats",
    ],
    "interactions": [
        "focus", "pointer", "selection", "find", "scrollbar",
        "modal-stack", "dispatch",
    ],
    "styling": ["theme-tokens", "custom-theme", "glyphs", "row-bands"],
    "patterns": [
        "streaming-markdown", "form-validation", "command-palette", "own-shell",
    ],
    "reference": ["api-layers", "keymap", "component-matrix", "non-goals"],
}

_INTERACTION_TIERS = {
    "FocusManager", "Pointer", "SelectionGesture", "Find", "Scrollbar",
    "Modal", "Palette", "Toasts", "Tooltip", "Stats",
}


def test_the_six_sections_are_the_header_order():
    assert SECTIONS == tuple(
        type(SECTIONS[0])(key, title)
        for key, title in (
            ("overview", "Overview"),
            ("components", "Components"),
            ("interactions", "Interactions"),
            ("styling", "Styling"),
            ("patterns", "Patterns"),
            ("reference", "Reference"),
        )
    )
    assert set(SECTION_BY_KEY) == {section.key for section in SECTIONS}


def test_the_topic_table_is_the_work_orders_ia():
    """Every section's keys, in registry order, are exactly the IA's list."""
    for section, expected in _SECTION_TOPICS.items():
        assert [topic.key for topic in topics_for(section)] == expected, section
    assert [topic.key for topic in TOPICS] == [
        key for keys in _SECTION_TOPICS.values() for key in keys
    ]


def test_keys_are_unique_and_resolve_through_by_key():
    assert len({topic.key for topic in TOPICS}) == len(TOPICS)
    assert BY_KEY == {topic.key: topic for topic in TOPICS}
    for topic in TOPICS:
        assert topic.section in SECTION_BY_KEY
        assert topic.title and topic.summary and topic.group
        assert len(topic.summary) <= 100
        assert topic.try_line and topic.api_line
        assert callable(topic.build)
        assert topic.components


def test_groups_are_contiguous_runs_of_topics():
    for section in SECTIONS:
        topics = topics_for(section)
        seen: set[str] = set()
        previous = None
        for topic in topics:
            if topic.group != previous:
                assert topic.group not in seen, (
                    f"{section.key}: group {topic.group!r} is not contiguous"
                )
                seen.add(topic.group)
                previous = topic.group
    assert GROUPS == tuple(
        (index, topic.group)
        for index, topic in enumerate(TOPICS)
        if topic.group and (index == 0 or TOPICS[index - 1].group != topic.group)
    )


def test_every_public_widget_class_and_interaction_tier_is_covered():
    """The union of the topics' declared components is the public surface."""
    covered: set[str] = set()
    for topic in TOPICS:
        covered.update(topic.components)
    public_widgets = {
        name
        for name in widgets.__all__
        if inspect.isclass(getattr(widgets, name))
    }
    assert public_widgets <= covered, public_widgets - covered
    assert _INTERACTION_TIERS <= covered, _INTERACTION_TIERS - covered


def test_topic_bodies_and_reports_are_plain_values():
    body = TopicBody(blocks=())
    assert body.focus is None and body.modal is None and body.tick is None
    assert body.note is None and body.enter is None and body.leave is None
    assert body.overlays == ()
    report = Report("source", True)
    assert report.source == "source" and report.value is True


def test_the_palette_label_spells_section_and_topic():
    topic = BY_KEY["select"]
    assert topic.command_name("Components") == "Components \u00b7 Select"
