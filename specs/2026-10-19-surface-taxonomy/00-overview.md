# 00 · Overview — the 1.1.8 surface taxonomy

## Goal and scope

Restructure three families bottom-up so each carries exactly one concept. No
compatibility shims: the release owner has authorized breaking changes for 1.1.8 and
waived the CONTRIBUTING major-release rule for this wave (decision D0 below).

1. **The Theme band vocabulary** — one token per role: `ground` (resting surface),
   `ground_active` (engaged row surface), `focus` (focused control band, renamed from
   `cursor`), `caret` (text caret, split out of `cursor`), `selection` (text selection
   only — the List/Tree/Table row cursor moves off it), `hover` (pointer band for
   spans and controls).
2. **The Line sizing family** — `fit(width)` trims, `fill(width, style)` extends and
   surfaces (the absorbed `pad_to`), `filled(width, style)` builds a blank row.
3. **The row-band contract** — every vertical row-carrying widget resolves its bands
   from the vocabulary through one rule.

Out of scope for this release: the `Split` constraint values (`Weight` / `Natural`) —
that is the next wave.

## Waves (serial; the merge order is the execution order)

| Wave | Ticket | Branch | After |
|---|---|---|---|
| W1 | `01-kernel.md` — `Line.fill` / `pad_to` absorbed / `ScreenLayout` geometry / `Pane.inner_rect` | `refactor/118-kernel` | main |
| W2 | `02-tokens.md` — the vocabulary: rename, caret split, ground tokens | `refactor/118-tokens` | W1 merged |
| W3a | `03-bands.md` — the row-band contract + golden re-record | `refactor/118-bands` | W2 merged |
| W3b | `04-delegate-markdown.md` — `Delegate` + `Markdown(max_width)` | `refactor/118-delegate` | W2 merged (parallel with W3a) |
| W4 | `05-docs.md` — DESIGN / COMPONENTS / CHANGELOG | `docs/118-surface` | W3a + W3b merged |

W3a and W3b are file-disjoint and run in parallel; every other pair is serial.

## Decisions (settled — do not re-litigate inside the tickets)

- **D0** — 1.1.8 ships the breaking changes; no shims, no deprecation cycle.
- **D1** — `ground` defaults to `NONE`; `ground_active` defaults to
  `Style(reverse=True)` written inline (the `Theme.hover` precedent). List, Tree,
  Table, Radio and CheckGroup render byte-identically at the defaults.
- **D2** — `ground_active` serves both the keyboard cursor row and the hovered row
  (today they are the same reverse band; splitting them is a token with no consumer).
  Textual's three-surface split (`$block-cursor-background` vs
  `$block-hover-background`, `ref/industry.md` §1) is documented as the growth path;
  a host that wants them different overrides at the widget (`cursor_style=` /
  `hover_style=`).
- **D3** — `Select`'s cursor row and `NavList`'s active row gain the `ground_active`
  band under their existing accent label. This is the one registered default-visual
  change; the golden diff is its evidence. `Tabs` stays out of the contract (its
  active tab is a label idiom, not a row band).
- **D4** — `Option` gains no `style` field: Textual's `Select` puts per-item richness
  in the label slot and styles the widget as a whole (`ref/industry.md` §3); a style
  on the data would bypass the resolution charter.
- **D5** — `Delegate` ships both doors: it forwards `render` / `revision` / `click` /
  `hover_at` (the urwid `AttrMap` proxy door, `ref/industry.md` §5) and implements
  `child_at` (the container door). It never proxies `handle` / `move` / `activate` /
  `focused`.
- **D6** — `Markdown(max_width=None)` clamps the wrap width (sibling of
  `divider_max_width`, `ref/industry.md` §4); it never pads.
- **D7** — `fill` merges its style *underneath* the content segments (the Rich
  `Padding(style=...)` rule — the style applies "to the padding and contents",
  `ref/industry.md` §2), while `overlay`'s colored-vs-attribute rule stays untouched
  for `find` and `Toasts`. Two rules, two purposes, both stay.

## Global invariants

1. Default renders stay byte-identical except the D3 change. The golden re-records in
   W2 (the themes showcase page) and W3a (Select/NavList rows) are the only registered
   golden moves, each reported as a diff summary naming the pages.
2. `fill`'s `NONE` fast path is byte-identical to the removed `pad_to`.
3. Every commit passes the full gate on its own — no half-changed intermediate state.
4. Mechanism in the kernel, policy above it; new capability ships no compatibility
   patch; a name that loses its last consumer is removed in the same wave.
5. Comments and docs in English (the repository's convention); commit messages in the
   repository's style: `area: one statement -- one reason`.

## The gate (every line's real output goes in the report)

    uv run pytest -q
    uv run python tools/golden.py --check
    uv run python -c "import re, subprocess, sys; done = subprocess.run([sys.executable, 'tools/framebench.py'], capture_output=True, text=True); sys.stdout.write(done.stdout); sys.stderr.write(done.stderr); raise SystemExit(0 if done.returncode == 0 and re.search(r'^render-hash  : [0-9a-f]{64}$', done.stdout, re.M) else 1)"
    uv run python -c "import subprocess, sys; raise SystemExit(subprocess.run([sys.executable, '-m', 'motui'], stdin=subprocess.DEVNULL).returncode)"
    uv run python -m motui --pages

## Git / worktree protocol

Per the spec-team skill: worktrees live outside the repository
(`~/.worktrees/mocode-tui/<branch>`), each branch is created from main at the moment
its wave starts, the lead merges every branch with `--no-ff` and runs the full gate
before and after each merge, nothing is pushed or tagged. The version bump
(`pyproject.toml` + the `__init__.py` fallback string) and the release (tag, GitHub
release) wait for the release owner's explicit instruction — this group writes the
CHANGELOG entry only.

## Reference

`ref/industry.md` — the verified industry facts this design leans on (Textual, Rich,
urwid, ratatui), with sources. The tickets cite it; do not re-research.
