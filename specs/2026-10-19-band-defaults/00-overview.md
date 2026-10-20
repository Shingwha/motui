# 00 · Overview — the band defaults (1.1.9)

✅ 2026-10-20 · W1–W3 all merged (main @ 22ef64e); the 1.1.9 release awaits the
release owner's instruction.

## Goal

Correct the 1.1.8 band-family defaults and complete the taxonomy's semantics.
The decision in one sentence: **the toolkit paints structure, the host paints
feedback** — `ground`, `ground_active` and `hover` default to `NONE`, and the
only things a default render paints are position signals (the caret's block, a
focused control's band) and structure (the new cursor markers).

## Decisions (settled — do not re-litigate inside the tickets)

- **D1 — the band family defaults to `NONE`.** `hover` and `ground_active`
  become `NONE` (`ground` already is). The industry line this takes: urwid's
  `AttrMap` maps explicit attributes, Rich's `Padding(style=None)` pads plain,
  ratatui's `highlight_style` starts empty — the toolkits that do not own the
  screen never assume a background; Textual does own one and defaults to
  surfaces, which is the other camp. motui's host owns the screen, so the
  default assumes nothing: a transparent terminal, a light terminal and a
  custom theme are all safe.
- **D2 — two carve-outs, kept on purpose.** `caret` keeps its `reverse` block:
  the insertion point is a *position*, not feedback — a text field without a
  caret is not a text field, and at one cell reverse is the only
  terminal-independent visibility. `focus` keeps its band: the keyboard
  position signal predates this taxonomy and mocode's dialog buttons sit on
  its default; changing it is out of this wave's scope. `selection` keeps its
  band — the text selection's own semantics.
- **D3 — the pointer row reads `hover`, not `ground_active`.** Semantic
  rehoming, independent of the defaults: a host that themes `hover` wants
  pointer feedback and must get it on list rows; a host that themes
  `ground_active` means the keyboard cursor row and must not move the hover.
  One token per signal, everywhere in the toolkit. Precedence: **the hovered
  row wears the hover band whatever row it is on; the unhovered cursor row
  wears the active band.**
- **D4 — cursor markers on NavList, Table and Tree.** With D1 the cursor row
  is bare by default, so position needs a structural carrier: the `▸` seat
  `List` already uses (and `→` for `Select`). The contract: **marker =
  position, band = emphasis** — a fixed-width seat on every row, the glyph on
  the cursor row, the seat styled with the row's own text style.
- **D5 — the invariant test.** Under `DEFAULT_THEME` the library paints zero
  `bg`; the only `reverse` a default render paints is the caret's cell and a
  focused control's focus band. This is the machine-checkable form of "the
  default never surprises", and the guardrail against the defaults drifting
  back.
- **D6 — 1.1.9, a PATCH under the year-let rule.** The CHANGELOG says it
  plainly: 1.1.8's reverse default for the band family was the wrong call and
  this version corrects it — a documented breaking change, no shim
  (`CONTRIBUTING.md`'s year-let).

## Waves (serial; the merge order is the execution order)

| Wave | Ticket | Branch | After |
|---|---|---|---|
| W1 | `01-defaults.md` — the defaults, the hover rehoming, the invariant | `refactor/119-defaults` | main |
| W2 | `02-markers.md` — the cursor markers (NavList / Table / Tree) | `refactor/119-markers` | W1 merged |
| W3 | `03-demo-docs.md` — the demo themes the family, docs + CHANGELOG | `docs/119-bands` | W2 merged |

W1 and W2 share the row-widget files, so they are serial; W3 is docs-only.

## Global invariants

1. Resting rows and every non-band render stay byte-identical; the A/B probe
   (styled bytes, base against head) is the evidence for the default-visual
   changes, since the golden dump is plain text and cannot see them.
2. The invariant test (D5) ships in W1 and must pass on every later commit.
3. Every commit passes the full gate on its own.
4. Comments and docs in English; commit messages in the repository's style:
   `area: one statement -- one reason`.

## Host impact (for the record)

mocode's spec themes `ground_active` for its hover pill. After D3 that line
moves to `hover` (one line) — and the split is the point: cursor rows and
hover pills become independently themeable. Nothing else changes for the host.

## Reference

The industry evidence is in the sibling group, in-repo and authoritative:
`specs/2026-10-19-surface-taxonomy/ref/industry.md`. Do not re-research.

## The gate

    uv run pytest -q
    uv run python tools/golden.py --check
    uv run python -c "import re, subprocess, sys; done = subprocess.run([sys.executable, 'tools/framebench.py'], capture_output=True, text=True); sys.stdout.write(done.stdout); sys.stderr.write(done.stderr); raise SystemExit(0 if done.returncode == 0 and re.search(r'^render-hash  : [0-9a-f]{64}$', done.stdout, re.M) else 1)"
    uv run python -c "import subprocess, sys; raise SystemExit(subprocess.run([sys.executable, '-m', 'motui'], stdin=subprocess.DEVNULL).returncode)"
    uv run python -m motui --pages

## Git / worktree protocol

Per the spec-team skill: worktrees outside the repository
(`~/.worktrees/mocode-tui/<branch>`), branches from main at the moment the
wave starts, the lead merges with `--no-ff` and runs the gate before and
after, nothing pushed or tagged. The version bump and the release wait for
the release owner's explicit instruction — this group writes the CHANGELOG
entry only.
