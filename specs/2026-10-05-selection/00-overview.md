# Spec Group 2026-10-05-selection · Document-space selection & copy

> Lead: the main ZCode session. Workers: one agent per work order (01–05).
> Lineage: follows `2026-10-05-api-overhaul` (merged W1–W3b; W4 docs merged;
> W5 test-trim merges before this group dispatches). All its conventions —
> naming charter, test policy, no-tooling rule, honest imports, worktree
> protocol — carry over verbatim and are restated here where binding.

## Goal

Mouse text selection over the block document, with drag-to-edge auto-scroll
across pages, and copy on selection end (OSC 52). The feature exists because
enabling SGR 1006 mouse reporting takes the terminal's native selection away
— the application must own selection and copy from that moment on.

## Design rationale (the decisions every wave must uphold)

**D1 — Selection lives in document space, not screen space.**
A selection is a range of `(block_id, row_in_block, col)` addresses. Screen
rows shift when scrolling; document addresses do not. This single decision
buys the feature's headline behaviors: select → scroll → the highlight is
still where the text is; copy extracts the **full** selected range even for
parts scrolled out of view (something a real terminal cannot do — we own the
document model). It also makes drag-to-edge auto-scroll pure arithmetic
(D4). Rejected alternative: screen-space (row, col) ranges — they break on
every scroll, forcing selection tracking into the scroll path.

**D2 — Selection is an overlay, not content.**
Components stay pure `render(width) -> list[Line]` and know nothing about
selection. The highlight is a pure function applied to the **laid-out**
frame at the composition root: `painter.paint(highlight(viewport.layout(…),
selection))`. Consequences that matter:
- the sealed-row cache stays pristine (the overlay runs after the cache
  read; selection changes never thrash it);
- the painter's per-row diff gives incremental repaint for free;
- `snapshot()`/headless tests see the highlight, so gestures are testable
  without a terminal;
- the same overlay shape is the future home of search highlighting and
  URL hot-zones (the "one gate for a family of features" argument).

**D3 — Mechanism in the kernel, policy in an assembly controller.**
The three-tier shape the toolkit already uses (kernel / driver facade /
controller, cf. Viewport / TUI / Composer):

| Tier | Home | Contents | Character |
|---|---|---|---|
| mechanism | `core/selection.py`, `core/ansi.py`, `core/screen.py` | the `Selection` model, the `highlight` overlay, `extract`, the OSC 52 primitive `Screen.copy` | pure, timeless, side-effect-free |
| driver facade | `app.py` | `tui.selection` (read) + `tui.set_selection(...)` (write + invalidate) | minimal imperative surface |
| policy | top-level `mocode_tui/selection.py` | `SelectionGesture` (press/drag/release/auto-scroll/double-click) + `copy_on_select` default action | every behavior swappable |

The kernel gets **no timers, no event policy, no clipboard opinion**.
Auto-copy-on-release is a default *function argument*, never a kernel `if`.

**D4 — A stationary pointer emits no events; auto-scroll is time-driven.**
Mode 1002 reports motion only on cell changes. Holding at the bottom edge
therefore runs on the pump's existing `every(seconds, fn)` handles (the
Composer-spinner pattern). Each tick advances the selection head **in
document space** (`head_row += n`) — never by re-`hit_test`ing, which would
read the previous frame's ownership table and form a latency feedback loop.
Scrolling `n` rows shifts content under a fixed screen row by exactly `n`
document rows; that identity is the whole mechanism.

**D5 — The edge zone is the scrolling region's border, not the screen's.**
The pinned footer (composer) rows are not scrollable content; dragging into
them must not scroll. The boundary comes from `ScreenLayout.viewport_rows`.

**D6 — Copy is best-effort OSC 52; the hook is the contract.**
`Screen.copy(text) -> bool` emits `\x1b]52;c;<base64>\x07` on live screens
only. Terminal support varies (and some terminals refuse app clipboard
writes by policy), so the real contract is the gesture's `on_end` hook —
`copy_on_select` is the shipped default (extract + `Screen.copy`), a
3-line replacement for hosts with stronger needs.

**D7 — Two kinds of selection, one vocabulary, two mechanisms.**
Document-level selection (this group) is a viewport overlay over read-only
content. Intra-component selection (selecting text inside `Input`/`Editor`)
is `TextBuffer` state rendered by the component itself. They share the
`SELECTION` style constant and the coordinate vocabulary — never the
mechanism. Writing this boundary down now is what prevents the future
"shove editor selection into the overlay" patch.

**D8 — Documented v1 semantics for the hard edges.**
- Width change (reflow) clears the selection: column addresses no longer
  point at the same glyphs; char-offset anchoring is rejected because
  markdown renders non-1:1 with source.
- Selection over `OPEN` (streaming) blocks addresses *cells*, not content
  identity — if the block mutates underneath, the highlight lands on
  whatever is at those addresses now (terminal-grid semantics).
- Addresses whose block was removed resolve to nothing at overlay/extract
  time (the `hit_test` precedent: defensive `None`/skip, never an error).
- One selection range (anchor…head); the model may hold spans internally,
  the v1 API exposes a single range. Empty press-release at one cell clears
  the selection and does **not** touch the clipboard.

## API surface (binding)

```
# kernel (down-listed paths, exported from the core facade)
from mocode_tui.core.selection import Selection, highlight, extract
Selection.between(anchor, head) -> Selection      # anchors are (block_id, row, col)
highlight(layout, selection) -> ScreenLayout      # pure overlay, merges SELECTION
extract(document, selection) -> str               # full range, off-screen included

# driver
tui.selection            # Selection | None (read)
tui.set_selection(sel)   # write + invalidate; None clears

# assembly (root-public)
from mocode_tui import SelectionGesture, copy_on_select
SelectionGesture(tui, on_end=copy_on_select, scroll_rows=2,
                 scroll_tick=0.05, double_click_seconds=0.35)
gesture.handle(event) -> bool      # the established consume-a-key contract
gesture.detach()

# screen primitive
screen.copy(text) -> bool         # OSC 52; False on non-live
MouseEvent.kind                    # "press" | "release" | "motion"
```

Root grows 63 → 65 (`SelectionGesture`, `copy_on_select`); the core facade
gains `Selection`, `highlight`, `extract`. `TUI` never attaches the gesture
itself — hosts opt in with one explicit line (the `Composer.attach`
philosophy: the driver decides nothing about interaction policy).

## Out of scope (deliberate, documented)

Horizontal wheel; multi-range selections; char-offset anchors surviving
reflow; `Viewport.scroll_to(block, row)` (natural follow-on, separate
group); `/quote`-into-composer as shipped chat API (ships as a documented
extension example instead); auto-scroll acceleration ramp (the
`scroll_rows`/`scroll_tick` knobs are the seam); triple-click line select.

## Waves

| Wave | Spec | Branch | Content |
|---|---|---|---|
| W1 | 01 | `selection/w1-mouse-events` | decoder release/motion + `kind`, mode 1002, Windows console path |
| W2 | 02 | `selection/w2-kernel` | `core/selection.py` model + overlay + extract, `Screen.copy` OSC 52 |
| W3 | 03 | `selection/w3-driver` | `tui.selection` facade + overlay at the composition root |
| W4 | 04 | `selection/w4-gesture` | `SelectionGesture` + `copy_on_select` + auto-scroll + double-click |
| W5 | 05 | `selection/w5-docs` | README/DESIGN/COMPONENTS + the extension cookbook |

Serial (W1 and W2 both touch `core/screen.py`'s neighborhood; the rest
build upward). Branches cut from merge-time latest main.

## Global invariants & red lines

- The kernel (`core/`, `keys/` semantics) gains no timers, no event loop,
  no clipboard policy, no selection *behavior* — only the D3 mechanisms.
- The piped demo dump stays byte-identical to
  `specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt` for waves W1–W4
  (the demo is untouched; the headless path is non-live so OSC 52 and the
  new tracking modes never reach its output). W5 may not change it either.
- Test policy (carried from the overhaul group): no private-underscore
  assertions (sole exemption `TUI._clock`/`_tick`), no default-color pins,
  round-trip style injection, parametrized matrices, `_doubles.py` shared.
  The autoscroll chain is tested through the `_clock` seam headlessly.
- No lint/type/format tooling. Honest imports; `__all__`-listed re-exports;
  the `import x as x` idiom stays forbidden.
- Decoder growth stays structured (report-class dispatch or documented
  branch table) — the mouse decoder was flagged as an accretion point once
  already; this group must not re-grow it as an if-ladder.
- Every commit passes the gate; zero diff outside the wave's write scope;
  no compatibility shims; no push, no tags, no version bump (stays 0.3.0).

## Environment facts & protocol

Unchanged from the overhaul group: Windows 10, Git Bash, `uv`, Python 3.12;
worktrees under `C:\Users\shifu\.worktrees\mocode-tui\<branch>`; the lead
creates/merges/destroys them; workers never merge/push/rebase; specs are
lead-owned; commits in English, one line, imperative. Report format:
task-status table, commit list, true gate outputs, deviations, open
questions. Blocked → report and stop.
