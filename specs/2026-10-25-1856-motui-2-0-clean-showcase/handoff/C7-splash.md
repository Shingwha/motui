# C7 · Persistent MOTUI splash; square snake cells

> 2026-10-25, after C6 (`f62fc60` + `b557a68`)

## A. What changed

- Splash logo is uppercased **MOTUI**; `FONT_5X7` gained `M/O/T/U/I` glyphs
  (M/O/U reuse the block forms, T gets a top bar, I gets serifs).
- The splash no longer times out: `SplashScene.tick` always returns `None`;
  only a key or a click enters the menu.
- Four style packs rotate every `SPLASH_ROTATE_TICKS` (120 ticks ≈ 4 s):
  `neon` (cyan→lavender ramp + white sweep), `plasma` (HSL hue walk),
  `retro` (green/amber CRT with scanlines), `starfield` (drifting colors,
  red/cyan glitch bands, star rows around the logo).
- Each pack morphs the fill glyph every 18 ticks
  (`█/▓/▒/■/▣/✦`) and changes colors; the hint names the active pack.
- `Showcase(seed=0)` is deterministic for `--pages`/semantic; a live launch
  uses `seed=None` (system RNG), reshuffling on every return to the splash.
- Live `python -m motui` starts on the splash; a piped run still prints the
  menu frame (no screen to wait on). `--scene` still wins.
- Snake body switched from `■` to half-block cells (`▀`/`▄`/`█`): two
  logical rows per screen row, so horizontal and vertical runs are made of
  the same square-ish units and vertical runs no longer show gaps.

## B. Gates

```
pytest                      1639 passed
semantic --check            5 scenes match
pages                       5 scenes
ruff / pyright              0 / 0
lint-imports / api          4 kept / 188 names
growth (full)               OK
version                     2.0.0
```

## C. Files

- `src/motui/demo/art.py` (uppercase glyphs, `style_at`)
- `src/motui/demo/showcase.py` (SplashScene packs, seed, persistent)
- `src/motui/demo/snake.py` (half-block body)
- `src/motui/demo/__init__.py` (live default splash, seed wiring)
- `tests/test_demo_scenes.py`, `tests/test_smoke.py`,
  `tests/golden/semantic/splash.txt`
- `README.md`, `docs/releases/2.0.0.md`
