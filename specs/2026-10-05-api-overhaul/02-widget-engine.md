# Spec 02 · Widget engine dedup: TextBuffer, option rows, style-once (Wave W2a)

> ✅ 2026-10-05 — merged via refactor/w2-widget-engine.

> Branch `refactor/w2-widget-engine`. Prerequisite: **W1 merged** (cut from
> post-W1 main). Runs in parallel with W2b — your write scopes are disjoint.
> Must read first: `specs/2026-10-05-api-overhaul/00-overview.md`.

## Goal

Collapse the duplicated widget machinery: one `TextBuffer` engine under
`Input`/`Editor`, one option-row implementation under `Select`/`Autocomplete`,
style resolution once at construction, dead parameters deleted. **Rendered
output (the `Line`/`Segment` stream) must stay identical** for equal inputs;
the demo diff must stay empty.

## Work order (each task = one commit)

### T1 · `widgets/textbuf.py` — the shared editing engine
- Extract from `input.py` + `editor.py` one engine holding: the text model
  (`list[str]` rows; `Input` enforces single-row), the cursor, the full
  editing-method set (`insert`, `backspace`, `delete`, `clear`, `move_*`,
  `home`, `end`, `newline`), keymap-driven routing, the visual-row geometry
  (`_visual_rows`/`_locate` — one implementation, parameterized by prompt
  indent), the reverse-video cursor body painting, and the placeholder body.
- `Input` and `Editor` become thin policy shells (prompt, placeholder,
  `Editor`'s sliding window, per-component defaults/keymaps). Their public
  constructor surface is unchanged **except**:
  - `Editor.prompt_style` is deleted (it was never read);
  - `handle_key(event)` loses its `width` parameter for both components — the
    width of the last `render(width)` call is remembered (both classes already
    tracked `_last_width`); `handle_key` before any render falls back to a
    sane default (80) — document that.
- Update `examples/pi_demo.py` call sites (`editor.handle_key(event,
  tui.screen.width)` → `editor.handle_key(event)`) and README code blocks if
  they pass a width.

### T2 · Option rows: one implementation
- One shared option-row layout (`"❮ " + label` selected marker, `"  "` body,
  hint/`value` alignment, fit) used by both `Select` and `Autocomplete`
  (today's two `_option_row` copies, similarity 0.86, the `Autocomplete`
  docstring even admits the copy). Shared clamped-cursor move for both.
  Host-visible behavior identical (same marker glyphs, same rows).

### T3 · Style resolution once, dead parameters gone
- Every widget in your scope resolves `explicit > theme field >
  DEFAULT_THEME` **at construction** (charter in 00-overview): store the
  resolved `Style`s (or `self._theme` for state-dependent picks like
  `ToolBlock`-style tones — not in your scope — or `Notice` levels). The
  render-time `theme = self.theme or DEFAULT_THEME` boilerplate disappears
  from your files.
- Delete the never-read `theme=` parameters: `Row`, `Column`, `Padding`,
  `Spacer`, `Spinner`, `StatusBar` (keep `theme=` everywhere it is read).
- Rename width locals to `inner` in your files.

### T4 · Segment utilities migrate
- `table.py::_fuse` → `core.lines.fuse`; `table.py`'s colored-vs-attribute
  rule → `core.lines.overlay` (both exist since W1). Same for the equivalent
  inline merges in your files (e.g. `status.py`, `chrome.py` if present).

### T5 · Tests rewritten under the policy
- Merge `tests/test_widgets_input_keymap.py` into `tests/test_widgets_editor.py`
  (or a combined `test_widgets_editing.py`); the five cross-file duplicate
  pairs (identical names/bodies listed in the audit) keep one copy each.
- `tests/test_widgets_table.py`: 11 → ~7 tests; keep at most two box-drawing
  grids (one full grid, one shrink case); assert structure (row texts, rule
  count) not 9-row literals.
- `test_widgets_progress.py`: merge the duplicated 5-segment golden pair.
- `test_widgets_chrome.py`: drop the duplicated same-assertion-twice sites.
- `test_widgets_tree.py`: drop the theme-fallback variant kept elsewhere.
- `test_widgets_autocomplete.py` / `choice.py` tests: dedupe, parametrize the
  selection matrices.
- Style assertions become round-trip injections; no default color pinned;
  parametrize matrices; use `tests/_doubles.py` (read-only — add local helpers
  in your own test files if needed).

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts reported).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. `grep -n "prompt_style" -r src tests examples` — zero hits.

## Forbidden

- `src/mocode_tui/widgets/markdown.py` and everything that will become
  `widgets/markdown/` (wave W2b owns it), `src/mocode_tui/widgets/syntax.py`.
- `tests/test_widgets_markdown*.py`, `tests/test_widgets_syntax*.py` (W2b).
- `src/mocode_tui/chat/**` (wave W3a; its `composer`/`slash` will adapt to
  `handle_key(event)` there — do not edit chat even for call sites).
- `src/mocode_tui/core/**`, `src/mocode_tui/app.py`, `src/mocode_tui/testing.py`
  (read-only; `fuse`/`overlay` already exist).
- `tests/_doubles.py` is read-only for you.
- `docs/**`, README prose, `specs/**`, `pyproject.toml`.

## Report

Per the overview format. State the line-count delta of
`input.py`+`editor.py` before/after and where the engine landed.
