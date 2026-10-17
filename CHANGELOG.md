# Changelog

All notable changes to this project are documented in this file.  The format
is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version
numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with
the library-specific reading spelled out in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## [Unreleased]

## [1.1.0] — 2026-10-17

### Added

- **`Diff(numbers=True)`** — an optional line-number gutter, off by default.
- **`Revisioned` — a component declares the snapshot its rows depend on** — a
  component that implements `revision() -> object` (the protocol lives in
  `motui.kernel`, beside the other block protocols) answers everything its rows
  depend on as a value; the block-level row cache keys on it, so an open block
  whose snapshot holds re-renders nothing, and a moved snapshot — a hover, a
  streamed assignment, a keystroke — re-renders even a **sealed** block: that is
  how a sealed block's hover or state change reaches the screen.

### Changed

- **Unchanged blocks are no longer re-rendered every frame** — the row cache now
  lives on the block (`Block.rows`, keyed on the width and a revision snapshot of
  everything the component's rows depend on) and every walk shares it: the
  viewport, `reveal`, the search tier, the selection extraction and the gesture
  walk.  A repainting frame re-wraps a 3000-line open `Text` in 0.1 ms instead of
  28.2, and a 240-row `Table` in 0.1 instead of 25.6; a sealed block whose
  snapshot moved also re-renders, so sealing no longer freezes a stale frame.
- **`Markdown` re-renders only what grew** — a document that only gained text
  paints its tail block onto the remembered prefix, and a growing paragraph
  re-wraps from its first changed word, so a streaming reply costs about the same
  per frame whatever already landed (a paragraph at 1 000 lines: 36.8 → 0.6
  ms/frame).
- **Editors and fields re-wrap one line per keystroke** — the buffer remembers
  its wrap per line and its assembled rows per version, so a keystroke costs
  0.2 ms on a 3000-line buffer instead of 9.1.
- **Frames with a scrollbar no longer rebuild the screen** — unchanged rows are
  carried over as they stand, `splice_row` hands a whole-row window through, and
  the scrollbar's and the divider's strips are remembered under the state they
  read.
- **`Diff` keeps real hunks in large files** — the walk trims the common head
  and tail and splits an over-budget region at the lines both sides hold
  exactly once, instead of replacing the whole text; a region with nothing
  shared degrades to a single hunk.
- **`Diff` elision rows carry the skipped-line count** — `… N lines`.
- **`Diff` deletion rows lost their weight** — the `error` hue only, keeping
  bold reserved for `**…**`.
- **`Diff` inputs are assignment-live** — assigning `before` / `after` /
  `context` / `numbers` / `theme` rebuilds the rows instead of leaving a stale
  render behind.
- **`Diff.render(width)` caches its fitted rows per width.**

### Fixed

- **A sealed block's hover or state change now reaches the screen** — its rows
  used to come back from the width-keyed cache, so a moved hover on a sealed
  `Button` (or a table's row mark, a link's span, a task box) never repainted.

## [1.0.0] — 2026-10-17

First public release.  The toolkit ships as `motui`; it was developed as
`mocode-tui` while it was a private project, and nothing under the old name
was ever published.

### Added

- **The kernel** — `Line`/`Segment` rows and `Style`/`Theme`, the event model
  (`Key` / `Paste` / `MouseEvent`), the addressable block document, the render
  core (screen / viewport / painter), the frame model (panes, the split
  algebra, chrome and overlays) and the document-space selection kernel.
- **The component library** — `Text`, `Input`, `Editor`, `Markdown` (a
  streaming-safe rule-registry engine with GFM tables and fenced code),
  `Table`, `List`, `Tree`, `Diff`, the action primitives (`Button`,
  `Checkbox`, `Link`), the form widgets, the layout containers, `Palette`,
  `StatusLine`, `ShortcutBar`, and the zero-dependency `syntax` highlighter
  seam.
- **The interaction tiers** — `SelectionGesture` (drag to select in document
  space, OSC 52 on release), `Pointer` (hover and stationary clicks),
  `FocusRing` and `Find`.
- **The chrome tier** — `Scrollbar`, `Toasts`, `Tooltip` and the developer's
  `Stats` overlay.
- **The driver** — the alternate screen, diffed-row painting, viewport
  scrollback, pinned bands, split panes, configurable keymaps, and the
  headless helpers (`headless_tui`, `snapshot`).
- **The demo** — `python -m motui` runs an 11-page exhibit of the library,
  shipped inside the wheel and pinned frame by frame in the test suite.

[Unreleased]: https://github.com/Shingwha/motui/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Shingwha/motui/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Shingwha/motui/releases/tag/v1.0.0
