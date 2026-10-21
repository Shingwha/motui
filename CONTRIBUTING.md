# Contributing

One page of rules: how the code changes, how a change lands, and how a
release is cut. The mechanisms are in [`docs/`](docs/); this page is the
process.

## The invariants

1. **Dependency direction is one-way.** `kernel` imports nothing above
   itself; `keys` imports `kernel`; `widgets` imports `kernel` and
   `keys.keymap`; `commands` imports `widgets.choice`; `interaction` imports
   `kernel` and the `Host` protocol; `app` may import anything, and
   `testing` imports `app`/`kernel`. Never the other way round.
2. **One name, one home.** A public name lives in exactly one facade. The
   root is a curated 37-name subset (including `CommandPalette`,
   `ColorPalette`, `Glyphs` and `Border`); everything else is public one
   import deeper. `tests/test_api.py` asserts that every facade name
   resolves and that the root is a subset of the layers.
3. **One source module, one test file.** `src/motui/x/y.py` is exercised by
   `tests/test_y.py`; the component families share one test file per family.
4. **Rendering is pinned.** `tests/golden/topics/*.txt` is what a user sees,
   topic by topic, byte for byte. `tools/framebench.py`'s render hash is the
   coarse proof that a refactor moved nothing.
5. **No compatibility shims.** A renamed name is deleted with its last
   consumer: no alias, no `_deprecated` re-export, no forwarding module.
   The 1.x `RowBands`, the flat `Theme` fields and the `kernel.style` /
   `kernel.glyphs` constants were removed this way in 2.0; new code reads
   `theme.<group>.<role>` and the `Glyphs` vocabulary.
6. **Within a major series the contract is additive.** 2.x adds names,
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
kernel  ->  keys  ->  widgets  ->  commands
                               ->  interaction  ->  app
testing (/app, /kernel)
```

- `motui.kernel` is the root: rows, styles, palettes, themes, glyphs and
  borders, events, the document model, screen, viewport, painter, frame,
  selection, chrome, clipboard and the `Host` protocol. It imports the
  standard library and `wcwidth` only.
- `motui.keys` decodes bytes and carries the keymaps.
- `motui.widgets` is the component library, Markdown rules and syntax
  highlighting.
- `motui.commands` is the named-action registry; it imports only `Option`.
- `motui.interaction` is policy over a running driver. It sees `Host`, not
  `TUI`; `Find` and `CommandPalette` build their fields through
  `Host.make_input` / `Host.make_autocomplete`.
- `motui.app` is the driver and composition root.

If a change needs a new edge, stop and fix the seam instead. The two usual
answers are "put the mechanism in `kernel`" and "add a small method to
`Host`".

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

1. `render(width) -> list[Line]` that is pure and fits every row.
2. The controller verbs it answers: `handle`, `click`, `hover_at`, `move`,
   `select`, `activate`, `toggle`, and `take_result` when it has a one-shot
   result.
3. A `revision()` snapshot when it holds mutable state.
4. Tests for rendering, every verb and the protocol surfaces.
5. A catalogue entry in [`docs/COMPONENTS.md`](docs/COMPONENTS.md), in the
   fixed template (`purpose -> signature -> verbs -> result -> protocols ->
   notes`), and a demo topic if the component belongs on the tour.

If the component joins a public facade, update `tests/test_api.py` in
the same commit. If it changes what a topic renders, re-record that topic's
golden frame.

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
and PATCH releases in between only when they were already announced. Inside
2.x the public contract is **additive**: a name joins a facade, no existing
name changes meaning, and no name is removed. The one rule is that a change
must be documented, never silent.

- **MAJOR** — the yearly cut that owns the year's removals and renames.
- **MINOR** — a name joins a facade, a new component/verb, or an additive
  behavior.
- **PATCH** — a fix that changes no contract. A rendering fix that moves the
  golden frames is still a PATCH: the frame diff is the evidence.
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
