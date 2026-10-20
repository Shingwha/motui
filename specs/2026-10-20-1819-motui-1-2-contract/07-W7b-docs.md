# W7b · 文档重写（不发版）
> 分支 `w7b-docs`；前置：W7a demo 已合并；写入范围见下。
> **按用户 2026-10-21 指示：本波只重写文档，不 bump 版本、不写 release notes、不打 tag。**
> 1.2.0 的测试重构由用户先做；发版单独等指令（见 W8）。

## 目标

把 `README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`、`docs/CONTRACT.md`、`CONTRIBUTING.md`
**从逻辑上整体重写**，而不是在现有章节上小修小补。当前文档只作为事实来源，不作为结构模板：
目录、叙事顺序、示例组织方式都可以推翻重来。目标是让新读者更快建立心智模型、更快找到要用的组件、
需要时能查到机制与扩展点。**不写发版内容。**

## 重写原则（硬约束）

1. **从零设计目录**：不沿用当前章节顺序；先写读者路径，再决定章节。
2. **三层阅读路径**：
   - 5 分钟：安装 + 最小可运行示例 + 库的定位；
   - 30 分钟：按任务选组件、看交互模型、改主题；
   - 深入：机制、扩展点、契约与边界。
3. **一篇一个中心问题**：README 是入口，不是手册；DESIGN 讲“为什么这样工作”；COMPONENTS 讲“用哪个、
   怎么用”；CONTRACT 讲“不可协商的规则”；CONTRIBUTING 讲“怎么改、怎么发”。
4. **一个概念只定义一次**：其他地方链接过去，不复制。删除重复的层数/导出表/组件列表/键位说明。
5. **统一模板**：每个组件固定 `purpose → signature → verbs → result → protocols → notes`；
   参考数据用表，不用长段落；每个概念给一个可运行示例。
6. **删掉历史包袱**：不写“曾经如何”“旧名是”“参见某个 spec”；历史只留在 CHANGELOG/release notes（W8）。
7. **面向新读者**：先给心智模型，再给细节；术语首次出现时解释；不假设读者读过旧文档。
8. **可验证**：README 代码块由测试执行；文档中的组件/层/导出名由测试或 grep 校验。
9. **语言**：公开文档保持英文（与 PyPI/仓库一致）；给用户的汇报用中文。

## 不做什么

- 不在旧章节上做逐句修补；不保留只为“兼容旧目录”而存在的段落。
- 不写版本号、release notes、迁移指南或“1.1 → 1.2”对比（W8）。
- 不复制 `docs/CONTRACT.md` 的规范正文到 README/DESIGN；只链接。
- 不引入新依赖，不改库代码。

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

## 文档结构（目标，允许在动笔时继续优化）

### README.md（入口，10 分钟读完）

1. 一句话定位 + 三个卖点。
2. Install。
3. Quickstart：一个最小可运行 app（Button + Input + FocusManager + Pointer），标注每一行在做什么。
4. The 60-second mental model：document of blocks + viewport + frame + interaction tiers（一张小图/表）。
5. Features：按能力分组，每组 2–4 条，不按文件罗列。
6. Components：按 Text / Forms / Data / Layout / Actions / Overlays 分组的表，每行一个组件 + 一句用途。
7. Interactions：每 tier 一行 + 最小挂载代码。
8. Styling：Theme/Style/RowBands/glyphs，一个 `replace` 示例。
9. Markdown + syntax。
10. Keys & keymaps。
11. Demo：新的 master–detail explorer + 三个入口。
12. Docs / Contributing / License。
13. **不写版本号/发布说明**。

### docs/DESIGN.md（机制，按“问题 → 机制 → 取舍”组织）

- The problem: why a full-screen document model, not a widget tree.
- The layers + import table + Host seam.
- Coordinates and hit testing.
- Events and the decoder.
- The driver lifecycle.
- Document/block/Revisioned/caching.
- Viewport and docks.
- Frame composition and overlay layers.
- Painter.
- Selection and focus.
- Value semantics.
- What is deliberately out of scope.
- 每节结尾一句“如果你要扩展 X，改这里”。

### docs/COMPONENTS.md（任务目录，按用户任务分组）

- The 4 protocols in one page: render / controller / result / container; plus Revisioned.
- Driver in call order.
- Catalogue, grouped as above; every entry uses the fixed template.
- RowBands contract.
- Disabled/read-only.
- Containers and `child_at`.
- FocusManager / Pointer / SelectionGesture / Find / Scrollbar / Modal / Palette / Toasts / Tooltip / Stats.
- Command/CommandRegistry, Clipboard.
- Theme fields; glyph vocabulary; keymaps.
- Build-your-own walkthroughs (5 short recipes).
- Testing.

### docs/CONTRACT.md

- Normative, short, linked from README/DESIGN/COMPONENTS.
- Verify against code; no duplication of tutorials.

### CONTRIBUTING.md

- The one-way dependency graph (1.2).
- Gates and how to run them.
- How to add a component/topic.
- Versioning policy + “release waits for the user's test refactor” note.

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
