"""The interactive showcase scenes, driven directly instead of through a TTY.

``test_smoke`` covers the entry points; this file pins the scene mechanics
that a key sequence exposes: the paddle, serve/pause, losing the last ball,
and the determinism a headless replay relies on.
"""

from __future__ import annotations

from motui.demo import PAGE_PHASE, render_scene
from motui.demo.showcase import BreakoutScene, DashboardScene
from motui.kernel.events import KeyEvent
from motui.kernel.layout import Constraints
from motui.kernel.theme import Theme

FRAME = Constraints(width=80, max_height=24)


def _breakout() -> BreakoutScene:
    scene = BreakoutScene(Theme.dark())
    scene.render(FRAME, 0)
    return scene


def test_the_paddle_moves_and_carries_a_parked_ball():
    scene = _breakout()
    scene.launched = False
    scene.ball_x = scene.paddle_x + 3
    scene.ball_y = scene.paddle_y - 1
    start = scene.paddle_x
    scene.on_key(KeyEvent("right"))
    assert scene.paddle_x == start + 4
    assert scene.ball_x == scene.paddle_x + 3
    scene.on_key(KeyEvent("h"))
    assert scene.paddle_x == start


def test_space_serves_pauses_and_resumes():
    scene = _breakout()
    scene.launched = False
    scene.on_key(KeyEvent("space"))
    assert scene.launched and not scene.paused

    scene.on_key(KeyEvent("space"))
    assert scene.paused
    parked = (scene.ball_x, scene.ball_y)
    scene.tick(1)
    assert (scene.ball_x, scene.ball_y) == parked

    scene.on_key(KeyEvent("space"))
    assert not scene.paused
    scene.tick(2)
    assert (scene.ball_x, scene.ball_y) != parked


def test_losing_the_last_ball_ends_the_game_and_space_restarts():
    scene = _breakout()
    scene.lives = 1
    scene.ball_x = 0
    scene.paddle_x = 60
    scene.dx, scene.dy = 1, 1
    for phase in range(1, 60):
        scene.tick(phase)
        if scene.game_over:
            break
    assert scene.game_over and scene.lives == 0

    scene.on_key(KeyEvent("space"))
    assert not scene.game_over
    assert scene.score == 0 and scene.lives == 3 and scene.level == 1


def test_breakout_renders_deterministically():
    first = render_scene("breakout", width=80, height=24, phase=40)
    second = render_scene("breakout", width=80, height=24, phase=40)
    assert first == second
    assert "score" in first and "\u2584" in first


def test_breakout_returns_to_the_menu():
    assert _breakout().on_key(KeyEvent("escape")) == "menu"
    assert _breakout().on_key(KeyEvent("q")) == "menu"


def _dashboard() -> DashboardScene:
    return DashboardScene(Theme.dark())


def test_dashboard_pushes_a_sample_every_tick():
    scene = _dashboard()
    before = scene.samples[-1]
    scene.tick(1)
    assert scene.samples[-1] != before
    assert len(scene.samples) == 48
    assert scene.log


def test_dashboard_is_deterministic_and_reflows_at_both_sizes():
    for width, height in ((80, 24), (100, 30)):
        first = render_scene("dashboard", width=width, height=height, phase=30)
        second = render_scene("dashboard", width=width, height=height, phase=30)
        assert first == second
        lines = first.splitlines()
        assert len(lines) <= height
        assert all(len(line) <= width for line in lines)
        for label in ("throughput", "pressure", "metrics", "events"):
            assert label in first


def test_dashboard_clock_is_derived_from_phase():
    one = render_scene("dashboard", phase=30)
    two = render_scene("dashboard", phase=60)
    assert "00:01.0" in one and "tick 0030" in one
    assert "00:02.0" in two and "tick 0060" in two


def test_dashboard_returns_to_the_menu():
    assert _dashboard().on_key(KeyEvent("escape")) == "menu"
    assert _dashboard().on_key(KeyEvent("q")) == "menu"


def test_the_page_phase_has_content_in_the_game_and_the_dashboard():
    breakout = render_scene("breakout", phase=PAGE_PHASE)
    assert "score" in breakout and "\u2584" in breakout
    dashboard = render_scene("dashboard", phase=PAGE_PHASE)
    assert f"tick {PAGE_PHASE:04d}" in dashboard
    assert "t00018" in dashboard  # a streamed log line, not the seed window
