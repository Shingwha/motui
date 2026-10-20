"""Every demo topic: it builds, it renders, it follows the template.

One probe per topic is expensive to mount in isolation, so the module
fixture walks the registry once and hands each test the built bodies.  The
assertions the work order names are here: the eight-block skeleton, the
Try/API rows, the coverage of every public widget class and interaction
tier, the two-width render, and the ban on the old Page/Exhibit model.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from motui import Text, TUI
from motui.kernel import HeadlessScreen
from motui.kernel.text import visible_width
from motui.widgets import Divider, Panel

import motui.widgets as widgets

from motui.demo import render_topic
from motui.demo.model import TopicBody
from motui.demo.registry import TOPICS
from motui.demo.session import Session
from motui.demo.stage import walk_objects

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "src" / "motui" / "demo"

_OLD_NAMES = re.compile(r"Page\(|PageBody|Exhibit|Pick\(|Slot|Action\(|CheckGroup|\bRadio\b")


@pytest.fixture(scope="module")
def built():
    tui = TUI(screen=HeadlessScreen(110, 70), interactive=False)
    session = Session(tui)
    bodies: dict[str, TopicBody] = {}
    for topic in TOPICS:
        session.show_topic(topic.key, toast=False)
        assert session.body is not None
        bodies[topic.key] = session.body
    return session, bodies


def _text(component: object) -> str:
    return getattr(component, "text", "")


def _topic_objects(body: TopicBody):
    """Every object a topic mounts: blocks, the modal controller, overlays."""
    roots = list(body.blocks)
    if body.modal is not None:
        roots.append(body.modal)
    roots.extend(body.overlays)
    for root in roots:
        yield from walk_objects(root)


@pytest.mark.parametrize("topic", TOPICS, ids=lambda topic: topic.key)
def test_every_topic_mounts_the_fixed_template(topic, built):
    """title, summary, divider, preview, try, API -- in that order, at most 8."""
    _, bodies = built
    blocks = list(bodies[topic.key].blocks)
    assert 6 <= len(blocks) <= 8, topic.key
    assert isinstance(blocks[0], Text) and _text(blocks[0]) == topic.title
    assert isinstance(blocks[1], Text) and _text(blocks[1]) == topic.summary
    assert isinstance(blocks[2], Divider)
    assert isinstance(blocks[3], Panel) and blocks[3].title == "preview"
    tries = [index for index, block in enumerate(blocks) if _text(block).startswith("Try: ")]
    apis = [index for index, block in enumerate(blocks) if _text(block).startswith("API: ")]
    assert tries and apis, topic.key
    assert 3 < tries[0] < apis[0], topic.key
    assert _text(blocks[tries[0]]) == f"Try: {topic.try_line}"
    assert _text(blocks[apis[0]]) == f"API: {topic.api_line}"


@pytest.mark.parametrize("topic", TOPICS, ids=lambda topic: topic.key)
def test_the_template_rows_are_one_line_each(topic):
    """The stage is 87 cells wide at the replay geometry: no prose wraps."""
    assert visible_width(topic.summary) <= 87
    assert visible_width(f"Try: {topic.try_line}") <= 87
    assert visible_width(f"API: {topic.api_line}") <= 87


@pytest.mark.parametrize("topic", TOPICS, ids=lambda topic: topic.key)
def test_every_topic_renders_at_wide_and_narrow_widths(topic, built):
    _, bodies = built
    for block in bodies[topic.key].blocks:
        for width in (40, 87):
            rows = block.render(width)
            assert isinstance(rows, list)
            for row in rows:
                assert row.width <= width, (topic.key, width, row.width)


@pytest.mark.parametrize("topic", TOPICS, ids=lambda topic: topic.key)
def test_every_topic_actually_mounts_the_components_it_declares(topic, built):
    """The declared coverage is honest: each widget class is in the tree."""
    _, bodies = built
    names = {type(obj).__name__ for obj in _topic_objects(bodies[topic.key])}
    for name in topic.components:
        if name in widgets.__all__ and isinstance(getattr(widgets, name), type):
            assert name in names, (topic.key, name)


def test_the_whole_public_widget_surface_is_covered(built):
    _, bodies = built
    names = {
        type(obj).__name__
        for body in bodies.values()
        for obj in _topic_objects(body)
    }
    public = {name for name in widgets.__all__ if isinstance(getattr(widgets, name), type)}
    assert public <= names, public - names


def test_the_session_mounts_every_interaction_tier(built):
    """The tiers the interaction topics name are live on the session."""
    session, _ = built
    assert type(session.pointer).__name__ == "Pointer"
    assert type(session.gesture).__name__ == "SelectionGesture"
    assert type(session.find).__name__ == "Find"
    assert type(session.scrollbar).__name__ == "Scrollbar"
    assert type(session.toasts).__name__ == "Toasts"
    assert type(session.tooltip).__name__ == "Tooltip"
    session.toggle_stats()
    assert session.stats is not None and type(session.stats).__name__ == "Stats"
    session.toggle_stats()


def test_every_focus_target_is_inside_the_topic_body(built):
    _, bodies = built
    for key, body in bodies.items():
        if body.focus is None:
            continue
        mounted = {id(obj) for obj in _topic_objects(body)}
        for target in body.focus.targets:
            assert id(target) in mounted, (key, type(target).__name__)


def test_render_topic_is_the_pages_path(built):
    topic = TOPICS[0]
    text = render_topic(topic)
    assert text.startswith(f"\u2500\u2500 /{topic.section}/{topic.key} ")
    assert topic.title in text
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_the_old_page_model_is_gone():
    """No Page/PageBody/Exhibit/Pick/Slot/Action/CheckGroup/Radio in the demo."""
    offenders: list[str] = []
    for path in sorted(DEMO.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _OLD_NAMES.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert offenders == []
