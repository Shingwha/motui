"""The motion rings game and the pixel splash."""

from __future__ import annotations

from motui.demo import render_scene
from motui.demo.sections import MotionScene, SplashScene
from motui.kernel.events import KeyEvent
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.theme import Theme

FRAME = Constraints(width=80, max_height=24)


def _motion() -> MotionScene:
    """One rings scene rendered once, so the geometry and clock are set."""
    scene = MotionScene(Theme.dark())
    scene.render(FRAME, 0)
    return scene


def test_rings_judge_on_the_contract_windows():
    scene = _motion()
    # Ring 1 is born at 0.4 s and judged exactly on its deadline: Perfect.
    scene.render(FRAME, 24)
    scene.render(FRAME, 84)
    scene.on_key(KeyEvent("space"))
    assert (scene.score, scene.combo, scene.hits, scene.attempts) == (300, 1, 1, 1)
    # Ring 2 (born 1.6 s) judged 0.10 s past its deadline: a Good.
    scene.render(FRAME, 162)
    scene.on_key(KeyEvent("space"))
    assert (scene.score, scene.combo, scene.hits, scene.attempts) == (400, 2, 2, 2)
    # Ring 3 (born 2.8 s) judged 0.15 s late: a force hit, combo clears.
    scene.render(FRAME, 237)
    scene.on_key(KeyEvent("space"))
    assert (scene.score, scene.combo, scene.hits, scene.attempts) == (400, 0, 2, 3)
    # Ring 4 (born 4.0 s) is never judged: it misses on its own at +1.2 s.
    scene.render(FRAME, 313)
    assert (scene.attempts, scene.combo, scene.hits) == (4, 0, 2)


def test_the_motion_frame_is_deterministic_and_has_a_live_board():
    first = render_scene("motion", width=80, height=24, phase=40)
    second = render_scene("motion", width=80, height=24, phase=40)
    assert first == second  # a pure function of the geometry and phase
    assert "combo" in first and "score" in first and "hits" in first
    assert any(char in first for char in ("\u2800", "\u2580", "\u2584", "\u2588"))


def test_enter_lands_on_a_fresh_rings_board():
    scene = _motion()
    for phase in range(1, 100):
        scene.tick(phase)
    assert scene.attempts > 0  # the auto-missed rings left a real residue
    scene.enter()
    assert (scene.score, scene.attempts, len(scene.rings)) == (0, 0, 0)
    scene.render(FRAME, 1)
    assert "rings" in "\n".join(row.text for row in scene.render(FRAME, 1))


def test_the_splash_paints_a_pixel_wordmark():
    frame = render_scene("splash", width=80, height=24, phase=30)
    assert "press any key" in frame
    assert "\u2580" in frame or "\u2584" in frame or "\u2588" in frame  # wordmark
    scene = SplashScene(Theme.dark(), seed=0)
    assert scene.tick(10_000) is None  # never times out
    assert scene.on_key(KeyEvent("x")) == "menu"
    assert scene.on_click(Pos(x=0, y=0)) == "menu"
