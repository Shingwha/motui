"""Scene behavior driven directly through the keyboard-first public protocol."""

from __future__ import annotations

from motui.demo import PAGE_PHASE, render_scene
from motui.demo.minis import mini_layout
from motui.demo.sections import DashboardScene, GalleryScene
from motui.demo.sections.splash import ACT_TICKS, SplashScene
from motui.kernel.events import KeyEvent
from motui.kernel.geom import Pos
from motui.kernel.layout import Constraints
from motui.kernel.theme import Theme

FRAME = Constraints(width=80, max_height=24)


def test_splash_combines_a_scene_auxiliary_and_particle_field():
    scene = SplashScene(Theme.dark(), seed=0)
    scene.enter()
    effects = scene.effects(240)
    assert effects[0] == "deep" and len(effects) == 2
    assert effects == scene.effects(240)
    assert scene.effects(240 + ACT_TICKS) != effects
    scene.on_key(KeyEvent("space"))
    assert scene.effects(240) == effects
    scene.tick(ACT_TICKS)
    assert scene.effects(ACT_TICKS) != effects
    assert scene.previous_effects(ACT_TICKS) == effects
    assert scene.on_key(KeyEvent("enter")) == "menu"


def test_splash_particle_frames_replay_at_both_sizes():
    for width, height in ((80, 24), (100, 30)):
        first = render_scene("splash", width=width, height=height, phase=240)
        assert first == render_scene("splash", width=width, height=height, phase=240)
        assert "SIGNAL LAB" in first and "86 STARS" in first
        assert "space remix" in first


def test_splash_keyboard_launches_and_remixes():
    scene = SplashScene(Theme.dark(), seed=0)
    scene.enter()
    assert scene.on_key(KeyEvent("enter")) == "menu"
    assert scene.on_key(KeyEvent("space")) is None
    assert scene._pending_remix == 1
    assert scene.on_key(KeyEvent("q")) == "quit"


def test_sections_return_to_the_menu():
    for factory in (lambda: DashboardScene(Theme.dark()), lambda: GalleryScene(Theme.dark())):
        assert factory().on_key(KeyEvent("escape")) == "menu"


def test_dashboard_samples_at_four_hz_and_runs_a_causal_mission():
    scene = DashboardScene(Theme.dark())
    before = list(scene.samples)
    scene.tick(1)
    assert scene.samples == before
    scene.tick(15)
    assert scene.samples != before and len(scene.samples) == 48
    scene.render(FRAME, 400)
    assert scene._stage == "REROUTING TRAFFIC"
    assert any("traffic moved" in event for event in scene.log)


def test_dashboard_keyboard_controls_pause_inject_recover_and_switch_relay():
    scene = DashboardScene(Theme.dark())
    scene.on_key(KeyEvent("space"))
    scene.tick(100)
    assert scene.paused and scene._time == 0
    scene.on_key(KeyEvent("space"))
    scene.on_key(KeyEvent("n"))
    assert scene._stage == "MANUAL INTERFERENCE"
    scene.on_key(KeyEvent("r"))
    assert scene._stage == "RECOVERING UPLINK"
    scene.on_key(KeyEvent("right"))
    assert scene.channel == 1
    scene.on_key(KeyEvent("3"))
    assert scene.channel == 2


def test_viewport_preview_closes_both_borders_with_bottom_corners():
    rows = mini_layout(20, 50, Theme.dark())
    top, bottom = rows[2].text, rows[7].text
    assert top.count("┌") == 2 and top.count("┐") == 2
    assert bottom.count("└") == 2 and bottom.count("┘") == 2


def test_dashboard_is_deterministic_and_reflows_at_both_sizes():
    for width, height in ((80, 24), (100, 30)):
        first = render_scene("dashboard", width=width, height=height, phase=400)
        assert first == render_scene("dashboard", width=width, height=height, phase=400)
        assert "DEEP SPACE UPLINK" in first and "MISSION EVENTS" in first
        assert all(len(line) <= width for line in first.splitlines())


def _gallery() -> GalleryScene:
    scene = GalleryScene(Theme.dark())
    scene.render(Constraints(width=100, max_height=30), 0)
    return scene


def test_gallery_click_reaches_the_tree_and_folds_a_branch():
    scene = _gallery()
    node = scene.tree.nodes[0]
    scene.on_click(Pos(x=3, y=scene.origin + 5))
    assert node.open is False
    scene.on_click(Pos(x=3, y=scene.origin + 5))
    assert node.open is True


def test_gallery_click_focuses_the_clicked_widget():
    scene = _gallery()
    scene.on_click(Pos(x=40, y=scene.origin + 5))
    assert scene.focus == 1


def test_page_phases_have_live_content():
    dashboard = render_scene("dashboard", phase=PAGE_PHASE)
    assert "SIGNAL STRENGTH" in dashboard and "00:00" in dashboard
    gallery = render_scene("gallery", phase=PAGE_PHASE)
    assert "COMPONENT ARCHIVE" in gallery and "tab focus" in gallery
