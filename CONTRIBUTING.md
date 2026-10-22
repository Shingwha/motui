# Contributing

One page of rules: how the code changes, how a change lands, and how a
release is cut. The mechanisms are in [`docs/`](docs/); this page is the
process.

## The invariants

1. **Dependency direction is one-way.** `core` imports nothing above
   itself; `widgets` imports `core`; `app` imports `core` and `widgets`;
   `testing` imports `app` and `core`. Never the other way round. There is
   no `kernel`, `keys`, `interaction` or `commands` namespace.
2. **One name, one home.** A public name lives in exactly one facade. The
   root is a curated 41-name subset (including `App`, `CommandPalette`,
   `ColorPalette`, `Glyphs`, `Border`, `ScrollView`, `Row`, `Column` and
   `Panel`); everything else is public one
   import deeper. `tests/test_api.py` asserts that every facade name
   resolves and that the root is a subset of the layers.
3. **One source module, one test file.** `src/motui/x/y.py` is exercised by
   `tests/test_y.py`; the component families share one test file per family.
4. **Rendering is pinned.** `tests/golden/topics/*.txt` is what a user sees,
   topic by topic, byte for byte. `tools/framebench.py`'s render hash is the
   coarse proof that a refactor moved nothing.
5. **No compatibility shims.** A renamed name is deleted with its last
   consumer: no alias, no `_deprecated` re-export, no forwarding module.
   The 1.x `RowBands`, the flat `Theme` fields, the `kernel.style` /
   `kernel.glyphs` constants, `BlockState`/`seal`, `Delegate`, `Host` and
   the old namespaces were removed this way in 1.2.0; new code reads
   `theme.<group>.<role>`, `styles: Styles`, and the `Glyphs` vocabulary.
6. **Within 1.2.x the contract is additive.** A release adds names,
   components and verbs; it does not rename or re-purpose an existing one.
   A removal is a MAJOR decision.
7. **The library never sleeps.** Time enters through `tui.clock()`, which a
   test injects.
8. **A public-surface change is a decision, not an accident.** The pinned
   surface is the API test plus the golden frames; moving either is a
   versioning call.
9. **Docs move with the code**, in the same commit.

## The dependency graph

```
core  ->  widgets  ->  app
testing (above app and core)
```

- `motui.core` is the root: values, styles, palettes, themes, glyphs and
  borders, events, the document model, screen, viewport, painter, frame,
  selection, chrome, clipboard, the decoder/keymaps/key sources, `Widget`,
  `ScrollState`, `Cursor` and `Hit`. It imports the standard library and
  `wcwidth` only.
- `motui.widgets` is the component library, Markdown rules and syntax
  highlighting. It imports `core`.
- `motui.app` is the driver and composition root: `App`, `TUI`, focus,
  pointer, gesture, find, modal, palette, overlays, scrollbar and the
  command registry. It imports `core` and `widgets`.
- `motui.testing` sits above both: headless screens, scripted sources,
  `headless_tui` and `snapshot`.

If a change needs a new edge, stop and fix the seam instead. The two usual
answers are "put the mechanism in `core`" and "compose it in `app`".

## Gates

Every commit passes all of these:

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

What each protects:

| Gate | Protects |
|---|---|
| `pytest` | behavior, the API pin and the import graph |
| `golden.py --check` | the rendered topic frames users see |
| `framebench.py` | timing workloads and the render hash |
| the two piped demo entries | the demo's headless replay and page dump |

CI runs the same set on Linux and Windows with the oldest supported Python.

Use `-p no:cacheprovider` in parallel work: several agents must not share
one `.pytest_cache`.

## Changing the code

`main` is always releasable. Every change lands on a short-lived branch and
is merged with `--no-ff`; there is no `develop` branch and no long-lived
branch.

Larger work is planned as a spec group under `specs/<date>-<slug>/`: an
overview plus one ticket per wave. Waves are executed and merged in order.
Small fixes skip that: a branch and a commit are enough.

The definition of done for a behavior change:

- tests for the behavior, in the same commit;
- its documentation updated in the same commit;
- if it moves what a user sees, re-record the golden frames with
  `tools/golden.py --update` and explain every changed frame in the commit
  message;
- if it touches a facade, make a version decision first.

**Interactive paths need tests that reach them.** A headless session with
scripted events runs the same handlers a live session runs. A behavior that
only ever runs on a real terminal is invisible to the suite.

**Don't hand-edit the golden frames**, don't rewrite `specs/` (it is an
add-only process archive), and don't commit local tool directories.

## Adding a component

Five things, in one commit:

1. `render(width) -> list[Line]` that is pure and fits every row. If the
   component is themed and interactive, inherit `Widget` and accept
   `theme=None, styles=None`; if it is a pure renderer, `Component`'s one
   method is enough.
2. The verbs it answers: `handle`, `click`, `drag`, `hover_at`, `move`,
   `select`, `activate`, `toggle`, and `take_result` when it has a one-shot
   result. `Widget` already supplies all of them as no-ops.
3. A `revision()` snapshot when it holds mutable state, and `theme` /
   `styles` included in that snapshot.
4. Tests for rendering, every verb and the protocol surfaces. A widget with
   no `*_style` constructor arguments and no `focused=` flag: assign the
   shared flags and override role groups with `Styles`.
5. A catalogue entry in [`docs/COMPONENTS.md`](docs/COMPONENTS.md), in the
   fixed template (`purpose -> signature -> verbs -> result -> protocols ->
   notes`), and a demo topic if the component belongs on the tour.

If the component joins a public facade, update the facade `__all__`; the
API test pins the structure, not a name list. If it changes what a topic
renders, re-record that topic's golden frame.

## Adding a demo topic

The demo is a master-detail explorer, not a gallery. A topic is one
`Topic` value registered in `src/motui/demo/registry.py` and one entry in a
`topics/*.py` module. Keep the template:

- a title, one summary line, a `Divider`, a live preview panel;
- optional variants and one extra block;
- at most one `Try:` line and one `API:` line;
- no more than eight blocks.

Then:

```bash
uv run python tools/golden.py --update   # records tests/golden/topics/<section>--<topic>.txt
uv run python -m motui --pages           # review the plain-text dump
```

Do not invent a second rendering path: `--pages`, the golden tool and the
tests share `render_topic`.

## Versioning

SemVer, with a deliberately slow MAJOR cadence: a MAJOR release lands about
once a year, so the removals and contract changes of the year ride the MINOR
and PATCH releases in between only when they were already announced. The
current release is **1.2.2**. Inside the 1.2.x line the public contract is
**additive**: a name joins a facade, no existing name changes meaning, and
no name is removed. The one rule is that a change must be documented, never
silent. A PATCH may correct a default that contradicted the contract's own
ownership rule; the correction is documented under Changed with its
migration.

- **MAJOR** — the yearly cut that owns the year's removals and renames.
- **MINOR** — a name joins a facade, a new component/verb, or an additive
  behavior.
- **PATCH** — a fix that changes no contract. A rendering fix that moves the
  golden frames is still a PATCH: the frame diff is the evidence. So is a
  documented additive name that is the door a fix needs
  (`Document.mutation` and `Block.rows_view`/`row_count` rode 1.2.2 with
  the frame-cost and security work they serve); a name that is not such a
  door waits for a MINOR.
- Prereleases are allowed and publish through the same workflow.

A name with real users gets a deprecation cycle first: one release that
keeps it working with a `DeprecationWarning` naming the replacement and the
removal version, then the next yearly MAJOR removes it. Machinery for names
nobody uses is not worth writing.

**Release timing.** Documentation and code may land continuously, but a
release is a single bundle: version bump, changelog section, release notes,
annotated tag and GitHub release. The release itself waits for the user's
test refactor to land and for a separate go-ahead; do not bump
`pyproject.toml`, write release notes, tag or publish as part of a docs or
feature change.

## Releasing

When the go-ahead comes:

1. On `main`, every gate green, and CI green on the commit to tag.
2. Bump `version` in `pyproject.toml`; `motui.__version__` reads the
   installed metadata and `tests/test_packaging.py` pins them equal.
3. Move the `Unreleased` material in `CHANGELOG.md` into a dated section.
4. Write the release notes to `docs/releases/<version>.md`.
5. Commit the bundle, push, wait for green CI.
6. Create an **annotated** tag and push it. `release.yml` builds on both
   platforms and publishes through PyPI trusted publishing.
7. Create the GitHub release from the notes file.
8. Verify the tag, the uploaded files and a scratch install:
   `uv run --no-project --with "motui==<version>" python -m motui --pages`.

A published version can never be re-uploaded. A broken release is yanked
and fixed in a PATCH; the tag stays where it is.
