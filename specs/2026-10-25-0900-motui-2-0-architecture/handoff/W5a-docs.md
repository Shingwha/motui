# W5a 交接 · 文档、ADR、迁移与 2.0.0 版本

> 分支 `2.0/w5a-docs`；起点 `a5aa8bc`（W5b 工单入库后）。T1–T5 完成：**1592 passed**；57 byte / 57 semantic / hash `e7ca544b…` 全不变；demo 70 / 4059 行；版本 `2.0.0`；文档链接 0 死链；ADR 23 条五段齐全；ruff / pyright / lint-imports / api 184 / growth full 全绿。

## A. 交付面与门禁

### 文档清单

- 重写 `README.md`：安装、≤30 行 quickstart（`App` + `TerminalOptions` + `Text` + `Input`，23 行）、能力矩阵（游戏/仪表盘/宽表/流式文档/分屏/表单）、五个核心概念、控制器与 dispatch 顺序、布局/样式/键位/结果/测试、demo、文档索引。
- 新 `docs/ARCHITECTURE.md`：分层图、模块表、四条 import-linter 规则、所有权/构造、生命周期、渲染管线、dispatch 顺序、扩展点、已知偏差、2.x 非目标。
- 重写 `docs/CONTRACT.md`：值/不可变性、几何、行模型与内容门、`Surface` 裁剪不变量、`Component` 协议、`Section`/`Document`、`Frame`/`Pane`、Widget 能力/hooks/tree/take、Runtime/Terminal、错误模型、公开面计数（40/61/17/46/16/4，共 184）。
- 新 `docs/WIDGETS.md`：46 个导出组件的构造要点、能力集、hooks、`take()` 结果、ScrollPanel/Canvas 专节、自定义组件配方、`HasResult` 收集。
- 新 `docs/MIGRATION.md`：一页旧名表（覆盖工单全部条目）、App/widget/Screen/theme/test 配方、删除名单、仍保留的兼容入口、迁移 checklist。
- 新 `docs/adr/ADR-001.md` … `ADR-023.md` + `docs/adr/README.md` 索引；每条 Context/Decision/Why/Consequences/Alternatives。
- 删除 `docs/DESIGN.md`、`docs/COMPONENTS.md`（1.x 叙述）；`docs/releases/` 历史保留。
- `CHANGELOG.md` 顶部 `## [2.0.0] — 2026-10-25`，含 Breaking/Added/Changed/Removed/Performance；链接引用补 `2.0.0`。
- `CONTRIBUTING.md` 重写目录/kernel-terminal-widgets-app-testing/完整门禁/commit 风格/spec 流程/2.x 版本策略。
- 版本：`pyproject.toml` 2.0.0、`motui.__version__` 回退值 2.0.0、`uv.lock` 同步。

### 工单状态

| 项 | 状态 | 产出 |
|---|---|---|
| T1 版本 | 完成 | 2.0.0 / fallback / uv.lock |
| T2 README | 完成 | quickstart + 能力矩阵 + 五概念 + docs 链接 |
| T3 ARCHITECTURE/CONTRACT/WIDGETS | 完成 | 三份 2.0 文档；DESIGN/COMPONENTS 删除 |
| T4 ADR-001..023 | 完成 | 23 文件 + 索引，五段齐全 |
| T5 MIGRATION/CHANGELOG/CONTRIBUTING | 完成 | 旧名表/配方/删除名单/2.0 CHANGELOG/门禁 |

### 真实门禁输出（本 worktree，2026-10-25）

- `uv sync --locked`：Checked 20 packages；`motui==2.0.0`（editable）。
- `pytest -q -p no:cacheprovider`：**1592 passed in 33.80s**。
- `golden.py --check`：**57 topics match**；`semantic.py --check`：**57 topics match**。
- `framebench.py`：`e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`（不变）。
- `python -m motui < /dev/null`：exit 0，**70** 行；`--pages`：exit 0，**4059** 行。
- `motui.__version__` / `importlib.metadata.version("motui")`：`2.0.0` / `2.0.0`；`tests/test_packaging.py` 2 passed。
- `ruff` All checks passed；`pyright` 0 errors；`lint-imports` **4 kept**；`api --check` **184 names match**；`growth.py`（full）OK。
- 三个示例 `--headless` exit 0：snake / dashboard(12 frames) / wide_table(c199 可见)。
- README quickstart 块执行（非 live 会话）exit 0，打印两行最终屏幕。
- 链接检查：README/CONTRIBUTING/CHANGELOG/docs(含 adr) 本地链接 **0 死链**；ADR **23** 文件、**0** 缺段；MIGRATION 覆盖脚本要求的 **20** 个条目 **0** 缺失。
- 文档 Python 代码块全部通过 `ast.parse`；文中 37 条 `from motui…` 导入全部解析。

## B. 内容取舍、如实描述与链接检查

1. **只描述 2.0 实际面**：公开面以 `tools/api-2.0.txt`（184 names）与代码为准；文档正文（README/ARCHITECTURE/CONTRACT/WIDGETS/CONTRIBUTING/CHANGELOG）中 `TUI`/`take_result`/`Revisioned`/`Themed`/`set_focus_targets` 作为当前 API 为 0 次。`MIGRATION.md` 旧名表/删除名单与 ADR 的历史 Context 保留这些名字（ADR-004/021/022 按源决策标题记录），ADR 索引声明“记录是历史，当前 API 看 CONTRACT/WIDGETS”。
2. **已知偏差如实写入**：`app/runtime.py` 仍约 1,617 行（未拆 session/layout/documents/protocol）；`Workspace` 是无状态委托 facade；`Fill` 是 `sizing=Sizing.FILL` 的文档形态（无 `PaneContent` 联合）；`ScrollPanel` 与 pane chrome 仍用 `ScrollState`；`App` 旧构造参数仍兼容；`split`/`dock` 字符串仍接受；字节 golden 保留为额外门禁；`Placement`/`Sizing` 只在 `motui.kernel.document`；`TerminalOptions` 只在 `motui.terminal`；`HasResult` 只在 `motui.widgets.base`。
3. **未实现能力不外推**：图片/媒体协议、文档流横向滚动、网格布局、`RenderEnv`、per-widget result 回调均写为 2.x/非目标；横向滚动明确限定 `ScrollPanel` + 非换行内容。
4. **文档与代码的最小偏差**：工单示例旧表写 `Themed → Widget.style()`，实际没有 `style()`，文档写 `Widget.group(name)` + `theme`/`styles`；工单写 `RowRange → RowSpan`，实际 `RowSpan` 未落地，文档如实写 `RowRange` 仍在、`RowSpan` 未实现；`Command` 位置参数 shim 与 `App.remove` 收窄标注为 W5b 计划删除。
5. **README quickstart 对齐**：`examples/quickstart.py` 尚未合并（W5b T1 创建）。README 块按工单用 `App` + `TerminalOptions` + `Text` + `Input` 写成 23 行，并留 HTML 注释 `<!-- The exercised copy of this block is examples/quickstart.py (W5b). -->`；W5b 应复制该块到 `examples/quickstart.py`（或反向同步 README）。块已在本机以非 live 会话执行通过。
6. **链接检查方式**：本地脚本对 `README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`、`docs/*.md`、`docs/adr/*.md` 的 Markdown 本地链接做“相对路径去掉 anchor 后是否存在”检查，排除 `http(s)`/`mailto`/纯 anchor；结果 0 死链。
7. **内容生成方式**：ADR 由 `ref/source/11-decisions.md` 人工拆分为英文五段；迁移表由 `05-api-surface.md`、`13-risks-migration.md` 与实测签名合成。所有教程代码块只使用真实存在且已验证的导入路径。
8. **未改代码**：除 `__init__.py` 的 `__version__` 回退值与 `uv.lock` 版本同步外，`src/motui/**`、`tests/**`、`tools/**`、`examples/**` 零 diff。

## C. 位置与 commit

- 文档：`README.md`、`docs/ARCHITECTURE.md`、`docs/CONTRACT.md`、`docs/WIDGETS.md`、`docs/MIGRATION.md`、`docs/adr/**`、`docs/DESIGN.md`（删）、`docs/COMPONENTS.md`（删）、`CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml`、`src/motui/__init__.py`（仅版本）、`uv.lock`。
- commit：
  - `332dafd` release: the package is 2.0.0（T1）
  - `0d0dea2` docs: the readme teaches the 2.0 app, values and hooks（T2）
  - `16b7bdf` docs: architecture, contract and widgets describe the 2.0 tree（T3）
  - `a2c019f` docs: record the twenty-three 2.0 architecture decisions（T4）
  - `1ce6526` docs: migration, changelog and contribution gates for 2.0（T5）
  - `c4cdb30` docs: the examples use the real import doors（导入路径修正）
  - 本文件（收口）
- 待 W5b：创建 `examples/quickstart.py` 并与 README 块对齐；删除 `Command` 位置 shim / `App.remove(str)`；demo 文案与 golden 重录；终验。
