# Changelog

All notable changes to this project are documented in this file.  The format
is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version
numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with
the library-specific reading spelled out in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## [Unreleased]

### Breaking

- **`motui.kernel.MORE_BELOW` is removed.** The kernel no longer paints the
  `─ more below ─` marker row: a scrolled window shows the content rows
  themselves, blank-padded below the content, so every painted row is either a
  real block row or empty fill. The marker bypassed the theme system, silently
  took a content row, duplicated the host's chrome when a `Scrollbar` was
  mounted, and was the one row whose ownership table pointed at a block the
  row did not show — scrolling feedback belongs to the host's chrome, not the
  render core. Removing it closes that hit-test mismatch structurally.

### Fixed

- **`Dialog` under a sealed block's row cache**: the snapshot now carries every
  row input `render` reads — `title`, `width`, `frame`, `shade`, `align`, the
  border tuple and the resolved bands — and the body through its own
  `revision()` when it has one, so an in-place frame change or a streamed body
  reaches the screen instead of serving stale rows.
- **Sealed-block updates in `Diff`, `Tabs`, `NavList`, `Slider`, `ProgressBar`
  and `Collapsible`**: each now implements `revision()`, so a hover, a focus
  flip, a selection or a value assignment lands on screen after the block was
  sealed — the remaining rollout of the render-cost D4 fix.
- **`Palette.detach()`**: the palette's modal overlay can be unmounted (the
  `Toasts` lifecycle, idempotent); `close()` still only hides.
- **`Find.detach()`**: a detached search tier is inert — `handle()` answers
  `False` to every key instead of continuing to consume input after unmount.
- **The gesture scroll path repaints once**: the redundant direct
  `invalidate()` beside `set_selection` is gone; one scroll extension is one
  repaint.
- **`__version__`'s source-checkout fallback** now reads the release it is cut
  from (1.1.6), pinned against `pyproject.toml` by a test.
- **Documentation**: the root facade's 34 names are complete again, the
  dangling `README.md` pointer now names the real authoritative list, three
  decision references (D2→D1, D10→D3, and a bare D10 removed) resolve to the
  specs that define them, and a test now pins "styles resolve once at
  construction".

## [1.1.6] — 2026-10-19

### Added

- **`Panel(frame=False)` and `Dialog(frame=False)` — the borderless mode**: the
  frame is decor, not structure, so the box drops and the layout stays — the
  child inset one column per side and every row still spanning the panel's
  width, the dialog's body, `align`, cursor and click mapping unchanged (the hit
  columns shift with the missing border) — and the title goes with the frame:
  there is no edge left to embed it in, so the host composes its own heading.
  A borderless `Panel` with an explicit `style` paints it as the **ground** (the
  panel's own cells fill, the ground merges *under* the child's own colors — the
  `Padding` `fill_style` rule), so an inset band needs no `Padding`/`Panel`
  swap; `confirm_dialog` / `prompt_dialog` forward the switch, and a borderless
  dangerous dialog carries its cue on the dangerous button's `error` band.

## [1.1.5] — 2026-10-18

### Breaking

This cycle's removals and incompatible changes — cut clean, documented here,
no shims (the yearly MAJOR cadence owns the slow path; see CONTRIBUTING):
the widget families moved one file each (`action.py` / `choice.py` /
`textfield.py` / `rows.py` / `indicators.py` replace thirteen modules), the
interaction tier absorbed `chrome.py` and `search.py` became `find.py`, the
root facade carries 34 names (`Dialog` / `Modal` / `NavList` joined), `Tabs`
shed its vertical mode and its reverse-video default for the indicator
vocabulary (`NavList` is the rail), `Palette` takes `tui` first, and
`Confirm` / the generated API page / the retired modules are gone.

### Added

- **`Modal` — the blocking layer, and `Dialog` — its pure component**: a modal
  scrims the composed frame, places its panel centered or anchored at a cell, routes
  every event into the panel **body-first** and dismisses on a click outside, while
  the dialog is a title edge, a body and a `ButtonSpec` button row whose `enter`
  takes the focused button's value, whose `escape` cancels and whose `danger=True`
  opens on the last non-dangerous button (a stray return never lands the destructive
  action).
- **`confirm_dialog` and the `Prompt` (`prompt_dialog`)** — the Yes/No box and the
  one-line prompt whose `Input` body lets `enter` fall through to the button row
  (the field is the payload, the modal's result says whether it was taken).
- **`ComboBox`** — the form's pick-or-type: an editable `Input` over a dropdown
  filtered by what is typed (`enter` takes the option's value into `chosen` and
  writes its label back into the field), the dropdown painted through a host-mounted
  `Modal` anchored one row under the field.
- **`CheckGroup`** — the multiple-choice group beside `Radio`, and the family's five
  knobs (`wrap` / `commit` / `multi` / `marked` / `window`) documented as the whole
  variation catalog over one `Select` base (`Autocomplete` is a preset too).
- **`Input(mask=…)` and `Editor(mask=…)`** — the display-only secret field: every
  rendered character becomes the mask's glyph while `.text` stays plain.
- **Marks on `Table` and `List`** — a public `marked: MarkSet`, a `toggle()` on the
  cursor row and the three-column `[x] `/`[ ] ` prefix while the set is non-empty (an
  empty set renders byte-for-byte what the view always did; the host routes the key).
- **`CursorWindow` and `MarkSet` (`motui.kernel`)** — the one cursor-and-window
  arithmetic the menus and `List` share, and the marked-row set with its
  `mark_prefix` glyphs.
- **The demo's `modals` page** — a danger confirm, a prompt and a plain confirm
  over the scrim — plus a marking exhibit on `views`, and the mask, the `ComboBox`
  dropdown, `CheckGroup` and `Select(commit=True)` on `forms`.
- **The demo is rebuilt around component families** — the pages regrouped to
  one per family (`overview` / `text` / `layout` / `actions` / `forms` / `views` /
  `modals` / `shell` / `themes` / `streaming` / `notes`), the exhibit grammar
  collected into `demo/kit.py` (a page's skeleton, its echo and its pick
  resolution all one implementation, with `Action` as the data a row carries and
  the session no longer knowing any page by name), the replay's hand-computed
  mouse cells replaced by symbolic anchors resolved against the live layout, and
  `NavList`'s rail given group headers (foundations / components / shell).

### Changed

- **The demo's presentation is normalized** — the rail is grouped into
  foundations / components / shell, and every page rides one template: its title
  rule, one factual line, then `── section ──` rules, the live exhibit and at
  most one caption that enumerates states and values.  The prose moved to the
  `notes` page — now the manual: how to play, the tour, the signature quick
  reference and the interaction model — and `Tabs`, the one component with no
  exhibit, joins the `layout` page, so every widget the library ships has a live
  exhibit.
- **`Palette` is a modal controller** — `Palette(tui, commands, …)` paints through a
  `Modal`, so opening it raises the scrim and a click outside dismisses it.
- **`Dialog` and `Modal` join the root facade**, which carries 34 names with
  `NavList` (`Modal` and `Palette` from `motui.interaction`, `Dialog` from
  `motui.widgets`) — the additions live in the `Breaking` note above.
- **The widget families live one file each** — `action.py` (Button / Checkbox /
  Link), `choice.py` (Option / Select / Autocomplete / Radio / CheckGroup),
  `textfield.py` (Input / Editor), `rows.py` (StatusLine / ShortcutBar / Notice) and
  `indicators.py` (ProgressBar / Slider / Spinner).
- **The demo is regrouped into page families** — the twelve pages become eleven:
  the ten component families (`overview`, `text`, `layout`, `actions`, `forms`,
  `views`, `modals`, `shell`, `themes`, `streaming`) plus the `notes` manual, all
  riding the kit's exhibit grammar (`demo/kit.py`), where a pick's *action* is data
  a page hands a component (`Action`) and the session routes it with no page's name
  in host code; the replay's hand-computed mouse cells become symbolic anchors
  (`Anchors`) resolved against a live layout, so an exhibit that moves fails the run
  by name instead of clicking a neighbour.
- **The interaction tier is every controller's home** — `interaction/{find,modal,
  overlays,palette,scrollbar}.py` beside focus, pointer and gesture, with
  `kernel/cursor.py` and `kernel/mark.py` holding the shared primitives.
- **`Tabs` is the horizontal content strip and `NavList` the vertical rail** — the
  one-class-two-semantics `Tabs(orientation=…)` splits apart with no alias: `Tabs` is
  one row of `" a │ b │ c "` whose active label wears the indicator vocabulary (the
  theme's `accent` merged with the indicator color plus the **underline** mark — an
  attribute, so the state reads with the colors off) and whose reverse-video
  `theme.selection` default is gone; the new `NavList` is the rail's own component —
  one row per item, a one-cell `▌` bar plus the label, the active item in `accent`
  over a `muted` seat, hover a band, disabled rows visible but unselectable, every
  state readable without colour.  `NavList` joins the root facade (33 → 34 names)
  and the demo's rail migrates from `Tabs(orientation="vertical")` to `NavList`.

### Removed

- **`Confirm`** — the `Select`-specialized dialog; `Dialog` / `confirm_dialog`
  replace it.
- **`motui/chrome.py`** — split into `interaction/overlays.py`,
  `interaction/scrollbar.py` and `interaction/modal.py`; `Scrollbar` / `Toasts` /
  `Tooltip` / `Stats` stay public one import deeper.
- **The retired widget modules and `interaction/search.py`** — `button.py`,
  `checkbox.py`, `link.py`, `field.py`, `input.py`, `editor.py`, `radio.py`,
  `statusline.py`, `shortcutbar.py`, `progress.py`, `spinner.py`, `slider.py` and
  the widget `palette.py`, with no shims and no aliases.
- **The generated API page** — `docs/API.md`, `tools/apidoc.py` and its drift
  test: a flat signature dump duplicates the IDE and the component catalogue while
  costing a gate per wave. The facade names stay pinned by `tests/test_api_root.py`
  and the import surface is the table in `docs/DESIGN.md`.

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

[Unreleased]: https://github.com/Shingwha/motui/compare/v1.1.5...HEAD
[1.1.5]: https://github.com/Shingwha/motui/compare/v1.1.0...v1.1.5
[1.1.0]: https://github.com/Shingwha/motui/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Shingwha/motui/releases/tag/v1.0.0
