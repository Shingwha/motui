"""The showcase scenes driven directly instead of through a TTY."""

from __future__ import annotations

import pytest

from motui.demo import PAGE_PHASE, render_scene
from motui.demo.sections import DashboardScene, GalleryScene
from motui.demo.sections.splash import SPLASH_ROTATE_TICKS, SplashScene
from motui.demo.snake import SnakeScene
from motui.kernel.events import KeyEvent
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.theme import Theme

FRAME = Constraints(width=80, max_height=24)


def _snake() -> SnakeScene:
    scene = SnakeScene(Theme.dark())
    scene.render(FRAME, 0)
    return scene


def test_the_splash_cycles_styles_and_shapes():
    scene = SplashScene(Theme.dark(), seed=0)
    scene.enter()
    assert scene.style_name(0) != scene.style_name(SPLASH_ROTATE_TICKS * 2)
    one = render_scene("splash", width=80, height=24, phase=0)
    two = render_scene("splash", width=80, height=24, phase=SPLASH_ROTATE_TICKS)
    assert one != two
    assert "press any key" in one and "press any key" in two


def test_the_snake_moves_turns_eats_and_pauses():
    scene = _snake()
    head = scene.snake[0]
    scene.tick(3)
    assert scene.snake[0] == head
    scene.tick(4)
    assert scene.snake[0] == (head[0] + 1, head[1])

    scene.on_key(KeyEvent("down"))
    assert (scene.dx, scene.dy) == (0, 1)
    scene.on_key(KeyEvent("up"))  # reverse of down: refused
    assert (scene.dx, scene.dy) == (0, 1)

    head = scene.snake[0]
    length = len(scene.snake)
    scene.food = (head[0], head[1] + 1)
    scene.tick(8)
    assert scene.score == 10 and len(scene.snake) == length + 1
    scene.on_key(KeyEvent("left"))
    assert (scene.dx, scene.dy) == (-1, 0)

    scene.on_key(KeyEvent("space"))
    paused_head = scene.snake[0]
    scene.tick(12)
    assert scene.snake[0] == paused_head
    scene.on_key(KeyEvent("space"))
    scene.tick(16)
    assert scene.snake[0] != paused_head


def test_hitting_the_wall_ends_the_game_and_space_restarts():
    scene = _snake()
    scene.snake = [(scene.playfield_width - 1, 0)]
    scene.dx, scene.dy = 1, 0
    scene.tick(4)
    assert not scene.alive
    assert "GAME OVER" in scene.render(FRAME, 4).rows[0].text
    first = render_scene("snake", width=80, height=24, phase=40)
    assert first == render_scene("snake", width=80, height=24, phase=40)

    scene.on_key(KeyEvent("space"))
    assert scene.alive and scene.score == 0 and len(scene.snake) == 4


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _snake(),
        lambda: DashboardScene(Theme.dark()),
        lambda: GalleryScene(Theme.dark()),
    ],
)
def test_sections_return_to_the_menu(factory):
    assert factory().on_key(KeyEvent("escape")) == "menu"


def test_dashboard_pushes_a_sample_every_tick():
    scene = DashboardScene(Theme.dark())
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


def _gallery() -> GalleryScene:
    scene = GalleryScene(Theme.dark())
    scene.render(Constraints(width=100, max_height=30), 0)
    return scene


def test_gallery_click_reaches_the_tree_and_folds_a_branch():
    scene = _gallery()
    node = scene.tree.root_nodes[0]
    assert node.expanded is True
    scene.on_click(Pos(x=3, y=scene.origin + 5))
    assert node.expanded is False
    scene.on_click(Pos(x=3, y=scene.origin + 5))
    assert node.expanded is True


def test_gallery_click_focuses_the_clicked_widget():
    scene = _gallery()
    assert scene.focus == 0
    scene.on_click(Pos(x=40, y=scene.origin + 5))
    assert scene.focus == 1


def test_the_page_phase_has_content_in_the_game_and_the_dashboard():
    snake = render_scene("snake", phase=PAGE_PHASE)
    assert "score" in snake and (
        "▀" in snake or "▄" in snake or "█" in snake
    )
    dashboard = render_scene("dashboard", phase=PAGE_PHASE)
    assert f"tick {PAGE_PHASE:04d}" in dashboard
    assert "t00018" in dashboard  # a streamed log line, not the seed window
