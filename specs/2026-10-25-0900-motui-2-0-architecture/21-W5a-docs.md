# W5a · 文档、ADR、迁移与 2.0.0 版本

> 分支 `2.0/w5a-docs`；前置：W4b 已合并（`14756cb`）；写入范围：`README.md`、`docs/**`、`CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`、`src/motui/__init__.py`（仅 `__version__` 回退值）
> 权威：`ref/source/10-waves/W5-docs-release.md`、`05-api-surface.md`、`11-decisions.md`、`13-risks-migration.md`

## 目标

把 2.0 变成可发布、可学习、可迁移的版本：

1. 重写 `README.md`（quickstart + 能力矩阵 + 安装）；
2. `docs/ARCHITECTURE.md`、`docs/CONTRACT.md`、`docs/WIDGETS.md`、`docs/MIGRATION.md`；
3. `docs/adr/ADR-001.md` … `ADR-023.md`（从 `ref/source/11-decisions.md` 拆出，每条一个文件）；
4. 删除/替换 1.x 叙述的 `docs/DESIGN.md`、`docs/COMPONENTS.md`（CONTRACT 被重写）；
5. `pyproject.toml` 版本 `2.0.0`、`motui.__version__` 回退值 `2.0.0`、`uv.lock` 同步；
6. `CHANGELOG.md` 2.0 段（Breaking/Added/Changed/Removed/Performance）；
7. `CONTRIBUTING.md` 更新目录/门禁命令。

**本波结束：文档只描述 2.0；版本 2.0.0；无 `TUI`/`take_result`/`Revisioned`/`Themed`/`set_focus_targets` 作为“当前 API”的叙述；链接无死链。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W4b-api.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1592 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 2.0 实际面（以代码为准，不要照抄旧 spec）：
  - `motui` root：`App`、`Text`、`Input`、`Editor`、`Panel`、`Row/Column`、`Markdown`、`Table`、`List`、`Tree`、`Dialog`、`Theme` 等；`TUI` 已删除。
  - `motui.kernel`：值/协议（`Rect/Size/Pos/Axis`、`Cell/Line/Segment/Surface`、`Constraints`、`WrapMode`、`Scroll/ScrollAxis`、`Section/Document`、`Placement/Sizing`、`Theme`、`Glyphs`、事件、`Keymap` 等）。
  - `motui.terminal`：`Screen` ABC、`Terminal`、`TerminalOptions`、`MouseMode`、`KeyDecoder`、`RawTerminalKeys`、`Clipboard`、`Painter`、`styled_line`。
  - `motui.app`：`Runtime`、`Workspace`、`App`、`FocusManager`、`Pointer`、`SelectionGesture`、`Find`、`Modal`、`CommandPalette`、`Command/CommandRegistry`、`Scrollbar`、overlays。
  - `motui.widgets`：`Text`、`Canvas/Sparkline`、`ScrollPanel`、`Button/Checkbox/Link`、`Input/Editor`、`List/Tree/Table/Select/...`。
  - `motui.testing`：`headless_tui`（返回 `Runtime`）、`snapshot`、`Emulator`、`ScriptedEvents`。
  - 组件签名：`render(c: Constraints) -> Surface`；hooks `on_key/on_mouse/on_paste/on_resize/on_focus/on_click/on_hover/on_drag/on_action`；`take()`；`walk()`；`focusable/clickable/hoverable/activatable`；`keymap`。
  - `App(terminal=TerminalOptions(...))`；`app.add(...) -> Section`；`app.split(Axis.X)`；`app.dock(placement=Placement.BOTTOM)`；`Command(name=..., group=..., ...)`；`registry.bind(app)`；`app.open_palette(registry)`。
- 已知事实/偏差（文档必须诚实描述，不要写未实现的东西）：
  - 公开面计数：root 40?（以 `tools/api.py --check` 为准）、kernel 60+、terminal 15+；不要写死目标数字，写实际命名空间。
  - `ScrollPanel` 仍用 `ScrollState`/`ScrollAxis`；`Pane`/`Document` 横向只经 ScrollPanel。
  - `Fill` 是 `Document.add(sizing=Sizing.FILL)` 的形态（不是 `PaneContent` 联合）。
  - `App` 仍接受旧参数做兼容（W5b 可能删除）；文档只写 `terminal=TerminalOptions(...)` 的推荐用法。
  - Runtime 文件仍较大（>450 行）；文档架构图不要声称已按行数拆分。
  - `docs/releases/` 是历史发布记录，可以保留。
- 写作要求：
  - 英文（与代码一致）；简洁、可执行、面向应用作者。
  - 每个公开 API 至少一个短示例；README quickstart 必须与 `examples/quickstart.py` 一致（W5b 会创建）。
  - 不写“1.x 兼容/迁移中”作为当前状态；`MIGRATION.md` 专门写 1.x→2.0 表与配方。
  - 代码块用 2.0 API（`render(Constraints)`、`on_action`、`take()`、`TerminalOptions`、`Section`、`Axis`/`Placement`）。
  - ADR 每条保留 Context/Decision/Why/Consequences/Alternatives；文件头 `# ADR-00N · <title>`。
  - 删除旧 `docs/DESIGN.md`/`docs/COMPONENTS.md`（它们是 1.x 叙述）；`docs/CONTRACT.md` 重写为 2.0。
  - README 链接到 `docs/ARCHITECTURE.md`、`docs/CONTRACT.md`、`docs/WIDGETS.md`、`docs/MIGRATION.md`、`docs/adr/`。
- 不改代码（除 `__version__` 回退值）；不改 tests/examples。

## 工单（按序，每步一个 commit）

### T1 版本

- `pyproject.toml` `version = "2.0.0"`；`src/motui/__init__.py` 的 `PackageNotFoundError` 回退值 `"2.0.0"`。
- `uv lock`（或 `uv lock --offline`）更新 `uv.lock`；确认 `uv sync --locked` 可跑。
- 验证：`uv run python -c "import motui; print(motui.__version__)"` → `2.0.0`（安装元数据为准）；`uv run pytest -q tests/test_packaging.py`。

### T2 README

- 重写 `README.md`：
  - 3 行安装（`pip install motui` / `uv add motui`）+ 一个 ≤30 行 quickstart（`App` + `Text` + `Input` + `TerminalOptions`）。
  - 能力矩阵（游戏/图表/仪表盘/宽表/流式文档）。
  - 3–5 个核心概念（kernel 值 / widgets hooks / Surface+Constraints / Section / TerminalOptions）。
  - 链接 docs。
- 验证：人工检查代码块 API 与 `examples/quickstart.py` 一致（W5b 创建后复核）。

### T3 ARCHITECTURE / CONTRACT / WIDGETS

- `docs/ARCHITECTURE.md`：分层图（kernel ← widgets ← app；kernel ← terminal；testing 最外）、依赖规则、对象模型、生命周期、扩展点、所有权/构造规则。
- `docs/CONTRACT.md`：值（几何/行/帧/文档/滚动）、`Surface` 裁剪不变量、内容门、`Component` Protocol、`Screen` ABC、Widget hooks/keymap/focus、`take`/`walk`、错误模型、删除名单。
- `docs/WIDGETS.md`：组件目录（文本/布局/装饰/数据/编辑/选择/模态/指示器/Canvas/ScrollPanel），每个的构造参数要点、能力、hooks、`take` 用法。
- 删除 `docs/DESIGN.md`、`docs/COMPONENTS.md`；重写 `docs/CONTRACT.md`（覆盖旧文件）。
- 验证：`grep -rn "TUI\|take_result\|Revisioned\|Themed\|set_focus_targets" docs/*.md` 只允许出现在 `MIGRATION.md` 的旧名对照表；其它文档为 0。

### T4 ADR 001–023

- `docs/adr/ADR-001.md` … `ADR-023.md`：从 `ref/source/11-decisions.md` 拆出；每文件保留五段；标题 `# ADR-00N · <title>`。
- `docs/adr/README.md`：索引表（编号/标题/状态）。
- 验证：23 个文件存在；每条有 Context/Decision/Why/Consequences/Alternatives。

### T5 MIGRATION / CHANGELOG / CONTRIBUTING

- `docs/MIGRATION.md`：
  - 一页表：1.x → 2.0（`render(width)`→`render(Constraints)`、`Block`→`Section`、`pin`→`Placement`、`TUI`→`Runtime/Workspace/Terminal`、`Revisioned`→`touch()`、`Themed`→`Widget.style()`、`take_result`→`take`、`Resultful`→`HasResult`、`ScrollView`→`ScrollPanel`、`ScrollState`→`Scroll/Axis`、`split("vertical")`→`Axis.X`、`dock(edge=)`→`Placement`、`Command` kw_only/group、`Table(wrap=)`→`cell_wrap`、`EveryHandle`→`Timer`、`RowRange`→`RowSpan`、`fit/fill/...`→`reflow/clip/pad`）。
  - 配方：App/TerminalOptions、自定义 widget（render/hooks/keymap/take）、自定义 Screen、theme/styles、测试（headless/Runtime/Emulator）。
  - 删除名单（无 alias）。
- `CHANGELOG.md` 顶部加 `## 2.0.0`（Breaking/Added/Changed/Removed/Performance），引用 MIGRATION。
- `CONTRIBUTING.md`：目录（kernel/terminal/widgets/app/testing）、门禁命令（pytest/golden/semantic/framebench/ruff/pyright/lint-imports/api/growth/examples）、commit 风格、spec 流程。
- 验证：链接检查（README/docs 内部链接存在）；`grep -rn "1.x 兼容\|兼容层" README.md docs/*.md` 只允许 MIGRATION 的历史段落。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字；文档波不改测试）。
2. `uv run python tools/golden.py --check`、`semantic --check`、`framebench` hash 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `motui.__version__ == "2.0.0"`（安装元数据）；`uv sync --locked` 成功。
5. README/docs 链接无死链；ADR 23 条；MIGRATION 表覆盖删除名单。
6. `ruff`/`pyright`/`lint-imports`/`api --check`/`growth --quick` 全绿。
7. 文档不把未实现能力写成已实现（Runtime 行数、Fill 形态、兼容参数如实说明）。

## 禁触清单

`src/motui/**`（除 `__init__.py` 的 `__version__` 回退值）、`tests/**`、`tools/**`、`examples/**`、`tests/golden/**`、`pyproject.toml` 除版本号、`uv.lock` 除版本同步。

## 交接包

最后 commit 写 `handoff/W5a-docs.md`：A 节给文档清单/版本/门禁；B 节给内容取舍、未实现能力的如实描述、链接检查方式；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W4b 事实）/ 探索审计 / 未决问题。
