# W7b · 文档重写（不发版）
> 分支 `w7b-docs`；前置：W7a demo 已合并；写入范围见下。
> **按用户 2026-10-21 指示：本波只重写文档，不 bump 版本、不写 release notes、不打 tag。**
> 1.2.0 的测试重构由用户先做；发版单独等指令（见 W8）。

## 目标

把 `README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`、`docs/CONTRACT.md`、`CONTRIBUTING.md`
从“1.1.x 文档 + 多轮局部补丁”重写成与 1.2 代码一致的规范文档。语气面向使用者：先讲能做什么，
再讲怎么用，最后讲机制与扩展点。**不写发版内容**。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → W7a handoff → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
- 稳定区：`src/motui/**` 已验收；本波只读代码，不改库。
- W7a 会改变 demo 的 IA 与 README demo 段；W7b 读取 W7a handoff 后再动 README。

## 文档结构（目标）

### README.md

- 一句话定位 + 三个卖点（full-screen document model、interaction tiers、zero deps）。
- Install / Quickstart（可执行，`test_readme_examples.py` 覆盖）。
- Feature map（按能力分组，不按文件）。
- The layer model（kernel/keys/widgets/interaction/app + Host）。
- Components（按 Text / Forms / Data / Layout / Actions / Overlays 分组；每项一行）。
- Interactions（FocusManager、Pointer、SelectionGesture、Find、Modal/Palette、Scrollbar、Toasts/Tooltip/Stats）。
- Styling（Theme/Style/RowBands/glyphs）。
- Markdown + syntax.
- Keys & keymaps.
- Demo（新的 master–detail explorer；`python -m motui`、`--pages`）。
- Docs / Contributing / License。
- **不写版本号/发布说明**。

### docs/DESIGN.md

- The layers and the import table (1.2 reality: kernel -> keys -> widgets -> interaction -> app; Host seam).
- Coordinates & hit testing (`hit`/`hit_leaf`/`pane_at`; inner rect; strict bounds).
- Events (Event/KeyEvent/MouseEvent/PasteEvent/ResizeEvent/FocusEvent; key grammar; decoder coverage).
- The driver lifecycle (`run_session`/`run_async`/`run`, `exit`, `refresh`, per-run reset).
- Document/block model, `Revisioned`, one cache owner.
- Viewport / docks / frame model (`dock`, top/bottom, overlay layers).
- Painter, selection, focus, modal stack.
- Value semantics (Pane mutable, ScreenLayout tuples, Theme tables read-only).
- Deliberately out of scope (update: menus now in, ScrollView/Form in, etc.).
- Remove stale claims (four vs five layers, kernel "imports nothing" vs wcwidth, old names).

### docs/COMPONENTS.md

- The render protocol + controller/result protocols (`handle` = consumed, `take_result`).
- The driver in call order (1.2 names).
- Component catalogue, grouped:
  - Text/structure: Text, Markdown, Diff, Divider, Panel, Notice, Row/Column/Padding/Spacer, Delegate, Collapsible, ScrollView.
  - Forms: Input, Editor, Checkbox, RadioGroup, CheckboxGroup, Select, ComboBox, Autocomplete, Slider, Form/Field.
  - Data: List, Table, Tree, Tabs, NavList, ProgressBar, Spinner.
  - Actions: Button, Link, MenuBar, ContextMenu.
  - Overlays: Dialog, Modal, Palette, Toasts, Tooltip, Stats.
- Each entry: purpose, signature (one line), verbs, result type, protocols, notes.
- RowBands contract; disabled/read_only; containers/`child_at`; `Revisioned` rules.
- FocusManager / Pointer / SelectionGesture / Find / Scrollbar / Modal / Palette / Toasts / Tooltip / Stats.
- Command/CommandRegistry, Clipboard.
- Theme fields table; glyph vocabulary; keymaps.
- Build-your-own walkthroughs (custom chrome, overlay, container, Markdown rule, Form pattern).
- Testing (headless_tui, snapshot, golden).

### docs/CONTRACT.md

- Verify every section against the shipped code; update Host (document/selection/selection_pane/scroll_keys/painter/reveal),
  LAYERS, FocusManager, MenuBar/ContextMenu, ScrollView/Form/CommandRegistry/Clipboard, `take_result`.
- Keep it normative and short; link to DESIGN/COMPONENTS rather than duplicate prose.

### CONTRIBUTING.md

- Update the one-way dependency rule to the 1.2 graph (interaction -> kernel/Host only).
- Update gates: pytest, golden, framebench, demo two entries; add any new commands.
- Keep versioning policy, but add: 1.2.0 release is gated on the user's test refactor; do not bump in docs wave.

### Tests

- `tests/test_readme_examples.py`: every README code block still executes; update examples to 1.2 APIs.
- Add `tests/test_docs_claims.py` (optional): assert the layer list, root 34, component catalogue names,
  and no stale API names in docs.
- No golden changes expected.

## 工单（按序执行；HEAD 全绿即可）

### T1 `README.md`
### T2 `docs/DESIGN.md`
### T3 `docs/COMPONENTS.md`
### T4 `docs/CONTRACT.md` + `CONTRIBUTING.md`
### T5 tests/examples + stale-name grep
### T6 handoff

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed（≥ W7a 后基线）
2. `uv run python tools/golden.py --check`：W7a 的新 topic frames 全 match
3. `uv run python tools/framebench.py`：exit 0；render-hash 与 W7a 后一致
4. `uv run python -m motui < /dev/null`、`--pages`：exit 0
5. README 示例测试通过；docs 中的 API 名称与代码一致
6. 过期 API grep：`FocusRing`、`chosen`、`hit_test`、`add_band`、`viewport_rows`、`invalidate(`、`stop()`、
   `read_key`、`CheckGroup`、`Radio(`、`cursor_style`、`selected_style` 在 `README.md`/`docs/` 零命中
   （历史 spec 与 release notes 除外）
7. **版本号未动**：`git diff --name-only main...HEAD` 不含 `pyproject.toml`、`uv.lock`、`CHANGELOG.md`、
   `docs/releases/`；`motui.__version__` 仍是 1.1.8
8. `git diff --stat main...HEAD`：范围 = README/docs/CONTRIBUTING/tests-examples

## 禁触清单

- 禁改：`src/motui/**`（只读）、`pyproject.toml`、`uv.lock`、`CHANGELOG.md`、`docs/releases/**`、
  `tests/golden/**`、`specs/**`（handoff 除外）。
- 禁做：版本 bump、release notes、tag、push、merge、checkout main。
- 如果文档发现代码 bug：报告，不在本波修。

## 交接包

完成后写 `handoff/W7b-docs.md`（60–80 行，A/B/C），附：
- 文档结构目录
- 过期名清扫清单
- README 示例测试结果
- 未决问题（例如需要代码修复的文档发现）

## 最终报告

工单状态表 / commit 清单 / 自测真实输出 / 文档结构 / 过期名 grep / 偏差与取舍 /
交接校验 / 探索审计 / 未决问题。
