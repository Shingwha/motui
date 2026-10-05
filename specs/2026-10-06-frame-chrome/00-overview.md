# Spec Group 2026-10-06-frame-chrome · The frame model: panes, chrome, overlays

> ✅ 2026-10-06 — the group constitution; all seven waves merged.

> Lead: the main ZCode session. Workers: one agent per work order (01–06).
> Lineage: follows `2026-10-05-api-overhaul` (closed) and
> `2026-10-05-selection` (closed). Their conventions — naming charter, test
> policy, no-tooling rule, honest imports, worktree protocol, report format —
> carry over verbatim.

## Goal

One architecture for everything that claims screen space: the split screen,
the scrollbar, the right-hand rail, the transient toast. The owner's brief:
simple and clear architecture, high usability, high customizability, no
patch-style code — industry defaults where judgment calls arise.

## The design constitution: three kinds of space claims

Every feature that draws outside the document flow is exactly ONE of these,
and each has its own mechanism. Deciding which one a feature is, IS the
design step; blurring them is how patches are born.

1. **Pane** — an exclusive rectangle of the frame. Owns its own
   `Viewport`/`Document`: independent scroll, independent sealed cache,
   independent hit domain. Splits (transcript | preview) are panes. Many
   panes partition the frame; separators between them are inter-pane chrome.
2. **Chrome** — a small band INSIDE a pane's rectangle (edge columns or
   rows), acquired by budget negotiation: the chrome declares how many
   edge cells it wants, the pane lays its viewport out in what remains
   (content re-wraps at the reduced width — content is never hidden under
   chrome). Chrome renders from pane view state (offset/total) and may
   route input. A scrollbar (1 column), a line-number rail (3 columns), a
   hit-tick rail are chrome; several chromes may stack, budgets add.
3. **Overlay** — claims nothing, painted last over the composed frame.
   Toasts, the selection highlight, a jump-to-bottom chip. Pure
   `frame -> frame` transforms plus lifecycle/input that live in
   controller objects, never in the kernel.

Layering rule (unchanged from the selection group): mechanisms in the
kernel (`core`), policy in assembly modules (top-level, peer of `app.py`).
The kernel gains no timers, no event policy, no opinion about what a
scrollbar looks like.

## Decisions (lead, final — do not re-litigate)

- D1 **Waves W1–W2 are behavior-identical migrations**: the frame model and
  the chrome/overlay pipeline land with the demo dump byte-identical and
  the 65-name root untouched. Proof of equivalence is the gate.
- D2 **Scrollbar budgets columns** (reserves, never overlaps content);
  thumb geometry maps `offset/total_rows`; drag/track-click input mirrors
  `SelectionGesture` (`handle(event) -> bool`).
- D3 **Toasts are floating overlays**: TTL 4.0 s default, at most 3 shown
  (oldest evicted), optional click-to-dismiss, corner-configurable.
  `show(text_or_component, *, style=, ttl=)` — components allowed, so a
  toast can be any renderable (customizability charter).
- D4 **Splits ship in this group** (a stated need validates the abstraction
  for real): `tui.split("vertical"|"horizontal", *, ratios=(1, 1)) ->
  (Pane, Pane)` and `pane.split(...)` (same code path); separators are
  1-cell inter-pane chrome, the focused pane's side accent-colored
  (tmux convention); `pane.focus()` explicit, mouse-press-in-pane focuses
  (default policy, replaceable — the assembly tier owns it).
- D5 **Wheel routes by pointer position; keys route to the focused pane.**
  `scroll_keys` interception scrolls the pane under the pointer when a
  pane table resolves it, else the focused pane.
- D6 **Composer promotes to a frame-level bottom band in the split wave**
  (W5). Single-pane rendering must stay identical (pinned tests); the
  migration point is written here so nobody ever wedges a composer into a
  pane.
- D7 **Selection stays single-document in this group** (the focused pane);
  cross-pane ranges are a documented future extension (addresses are
  document-local already, so the door is open by construction).
- D8 **`─ more below ─` marker stays** as viewport behavior; a jump-chip
  would be an optional overlay later, not a replacement.
- D9 Root grows 65 → 68 (`Scrollbar`, `Toasts`, `Pane`), version bumps to
  **0.4.0** at W6; the demo is re-baselined ONCE at W6 (old baseline
  archived as `pi-demo-baseline-pre-chrome.txt`).

## Target shape

```
core/frame.py      Rect + split algebra (fixed/flex sizes, the Row/Column
                   vocabulary lifted to frame level) + the compositor:
                   per pane: chrome budgets -> viewport.layout(inner rect)
                   -> splice rows; frame-level ownership table
                   (pane, block, row) for hit routing; overlay pipeline
                   applied last. ScreenLayout gains offset/total_rows
                   (per pane, for chrome math).
app.py             TUI keeps every current API; internally one Frame whose
                   primary pane is tui.document/tui.viewport. hit_test
                   routes through the frame table; scroll facades route to
                   the focused pane (single pane = today's behavior).
mocode_tui/chrome.py   Scrollbar (pane chrome + gesture) and Toasts
                       (overlay + controller) — the assembly tier.
```

## Waves (serial; each builds only on landed abstractions)

| Wave | Spec | Branch | Content |
|---|---|---|---|
| W1 | 01 | `chrome/w1-frame` | frame/pane kernel, single-pane migration (byte-identical), pane-namespaced hit routing, `offset`/`total_rows` |
| W2 | 02 | `chrome/w2-pipeline` | chrome budget + overlay registry; selection highlight becomes overlay #1 (identical) |
| W3 | 03 | `chrome/w3-scrollbar` | `Scrollbar` chrome + drag/track gesture; root 66 |
| W4 | 04 | `chrome/w4-toasts` | `Toasts` overlay controller; root 67 |
| W5 | 05 | `chrome/w5-split` | `split`/`Pane`, separators, focus policy, wheel routing, Composer → frame band; root 68 |
| W6 | 06 | `chrome/w6-demo` | demo (scrollbar, copy-toast, `/preview` split), docs, 0.4.0, re-baseline |
| W7 | 07 | `chrome/w7-unsplit` | `Pane.close()` — the tiling stops being append-only; the demo's close is real |

## Red lines

- W1–W2: demo dump byte-identical; full suite green with no assertion
  weakened; root `__all__` unchanged.
- W3–W5: demo dump still byte-identical (nothing attaches chrome/overlays
  to the demo until W6); every new public name is root-pinned and
  documented in the same wave it lands.
- Kernel purity: no timers, no event policy, no styling opinion in
  `core/**`. Chrome/overlay rendering styles resolve via the Theme/Style
  charter (explicit > theme > DEFAULT).
- Test policy carried over (no private-underscore assertions beyond the
  `_clock` seam, no default-color pins, parametrized matrices, `_doubles`
  shared). Group ceiling — **revised twice, final: ≤ 545 test functions,
  ≤ 9,000 test lines**. First revision after W1 (structural identity pins);
  final revision after W7 (the group grew a genuinely new kernel surface —
  frame/chrome/split/close — and its tests are policy-clean; the quality
  policy, not the number, is the binding constraint). Landed: 537
  functions / 8,822 lines.
- No lint/type tooling. Honest `__all__`; `import x as x` forbidden.
  No compatibility shims. No push/tags until the owner says so.

## Environment & protocol

Unchanged: Windows 10, Git Bash, `uv`, Python 3.12; worktrees under
`C:\Users\shifu\.worktrees\mocode-tui\<branch>`; lead merges; workers never
merge/push/rebase; specs lead-owned; English one-line imperative commits;
report format: task table, commits, true gate outputs, deviations, open
questions; blocked → report and stop.
