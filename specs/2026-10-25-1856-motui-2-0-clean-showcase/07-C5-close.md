# C5 · 文档、残留名与 2.0 终验

> 分支 `2.0-clean/c5-close`；前置：C3a 已合并（`b62d6c8`）；写入范围：`README.md`、`docs/**`、`CONTRIBUTING.md`、`CHANGELOG.md`、`src/motui/app/{runtime,workspace,find,focus}.py`（仅 seam/命名/注解）、`src/motui/demo/__init__.py`、`examples/quickstart.py`、`tools/semantic.py`（docstring）、`pyproject.toml`（仅 stale ruff ignore）、`tests/**`（相应 seam 调用）、`tools/api-2.0.txt`
> 权威：本组 `00-overview.md`、`../2026-10-25-0900-motui-2-0-architecture/ref/source/{05,11,13}.md`

## 目标

把干净版 2.0 收口：

1. 文档与代码一致：Showcase 5 场景、examples 3 个、Revisioned/Themed/ScrollState/RowRange/pin/TUI/take_result 已删除、Runtime/Workspace/Router 新结构；
2. 删除 Runtime 最后两个 workspace seam（`fill`/`rows`）：`demo.scene_output` 与 `examples/quickstart.py` 改调 `workspace`；
3. 清理残留旧名（docstring/注释/工具文案/pyproject stale ignore）；
4. `docs/releases/2.0.0.md` + CHANGELOG 干净版条目；README demo/examples 更新；
5. 终验全绿，版本 2.0.0，产出结项报告。

**本波结束：主文档无旧名作为当前 API；Runtime 不再有 workspace 方法；5 场景/3 示例/1633 测试全绿；结项报告落盘。**

## 前置上下文

- 必读：C1/C2a/C2b/C4a/C4b/C3a handoff → 本工单。
- 基线：`uv sync --locked`；`pytest`（1633 passed）；`semantic --check`（5 scenes）；`pages` 5；examples 3；version 2.0.0。
- 现状：
  - README/CONTRIBUTING/docs 仍描述 topic tour/snake/dashboard/57 golden；`docs/ARCHITECTURE` 的 Runtime 行数与 Workspace facade 描述过时。
  - `Runtime` 仍有 `fill`/`rows` 两个 seam（demo/examples 使用）。
  - `Workspace` 有 6 个 runtime delegate seam（控制器 host 用）；本轮可保留，文档写明“控制器 host 是 Workspace”。
  - `tools/semantic.py` docstring 仍写 “three showcase scenes”。
  - `pyproject.toml` ruff per-file ignore 仍列 `tools/golden.py`（已删除）。
  - src 仍有少量 `TUI`/`take_result`/`Revisioned`/`Themed`/`ScrollState`/`RowRange` 的 docstring/注释。
- 写作要求：
  - 文档英文；只写 2.0 实际面；旧名只允许在 `MIGRATION.md` 对照表/删除名单。
  - README demo 段：`python -m motui` = splash → menu → Breakout/Dashboard/Gallery；`--pages`/`--scene`/`--headless`；examples = quickstart/code/wide_table。
  - ARCHITECTURE：kernel/terminal/widgets/app/testing；Runtime/Workspace/Router/App 职责；`testing.Harness` 是测试面；控制器 host = Workspace；行数如实（Runtime 729/Workspace 894/App 643，未达 450/250，写明）。
  - CONTRACT：值/`Surface`/`Constraints`/`Scroll`/`Section`/`Widget.touch/generation`/`Theme.group`/hooks/keymap/take/walk/`Router`；不含 Revisioned/Themed/ScrollState/RowRange/pin。
  - WIDGETS：组件目录 + capabilities/hooks/take；Canvas/ScrollPanel；无旧动词。
  - MIGRATION：完整旧名表（`render(width)`、`Block`、`pin`、`TUI`、`Revisioned`、`Themed`、`take_result`、`Resultful`、`ScrollView`、`ScrollState`、`RowRange`、`split("vertical")`、`dock(edge=)`、`Table(wrap=)`、`EveryHandle`、`fit/fill/...`）；配方。
  - ADR：至少更新 ADR-004（Revisioned 已删）、ADR-013（Scroll）、ADR-016（值方法）、ADR-019（Section）、ADR-021（focus tree）的 Consequences/状态；其余保留。
  - CHANGELOG：2.0.0 干净版条目（Breaking：旧名删除；Added：Showcase/Breakout/Dashboard/Gallery、Router、touch 缓存；Removed：Revisioned/Themed/ScrollState/RowRange/TUI/pin/字节 golden；Performance：缓存命中）。
  - docs/releases/2.0.0.md：一页发布说明（未发布，本地）。
- 代码清理：
  - `demo/__init__.py:scene_output` 的 `runtime.fill(showcase)` → `runtime.workspace.fill(showcase)`；
  - `examples/quickstart.py` 的 `app.runtime.rows` → `app.workspace.rows`（或 `app.workspace` 代理）；
  - 然后删除 `Runtime.fill`/`Runtime.rows`；确认 grep 0。
  - `app/find.py` 内部属性 `self.runtime` 改名 `self.workspace`（若只在文件内）；`app/focus.py` 的 `focus_targets` 注解改 `Workspace`/`Runtime` 宽类型或 `object`（实际 duck-typed）。
  - `tools/semantic.py` docstring “three” → “five”。
  - `pyproject.toml` 删除 `tools/golden.py` 的 per-file ignore（若存在）。
  - src 残留旧名：只改 docstring/注释；不保留功能旧名。`Frame.revision` 保留（结构修订），文档说明不是行缓存。
- 已知坑：
  - `Runtime.fill/rows` 删除会影响 `demo`/`examples` 与测试；全仓更新。
  - `Workspace` 的 runtime delegate 保留（控制器 host 依赖）；文档写明，不当作公开 API。
  - `Harness.__getattr__` 仍可访问 `workspace`/`runtime`；`headless_tui` 返回 Harness。
  - 文档代码块用 2.0 API；不写 snake/dashboard 示例。
  - `docs/releases/` 历史文件可保留；新增 2.0.0.md。
  - semantic 5 场景；没有 byte golden。
- 不改 widgets/kernel/terminal/demo 场景逻辑；不改 examples 行为（只改调用面）。

## 工单（按序，每步一个 commit）

### T1 Runtime seam 删除

- `demo/__init__.py`、`examples/quickstart.py` 改 `workspace.*`；删除 `Runtime.fill/rows`；更新 tests/framebench 若有。
- `grep "runtime\.fill\|runtime\.rows"` → 0（Harness 的 runtime 属性除外）。
- 验证：`uv run pytest -q tests/test_examples.py tests/test_smoke.py tests/app`；`python -m motui --pages`。

### T2 代码残留名清理

- `app/find.py` 内部 `runtime` 改名 `workspace`；`app/focus.py` 注解；`tools/semantic.py` docstring；`pyproject.toml` stale ignore；src docstring `TUI`/`take_result`/`Revisioned`/`Themed`/`ScrollState`/`RowRange` 清理。
- `grep` 报告剩余（允许历史说明/`Frame.revision`）。
- 验证：全量 pytest；ruff/pyright/lint/api。

### T3 README + docs

- README：showcase 5 场景、examples 3 个、安装/quickstart、能力矩阵、docs 链接。
- ARCHITECTURE/CONTRACT/WIDGETS/MIGRATION：按上文更新；删除过时 1.x 叙述。
- ADR 更新/索引；`docs/releases/2.0.0.md`。
- 验证：链接无死链；主文档旧名 0（MIGRATION 表除外）。

### T4 CHANGELOG + CONTRIBUTING

- CHANGELOG 2.0.0 干净版段；CONTRIBUTING 目录/门禁/demo/examples/commit 风格。
- 验证：命令与实际一致（semantic 5、pytest、ruff、pyright、lint-imports、api、growth、examples）。

### T5 终验 + 报告

- 全量：pytest、semantic 5、pages 5、demo `< /dev/null`、examples 3、`--scene breakout/dashboard`、ruff/pyright/lint-imports/api/growth full、framebench。
- 版本 2.0.0；`git status` clean。
- 写 `handoff/C5-final.md`：最终门禁、结构/质量/能力/性能/文档五组、行数、剩余偏差、分支/提交。
- 更新 `00-overview.md` 状态。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. `semantic --check` 5；`python -m motui --pages` 5 场景；`< /dev/null` exit 0；Breakout/Dashboard headless exit 0；examples 3 个 exit 0。
3. `Runtime.fill/rows` 删除；工具/测试无引用；主文档旧名 0（MIGRATION 表除外）。
4. 版本 2.0.0；`ruff`/`pyright`/`lint-imports`/`api --check`/`growth.py` full 全绿。
5. framebench 无 >10% 劣化；新 hash 记录（如变化）。
6. `handoff/C5-final.md` 与 `00-overview.md` 状态完整。

## 禁触清单

`kernel/**`、`terminal/**`、`widgets/**`、`demo/**`（除 `__init__.py` 的 workspace 调用）、`tests/golden/**`（只允许 semantic `--update` 若必要）、`tools/{framebench,growth}.py`、`uv.lock`（版本不变）。

## 交接包

最后 commit 写 `handoff/C5-final.md`：A 节给最终门禁/五组验收/行数；B 节给残余偏差（Workspace runtime seam、行数、旧名白名单）、未决；C 节给关键路径/commit/分支。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
