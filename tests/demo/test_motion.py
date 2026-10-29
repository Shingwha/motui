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
    scene.render(FRAME, 24)
    scene.render(FRAME, 84)
    scene.on_key(KeyEvent("space"))
    assert (scene.score, scene.combo, scene.hits, scene.attempts) == (300, 1, 1, 1)
    # 0.15 s late is Good inside the wider 0.20 s window.
    scene.render(FRAME, 165)
    scene.on_key(KeyEvent("space"))
    assert (scene.score, scene.combo, scene.hits, scene.attempts) == (400, 2, 2, 2)
    # 0.30 s late is a Close hit: 40 points, but the combo clears.
    scene.render(FRAME, 246)
    scene.on_key(KeyEvent("space"))
    assert (scene.score, scene.combo, scene.hits, scene.attempts) == (440, 0, 2, 3)
    scene.render(FRAME, 330)
    assert (scene.attempts, scene.combo, scene.hits) == (4, 0, 2)


def test_space_and_click_share_judgment_score_and_feedback():
    keyboard = _motion()
    mouse = _motion()
    keyboard.render(FRAME, 84)
    mouse.render(FRAME, 84)
    keyboard.on_key(KeyEvent("space"))
    mouse.on_click(Pos(x=1, y=1))
    assert keyboard.score == mouse.score == 300
    assert keyboard.verdict == mouse.verdict == "perfect"
    assert "PERFECT +300" in keyboard._hud(80).text
    assert "PERFECT +300" in mouse._hud(80).text


def test_judgment_windows_have_distinct_ready_hit_and_perfect_cues():
    scene = _motion()
    assert scene._game.stage == "approach"
    scene.render(FRAME, 66)
    assert scene._game.stage == "close" and "READY" in scene._hud(80).text
    scene.render(FRAME, 72)
    assert scene._game.stage == "good" and "HIT" in scene._hud(80).text
    scene.render(FRAME, 78)
    assert scene._game.stage == "perfect" and "PERFECT" in scene._hud(80).text


def test_the_motion_frame_is_deterministic_and_has_a_live_board():
    first = render_scene("motion", width=80, height=24, phase=40)
    second = render_scene("motion", width=80, height=24, phase=40)
    assert first == second  # a pure function of the geometry and phase
    assert "combo" in first and "score" in first and "hits" in first
    assert any(char in first for char in ("\u2800", "\u2580", "\u2584", "\u2588"))


def test_enter_lands_on_a_fresh_rings_board():
    scene = _motion()
    for phase in range(1, 110):
        scene.tick(phase)
    assert scene.attempts > 0  # the auto-missed rings left a real residue
    scene.enter()
    assert (scene.score, scene.attempts, len(scene.rings)) == (0, 0, 0)
    scene.render(FRAME, 1)
    assert "PULSE" in "\n".join(row.text for row in scene.render(FRAME, 1))


def test_the_splash_paints_a_pixel_wordmark():
    frame = render_scene("splash", width=80, height=24, phase=240)
    assert "space remix" in frame
    assert any("\u2800" < char < "\u2900" for char in frame)  # braille wordmark
    scene = SplashScene(Theme.dark(), seed=0)
    assert scene.tick(10_000) is None  # never times out
    assert scene.on_key(KeyEvent("x")) == "menu"
    assert scene.on_click(Pos(x=0, y=0)) == "menu"
