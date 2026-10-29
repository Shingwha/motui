# W7b handoff — docstrings: kernel / app / terminal / demo / root

Agent deepseek-v4.1-flash. Branch `w2.1.2-w7b-docstrings-kernel-app`, base main @ e1196cd.
Commits af8e34d (kernel), bf2c401 (app), c4818e3 (terminal/demo/root), this handoff commit.

## A. Before / after (AST docstring lines)

| scope | before | after | target |
|---|---:|---:|---:|
| kernel | 2583 | 597 | <=1300 |
| app | 2836 | 602 | <=1400 |
| terminal | 958 | 278 | <=480 |
| demo | 225 | 118 | <=120 |
| root | 90 | 9 | <=40 |
| **total** | **6692** | **1604** | **<=3340** |

52 files, docstring literals only (AST-equality verified per file),
+1151 / -6259 lines. Longest 5 per directory (limits: class/public <=6,
private <=3):
- app: Workspace.reveal 6, Workspace.hit 6, Tooltip 6, SelectionGesture 6, _SelectionOverlay 5.
- kernel: theme module 6, visible_width 6, extract 6, selection module 6, Viewport.layout 6.
- terminal: win32 module 5, TerminalScreen 5, RawTerminalKeys 5, keys module 5, KeyDecoder 5.
- demo: GalleryScene 6, ComponentsScene 6, layout module 5, components module 5, terminal module 4.

## B. Key "why" kept (1-3 lines each)

- Paint/dispatch order: chrome -> content -> granted strips -> docks ->
  overlays; hosts route chrome -> overlays -> content -> host.
- `splice_row` grid invariant; `Frame.compose` row memo keyed `(width, steps)`;
  single-pane pass-through; retile mutates in place so id/viewport/chrome/
  focus survive.
- Split/close id rule (host ids never move), divider dies with its adjacency,
  `SEPARATOR_CHROME_NAME` negotiated outermost.
- Sticky scroll previous-extent bookkeeping; body index keyed
  `(Document.mutation, constraints)` with suffix-only prefix recompute.
- `Section` row cache keyed `(width, max_height, generation)`, owned by the
  block so nothing is pruned by id.
- Focus trap nesting; keymap -> on_key -> enter/space activation; click
  descends then focuses, second click activates.
- Selection is document-space, one pane per drag; auto-scroll moves the head
  by the rows the viewport actually travelled.
- Modal owns the keyboard and distinguishes a `None` decision from none;
  toasts/scrollbar see a band press before hit-testing; scrollbar strip =
  body-scoped window.

## C. Gates (real output)

- `uv run pytest -q -p no:cacheprovider`: **1838 passed**.
- `uv run ruff check .`: **All checks passed** (configured excludes).
- `uv run ruff check <52 changed files>` (no-exclude): **32 errors**, all
  pre-existing app code findings (I001/UP037/SIM/F401/B905/RUF007/RUF023/
  RUF100 + 3 code-line E501); base was **34**; no docstring/new finding.
- `uv run pyright`: **0 errors, 0 warnings, 0 informations**.
- `uv run lint-imports`: **5 kept, 0 broken**.
- `uv run python tools/semantic.py --check`: **9 scenes match**.
- `uv run python tools/api.py --check`: **244 names match**.

Deviation: "ruff no-exclude 全绿" is unreachable without code edits (32
pre-existing app findings). Left for the app-lint wave per the zero-code red
line. No merge/push/tag/checkout of main; no other deviations.
