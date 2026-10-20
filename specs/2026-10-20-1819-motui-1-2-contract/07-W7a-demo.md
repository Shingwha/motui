# W7a · demo 整体重构（master–detail 组件浏览器）
> 分支 `w7a-demo`；前置：W5b 已合并；写入范围见下。
> 用户要求：demo 整体重构，简洁清晰、逻辑合理，不参考当前展示方式；组件、样式、交互、功能分类整理。

## 目标

把 `src/motui/demo/` 从“页面 + 展品流”改成一个 **master–detail 的组件浏览器**：顶部 section 标签、
左侧分类目录、右侧单主题舞台。每个 topic 只回答四件事：它是什么、现场长什么样、可以怎么试、API 一行。
不再有“一页塞十组展品”的文档式页面。

## 信息架构

### Section（顶部，6 个）

| section | 内容 |
|---|---|
| `overview` | 库是什么、层图、快速开始、1.2 变化摘要 |
| `components` | 所有公共组件，按 Text / Forms / Data / Layout / Actions / Overlays 分组 |
| `interactions` | Focus / Pointer / Selection / Find / Scrollbar / Modal stack / Dispatch |
| `styling` | Theme tokens / Custom theme / Glyphs / RowBands |
| `patterns` | Streaming Markdown / Form validation / Command palette / Build-your-own shell |
| `reference` | API layers / Keymap / Component matrix / Non-goals |

### Topic（左侧目录，按 group 分组）

组件 section 的 topic 必须覆盖全部公共组件（可一个 topic 含 2–4 个同类组件）：

- Text: `text`, `markdown`, `diff`, `notice`
- Forms: `input`, `editor`, `checkbox`, `radio-group`, `checkbox-group`, `select`, `combobox`, `autocomplete`, `slider`, `form`
- Data: `list`, `table`, `tree`, `tabs`, `navlist`, `progress`, `spinner`
- Layout: `row-column`, `padding-panel`, `divider`, `collapsible`, `spacer`, `scroll-view`, `delegate`
- Actions: `button`, `link`, `menu-bar`, `context-menu`
- Overlays: `dialog`, `modal`, `palette`, `toasts`, `tooltip`, `stats`

其余 section 的 topic：

- interactions: `focus`, `pointer`, `selection`, `find`, `scrollbar`, `modal-stack`, `dispatch`
- styling: `theme-tokens`, `custom-theme`, `glyphs`, `row-bands`
- patterns: `streaming-markdown`, `form-validation`, `command-palette`, `own-shell`
- reference: `api-layers`, `keymap`, `component-matrix`, `non-goals`

`overview` 是一个 topic（`welcome`）。总数控制在 35–45 个 topic；每个 topic 一屏内读完。

## Shell 布局（ASCII 预览）

```
┌ header dock ──────────────────────────────────────────────────────────────────────────────┐
│ motui studio   Overview  Components  Interactions  Styling  Patterns  Reference   theme: dark │
├ catalog (1:4) ────────────────┬ stage ───────────────────────────────────────────────────────┤
│ ▸ Text                        │ Select                                                       │
│   Markdown                    │ One menu over a sequence; cursor, window, marks, commit.     │
│   Diff                        │ ── preview ──────────────────────────────────────────────── │
│   Notice                      │  [ live Select ]                                             │
│ ▸ Forms                       │ ── variants ─────────────────────────────────────────────── │
│   Input                       │  [ windowed ]  [ commit ]  [ multi ]                         │
│   Editor                      │                                                              │
│   Checkbox                    │ Try: ↑↓ move · enter take · space toggle                     │
│   RadioGroup                  │ API: Select(options, *, title, max_rows, wrap, marker, ...)  │
│   ...                         │                                                              │
├ footer dock ────────────────────────────────────────────────────────────────────────────────┤
│ c-1..6 section · c-n/c-p topic · tab focus · / palette · c-f find · c-t theme · q quit       │
│ theme dark · focus Select · last pick: "option 03"                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Header** uses a real top `dock` with a `MenuBar` of the six sections and a right-aligned theme name.
- **Catalog** is a `NavList` grouped by topic group; clicking or `c-n/c-p` selects a topic.
- **Stage** is the main pane document: title, one-line summary, preview panel, variants row, Try line, API line.
- **Footer** uses a bottom `dock` with `ShortcutBar` + `StatusLine` (theme, focused leaf, last pick).
- Long stage content scrolls through the pane's own viewport; a long single preview may use `ScrollView`.
- No page-level prose, no “notes” page; the reference section carries the facts.

## Topic 模板（强制）

Each topic is built by `TopicBody` with these blocks, in order:

1. `Text` title (accent, one row).
2. `Text` summary (dim, one row, ≤ 100 cells).
3. `Divider` rule.
4. **Preview**: one `Panel(title="preview")` or a `Column` of components, live.
5. **Variants** (optional): a `Row`/`Column` of 2–3 additional configurations, each with a one-line caption.
6. `Text("Try: ...")` (dim, one row): the keys/clicks that work in this topic.
7. `Text("API: ...")` (dim, one row): constructor/verbs/facade.
8. Optional `Echo` line for the last pick (the shell's inspector also shows it).

No free prose. A topic that needs more than 8 blocks is too broad and should split.

## 代码结构（新）

```
src/motui/demo/
├── __init__.py          # run / --pages entry
├── __main__.py
├── model.py             # Section, Topic, TopicBody, registry types
├── registry.py          # SECTIONS, TOPICS, BY_KEY, GROUPS
├── session.py           # Session: state, dispatch, theme, topic switch
├── shell.py             # docks, header MenuBar, catalog, footer, inspector
├── stage.py             # TopicBuilder: template helpers (title/summary/preview/try/api)
├── assets.py            # THEMES (keep the existing variants, names may change)
├── script.py            # headless replay: one pass over every section/topic
└── topics/
    ├── __init__.py
    ├── overview.py
    ├── components_text.py
    ├── components_forms.py
    ├── components_data.py
    ├── components_layout.py
    ├── components_actions.py
    ├── components_overlays.py
    ├── interactions.py
    ├── styling.py
    ├── patterns.py
    └── reference.py
```

- `Topic` is a value: `key`, `title`, `summary`, `group`, `section`, `build`, `try_line`, `api_line`.
- `TopicBody`: `blocks`, `focus: FocusManager | None`, `modal`, `tick`, `note`, `enter`, `leave`.
- `Session.show(section, topic)` switches; `Session.show_topic(key)` is the palette/replay door.
- `GROUPS` is derived from `TOPICS` (contiguous `group` runs), not hand-maintained.
- `TOPICS` ordering defines catalog order and `c-n/c-p` order.
- The old `Page`/`PageBody`/`Exhibit`/`Pick`/`Slot`/`Action` model is deleted; a simpler `Echo`/`report`
  helper may remain in `stage.py`.

## 交互与功能（必须现场可用）

- **Navigation**: `c-1`..`c-6` sections; `c-n`/`c-p` next/prev topic (wraps within the section);
  `[`/`]` previous/next section; clicking the header `MenuBar` or catalog row switches.
- **Focus**: `tab` cycles the current topic's `FocusManager`; `enter` activates; arrows drive the focused
  component; `esc` closes a modal/palette or returns focus to the catalog.
- **Palette**: `/` or `c-k` opens a `Palette` over a `CommandRegistry` of every topic ("Components · Select");
  selecting jumps to that topic. This is the live `CommandRegistry` + `Palette` showcase.
- **Find**: `c-f` opens `Find` over the stage; `enter` cycles matches; `esc` closes.
- **Theme**: `c-t` cycles `THEMES`; the whole shell and stage rebuild (or re-theme) without losing the topic.
- **Inspector**: footer shows theme, focused leaf class, and the last pick from any component
  (generic `take_result()` scan plus the topic's `note`).
- **Toasts/Tooltip/Stats**: `c-g` mounts the Stats; pointer hover shows the leaf's `hint`; a toast confirms
  topic jumps/theme changes.
- **Selection/copy**: drag selects, release copies through the configured `Clipboard` and shows a toast.
- **Scrollbar**: the stage pane has a `Scrollbar`; long topics scroll.
- **Docks**: header/footer are real `tui.dock` regions, not overlay bands; the split is catalog | stage.

## Topic 内容要点（不要写成手册）

- **welcome**: 3-line what/why, layer table (kernel/keys/widgets/interaction/app), quickstart snippet as
  `Markdown`, and the six section names. One clickable index table is fine.
- **Components**: one live preview + up to 3 variants; the Try line names the actual keys; the API line is one
  line. Disabled/focused/masked/windowed/commit states are variants, not separate topics.
- **Interactions**: each topic is a small live sandbox showing the tier's behavior; include the exact mount
  call in the API line (e.g. `FocusManager([...])`, `SelectionGesture(tui)`).
- **Styling**: theme-token table with live swatches; custom theme picked by `c-t`; glyph table with seats;
  RowBands precedence shown by a small List with three configured rows.
- **Patterns**: streaming Markdown (timer-driven), Form validation (empty/invalid/valid), command palette
  (same registry as `/`), own-shell (footer dock + Editor + StatusLine).
- **Reference**: API layer table, keymap table, component × protocol matrix, 1.2 non-goals. These are static
  tables; no interaction beyond scrolling.

## 兼容与工具

- `python -m motui` runs the new shell. `python -m motui --pages` dumps **every topic** as plain text
  (the headless path), one section header per section.
- `tools/golden.py` renders one file per topic: `tests/golden/topics/<section>--<topic>.txt`
  (replace the old `pages/*.txt`; delete the old files). `tests/test_golden_frames.py` walks `TOPICS`.
- `demo/script.py` replays: welcome → one topic per section → palette jump → theme switch → quit.
  The replay must exercise the new navigation, not the old pages.
- `tests/test_demo_protocol.py`, `test_demo_kit.py` → replace with `test_demo_model.py`,
  `test_demo_protocol.py` (new names), `test_demo_topics.py` (every topic builds, renders, and has a Try/API line).
- `tests/test_readme_examples.py`/`README.md` demo section update to the new IA.
- Keep `demo/assets.py` theme variants; adapt names to new shell.

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；demo tests rewritten; total ≥ 1926 + new
2. `uv run python tools/golden.py --check`：new topic frames match; old `pages/` files removed
3. `uv run python tools/framebench.py`：exit 0；render-hash **有意变化**（demo rewrite），贴新旧值
4. `uv run python -m motui < /dev/null`：exit 0；final dump is the welcome topic
5. `uv run python -m motui --pages`：exit 0；dumps every section/topic; no old page names
6. `grep -rn "Page(\|PageBody\|Exhibit\|CheckGroup\|\bRadio\b" src/motui/demo`：0 命中
7. Every public component appears in at least one topic (a test asserts the coverage list).
8. No prose page: every topic has title/summary/preview/try/API; a test asserts the block skeleton.
9. `git diff --stat main...HEAD`：范围 = `src/motui/demo/**`、`tools/golden.py`、demo tests、
   `tests/golden/**`（仅经工具）、`tests/golden/README.md`、`README.md` demo section。

## 禁触清单

- 禁改：`src/motui/kernel/**`、`src/motui/keys/**`、`src/motui/widgets/**`、`src/motui/interaction/**`、
  `src/motui/app.py`、`docs/CONTRACT.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`（W7b 重写）、
  `pyproject.toml`、`uv.lock`。
- 如果 demo 需要库缺少的能力：停下来报告，不要越界改库。
- 禁加：兼容 alias/旧 page 名 re-export。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。

## 交接包

完成后写 `handoff/W7a-demo.md`（60–80 行，A/B/C），附：
- 新 IA 的 section/topic 表
- 每个 topic 的覆盖组件
- golden 新旧命名与重录统计
- 三条 demo 入口的真实输出

## 最终报告

工单状态表 / commit 清单 / 自测真实输出 / 新 IA 与 topic 覆盖表 / 测试改动清单 /
golden 变更统计 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
