# Spec 04 · Chat layer on the new seams (Wave W3a)

> Branch `refactor/w3-chat`. Prerequisite: **W2a and W2b merged**.
> Must read first: `specs/2026-10-05-api-overhaul/00-overview.md`.

## Goal

Move the chat layer onto the wave-1/2 seams, unify its vocabulary, and
behavioralize its tests. Rendered output and host-facing semantics unchanged
(except the charter renames).

## Work order (each task = one commit)

### T1 · Seams and vocabulary
- `chat/message.py`: `_pad_row` → `Line.filled` (its own docstring admits it).
- `chat/tools.py`: `_band_row` → the shared band primitive (`Line.filled` /
  `core.lines` helpers).
- `chat/statusline.py`: inline equal-style merge → `core.lines.fuse`; fix the
  docstring that calls `Spinner.frame` a method (it is a property).
- `chat/slash.py`: `sync_query(editor_value)` → `set_query(editor_value)`
  (same behavior: strips the leading slash, delegates to
  `Autocomplete.set_query`).
- `chat/composer.py` + `chat/transcript.py`: adapt to the new driver seams —
  `tui.painter.set_cursor` (was `set_cursor_anchor`), `tui.viewport` (was
  painter-forwarded scroll state) — and to `Editor.handle_key(event)` (no
  width argument; W2a landed it). `COMPOSER_KEYMAP` unchanged.
- `chat/__init__.py`: re-curate (adds `COMPOSER_KEYMAP` to the facade — it is
  public for hosts customizing the composer keymap).

### T2 · Style resolution once
- Same charter as the widgets: `message.py`, `tools.py`, `statusline.py`,
  `slash.py` resolve `explicit > theme field > DEFAULT_THEME` at construction
  where the choice is static; state-dependent picks (`ToolBlock` tone,
  `Message` role) resolve at render through a stored `self._theme`. The
  render-time boilerplate disappears.

### T3 · Tests behavioralized
- `test_chat_composer.py`: the 8 private-underscore assertions
  (`tui._clock`, `tui._tick`, `tui._every`, `painter._anchor`) become
  behavioral assertions — observable frames (paint deltas via
  `_doubles.RecordingScreen` / `tui.rows`), statusline text, spinner label
  presence. 13 → ~9 tests. `BLOCK_IDS` deep import goes away (assert on the
  document's block ids through the public document/viewport).
- `test_chat_transcript.py`: replace the `tui._dirty` peek with a
  paint-delta/rows check. 10 → ~8 tests.
- `test_chat_statusline.py`: 13 → ~5 tests; the nine left/gutter/right
  variants collapse into two parametrized tests (composition; overflow
  ellipsis) plus the demo-row case.
- `test_chat_slash.py`: replace the render-text scraping helpers
  (`row.text.strip().split("  ")`) with structural assertions on
  `Line.segments` / `texts()` from `_doubles.py`; the 11 open→filter→assert
  variants collapse to ~5 parametrized cases; drop the end-to-end replay that
  re-runs three earlier tests. 16 → ~8 tests.
- `test_chat_tools.py` / `test_chat_message.py`: keep, tighten goldens to
  structure (padding via computed `" " * n`, not literals).

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run ruff check src tests examples` + `uv run ruff format --check` — clean.
3. `uv run mypy src` — clean.
4. `grep -rn "sync_query\|set_cursor_anchor\|_pad_row\|_band_row" src tests examples`
   — zero hits.
5. The demo still runs and its piped dump matches
   `specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt` **modulo the
   composer call-site renames W2a already applied** — if the demo text changed
   for any other reason, stop and report.

## Forbidden

- Everything outside `src/mocode_tui/chat/**` and `tests/test_chat_*.py`
  (the demo and README adapt in W3b; core/widgets are settled).
- `specs/**`, `pyproject.toml`, `docs/**`.

## Report

Per the overview format, including the chat test-file line deltas.
