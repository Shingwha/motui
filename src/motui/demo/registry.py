"""The registry: the six sections and every topic, in catalog order.

``TOPICS`` is the single source of navigation order: the catalog, the
``c-n`` / ``c-p`` walk, the palette and the golden tool all read it.  The
section order is the header's; a topic declares its section key, its group
label and its builder.  ``GROUPS`` is derived from contiguous group runs --
never hand-maintained.
"""

from __future__ import annotations

from .model import Section, Topic
from .topics import (
    components_actions,
    components_data,
    components_forms,
    components_layout,
    components_overlays,
    components_text,
    interactions,
    overview,
    patterns,
    reference,
    styling,
)

__all__ = ["BY_KEY", "GROUPS", "SECTION_BY_KEY", "SECTIONS", "TOPICS", "topics_for"]

#: The header's sections, in order.  ``c-1`` .. ``c-6`` address this tuple.
SECTIONS: tuple[Section, ...] = (
    Section("overview", "Overview"),
    Section("components", "Components"),
    Section("interactions", "Interactions"),
    Section("styling", "Styling"),
    Section("patterns", "Patterns"),
    Section("reference", "Reference"),
)

#: Every topic, in catalog order.  Components first inside their section,
#: grouped Text / Forms / Data / Layout / Actions / Overlays.
TOPICS: tuple[Topic, ...] = (
    *overview.TOPICS,
    *components_text.TOPICS,
    *components_forms.TOPICS,
    *components_data.TOPICS,
    *components_layout.TOPICS,
    *components_actions.TOPICS,
    *components_overlays.TOPICS,
    *interactions.TOPICS,
    *styling.TOPICS,
    *patterns.TOPICS,
    *reference.TOPICS,
)

#: The topics by key: the palette, the replay and tests address topics here.
BY_KEY: dict[str, Topic] = {topic.key: topic for topic in TOPICS}

#: The sections by key: a topic's ``section`` field resolves here.
SECTION_BY_KEY: dict[str, Section] = {section.key: section for section in SECTIONS}

#: The catalog's group rows, one per contiguous run in registry order.
GROUPS: tuple[tuple[int, str], ...] = tuple(
    (index, topic.group)
    for index, topic in enumerate(TOPICS)
    if topic.group and (index == 0 or TOPICS[index - 1].group != topic.group)
)

if len(BY_KEY) != len(TOPICS):
    raise ValueError("demo topics must have unique keys")

for _topic in TOPICS:
    if _topic.section not in SECTION_BY_KEY:
        raise ValueError(f"topic {_topic.key!r} names no known section")

del _topic


def topics_for(section: str | Section) -> tuple[Topic, ...]:
    """The topics of ``section``, in registry order."""
    key = section.key if isinstance(section, Section) else section
    return tuple(topic for topic in TOPICS if topic.section == key)
