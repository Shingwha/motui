"""The interactive showcase scenes, driven directly instead of through a TTY.

``test_smoke`` covers the entry points; this file pins the scene mechanics
that a key sequence exposes: the snake's pace/turns/food/death, the gallery's
click-through to its widgets, and the determinism a headless replay relies on.
"""

from __future__ import annotations

from motui.demo import PAGE_PHASE, render_scene
from motui.demo.showcase import DashboardScene, GalleryScene, SnakeScene
from motui.kernel.events import KeyEvent
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.theme import Theme

FRAME = Constraints(width=80, max_height=24)


def _snake() -> SnakeScene:
    scene = SnakeScene(Theme.dark())
    scene.render(FRAME, 0)
    return scene


def test_the_snake_takes_one_step_every_four_ticks():
    scene = _snake()
    head = scene.snake[0]
    scene.tick(3)
    assert scene.snake[0] == head
    scene.tick(4)
    assert scene.snake[0] == (head[0] + 1, head[1])


def test_the_snake_turns_and_refuses_a_reverse():
    scene = _snake()
    scene.on_key(KeyEvent("down"))
    assert (scene.dx, scene.dy) == (0, 1)
    scene.on_key(KeyEvent("up"))  # reverse of down: refused
    assert (scene.dx, scene.dy) == (0, 1)
    scene.on_key(KeyEvent("left"))
    assert (scene.dx, scene.dy) == (-1, 0)


def test_the_snake_eats_food_and_grows():
    scene = _snake()
    head = scene.snake[0]
    length = len(scene.snake)
    scene.food = (head[0] + 1, head[1])
    scene.tick(4)
    assert scene.score == 10
    assert len(scene.snake) == length + 1


def test_space_pauses_and_resumes():
    scene = _snake()
    scene.on_key(KeyEvent("space"))
    assert scene.paused
    head = scene.snake[0]
    scene.tick(4)
    assert scene.snake[0] == head

    scene.on_key(KeyEvent("space"))
    assert not scene.paused
    scene.tick(8)
    assert scene.snake[0] != head


def test_hitting_the_wall_ends_the_game_and_space_restarts():
    scene = _snake()
    scene.snake = [(scene._iw - 1, 0)]
    scene.dx, scene.dy = 1, 0
    scene.tick(4)
    assert not scene.alive
    assert "GAME OVER" in scene.render(FRAME, 4).rows[0].text

    scene.on_key(KeyEvent("space"))
    assert scene.alive and scene.score == 0 and len(scene.snake) == 4


def test_snake_renders_deterministically():
    first = render_scene("snake", width=80, height=24, phase=40)
    second = render_scene("snake", width=80, height=24, phase=40)
    assert first == second
    assert "snake" in first and "score" in first
    assert "\u2588" in first and "\u25cf" in first


def test_snake_returns_to_the_menu():
    assert _snake().on_key(KeyEvent("escape")) == "menu"
    assert _snake().on_key(KeyEvent("q")) == "menu"


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


def _gallery() -> GalleryScene:
    scene = GalleryScene(Theme.dark())
    scene.render(Constraints(width=100, max_height=30), 0)
    return scene


def test_gallery_click_reaches_the_tree_and_folds_a_branch():
    scene = _gallery()
    node = scene.tree.root_nodes[0]
    assert node.expanded is True
    # The gallery's title/gap/divider/gap occupy four rows above the body;
    # the tree panel's border is the body's first row, so its first node row
    # is five rows below the centred block's top.
    scene.on_click(Pos(x=3, y=scene._top + 5))
    assert node.expanded is False
    scene.on_click(Pos(x=3, y=scene._top + 5))
    assert node.expanded is True


def test_gallery_click_focuses_the_clicked_widget():
    scene = _gallery()
    assert scene._focus == 0
    # The middle panel starts after the first panel and its gap; a click in
    # its content row focuses the Table whatever its own click door says.
    scene.on_click(Pos(x=40, y=scene._top + 5))
    assert scene._focus == 1


def test_the_page_phase_has_content_in_the_game_and_the_dashboard():
    snake = render_scene("snake", phase=PAGE_PHASE)
    assert "score" in snake and "\u2588" in snake
    dashboard = render_scene("dashboard", phase=PAGE_PHASE)
    assert f"tick {PAGE_PHASE:04d}" in dashboard
    assert "t00018" in dashboard  # a streamed log line, not the seed window
