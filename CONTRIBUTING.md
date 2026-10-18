# Contributing

One page of rules: how the code changes, and how releases are cut. The
mechanisms themselves — the render core, the frame model, the selection
kernel — are documented in [`docs/`](docs/).

## The invariants

1. **Dependency direction is one-way.** `kernel` imports nothing above
   itself; `keys` imports `kernel`; `widgets` imports `kernel` (and
   `keys.keymap`); `interaction`, `app` and `testing` sit above and
   may import any of them. Never the other way round.
2. **One name, one home.** A public name lives in exactly one facade. The
   root is a curated subset — 34 names — and the rest are one import deeper.
   `tests/test_api_root.py` pins every facade name by name.
3. **One source module, one test file.** `src/motui/x/y.py` is exercised by
   `tests/test_y.py` (the component groups share a file per family).
4. **Rendering is pinned.** `tests/golden/pages/*.txt` is what a user sees,
   page by page, byte for byte; framebench's `render-hash` is the coarse proof
   that a refactor moved nothing.
5. **No compatibility shims.** A renamed name is deleted with its last
   consumer — no alias, no `_deprecated` re-export, no forwarding module.
6. **The library never sleeps.** Time enters through the pump's clock seam
   (`tui.clock()`), which a test injects.
7. **A public-surface change is a decision, not an accident.** The pinned
   surface is the API test plus the golden frames; moving either is a
   versioning call (below).
8. **Docs move with the code**, in the same commit.

## Changing the code

`main` is always releasable. Every change lands on a short-lived branch and
is merged with `--no-ff`; there is no `develop` branch and no long-lived
branch at all.

**Larger work is planned as a spec group**: `specs/<date>-<slug>/` holds an
overview plus one ticket per wave, and the waves are executed and merged in
order. Small fixes skip that — a branch and a commit are enough.

**Every commit passes the gates.** This is the rule that breaks first: a
commit that rewrites the demo's shell but re-records the frames in the *next*
commit leaves a red commit behind. Fold the re-record in.

The gates, and what each one protects:

```bash
uv run pytest -q                                 # the suite
uv run python tools/golden.py --check            # what a user sees, page by page
uv run python tools/framebench.py                # the render hash + the timing workloads
uv run python -m motui < /dev/null               # the demo's piped replay
uv run python -m motui --pages                   # the demo's page dump
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs all of them
on Ubuntu and Windows, on the oldest supported Python (3.12).

The definition of done for a behavior change:

- tests for the behavior, in the same commit;
- its documentation updated in the same commit;
- if it moves what a user sees: `tools/golden.py --update`, with every changed
  frame explained in the commit message;
- if it touches a facade: a version decision (below).

**Interactive paths need tests that reach them.** `TUI(screen=HeadlessScreen(...),
interactive=True)` runs the same handlers a live session runs, with scripted
events — a page's `note`, a control-bar verb, the alternate-screen entry. A
behavior that only ever runs on a real terminal is invisible to the suite:
three shipped bugs (a blank first frame, a crashing stream verb, a control
that did nothing) all came from exactly that gap.

**Adding a component** means five things: `render(width) -> list[Line]`, the
controller verbs it answers (`handle`, `click`, `move`, `activate`,
`select`), its tests, its line in the `docs/COMPONENTS.md` catalogue, and an
exhibit in the demo — its own page or a spot on an existing one.

## Versioning

SemVer, on a deliberately slow MAJOR cadence: **a MAJOR release lands about
once a year**, so the removals and contract changes of the year ride the MINOR
and PATCH releases in between — marked in the CHANGELOG (a ``**Breaking**`` tag
on the entry) and held to one rule: the change must be documented, never
silent. While the library is young and has no users to migrate, the removals
are clean cuts (no shims, below); once there are real users, the deprecation
cycle below carries the warning. Read through the pinned surface:

- **MAJOR** — the yearly cut: the release that owns the year's removals. A
  name leaves the *published* surface here unless a MINOR/PATCH of the year
  already carried it as a documented breaking change.
- **MINOR** — a name joins a facade, a new component / switch / verb, or an
  additive behavior; a documented breaking change of the year-let may ship
  here too.
- **PATCH** — a fix that changes no contract; a documented breaking change
  already announced for the cycle may ride here when the change is small and
  the CHANGELOG says so.  A rendering *fix* that moves the golden frames is
  still a PATCH: the frame diff is the evidence of the fix.
- Prereleases (`1.1.0rc1`) are allowed and publish through the same workflow.

**Deprecation, on demand.** Removal used to wait for the yearly MAJOR; that is
what the slow cadence is for. A name that has real users — an issue, a
downstream report — gets a deprecation cycle first: a release that keeps it
working while warning (`DeprecationWarning`, naming the replacement and the
removal version), then the next yearly MAJOR that removes it.
Machinery for names nobody uses is not worth writing.

## Releasing

A release is **one bundle**: the version bump, the changelog section, the
notes file, the annotated tag and the GitHub release, each one visible and
reviewable (the 1.1.5 release is the worked example: commit `5115653`, tag
`v1.1.5`, [`docs/releases/1.1.5.md`](docs/releases/1.1.5.md)).  The tag push
is the only publish button; the GitHub release is where its notes live.

1. On `main`, every gate green, and CI green on the commit you are about to
   tag (`gh run list --limit 5`).
2. Bump `version` in `pyproject.toml` — the single source of truth.
   `motui.__version__` reads the installed metadata and a test pins the two
   equal (`tests/test_packaging.py`), so a half-done bump fails the suite.
3. Move the `## [Unreleased]` material in [`CHANGELOG.md`](CHANGELOG.md) into a
   new dated section for the version — a `### Breaking` note on top when the
   cycle carries removals or incompatible changes; the `Unreleased` header
   stays as the next cycle's bucket.
4. Write the release notes to `docs/releases/<version>.md`: the CHANGELOG
   section's story for a reader, in English, led by what is new and closing
   on the breaking note.  It is committed with the release commit, so the
   GitHub release links a page the repository actually owns.
5. Commit the bundle, push, and wait for green CI:

   ```bash
   git commit -m "release: 1.1.5 -- <the one-line story>"
   git push origin main
   ```

6. Tag it — **annotated, always** (a lightweight tag carries no text, so the
   repository's Tags page shows nothing; `-a` is what gives the tag its own
   message) — and push the tag:

   ```bash
   git tag -a v1.1.5 -m "motui 1.1.5 -- <the one-line story>"
   git push origin v1.1.5
   ```

   [`release.yml`](.github/workflows/release.yml) builds on both platforms and
   publishes once, from the Linux leg, through PyPI **trusted publishing** — no
   secret lives in the repository. The one-time PyPI-side configuration is
   described in the workflow's own comments.  `gh` (GitHub CLI) is the tool
   for the release steps below; authenticate once with `gh auth login`.

7. Create the GitHub release from the notes file — it needs the tag to exist
   first, so this runs after the workflow settles:

   ```bash
   gh release create v1.1.5 --title "1.1.5" --notes-file docs/releases/1.1.5.md
   ```

   A past release's notes can be corrected later with
   `gh release edit v1.1.5 --notes-file docs/releases/1.1.5.md`.

8. Verify the release is real — the tag, the uploaded files and a scratch
   environment that installs and runs:

   ```bash
   gh release view v1.1.5                          # the page exists and is not a draft
   git ls-remote --tags origin v1.1.5              # the tag is on the remote
   uv run --no-project --with motui==1.1.5 python -m motui --pages
   ```

9. **A published version can never be re-uploaded.** A broken release is
   yanked (so `pip install` stops finding it by default) and fixed in a PATCH;
   the tag stays where it is.

## What not to do

- Don't hand-edit the golden frames (run `tools/golden.py --update`).
- Don't rewrite `specs/` — it is the process archive of how the library got
  here, and it is add-only.
- Don't add a compatibility shim, an alias, or a forwarding module.
- Don't publish from a laptop: the tag is the only release button, and it ends
  in the same workflow everyone can read.
- Don't commit local tool directories (`.zcode/` and friends are ignored).
