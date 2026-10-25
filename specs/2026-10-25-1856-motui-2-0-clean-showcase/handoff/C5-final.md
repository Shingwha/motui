# C5 · Documentation, residual names and the 2.0 closeout · Handoff

> Branch `2.0-clean/c5-close`; start `fa53fbd`; 4 work commits + this
> handoff. Version stays **2.0.0** (unpublished).
## A. Final gates (real output)
**Structure.** `Runtime.fill`/`Runtime.rows` are deleted; grep for
`runtime\.fill|runtime\.rows|Runtime\.fill|Runtime\.rows` over `src tests
examples tools` exits 1. `demo/__init__.py` calls `runtime.workspace.fill`;
`examples/quickstart.py` reads `app.workspace.rows`; `find.py` stores
`self.workspace`; `focus.py` annotates `Workspace`; `tools/semantic.py`
says five scenes; pyproject no longer ignores `tools/golden.py`.
`uv sync --locked`: Checked 20 packages; the import resolves to this
worktree; `motui.__version__ == "2.0.0"`.
**Quality.**
```
uv run pytest -q -p no:cacheprovider  -> 1633 passed in 11.90s
uv run ruff check .                   -> All checks passed!
uv run pyright                        -> 0 errors, 0 warnings, 0 informations
uv run lint-imports                   -> Contracts: 4 kept, 0 broken.
uv run python tools/api.py --check    -> api: 188 names match
uv run python tools/growth.py         -> pytest/semantic/api pass; OK (full probe)
```
**Capability.**
```
uv run python tools/semantic.py --check                -> semantic: 5 scenes match
uv run python -m motui --pages                         -> exit 0, 5 headers, 133 lines
uv run python -m motui < /dev/null                     -> exit 0, 20 lines
python -m motui --scene breakout --frames 30 --headless  -> exit 0, score 0010 level 1
python -m motui --scene dashboard --frames 30 --headless -> exit 0, tick 0030
examples/{quickstart,code,wide_table} --headless        -> exit 0 x3
```
**Performance.**
```
uv run python tools/framebench.py:
stream-single 0.8 / stream-split 4.9 / scroll 0.5 / scroll-long 0.8 /
idle-long 0.6 / text-open 0.1 / table-open 0.1 / stream-paragraph 0.9 ms;
replay 338 ms;
render-hash e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da
```
Same hash as the C3a/C4 baselines; no workload >10% slower (C3a:
0.8-0.9/4.8-5.0/0.5/0.7-0.8/0.6/0.1/0.1/0.9 ms, replay 346-355 ms).
**Documentation.** Main docs (README, ARCHITECTURE, CONTRACT, WIDGETS)
grep for `Revisioned|Themed|ScrollState|RowRange|take_result|EveryHandle|
TUI|pin=` exits 1; `MIGRATION.md` is the only old-name table (relative
links: 0 missing). README covers 5 scenes, 3 examples and the 2.0
dispatch/ownership; ARCHITECTURE records 706/894/643/357 lines and the
Workspace controller host; CONTRACT records Axis/Placement,
`touch()`/generation, `Scroll`/`RowSpan`, `Theme.group`, Router and the
188-name surface; WIDGETS drops `revision()`/`scroll_state`; ADR-004/008/
013/016/019/021 are updated; `docs/releases/2.0.0.md` is added; CHANGELOG
and CONTRIBUTING describe the clean release and gates.
**Lines.** Runtime 706 (target 450), Workspace 894 (target 450), App 643
(target 250), Router 357 (new). C3a shipped 729/894/643; the 23-line
Runtime drop is the `fill`/`rows` seam removal and its imports.
## B. Residual deviations and decisions
- **Line targets are not met** (706/894/643 vs 450/450/250). The gap is the
  migrated contract docstrings, `App`'s controller assembly and the
  `DEFAULT_HANDLERS` tiers now in `router.py`; no feature was deleted to
  game the count.
- **Workspace runtime seam.** `clock`, `every`, `refresh`, `screen`,
  `painter`, `copy_to_clipboard` exist because the controllers are hosted
  on the workspace. Documented as a controller seam, not public API.
  Removing it needs controllers to take `(workspace, runtime)`.
- **Old names outside the write scope.** `src/motui/__init__.py:1`
  ("TUI toolkit", generic phrase) and stale `motui.app.TUI` cross-refs in
  `terminal/terminal.py`, `widgets/{choice,list,table,textfield}.py`
  (7 hits) are in forbidden files; zero diff was kept. `Frame.revision`
  remains, documented as a structural counter, not a row cache.
- **Historical mentions.** ADR Context sections name removed concepts
  (Revisioned, EveryHandle, take_result); ADR-008 Consequences were updated
  because the byte set no longer exists. `MIGRATION.md` is the deliberate
  old-name table.
- **Gate scope unchanged.** `tools/framebench.py` stays pyright-ignored;
  ruff's 1.x ratchet excludes remain. No byte golden: the five semantic
  scenes are the only golden set.
- Unresolved: nothing blocking. Lead merge/push/tag are out of scope.
## C. Paths, commits and branch
Key paths: `src/motui/app/{runtime,workspace,find,focus}.py`,
`src/motui/demo/__init__.py`, `examples/quickstart.py`, `tools/semantic.py`,
`tools/api-2.0.txt`, `pyproject.toml`, `README.md`,
`docs/{ARCHITECTURE,CONTRACT,WIDGETS,MIGRATION}.md`,
`docs/adr/ADR-{004,008,013,016,019,021}.md`, `docs/releases/2.0.0.md`,
`CHANGELOG.md`, `CONTRIBUTING.md`, `tests/app/*`, `tests/testing/layout.py`.
Commits: `d28678e` runtime: hand fill and rows to the workspace ·
`2bf63d2` runtime: name the workspace where the seams are gone ·
`d3befd6` docs: describe the clean 2.0 surface and the five-scene showcase ·
`e265578` docs: record the clean 2.0 release and the current gates ·
this handoff.
Branch: `2.0-clean/c5-close`; `git status` clean after the handoff commit.
