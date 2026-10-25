# Contributing

One page of rules: how the code changes, how a change lands, and how a
release is cut. The mechanisms are in [`docs/`](docs/); this page is the
process.

## The invariants

1. **Dependency direction is one-way.** `motui.kernel` imports nothing
   above itself; `motui.widgets` imports the kernel; `motui.terminal`
   imports the kernel; `motui.app` composes the kernel, widgets and the
   terminal; `motui.testing` sits outside both. Never the other way round.
2. **One name, one home.** A public name lives in exactly one facade. The
   root is a curated 40-name subset; everything else is public one import
   deeper. `tests/test_api.py` asserts that every facade name resolves and
   that the root is a subset of the layers.
3. **One source module, one test file.** `src/motui/x/y.py` is exercised by
   the matching test module; a component family shares one test file.
4. **Rendering is pinned.** `tests/golden/semantic/` is the primary cell
   grid contract; `tests/golden/topics/*.txt` is an additional byte-level
   regression gate. `tools/framebench.py`'s render hash is the coarse proof
   that a refactor moved nothing.
5. **No compatibility shims.** A renamed name is deleted with its last
   consumer: no alias, no `_deprecated` re-export, no forwarding module.
   The small documented string entries in `MIGRATION.md` are the exception,
   and they are temporary.
6. **Within 2.x the contract is additive.** A release adds names,
   components and hooks; it does not rename or re-purpose an existing one.
   A removal is a MAJOR decision.
7. **The library never sleeps.** Time enters through `Runtime.clock()`,
   which a test injects; `Runtime.advance(dt)` replays it.
8. **A public-surface change is a decision, not an accident.** The pinned
   surface (`tools/api-2.0.txt`) plus the golden frames are the gate.
9. **Docs move with the code**, in the same commit.

## The directory

```
src/motui/
  __init__.py       curated root facade (40 names)
  kernel/           pure values and protocols: geom, cell, text, events,
                    document, layout, frame, hit, overlay, selection,
                    style, theme, glyphs, keymap
  terminal/         Screen ABC, Terminal/TerminalOptions, decoder, key
                    sources, capability, clipboard, Painter, SGR render,
                    private ansi
  widgets/          the component library (46 names) and Widget/Container
  app/              Runtime, Workspace, App, focus/pointer/gesture/find/
                    modal/palette/overlays/scrollbar/commands
  testing/          headless_tui, ScriptedEvents, snapshot, Emulator
  demo/             python -m motui; the golden frames render from it
tests/
  kernel/ widgets/ app/ terminal/   behavior and contract tests
  golden/semantic/                 cell-grid snapshots per topic
  golden/topics/                   byte-level snapshots per topic
  testing/                         clocks, doubles, events, layout helpers
tools/
  golden.py semantic.py            the frame gates
  framebench.py                    nine timing workloads and render hash
  api.py growth.py                 public surface and growth probe
docs/                              ARCHITECTURE, CONTRACT, WIDGETS, MIGRATION, adr/
```

The dependency graph is:

```
kernel  <-  widgets  <-  app
kernel  <-  terminal <-  app
testing (above app, terminal and kernel)
```

`import-linter` enforces the four structural contracts in
`pyproject.toml`: the kernel has no I/O, the kernel is a leaf, widgets do
not import terminal/app, and terminal does not import widgets/app. If a
change needs a new edge, stop and fix the seam instead.

## Gates

Every commit passes all of these:

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/semantic.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
uv run ruff check .
uv run pyright
uv run lint-imports
uv run python tools/api.py --check
uv run python tools/growth.py
uv run python examples/snake.py --headless
uv run python examples/dashboard.py --headless
uv run python examples/wide_table.py --headless
```

What each protects:

| Gate | Protects |
|---|---|
| `pytest` | behavior, the API pin, the import graph and packaging |
| `golden.py --check` | the byte-level topic frames (an extra gate) |
| `semantic.py --check` | the cell grid users actually see |
| `framebench.py` | timing workloads and the render hash |
| the two piped demo entries | headless replay and the plain-text page dump |
| `ruff` / `pyright` | style, imports and types |
| `lint-imports` | the four layering contracts |
| `api.py --check` | every exported name and signature |
| `growth.py` | a defaulted kernel field is a non-breaking change |
| the example scripts | the shipped assembly paths run without a TTY |

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
  `tools/semantic.py --update` (and `tools/golden.py --update` for the byte
  set) and explain every changed frame in the commit message;
- if it touches a facade, make a version decision first and update
  `tools/api-2.0.txt` with `tools/api.py --update`.

**Interactive paths need tests that reach them.** A headless session with
scripted events runs the same handlers a live session runs. A behavior that
only ever runs on a real terminal is invisible to the suite.

**Do not hand-edit golden frames**, do not rewrite `specs/` (it is an
add-only process archive), and do not commit local tool directories.

## Commit style

One logical change per commit. The subject is
`area: imperative lowercase phrase`; the body explains why and names any
golden or API snapshot change.

```
kernel: a wrap mode names how a row meets its width
widgets: scroll panel windows columns and rows
docs: architecture, contract and widgets describe the 2.0 tree
release: the package is 2.0.0
```

## Adding a component

Five things, in one commit:

1. `render(c: Constraints) -> Surface`, pure and fitting every row. If the
   component is interactive, inherit `Widget` and accept `theme=None,
   styles=None`; a pure renderer needs only the one method.
2. The capability flags it honors (`focusable`, `clickable`, `hoverable`,
   `activatable`) and the typed hooks it overrides (`on_key`, `on_click`,
   `on_action`, ...). `Widget` supplies all hooks as no-ops.
3. A `revision()` snapshot when it holds mutable state, including `theme`
   and `styles` when those change its rows.
4. Tests for rendering, every hook and the capability surface. Do not add
   per-token `*_style` constructor arguments or a `focused=` flag; assign
   the shared flags and override role groups with `Styles`.
5. A catalogue entry in [`docs/WIDGETS.md`](docs/WIDGETS.md) and, if the
   component belongs on the tour, a demo topic.

If the component joins a public facade, update the facade `__all__` and the
API snapshot. If it changes what a topic renders, re-record that topic's
golden frames.

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
uv run python tools/golden.py --update      # byte topics
uv run python tools/semantic.py --update    # semantic snapshots
uv run python -m motui --pages              # review the plain-text dump
```

Do not invent a second rendering path: `--pages`, the golden tools and the
tests share the same topic renderer.

## Versioning

SemVer, with a deliberately slow MAJOR cadence. The current release is
**2.0.0**. The 2.0 break is documented name by name in
[`docs/MIGRATION.md`](docs/MIGRATION.md); no compatibility aliases are
provided beyond the small entries that page lists.

Inside 2.x the public contract is **additive**: a name joins a facade, no
existing name changes meaning, and no name is removed without a MAJOR. A
new kernel field must be keyword-only with a default; `tools/growth.py`
proves that pattern.

- **MAJOR** — the yearly cut that owns the year's removals and renames.
- **MINOR** — a name joins a facade, a new component/hook, or an additive
  behavior.
- **PATCH** — a fix that changes no contract. A rendering fix that moves a
  golden frame is still a PATCH; the frame diff is the evidence.
- Prereleases are allowed and publish through the same workflow.

## Releasing

The release is a single bundle and waits for an explicit go-ahead:

1. On `main`, every gate green, and CI green on the commit to tag.
2. Confirm `version` in `pyproject.toml`, the `motui.__version__` fallback
   and `uv.lock` agree; `tests/test_packaging.py` pins the relation.
3. Move the changelog material into the dated `## [<version>]` section.
4. Write the release notes to `docs/releases/<version>.md`.
5. Commit the bundle, push, wait for green CI.
6. Create an **annotated** tag and push it. `release.yml` builds on both
   platforms and publishes through PyPI trusted publishing.
7. Create the GitHub release from the notes file.
8. Verify the tag, the uploaded files and a scratch install:
   `uv run --no-project --with "motui==<version>" python -m motui --pages`.

A published version can never be re-uploaded. A broken release is yanked
and fixed in a PATCH; the tag stays where it is.
