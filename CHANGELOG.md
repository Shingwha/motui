# Changelog

All notable changes to this project are documented in this file.  The format
is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version
numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with
the library-specific reading spelled out in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## [1.2.1] — 2026-10-21

**Ownership and whitespace.** Two structural fixes: editable text keeps every
character, and a block's document no longer depends on the input focus.

### Fixed

- **`Input` / `Editor` preserve whitespace in their wrap geometry.** The
  fields reused the prose break rule, which drops leading, trailing and
  break whitespace; a typed space stayed in the buffer but never reached a
  rendered row, so the painter correctly emitted no bytes until the next
  visible character. `wrap_spans(..., preserve_whitespace=True)` is the
  editing rule: contiguous spans that reassemble the exact text, word-aware
  and with the same wide-cell rule. The prose path (`wrap_text`,
  `wrap_line`, Markdown, tables) is unchanged.

### Changed

- **`TUI.add` / `TUI.system` target the main document, not the focused
  pane.** With no `pane=` they land in `primary` (or the first content pane
  in paint order), so focus routes input without choosing where content is
  written; pass `pane=tui.frame.focused_pane` when a focused-pane write is
  what is meant. `TUI.split` keeps targeting the focused pane (a user
  structural action), and `TUI.reveal` now resolves the pane that holds the
  block id instead of the focused pane.

## [1.2.0] — 2026-10-21

**Convergence.** 1.2.0 is the API-convergence release: three layers
(`core`, `widgets`, `app`), an `App` that owns the default interaction
policy, one `Widget`/`Styles` seam, one scroll state and one cursor. The
Ink & Signal visual work below is part of the same release.

- **Three namespaces, one direction.** `motui.core` (values, events, input,
  document, render), `motui.widgets` (components, Markdown, syntax) and
  `motui.app` (`App`, `TUI`, controllers). The `kernel`, `keys`,
  `interaction` and `commands` namespaces are gone.
- **`App` is the high-level entry.** It mounts focus, pointer, selection,
  wheel/page routing, toasts, tooltip, find and palette, and owns the
  documented dispatch order. `TUI` remains the low-level driver;
  `TUI.read_event()` is now a pure read (no scroll/focus side effects).
- **`Widget` + `Styles`.** Every themed component inherits `Widget` and
  accepts one `styles=` value instead of per-token `*_style` parameters;
  themes resolve at render time, so changing `App.theme` does not rebuild
  mounted widgets.
- **One state, one owner.** `ScrollState` drives Viewport, ScrollView and
  Scrollbar; `Cursor` drives every list-like widget. `BlockState`/`seal`,
  `Delegate`, `Host` and the capability-protocol exports are removed.
- **`Select` is single-choice; `MultiSelect` is the marked variant.**
- **`ScrollView(bar=True)` is interactive:** thumb drag, track paging and
  wheel all reach it; `Scrollbar` stays the pane-chrome controller.
- **`Table(wrap=True)` wraps cells** instead of ellipsizing long content;
  `wrap=False` keeps the old truncation.
- `TUI.add` returns the block id, `get`/`remove` return components, and
  `TUI.dock` takes a component.
- The root is still a curated 37-name face; advanced controllers and the
  remaining widgets live in `motui.app` and `motui.widgets`.

**Ink & Signal.** The visual layer replaces the flat 1.x theme with a
palette-derived role model, moves every structural mark into one glyph
vocabulary, and ships a new dark default. Rendered output changes on
purpose; the removed styling names are deleted rather than deprecated.

### Breaking

- **The default theme is the Ink & Signal dark theme.** `DEFAULT_THEME` is
  now `Theme()` and equals `Theme.dark()`. Every component renders with the
  new surfaces, text roles and glyphs unless it receives an explicit
  `theme=` / `glyphs=`. The 1.x `reverse`/`dim` defaults are gone.
- **There is no bare `Palette`.** The command controller is now
  `CommandPalette` (`motui.CommandPalette`, `motui.app.CommandPalette`,
  module `app/command_palette.py`), and the theme authoring layer is
  `ColorPalette` (`motui.ColorPalette`, `motui.core.ColorPalette`). Rename
  the import or constructor in one pass; the old name resolves to neither.
- **`Theme` is ten role groups.** The flat 1.x fields (`accent`, `muted`,
  `dim`, `success`, `error`, `warning`, `border`, `code`, `focus`,
  `selection`, `heading`, `link`, `inline_code`, `list_marker`, `hover`,
  `caret`, `ground`, `ground_active`, `table_border`, `first_column`,
  `scrollbar`, `scrollbar_thumb`, `toast`) and the derived `headings` /
  `notice_levels` mappings are removed. Read the group field:
  `theme.content.accent`, `theme.text.muted`, `theme.text.faint`,
  `theme.surfaces.hover`, `theme.surfaces.base`, `theme.rows.active`,
  `theme.text.selection`, `theme.overlays.toast`, ... Build a variant with
  `replace(theme, group=replace(theme.group, role=...))`.
- **The `kernel.style` semantic constants are removed**: `ACCENT`,
  `BORDER`, `CODE`, `DIM`, `ERROR`, `FOCUS`, `HEADING`, `INLINE_CODE`,
  `LINK`, `LIST_MARKER`, `MUTED`, `SELECTION`, `SUCCESS`, `WARNING`. Use
  `DEFAULT_THEME.<group>.<role>` or an explicit `Style`.
- **`RowBands` / `BandedRows` are removed.** Every vertical row widget
  resolves `theme.rows.band(...)`; theme the `rows` group once. The
  `bands=` keyword is gone from `List`, `Select`, `RadioGroup`,
  `CheckboxGroup`, `Tree`, `NavList` and `Table`.
- **Per-component glyph parameters are removed**: `mark_pair=`,
  `marker=`, `more_up=`, `more_down=`, `expanded=`, `collapsed=`, `bar=`,
  `divider=`, `separator=`, `empty=`, `filled=` and `task_marks=`. Pass one
  `glyphs: Glyphs` value instead. `Divider(char=)`, `Input(prompt=)` and
  `Scrollbar(track=/thumb=)` remain as instance content overrides;
  `None` means "use the vocabulary".
- **The old `kernel.glyphs` constants are removed**: `CURSOR`,
  `MENU_CURSOR`, `RAIL_BAR`, `EXPANDED`, `COLLAPSED`, `RADIO_EMPTY`,
  `RADIO_FILLED`, `MARKED`, `UNMARKED`, `MORE_UP`, `MORE_DOWN`, `TRACK`,
  `THUMB`, `TASK_OPEN`, `TASK_DONE`. Use the `Glyphs` fields or `GLYPHS`.
- **`Notice` levels lead with glyphs, not text**: `i`, `✓`, `!`, `×`.
  `WARNING: ` and `ERROR: ` are gone; `success` is a new level.
- **Markdown task boxes use `[ ]` / `[x]`** from `Glyphs` instead of
  `☐` / `☑`.
- **Box components take a `Border` value.** `Panel(border=)`,
  `Dialog(border=)` and `Table(grid=)` accept
  `Border.square/rounded/heavy/double/ascii/none`; the old six-tuple
  `Dialog(border=)` is gone.

### Added

- **`ColorPalette`** (`motui.core`, with `DARK_PALETTE` and
  `LIGHT_PALETTE`): the 18-field brand-colour authoring layer.
- **`CommandPalette`** (`motui.app`, module
  `app/command_palette.py`): the modal query row over a filtered
  command list. It replaces the 1.x command `Palette`.
- **`Theme.dark()`, `Theme.light()`, `Theme.flat()`, `Theme.auto(env=None)`
  and `Theme.from_palette(color_palette)`**: pure constructors, no global
  state. `auto` reads `TERM_BACKGROUND`, then `COLORFGBG`, and falls back to
  dark.
- **`Color`**: pairs a truecolor `#rrggbb` / `(r, g, b)` value with an
  `ansi` anchor, so a 16-color terminal keeps the intended hue.
- **Ten role groups**: `TextStyles`, `SurfaceStyles`, `BorderStyles`,
  `ControlStyles`, `RowStyles`, `StatusStyles`, `ContentStyles`,
  `ChromeStyles`, `OverlayStyles`, `SyntaxStyles`.
- **`RowStyles.band(...)` and `ControlStyles.band(...)`**: the state
  precedence in one place.
- **`Glyphs`, `GLYPHS`, `Border`, `seat`, `seat_width` and `pair_seat`**:
  the structural vocabulary, independent of `Theme`.
- `CommandPalette`, `ColorPalette`, `Glyphs` and `Border` are public at the
  package root; `ColorPalette`, `Glyphs` and `Border` also live at
  `motui.core`, and `CommandPalette` at `motui.app`.

### Changed

- The syntax highlighter reads `theme.syntax.*`; plain code still reads
  `theme.content.code`.
- Table headers use `text.muted`; select descriptions and divider labels
  use `text.muted`; list counters use `text.muted`.
- `RadioGroup` and `CheckboxGroup` labels use `text.base`, with the mark in
  `content.accent`; `Checkbox` resolves the same way.
- `List` / `Tree` unfocused cursor rows use the `rows.inactive` surface
  instead of a dynamic dim merge.
- `Find` marks matches with `text.selection` and the current match with
  `surfaces.hover`; its query band is `overlays.toast`.
- `ScrollView`, `Scrollbar`, `ProgressBar` and `Slider` draw from
  `Glyphs.bar_*` / `slider_*`.
- The demo themes and the styling topics show `theme.rows` and the
  `Glyphs` vocabulary; all 58 golden topics are re-recorded.

### Migration

```python
from dataclasses import replace

from motui import DEFAULT_THEME, Style

# 1.x: replace(DEFAULT_THEME, accent=..., heading=...)
theme = replace(
    DEFAULT_THEME,
    content=replace(
        DEFAULT_THEME.content,
        accent=Style(fg="#ff8800"),
        headings=(Style(fg="#ff8800", underline=True),) * 6,
    ),
)

# 1.x: List(items, marker=">", mark_pair=("[x]", "[ ]"))
from motui.core.glyphs import Glyphs

List(items, glyphs=Glyphs(cursor=">", check_on="[x]", check_off="[ ]"))
```

## [1.1.9] — 2026-10-20

### Breaking

- **The band family is the host's to theme.** `Theme.hover` and
  `Theme.ground_active` default to `NONE`, with `ground` — 1.1.8's reverse
  default for the family was the wrong call and this version corrects it. The
  toolkit owns no screen of its own and assumes no background, so a default
  render paints structure and position only: a transparent terminal, a light
  terminal and a custom theme are all safe, and feedback — a resting surface,
  an engaged row, a hover band — is the host's. A host themes the three tokens
  once and every row widget follows.
- **The row widgets' pointer row reads `hover`, not `ground_active`.** `hover`
  is the pointer's signal everywhere, list rows included; `ground_active` is
  the keyboard cursor row's alone. The precedence rule is the split's other
  half: the hovered row wears `hover` whatever row it is on, and the
  **unhovered** cursor row wears `ground_active`. A host that themed only
  `ground_active` for its hover pill moves that one line to `hover`.

Both are documented clean cuts, no shim, shipped under the year-let rule
(`CONTRIBUTING.md`): the library is young, the reverse default shipped in
1.1.8 and is corrected here, and the deprecation cycle waits for a name with
real users.

### Added

- **The glyph vocabulary** — `motui.kernel.glyphs` is the one home for the
  library's structural marks: `CURSOR` / `MENU_CURSOR` / `RAIL_BAR` /
  `EXPANDED` / `COLLAPSED` / `RADIO_EMPTY` / `RADIO_FILLED` / `MARKED` /
  `UNMARKED` / `MORE_UP` / `MORE_DOWN` / `TRACK` / `THUMB` / `TASK_OPEN` /
  `TASK_DONE`, plus `seat(glyph)` (glyph + one space), `seat_width(glyph)`
  (display columns through `visible_width`, never `len`) and
  `pair_seat(glyph, other)` (a state pair padded to the wider member). Glyphs
  are content, not style: they never enter `Theme`.
- **Every carrying component takes its glyphs as constructor keywords**,
  defaulting to the vocabulary: `List(marker=, more_up=, more_down=,
  mark_pair=)`, `Select(marker=, mark_pair=)`, `NavList(bar=, bar_space=)`,
  `Tree(expanded=, collapsed=)`, `Radio(empty=, filled=)`,
  `CheckGroup(mark_pair=)`, `Table(mark_pair=)`, plus
  `Scrollbar(track=, thumb=)` and `Markdown(task_marks=)`. Each parameter is
  part of its component's `revision()`; the defaults render byte-for-byte what
  the components always did.
- **The invariant test** (`tests/test_default_theme_paints_structure.py`):
  under `DEFAULT_THEME` every covered component paints zero `bg` and no
  `reverse` outside the caret's cell and a focused control's focus band —
  "the default never surprises", pinned so the family cannot drift back.
- **The demo themes the interactive bands**: its skins set a GitHub-dark
  `ground_active` and `hover` (amber and violet in their own hues), so the
  shipped demo shows the feedback a reader needs and the pointer row reads
  visibly weaker than the cursor row, while `ground` stays `NONE` on purpose —
  a row band is not a region surface, and a page-wide one stripes every widget
  instead of composing into a background.

### Changed

- **The old module glyph constants are gone, with no aliases**: `List`'s
  `MARKER` / `MORE_UP` / `MORE_DOWN`, `Select`'s `MARKER` / `EMPTY_MARK` /
  `FILLED_MARK`, Markdown's `TODO_MARK` / `DONE_MARK` and `Scrollbar`'s
  `TRACK` / `THUMB`. The shipped defaults live in `kernel.glyphs` only, and
  the consumers import them from there in the same release.
- **An empty glyph turns its mark off and collapses the seat** — `""` seats
  nothing (no dangling space) and the component's geometry shrinks with it; a
  state pair still shares the wider member's seat, so the two states keep one
  column. On the `Scrollbar` an empty glyph paints the reserved column blank
  (the chrome budget does not move) — the closest semantics to `size=0`.

### Fixed

- **The unfocused dim merge** — an unfocused cursor row merged the theme's
  `dim` onto its band even when that band carried an explicit background,
  which dimmed the text into the surface (the demo's `List` and `Select`
  cursor rows). `dim` is a foreground attribute: it is merged only when the
  band has no explicit background (`band.bg is None`). A background band is
  its own position signal; a host that wants a weaker unfocused look themes a
  weaker colour. A `NONE` band — the default theme — still dims exactly as
  before.
- **The 1.1.9 cursor seat is removed** — the wave's two-cell seat on
  `NavList`, `Table` and `Tree` stacked another marker on rows that already
  carry their own (the rail's bar, the tree's `▾`/`▸` indicators, the grid's
  frame), so it was taken out before release. Those rows keep their pre-seat
  shapes; the existing `▸` (`List`) and `→` (`Select`) remain the family's
  markers.
- **The row band's width** — 1.1.8's reading painted the engaged band and a
  themed `ground` out to the painting width, which ribboned across the pane.
  The band hugs the row's own cells now — a pill behind the text, never a
  ribbon — and a full-surface band is the host's container's job
  (`Padding(fill_style=...)` / `Panel(frame=False, style=...)`, which fill
  every row to the width they are handed). Resting rows are unchanged, and the
  `NONE` fast path still skips the fill entirely.
- **The token semantics** — `hover` is the pointer's signal everywhere (list
  rows included), `ground_active` is the keyboard cursor row's: one token per
  signal, and the hover wins where the two meet.
- **The overview page's index table** — the 1.1.9 cursor seat had pushed the
  page's pinned width past the pane, so the group labels ellipsized; with the
  seat removed the pin returns to 57 and lands on the pane's inner budget
  again, so `FOUNDATIONS` and the descriptions read whole.

## [1.1.8] — 2026-10-19

### Breaking

- **The surface taxonomy lands — `Theme.cursor` is `Theme.focus`** (and the
  `CURSOR` constant is `FOCUS`): the token names the band a focused control
  paints, not the text caret, which is `caret`'s own block now. The
  `focus_style=` parameters and the fields' `cursor_style=` keep their names.
- **`Radio` / `CheckGroup`'s `focus_style` parameter is `selected_style`** —
  the group's engaged band is named for the row it styles, the selection
  rather than a focus ring.
- **`Line.pad_to` is removed** — absorbed into `fill`, whose `NONE` fast path
  answers byte-for-byte what it did.
- **An engaged row spans the painting width** at the default theme — the
  cursor row of `List` / `Tree` / `Table` / `Select`, the active row of
  `NavList` and the selected row of `Radio` / `CheckGroup` now paint their
  band across the row, the Textual/ratatui cursor-row norm, so a themed
  `ground` reads as a full-width surface instead of per-row patches. Resting
  rows are unchanged byte for byte while the band is `NONE`.

All four are documented clean cuts, no shim, shipped under the year-let rule
(`CONTRIBUTING.md`): the library is young, the changes are documented here,
and the deprecation cycle waits for a name with real users.

### Added

- **The surface taxonomy — one token per role.** `Theme` gains `ground` (the
  resting surface, `NONE` by default), `ground_active` (the engaged row
  surface, shared today by the keyboard cursor row and the hovered row) and
  `caret` (the text caret's own block) beside the renamed `focus` and the
  text-selection-only `selection`; the naming charter in `docs/DESIGN.md`
  names the Textual analogue of each.
- **`Line.fill(width, style)`** — the sizing family's growing member: `fit`
  trims, `fill` extends and surfaces (the style merges *underneath* the
  content, the Rich `Padding(style=...)` rule, and it never truncates), and
  `Line.filled(width, style)` builds a blank row from scratch.
- **The row-band contract** — every vertical row-carrying widget (`List`,
  `Tree`, `Table`, `NavList`, `Select` and its presets) resolves its bands
  once, at construction, through one rule: the resting surface is
  `ground_style=` or the theme's `ground`, the engaged band is
  `ground_active`, and a row is its text-styled segments then
  `fit(width).fill(width, band)` — the band underneath, the surface spanning
  the painting width, and the fill skipped while the band is `NONE`.
- **`ScreenLayout.width` / `height`** — the rectangle the rows were laid out
  in, shipped with the layout itself, so chrome and an IME anchor read the
  geometry instead of remembering it beside it.
- **`Pane.inner_rect`** — the rectangle the pane's viewport lays out in,
  chrome subtracted, beside `Pane.band(chrome)`: the frame's two public
  geometry reads.
- **`Delegate`** — the single-child identity wrapper: it forwards `render` /
  `revision` / `click` / `hover_at` (the urwid `AttrMap` door) and answers
  `child_at`, so a host that wraps a component forwards nothing by hand; it
  never proxies `handle` / `move` / `activate` / `focused`.
- **`Markdown(max_width=…)`** — the wrap-width cap, the sibling of
  `divider_max_width` and Textual's `max-width`: the rows wrap at
  `min(width, max_width)` and are never padded back up.

### Changed

- **`Theme.cursor` is `Theme.focus`** (and the `CURSOR` constant is `FOCUS`):
  the token names the band a focused control paints, not the text caret —
  which is `caret`'s own block now. The `focus_style=` parameters and the
  fields' `cursor_style=` keep their names.
- **`Select`'s cursor row and `NavList`'s active row carry the
  `ground_active` band** under their accent label, and the engaged row of
  every widget in the contract spans the painting width — the one registered
  default-visual change: a themed `ground` reads as a full-width surface,
  where a text-width band would paint per-row patches. Resting rows are
  unchanged byte for byte at the default theme, since a `NONE` band paints
  nothing.
- **The row widgets' hovered rows read `ground_active`** — the same engaged
  surface the keyboard cursor row wears, one token today; Textual's
  cursor/hover split is the recorded growth path, and a host that wants them
  different overrides at the widget (`cursor_style=` / `hover_style=`).
- **`Radio` / `CheckGroup`'s `focus_style` parameter is `selected_style`** —
  the group's engaged band is named for the row it styles, the selection
  rather than a focus ring, and the one parameter now answers for the
  selected row's label style and its band.

### Removed

- **`Line.pad_to`** — absorbed into `fill`, whose `NONE` fast path answers
  byte-for-byte what it did.

## [1.1.7] — 2026-10-19

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

[Unreleased]: https://github.com/Shingwha/motui/compare/v1.2.1...HEAD
[1.2.1]: https://github.com/Shingwha/motui/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/Shingwha/motui/compare/v1.1.9...v1.2.0
[1.1.9]: https://github.com/Shingwha/motui/compare/v1.1.8...v1.1.9
[1.1.8]: https://github.com/Shingwha/motui/compare/v1.1.7...v1.1.8
[1.1.5]: https://github.com/Shingwha/motui/compare/v1.1.0...v1.1.5
[1.1.0]: https://github.com/Shingwha/motui/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Shingwha/motui/releases/tag/v1.0.0
