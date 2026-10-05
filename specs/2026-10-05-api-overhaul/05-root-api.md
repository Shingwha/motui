# Spec 05 · Root API curation, demo port, 0.3.0 (Wave W3b)

> Branch `refactor/w3-root`. Prerequisite: **W3a merged**.
> Must read first: `specs/2026-10-05-api-overhaul/00-overview.md` (the
> 63-name list below is the binding version).

## Goal

Cut the root namespace to the curated 63 names, port the demo and the README
to the final API, and mark the breaking release. After this wave the library
is the module a host actually installs.

## The 63 root names (binding)

`TUI`, `Hit`, `EveryHandle` · `Screen`, `TerminalScreen`, `HeadlessScreen` ·
`Block`, `Component`, `Line`, `Segment`, `Style`, `Theme`, `DEFAULT_THEME` ·
`MUTED`, `ACCENT`, `SUCCESS`, `ERROR`, `WARNING`, `DIM` · `visible_width`,
`wrap_text` · `Key`, `Paste`, `MouseEvent`, `KeySource`, `ScriptedKeys`,
`RawTerminalKeys`, `Keymap`, `DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP` ·
`headless_tui`, `snapshot` · `Text`, `Markdown`, `Table`, `Tabs`, `Tree`,
`TreeNode`, `Input`, `Editor`, `Select`, `Option`, `Confirm`, `Autocomplete`,
`Notice`, `Divider`, `Panel`, `Row`, `Column`, `Spacer`, `Padding`,
`Spinner`, `ProgressBar`, `StatusBar`, `StatusSegment` · `Composer`,
`Transcript`, `StreamHandle`, `Message`, `ToolBlock`, `EditBlock`,
`StatusLine`, `SlashPalette`.

Down-listed (public at their submodule path, gone from the root): `Painter`,
`Viewport`, `ScreenLayout`, `Document`, `BlockState`, `KeyDecoder`,
`wrap_line`, `ellipsize_tail`, `FG_CODES`, `NONE`, `RESET`, `BORDER`, `CODE`,
`CURSOR`, `SELECTION`, the ANSI helpers, `Highlighter`, `RegexHighlighter`,
`default_highlighter`, `highlight`, the Markdown rule classes and registries,
`COMPOSER_KEYMAP`.

## Work order (each task = one commit)

### T1 · Root and facades
- Rewrite `src/mocode_tui/__init__.py` to the 63 names (the module docstring
  becomes the one-paragraph tour of the four layers + where the deep seams
  live).
- Re-curate the four facades to coherent per-layer surfaces:
  - `core`: everything kernel — primitives, `Text`, events, screen, viewport,
    painter, `MORE_BELOW`, measure helpers;
  - `keys`: `KeyDecoder`, `RawTerminalKeys`, `Keymap`, both default tables;
  - `widgets`: the 23 components + `COMPOSER`-adjacent nothing (chat names
    stay in `chat`); `markdown`/`syntax` facades keep their extension names;
  - `chat`: the 8 names + `COMPOSER_KEYMAP`.

### T2 · `tests/test_api_root.py` re-pinned
- Rewrite to ~6 tests: pin the root `__all__` (the 63), pin each facade's
  `__all__`, identity (`mocode_tui.X is mocode_tui.<layer>.X`), ordering
  convention (constants → classes → functions, sorted), no underscore leaks,
  and "every down-listed name is importable from its documented submodule
  path" (one import sweep, not a residue tripwire).

### T3 · Demo and README port
- `examples/pi_demo.py`: import list trimmed to the new root; all call sites
  on final names; MouseEvent/hit_test 0-based (already landed in W1 — verify);
  `composer`/`palette`/`editor` calls match the final signatures. The scripted
  replay behavior is untouched — **the piped dump must still match the
  baseline byte-for-byte**.
- README: full pass so every code block runs against the final API
  (`test_readme_examples.py` executes them — it is your acceptance). Prose
  polish belongs to W4; here only make the code true.

### T4 · Version + sweep
- `pyproject.toml` → `version = "0.3.0"`.
- Sweep: `grep -rn "\.flush()\|flush(" src/mocode_tui` must only hit
  `Screen.flush` definitions/calls; `grep -rn "sync_query\|set_cursor_anchor\|
  prompt_style\|\.pinned" src tests examples README.md` — zero hits;
  `grep -rn "from mocode_tui import" tests` — only root-public names.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run ruff check src tests examples` + `uv run ruff format --check` — clean.
3. `uv run mypy src` — clean.
4. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
5. The greps of T4, verbatim.
6. `uv run python -c "import mocode_tui; print(len(mocode_tui.__all__))"`
   → 63.

## Forbidden

- Any file outside: `src/mocode_tui/__init__.py`, the four facades'
  `__init__.py`, `tests/test_api_root.py`, `tests/test_readme_examples.py`
  (only if mechanically needed by README changes), `examples/pi_demo.py`,
  `README.md` (code blocks; prose only where it names a moved symbol),
  `pyproject.toml`.
- Behavior edits anywhere — this wave moves names, not semantics. If a port
  requires a semantic decision, stop and report.

## Report

Per the overview format, plus the final `__all__` count and any name you had
to rescue into a facade (with the reason).
