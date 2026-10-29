# W2 handoff — Stack / Align
Branch `w2.1.2-w1-overlay`; worker `zcode`; W1 already on the branch.
## A. Recorded facts

Files/commits: `widgets/layout.py`, `widgets/__init__.py`,
`tests/widgets/test_containers.py`; `811a1a5` Stack, `8dd1163` Align,
`0139820` exports and tests.

Public API:
- `Stack(children, *, theme=None, styles=None)` (`layout.py:292`),
  `Container`; children bottom → top. `render` gives every child the same
  constraints, overlays bottom → top, then clips to width / `max_height`.
  No children → blank frame of `c.width × (max_height or 0)`.
- `Align(child, *, horizontal="center", vertical="middle", theme=None,
  styles=None)` (`layout.py:370`), `Widget`; anchors left/center/right ×
  top/middle/bottom, anything else `ValueError`.
- Exported from `motui.widgets` (`__init__.py:55`, `__all__` `:70` / `:110`).

Stack hit testing:
- Top → bottom; the first layer with an interactive node at the cell wins.
  Interactive = `clickable`/`focusable`/`hoverable` anywhere in its extent,
  or a `child_at` descent reaching one (`_interactive_at`, `layout.py:266`;
  iterative, depth 64, never calls `render`). `Canvas` is skipped;
  `Padding(Button)` is answered as the **Padding layer**, and
  `descend_chain` reaches the Button.
- No interactive layer → topmost layer containing the cell; outside every
  layer → `None`. Geometry is the last render's
  `(surface.height, surface.width)`.

Align semantics:
- The child renders once with the full constraints. "Actual size" is row
  count × **widest row**, not `Surface.width`, because `Text`/`Rows` return
  short rows with a full declared width; `Surface.width` would make centering
  a no-op. Frame = `c.width × (c.max_height or child height)`; blank rows are
  filled spaces; child rows are left-padded, hard-clipped, then filled.
  Overflow clips, never wraps. `child_at` forwards only inside the painted
  child rectangle minus the anchor offset.

Tests: +20 items in `tests/widgets/test_containers.py` (`:108` Stack, `:183`
Align): z-order/style/transparency, Canvas-vs-Button hit preference, nested
Padding(Button) via `descend`, topmost fallback, empty/budget frame, tree
adoption; 9 anchors, invalid anchors, overflow clipping, child_at offsets,
full-width no-op.

Verification (real output):
- `tests/widgets/test_containers.py`: `55 passed`.
- Full suite: `1687 passed, 3 failed`; expected surface-fixture fallout:
  `tests/test_invariants.py` CASES lacks Align/Stack (W3's write scope) and
  two `tests/testing/test_api_tool.py` snapshot tests.
- `ruff check .` green; changed files green under `--config "exclude=[]"`.
  `pyright` 0; `lint-imports` 5 kept; semantic 9 scenes match.
- `framebench.py` render-hash
  `e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`,
  identical to main @ `561ed56`.
- `api.py --check`: `+ motui.widgets:Align` / `+ motui.widgets:Stack` —
  expected; `tools/api-2.1.txt` untouched.
## B. Only-in-the-head knowledge

- `_interactive_at` is duck-typed on purpose: `Padding` is a `Widget`, not a
  `Container`, yet implements `child_at`; `isinstance(Container)` would miss it.
- Stack keeps untruncated `(height, width)` geometry like Row/Column/Padding;
  the `max_height` budget shapes the returned rows only.
- Align clamps offsets to 0 for an overwide child (anchors left/top, clips
  right/bottom); `child_at` then reports only the visible rectangle.
- Formatting-only edits were needed for the ticket's per-file
  `ruff --config "exclude=[]"`: `zip(strict=False)`, wrapped long lines,
  import order in `layout.py`, `test_containers.py`, `widgets/__init__.py`.
  No behavior change; Row/Column/Padding output is byte-identical.
- Merge-order note: updating `tools/api-2.1.txt` and adding Align/Stack
  factories to `tests/test_invariants.py` CASES turns the 3 red tests green.
- W6 usage: `Stack([PixelCanvas/Canvas, Align(Text(...))])` composes splash
  text over art; `Align.child_at` lets pointer/focus descend.

## C. Pointers

- `src/motui/widgets/layout.py:266` `_interactive_at`; `:292` `Stack`;
  `:370` `Align`.
- `src/motui/widgets/__init__.py:55` import; `:70` / `:110` `__all__`.
- `tests/widgets/test_containers.py:108` Stack tests; `:183` Align tests.
- Previous wave: `handoff/W1-zcode.md`.
