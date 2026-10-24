# Spec chrome-scope · A chrome band names the region it decorates (W1)

> Status: open — 2026-10-24 21:42 (local). Baseline `main` `67f2ca9`
> (1.2.2). Branch `chrome-scope`, worktree
> `C:\Users\shifu\.worktrees\mocode-tui\chrome-scope`. Target release:
> **1.2.3** (a PATCH; the version bump and the changelog section are their
> own commit, per CONTRIBUTING "Release timing").

Complaint: in a consumer whose composer is pinned (`pin="bottom"`) into the
same pane as a transcript, the pane's scrollbar paints track and thumb over
the composer's rows too, and a left press on the composer's last column
pages the transcript. The scrollbar's *mapping* is already the scrolling
window (`ScrollState(viewport_height=len(layout.body_rows))`) while its
*extent* is the whole pane edge -- one widget, two rectangles.

## The decision

> **A chrome band decorates one rectangle of its pane; `Chrome.scope` names
> which: `"pane"` (the pane's rectangle) or `"body"` (its scrolling
> window).**

The kernel already publishes both rectangles and their vocabulary
(`Pane.rect`/`Pane.inner_rect`, `ScreenLayout.viewport_start` +
`body_rows`); it only lacked the word for "which one". This is the split
every comparable toolkit makes: a **divider** decorates the layout (pane),
a **scrollbar** decorates the scroll container (window). `motui.core.frame`
already claims the rule in `_plan_chrome`'s docstring -- "a left/right band
shares its rows with the viewport" -- and then measured that band across
the pane's whole height, pinned regions included. The band's extent
contradicted the contract's own ownership rule.

| # | Decision | Value |
|---|---|---|
| D1 | Where the distinction lives | The kernel: `Chrome` gains `scope: str = "pane"`; band geometry and `Pane.band()` -- the one derivation paint and routing share -- honour it. Not in the widget: a bar that clips its own grant would make `Pane.band()` lie. |
| D2 | Default | `"pane"` -- **byte-identical** for every existing band (the split separator, the demo, third-party chrome). Only `Scrollbar` opts into `"body"`. |
| D3 | Legal edges for `"body"` | `left`/`right` only. A top/bottom band *owns* rows and cannot share the window's; a mismatched pair raises `ValueError` at construction rather than being silently ignored. |
| D4 | Budget (width) | Unchanged, and deliberately so: chrome is charged against the pane's rectangle, so the document lays out at one width and the column a body band holds stays empty beside a fixed region. Region-scoped widths (`Viewport.layout` taking a body width and a fixed width) are **out of scope** -- see Non-goals. |
| D5 | Scope knob on `Scrollbar` | None. A bar has exactly one meaning; a host that wants a full-edge decorative rail writes its own `Chrome` (`edge`/`size`/`paint`/`scope` is the whole surface). |
| D6 | Semantics of `Pane.band()` | Still "the cells the kernel granted this band". For a body band: `band ∩ window`; `None` before the first composition and when the window has no rows. |
| D7 | `Chrome.paint(layout, length)` | `length` stays "the band's extent along the other axis": the pane's height/width for a `pane` band, the window's for a `body` band. A painter only ever paints rows it owns -- no blank-row padding, no "paint less than granted" convention. |
| D8 | Release | 1.2.3 (PATCH). CONTRIBUTING allows exactly this shape: "a PATCH may correct a default that contradicted the contract's own ownership rule; the correction is documented under Changed with its migration", and `Chrome.scope` is "a documented additive name that is the door a fix needs". |

## Contract (normative after this wave)

- `Chrome(edge, size, paint, name="", scope="pane")`; `scope` ∈
  `("pane", "body")`; `scope="body"` requires `edge` ∈ `("left", "right")`.
- A granted band's extent:
  - `scope="pane"`: the pane's rectangle edge, all its rows/columns (today).
  - `scope="body"`: the same columns, clipped to the pane's last laid-out
    window (`[viewport_start, viewport_start + len(body_rows))`).
- `Pane.band(chrome)` and the compositor's band splice are the same
  derivation, so a press test and the painted strip cannot disagree.
- `Scrollbar` registers `scope="body"`: its strip, thumb length, travel,
  drag mapping and press region all become the window's, by construction --
  no arithmetic changes in `app/scrollbar.py`.
- A pane with no window (fixed regions fill it) paints no strip and routes
  no press.
- Everything else is unchanged: no-pin panes render byte-identically, the
  separator still spans the split's full height, docks/splits/focus untouched.

## Work order

- **T1 · Kernel** -- `Chrome.scope` + `_body_band()` + `_plan_chrome` clip +
  `Pane.band()` clip. `scrollbar.py`: one constructor argument and the
  docstrings that now tell the truth.
- **T2 · Tests** -- the pinned-footer case (replacing the test that codified
  the old extent), routing over a fixed region, drag mapping through the
  window, empty window, divider + bar stacked on one edge, `band()` scope
  semantics, `Chrome` validation.
- **T3 · Docs** -- frame/scrollbar docstrings, `docs/CONTRACT.md`,
  `docs/DESIGN.md`, `docs/COMPONENTS.md`. Lands **with** T1/T2: docs move
  with the code in the same commit.
- **T4 · Release** -- version, changelog and release notes, its own commit
  once the user's go-ahead for 1.2.3 is the only thing left standing.

Read `01-W1-chrome-scope.md` for the exact edits, tests and gates.

## Non-goals

- **Region-scoped widths** ("give the fixed region its column back"):
  `Viewport.layout` would take a body width and a fixed width, `ScreenLayout`
  would stop being uniform-width, and `extract`, find, the selection overlay,
  `with_pane_rows`, `FrameTable`/`Hit.col` and the row memo would all follow.
  The payoff is one column that is already reserved today, and the blast
  radius is a kernel feature, not a patch. Recorded as a known limitation in
  `docs/DESIGN.md` with the door left open (a body-only gutter/rail need).
- **A `scope` knob on `Scrollbar`** (D5).
- **A `rows=`/`span=` region argument on `Chrome`** -- lower-level than the
  problem, and it would put "which document region" in a type that should
  only know edges.
- Touching splits, docks, `App` routing, the demo, or the golden frames.
- Publishing, tagging, or rolling T4 into the code commit.
