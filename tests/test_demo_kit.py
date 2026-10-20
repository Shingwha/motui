"""The kit's protocol wiring: actions as data, the pick read, the echo, the ring.

The two kit-built pages are covered by the golden frames and the demo
protocol's plays (a pick opens the page it names, a task box echoes); these
probes pin the kit's own contract at the seams those paths do not name
directly: a pick is read exactly once, an ``Action`` runs with the session
while a bare value is only reported, the fallback action a slot carries
answers the components that carry none, the echo formats one line and
stays empty until something lands, and ``build`` rings the focused slots
in registration order.
"""

from __future__ import annotations

from types import SimpleNamespace

from motui import Button, Checkbox, DEFAULT_THEME, Option, Select

from motui.demo.kit import Action, Echo, Exhibit


def _exhibit() -> tuple[SimpleNamespace, Exhibit]:
    """The kit's whole need of a session is the theme (and being handed back)."""
    session = SimpleNamespace(theme=DEFAULT_THEME)
    return session, Exhibit(session, title="t", blurb="b")


def test_a_pick_that_carries_an_action_runs_it_with_the_session_and_is_not_reported():
    session, exhibit = _exhibit()
    opened: list = []
    index = Select(
        [Option("one", value=Action("one", "the first row", opened.append))],
        max_rows=None,
    )
    exhibit.show(index)
    reported: list = []

    assert index.activate() is True  # the cursor row lands the pick
    assert exhibit.resolve_picks(reported.append) is True
    assert opened == [session] and reported == []  # run, never reported
    assert index.take_result() is None  # the pick was read exactly once


def test_a_bare_value_is_only_reported():
    _, exhibit = _exhibit()
    box = Checkbox("fold me")
    exhibit.show(box)
    reported: list = []

    assert box.activate() is True
    assert exhibit.resolve_picks(reported.append) is True
    (pick,) = reported
    assert pick.source is box and pick.action is None and pick.value is True
    assert box.take_result() is None


def test_a_slots_action_is_the_fallback_the_component_carries_none():
    session, exhibit = _exhibit()
    shipped: list = []
    ship = Button("Ship")
    exhibit.show(ship, action=Action("ship", "shipped", shipped.append))
    reported: list = []

    assert ship.activate() is True  # chosen is the button's True, no action of its own
    assert exhibit.resolve_picks(reported.append) is True
    assert shipped == [session] and reported == []


def test_a_read_is_once_then_cleared_and_nothing_pending_answers_false():
    _, exhibit = _exhibit()
    box = Checkbox("once")
    exhibit.show(box)
    reported: list = []

    assert exhibit.resolve_picks(reported.append) is False  # nothing pending
    assert box.activate() is True
    assert exhibit.resolve_picks(reported.append) is True
    assert len(reported) == 1
    assert exhibit.resolve_picks(reported.append) is False  # read once, never twice


def test_the_echo_formats_one_line_and_renders_nothing_until_it_is_set():
    echo = Echo("echo")

    assert echo.render(40) == []  # nothing reported: the page is byte-identical
    echo.set("todo:0")
    assert echo.text == "echo \u25b8 todo:0"
    assert [row.text for row in echo.render(40)] == ["echo \u25b8 todo:0"]
    echo.set(None)
    assert echo.render(40) == []  # cleared, empty again


def test_build_rings_the_focused_slots_in_registration_order_and_hooks_reports():
    _, exhibit = _exhibit()
    first, second, third = Checkbox("a"), Button("b"), Checkbox("c")
    exhibit.show(first)
    exhibit.show(second, hint="the middle one").focus()
    exhibit.show(third).focus()
    seen: list = []
    exhibit.watch(seen.append)
    body = exhibit.build()

    assert body.focus is not None
    assert list(body.focus.targets) == [second, third]  # registration order, not mount order
    assert body.focus.focused is second  # the ring opens on the first target
    assert second.hint == "the middle one"
    assert list(body.blocks) == exhibit.blocks

    assert second.activate() is True
    assert body.resolve_picks(body.note) is True  # the session's report chain
    assert [pick.value for pick in seen] == [True]  # the watch saw the pick
