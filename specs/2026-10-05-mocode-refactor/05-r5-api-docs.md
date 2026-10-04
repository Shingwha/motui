# Spec R5 · Root API additions + docs final sync

> Branch `refactor/r5-api-docs`; worktree `~/.worktrees/mocode-tui/refactor-r5-api-docs`;
> depends on: R2, R3, R4 merged; deep-read: `00-overview.md`, `docs/DESIGN.md`,
> `docs/COMPONENTS.md`, `README.md`.

## Goal

Two things: (1) make the toolkit's measuring truth — `visible_width`,
`wrap_text`, `ellipsize_tail` — importable from the package root, because
`docs/COMPONENTS.md` tells custom-component authors to measure with the
toolkit's own truth and today that forces a deep import; (2) bring every doc
in line with R1–R4's structure (tree, module paths, signatures, the demo's
stale canned test count). This is the last wave allowed to touch the demo's
canned text.

## Write scope (exclusively yours)

- `src/mocode_tui/__init__.py`, `src/mocode_tui/text.py` (docstring only, if needed)
- `README.md`, `docs/DESIGN.md`, `docs/COMPONENTS.md`
- `examples/pi_demo.py` (the single canned-line change in T3 only)
- `tests/test_api_root.py` (new small file, see T2)
- nothing else — no other source module, no other test file.

## Tickets (one commit each)

### T1 — root exports for the text utilities

Add `visible_width`, `wrap_text`, `ellipsize_tail` to the root imports and
`__all__` (alphabetical placement in `__all__`). Update the root module
docstring's bullet list so it mentions the measuring utilities. `text.py`'s own
`__all__` already exports them; no logic change.

### T2 — a tiny root-surface test

New `tests/test_api_root.py`: assert `from mocode_tui import visible_width,
wrap_text, ellipsize_tail` works and that every name in
`mocode_tui.__all__` is resolvable via `getattr`, plus the R1–R4 ratified
surface (`Row`/`Column` from both `mocode_tui` and `mocode_tui.components`; the
seven `mocode_tui.keys` names). Keep it under ~40 lines — this is the tripwire
for export drift, not a new suite.

### T3 — demo: refresh the stale canned test count

`examples/pi_demo.py`'s `_REPLY_RICH` fenced bash block shows
`707 passed, 2 skipped in 1.99s`. Replace with the current real line the gate
reports at merge time (e.g. `NNN passed, M skipped in X.XXs` — report which).
This is the group's single intentional demo-dump diff; call it out in the
report. Touch nothing else in the demo.

### T4 — docs sync to the post-refactor tree

- `README.md`: the "Layout of the toolkit" tree becomes the real post-R4 tree
  (add `keys/` package with its four modules, `components/layout.py`; drop the
  root `layout.py` line; keep the W-wave comments minimal or drop them — the
  tree is about modules, not archaeology). If you cite test counts anywhere,
  make them real.
- `docs/DESIGN.md`: "The driver" section's `TUI(mouse=False)`/scroll_keys text
  stays; fix the keyboard-decoder paragraph if it names `keys.py` as a file
  (it should read as the `mocode_tui.keys` package now); the painter section
  already lost its throttle sentence in R3 — verify and say so.
- `docs/COMPONENTS.md`: nothing structural left from R4 except re-check that no
  sentence references `Spinner(..., interval=...)` or `mocode_tui.layout`; the
  "Building your own component" walkthrough may now import `visible_width` from
  the package root — keep the example as-is if unchanged behaviorally.
- Every doc claim must be verifiable against the tree at merge time; do not
  leave "W11/W12 revised" notes describing behavior this group deleted.

## Acceptance (run in your worktree, report real output)

1. `uv run pytest -q` — green; report the exact line (it includes the demo's
   new canned count only as text; the suite itself is unchanged).
2. `uv run python -c "
import mocode_tui as m
missing = [n for n in m.__all__ if not hasattr(m, n)]
print(missing)
print(m.visible_width('中x'), m.wrap_text('a bb ccc', 4), m.ellipsize_tail('abcdef', 4))"` → `[]` + sensible values.
3. `uv run python examples/pi_demo.py < /dev/null > out.txt; echo exit=$?; sha256sum out.txt`
   — **expected to differ from the R0 baseline exactly by the canned test-count
   line**; show `diff ref-baseline out.txt` (compute the baseline with
   `uv run python -c "print(open('specs/2026-10-05-mocode-refactor/ref/r0-demo-dump.txt').read()[:0])"`
   — actually diff against the file
   `specs/2026-10-05-mocode-refactor/ref/r0-demo-dump.txt` in your worktree) and
   confirm the only changed lines are the count/time ones.
4. `uv run python -m compileall -q src examples` → silent/zero.

## Red lines

- No source-logic changes in this wave (T1 is import/`__all__` plumbing only).
- No new features in docs that the code does not implement (no promising
  `Panel(padding=)` etc.).
- The demo diff must stay the canned-count lines only.

## Report format

Ticket status table / commit hashes+messages / real outputs for the four
acceptance commands, including the demo `diff` against the R0 file / list of
every doc sentence changed / deviations & open questions.
