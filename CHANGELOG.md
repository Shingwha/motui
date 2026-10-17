# Changelog

All notable changes to this project are documented in this file.  The format
is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version
numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with
the library-specific reading spelled out in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## [Unreleased]

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

[Unreleased]: https://github.com/Shingwha/motui/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Shingwha/motui/releases/tag/v1.0.0
