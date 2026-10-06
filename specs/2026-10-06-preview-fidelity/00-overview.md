# Spec Group 2026-10-06-preview-fidelity · The split preview renders what it lays out

> ✅ 2026-10-06 — the group constitution; three waves, W1–W3 merged.

> Lead: the main ZCode session. Workers: one agent per work order (01–03).
> Lineage: follows `2026-10-06-frame-chrome` (closed). Conventions carry over:
> naming charter, test policy, no-lint/type tooling, worktree protocol
> (`C:\Users\shifu\.worktrees\mocode-tui\<branch>`), report format, English
> one-line imperative commits, lead merges only, no push/tags.

## Owner brief

The `/preview` split in `examples/pi_demo.py` draws wrong while a selection
gesture is in flight. The brief: find the core causes and fix them from the
structure, not with patches; keep the code simple and clear. **No new test
files and no broad test expansion** (owner instruction: 非必要不要加测试):
each wave adds at most the two focused regression tests named in its work
order, and no existing assertion may be weakened to make a change pass.

## The four reports, and what each one turned out to be

The lead verified every one against `HEAD` (`0647787`/`b1ddf5e`, the two
baseline commits) plus the numbers below. Symptoms 1–2 are already fixed by
the baseline commits; 3–5 are this group's waves. All five share one shape —
a rendering surface that did not keep a single coherent coordinate space.

| # | Report | Root cause | Status |
|---|---|---|---|
| 1 | press-drag select renders wrong; the scrollbar's blocks land beside the text; the preview's content arrives on the main screen after a copy | `splice_row` padded only *around* the window it wrote, not the window itself: a short pane row left the frame row short, and the next write into it (the selection overlay, a chrome strip) dragged the cells past it leftwards | **fixed in baseline** (`0647787`) |
| 2 | a drag whose pointer crosses the divider marks rows the user never selected | block ids are numbered per document, so a split's second child holds a `b0` exactly as the first does; the gesture let its head wander into the neighbour's document | **fixed in baseline** (`b1ddf5e`) |
| 3 | the preview is dark, and the left pane's scrollbar looks mapped onto the right pane | `_negotiate` stacks a pane's chromes in registration order, so a band registered *before* the split (the demo's scrollbar) sits **outside** the divider: the dim `░` track hugs the preview's first column, one cell between it and the divider | **W1** |
| 4 | the character width looks slightly off (a slight offset) | `visible_width` rides `wcswidth`, which joins some emoji sequences but not skin-tone + ZWJ + emoji ones: the fixture's emoji row measures **95 columns where a terminal renders 90** | **W2** |
| 5 | while the preview streams, nothing on the left responds; after it finishes, everything succeeds | `/preview` awaits the streaming inside the host's event loop, so no key is read (hence nothing re-paints) until the fixture has landed | **W3** |
| 6 | the selection highlight read as a grey wash over a whole pane | `SELECTION` was `reverse + dim`; `dim` dims the foreground a reverse paints with, and a reversed foreground is the highlight's *background* | **fixed in baseline** (`b1ddf5e`) |

## Decisions (lead, final — do not re-litigate)

- D1 **W1 is a negotiation-order rule, not a registration change.** The
  divider stacks outermost on the edge it divides, *by name*, whatever else
  is registered and whenever: kernel `Pane.split(separator=True)` and the
  driver's themed `_Separator` both get it from the one rule. The generic
  "first registered sits outermost" stays for everything else.
- D2 **W2 measures grapheme clusters, no new dependency.** `visible_width`
  stays the single source of truth and the runtime dependency stays
  `wcwidth` only: the cluster rules (ZWJ joins, variation selectors, skin
  tone modifiers, regional-indicator pairs, combining marks contribute 0)
  are expressed with the code points directly.
- D3 **W3 is demo policy over the existing task pattern.** `/preview`
  streams in a background task the way `/md` already does; the split still
  happens synchronously, so the pane appears the instant the command runs.
  The library changes not at all.
- D4 **Baseline first, waves branch from it.** `main` at `b1ddf5e` carries
  reports 1, 2 and 6; W1 and W3 branch from it in parallel (disjoint
  files), W2 runs alone after both merge, because its blast radius touches
  shared test expectations that the other two waves would collide with.

## Wave table

| Wave | Work order | Branch | Touches |
|---|---|---|---|
| W1 | 01 | `fix/w1-chrome-order` | `src/mocode_tui/core/frame.py`, `tests/test_frame.py` |
| W2 | 02 | `fix/w2-cluster-width` | `src/mocode_tui/core/text.py`, `tests/test_core_text.py`, plus the expectation files its numbers move (listed in the order) |
| W3 | 03 | `fix/w3-preview-background` | `examples/pi_demo.py` |

## Red lines

- Full suite green before and after every merge (`.venv/Scripts/python.exe -m
  pytest -q`), the real output pasted; the demo's piped replay
  (`uv run python examples/pi_demo.py < /dev/null; echo exit=$?`)
  exits 0 with a complete final screen.
- No existing assertion weakened. Where a change legitimately moves a
  pinned value, the new value is stated in the report with the reason.
- Kernel purity: no timers, no event policy, no styling opinion added to
  `core/**`. Styles still resolve through the Theme/Style charter.
- No lint/type tooling. Honest `__all__`; `import x as x` forbidden; no
  compatibility shims. No push/tags until the owner says so.
- Test ceiling: this group adds at most six test functions total (two per
  wave).

## Environment & protocol

Windows 10, Git Bash, `uv`, Python 3.12; every worker's first
command in its fresh worktree is `uv sync` (it builds that worktree's own
`.venv`), and every gate command runs through `uv run` (`uv run pytest -q`,
`uv run python examples/pi_demo.py`); worktrees under
`C:\Users\shifu\.worktrees\mocode-tui\<branch>`; lead merges
(`--no-ff`); workers never merge/push/rebase or touch the main checkout;
specs are lead-owned (a worker never edits one); blocked → report and stop.
