"""The demo's protocol: navigation, tiers, picks, modals and the two dumps.

Every probe drives the real :class:`~motui.demo.session.Session` with the
events the piped replay feeds it.  The shell roads are covered end to end:
the header ``MenuBar`` and catalog ``NavList`` clicks, the section and
topic chords, focus cycling and activation, the global palette over the
``CommandRegistry``, Find, the theme rebuild, Stats, the selection copy,
and the topic-owned modals (dialog, context menu, combo dropdown, stack).
The last group runs the two piped entries as subprocesses, exactly the
gates the wave's acceptance names.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from motui import KeyEvent, MouseEvent, TUI
from motui.kernel import HeadlessScreen
from motui.widgets import Form

from motui.demo.registry import SECTIONS, TOPICS, topics_for
from motui.demo.script import HEADLESS_H, HEADLESS_W, script
from motui.demo.session import Session

ROOT = Path(__file__).resolve().parent.parent


def _mounted(width: int = HEADLESS_W, height: int = HEADLESS_H) -> tuple[TUI, Session]:
    tui = TUI(screen=HeadlessScreen(width, height), interactive=False)
    return tui, Session(tui)


def _round(session: Session, event) -> bool:
    answer = session._round(event)
    session._after_round()
    return answer


def _click(session: Session, tui: TUI, cell: tuple[int, int]) -> None:
    _round(session, MouseEvent("left", x=cell[0], y=cell[1], kind="press"))
    _round(session, MouseEvent("left", x=cell[0], y=cell[1], kind="release"))
    tui.paint()


def _cell(tui: TUI, needle: str, region) -> tuple[int, int]:
    for y in range(region.y, region.bottom):
        col = tui.rows[y].text.find(needle, region.x, region.right)
        if col >= 0:
            return (col + 1, y)
    raise AssertionError(f"{needle!r} is not in the region")


def _type(session: Session, text: str) -> None:
    for char in text:
        _round(session, KeyEvent(char, char))


# --- opening state ---------------------------------------------------------------


def test_the_session_opens_on_the_welcome_topic():
    tui, session = _mounted()
    assert session.topic_key == "welcome"
    assert session.section.key == "overview"
    assert session.theme_name == "default"
    tui.paint()
    assert any("Welcome" in row.text for row in tui.rows)
    assert "theme default" in tui.rows[-1].text


def test_the_catalog_holds_only_the_current_sections_topics():
    _, session = _mounted()
    session.show_topic("select")
    assert session.catalog.items == [topic.title for topic in topics_for("components")]
    session.show_topic("find")
    assert session.catalog.items == [topic.title for topic in topics_for("interactions")]


# --- navigation ------------------------------------------------------------------


def test_section_chords_switch_sections():
    _, session = _mounted()
    _round(session, KeyEvent("c-2"))
    assert session.topic_key == "text"
    _round(session, KeyEvent("c-4"))
    assert session.topic_key == "theme-tokens"
    _round(session, KeyEvent("c-6"))
    assert session.topic_key == "api-layers"
    _round(session, KeyEvent("c-1"))
    assert session.topic_key == "welcome"


def test_c_n_and_c_p_wrap_inside_the_section():
    _, session = _mounted()
    _round(session, KeyEvent("c-3"))  # interactions/focus
    first = session.topic_key
    _round(session, KeyEvent("c-p"))
    assert session.topic_key == "dispatch"  # the last interaction
    _round(session, KeyEvent("c-n"))
    assert session.topic_key == first
    for _ in range(len(topics_for("interactions")) - 1):
        _round(session, KeyEvent("c-n"))
    assert session.topic_key == "dispatch"


def test_square_brackets_step_sections():
    _, session = _mounted()
    _round(session, KeyEvent("]"))
    assert session.section.key == "components"
    _round(session, KeyEvent("]"))
    assert session.section.key == "interactions"
    _round(session, KeyEvent("["))
    assert session.section.key == "components"


def test_clicking_the_header_menu_switches_section():
    tui, session = _mounted()
    tui.paint()
    top = tui.dock_region("top")
    _click(session, tui, _cell(tui, "Interactions", top))
    assert session.topic_key == "focus"
    assert session.header.menu.index == 2


def test_clicking_a_catalog_row_opens_its_topic():
    tui, session = _mounted()
    session.show_topic("text", toast=False)
    tui.paint()
    region = tui.frame.region(session.catalog_pane.id)
    _click(session, tui, _cell(tui, "Table", region))
    assert session.topic_key == "table"


def test_show_validates_the_section_and_unknown_topics_raise():
    _, session = _mounted()
    with pytest.raises(KeyError):
        session.show_topic("no-such-topic")
    with pytest.raises(KeyError):
        session.show("overview", "select")


# --- the focus ring --------------------------------------------------------------


def test_tab_cycles_the_focus_ring_and_enter_lands_a_pick():
    _, session = _mounted()
    session.show_topic("select", toast=False)
    assert session.focus_name() == "select"
    _round(session, KeyEvent("enter"))
    assert session.last_pick == "value 01"
    _round(session, KeyEvent("tab"))
    assert session.focus_name() == "select"
    assert session.ring.focused is not session.body.focus.targets[0]


def test_escape_returns_the_focus_to_the_catalog():
    _, session = _mounted()
    session.show_topic("select", toast=False)
    _round(session, KeyEvent("escape"))
    assert session.ring.focused is session.catalog
    assert session.focus_name() == "navlist"


def test_space_toggles_the_focused_views_cursor_mark():
    _, session = _mounted()
    session.show_topic("list", toast=False)
    target = session.ring.focused
    assert target.index == 0
    _round(session, KeyEvent("space", " "))
    assert 0 in target.marked


# --- the global palette ----------------------------------------------------------


def test_the_palette_jumps_to_a_topic_and_closes():
    _, session = _mounted()
    _round(session, KeyEvent("c-k"))
    assert session.palette.is_open
    _type(session, "combobox")
    assert session.palette.input.text == "combobox"
    _round(session, KeyEvent("enter"))
    assert not session.palette.is_open
    assert session.topic_key == "combobox"
    assert "ComboBox" in session.last_pick


def test_the_palette_can_be_cancelled():
    _, session = _mounted()
    before = session.topic_key
    _round(session, KeyEvent("c-k"))
    _round(session, KeyEvent("escape"))
    assert not session.palette.is_open
    assert session.topic_key == before


def test_the_slash_opens_the_palette_only_when_no_field_owns_it():
    _, session = _mounted()
    session.show_topic("welcome", toast=False)
    _round(session, KeyEvent("/", "/"))
    assert session.palette.is_open
    _round(session, KeyEvent("escape"))

    session.show_topic("input", toast=False)
    _round(session, KeyEvent("/", "/"))
    assert not session.palette.is_open  # the focused Input typed it


# --- find, stats, theme ----------------------------------------------------------


def test_c_f_opens_find_and_escape_closes_it():
    tui, session = _mounted()
    session.show_topic("find", toast=False)
    tui.paint()
    _round(session, KeyEvent("c-f"))
    assert session.find.is_open
    _type(session, "find")
    assert session.find.matches
    assert session.find.index == 0
    _round(session, KeyEvent("enter"))
    assert session.find.index == 1
    _round(session, KeyEvent("escape"))
    assert not session.find.is_open


def test_c_g_mounts_and_unmounts_stats():
    _, session = _mounted()
    assert session.stats is None
    _round(session, KeyEvent("c-g"))
    assert session.stats is not None
    _round(session, KeyEvent("c-g"))
    assert session.stats is None


def test_theme_switch_rebuilds_without_losing_the_topic():
    tui, session = _mounted()
    session.show_topic("select", toast=False)
    _round(session, KeyEvent("c-t"))
    assert session.theme_name == "amber"
    assert session.topic_key == "select"
    tui.paint()
    assert "theme: amber" in tui.rows[0].text
    _round(session, KeyEvent("c-t"))
    _round(session, KeyEvent("c-t"))
    assert session.theme_name == "default"
    assert session.topic_key == "select"


# --- the shell's own roads -------------------------------------------------------


def test_a_drag_release_copies_the_range_and_toasts_the_answer():
    tui, session = _mounted()
    session.show_topic("text", toast=False)
    tui.paint()
    region = tui.frame.region(session.stage.id)
    start = _cell(tui, "Plain Text", region)
    end = (start[0] + 30, start[1] + 2)
    _round(session, MouseEvent("left", x=start[0], y=start[1], kind="press"))
    _round(session, MouseEvent("left", x=end[0], y=end[1], kind="motion"))
    _round(session, MouseEvent("left", x=end[0], y=end[1], kind="release"))
    tui.paint()
    assert "copied" in tui.screen.output
    assert session.tui.selection is not None


def test_a_toast_answers_a_topic_jump():
    tui, session = _mounted()
    _round(session, KeyEvent("c-2"))
    tui.paint()
    assert "Components \u00b7 Text" in tui.screen.output


# --- the topic-owned modals ------------------------------------------------------


def test_a_modal_opens_and_reports_its_decision():
    _, session = _mounted()
    session.show_topic("modal", toast=False)
    _round(session, KeyEvent("enter"))  # the opener
    assert session._modal() is not None
    _round(session, KeyEvent("right"))
    _round(session, KeyEvent("enter"))
    assert session._modal() is None
    assert session.last_pick == "shipped"


def test_the_context_menu_routes_arrows_and_enter():
    _, session = _mounted()
    session.show_topic("context-menu", toast=False)
    opener = session.body.focus.targets[1]
    session.ring.focus(opener)
    _round(session, KeyEvent("enter"))
    assert session._modal() is not None
    _round(session, KeyEvent("down"))
    _round(session, KeyEvent("enter"))
    assert session._modal() is None
    assert session.last_pick == "rename"


def test_the_combobox_dropdown_takes_a_keyboard_pick():
    _, session = _mounted()
    session.show_topic("combobox", toast=False)
    opener = session.body.focus.targets[1]
    session.ring.focus(opener)
    _round(session, KeyEvent("enter"))
    assert session._modal() is not None
    _round(session, KeyEvent("enter"))
    assert session._modal() is None
    assert session.last_pick == "dialog"


def test_two_modals_stack_and_restore_the_layer_below():
    _, session = _mounted()
    session.show_topic("modal-stack", toast=False)
    _round(session, KeyEvent("enter"))
    assert session._modal() is not None
    _round(session, KeyEvent("right"))
    _round(session, KeyEvent("enter"))
    assert session._modal() is not None  # the second panel took over
    _round(session, KeyEvent("enter"))
    assert session._modal() is None
    assert session.last_pick == "done"


def test_the_form_validates_then_submits_a_mapping():
    _, session = _mounted()
    session.show_topic("form-validation", toast=False)
    form = session.ring.focused
    assert isinstance(form, Form)
    _round(session, KeyEvent("enter"))  # empty: errors land on the fields
    assert form.fields[0].error == "required"
    form.fields[0].component.text = "Ada"
    form.fields[1].component.text = "ada@example.invalid"
    form.fields[2].component.checked = True
    _round(session, KeyEvent("enter"))
    assert "name=Ada" in session.last_pick


# --- the script and the two dumps ------------------------------------------------


def test_the_replay_visits_every_section_and_jumps_through_the_palette():
    keys = [event.key for event in script() if isinstance(event, KeyEvent)]
    for section in ("c-1", "c-2", "c-3", "c-4", "c-5", "c-6"):
        assert section in keys
    assert "c-k" in keys and "c-t" in keys
    assert keys[-2:] == ["q", "c-c"]


def _run(*args: str, stdin=subprocess.DEVNULL) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "motui", *args],
        stdin=stdin,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )


def test_the_piped_entry_exits_zero_and_ends_on_welcome():
    done = _run()
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-2000:]
    text = done.stdout.decode("utf-8")
    assert "Welcome" in text
    assert "theme:" in text
    assert text.count("\n") >= 60


def test_the_pages_dump_survives_a_legacy_codepage():
    """A piped cp1252 stdout still gets the whole UTF-8 frame."""
    done = subprocess.run(
        [sys.executable, "-m", "motui", "--pages"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "PYTHONIOENCODING": "cp1252",
            "PYTHONPATH": str(ROOT / "src"),
        },
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-2000:]
    assert "░".encode() in done.stdout  # the scrollbar track survived


def test_pages_dumps_every_section_and_topic_with_no_old_names():
    done = _run("--pages")
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-2000:]
    text = done.stdout.decode("utf-8")
    assert text.count("\u2500\u2500 /") == len(SECTIONS) + len(TOPICS)
    for section in SECTIONS:
        assert f"\u2500\u2500 /{section.key} " in text
    for topic in TOPICS:
        assert f"\u2500\u2500 /{topic.section}/{topic.key} " in text
    for old in ("/notes", "/views", "/modals", "/themes", "/shell", "/streaming"):
        assert f"\u2500\u2500 {old} " not in text
