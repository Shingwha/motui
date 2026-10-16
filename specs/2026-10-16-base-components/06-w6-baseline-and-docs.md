# Spec base-components · W6 基线重录与收尾（波次 W6）
> ✅ 已合并 2026-10-16 @ `bc6-final`（tip `71f1f5e`）→ main `40a0ffb`；985 passed，hash 未变（注记已写）。
> 分支 `bc6-final`；前置：W5（及追加波 W5b）。深读：`00-overview.md`（门禁、全局不变量 3/4/5）。
> **最高约束：本波只做「基线重录 + 文档终稿 + 残留清零 + 状态登记」。任何行为/API 变化都属上波遗漏，
> 停下上报。**

## 目标

1. `tools/framebench.py` 的 `render-hash` 按 W1–W5 后的真实渲染重录基线，并说明为什么变。
2. README / DESIGN / COMPONENTS 全量终稿；`git grep` 旧名/chat 零残留。
3. 全门禁一次跑通；`specs/2026-10-16-base-components/00-overview.md` 头部标记全组合并。
4. 真机手测清单收敛到最终版本（交用户/lead 执行）。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| render-hash 工作负载与打印 | `tools/framebench.py`（`hash_workload` / `hash_line`） |
| 基线引用位置 | `specs/2026-10-07-*` 与 perf 组的 spec（本波只在本组记录新值） |
| 门禁命令 | 本文件 `00-overview.md` 的「门禁」节 |
| spec 状态写法先例 | `specs/2026-10-07-showcase-redesign/00-overview.md` 头部（✅ 已合并） |

## 工单（按序执行，每项一个 commit）

### T1 `framebench` 基线

- 跑 `uv run python tools/framebench.py`，记录**当前** `render-hash`。
- 在 `tools/framebench.py` 的 docstring 或紧邻 `hash_workload` 处写一条**变更说明注释**：
  本组为什么动了渲染字节（chat 组件删除、`Theme` band 字段收敛、`Palette`/`StatusLine` 迁移、
  新原语、demo 重建），以及新基线值。
- 若 `render-hash` **未变**：同样记录「未变」并说明为什么（可能 hash 工作负载只覆盖
  `Markdown`+`Scrollbar`+split，与 chat 无关）——如实报告，不伪造。
- 验证：重复跑两次 hash 相同（确定性）。

### T2 文档终稿扫描

- `README.md`：库章节（W4）与 demo 段（W5）接缝处通读一遍，确认：
  - Quickstart 代码块可执行；
  - 组件表无 chat 名、含 `Button`/`Checkbox`/`Link`/`Palette`/`StatusLine`；
  - 键位段用 `EDITOR_SUBMIT_KEYMAP`；
  - Package layout 无 `chat/`，含 `pointer.py`；
  - 「What lives where」表无 `mocode_tui.chat`。
- `docs/DESIGN.md`：hover 节、四层图、命名表、`Deliberately out of scope` 全部与新代码一致；
  不再出现 `Composer`/`Transcript`（除历史决策的明确引用，若有则标注为历史）。
- `docs/COMPONENTS.md`：交互表、组件目录、focus/pointer 段、app recipe 小节齐全；
  每个文档里出现的名字都能在源码 grep 到。
- `examples/demo.py` docstring 与 README demo 段一致。
- 验证：`git grep` 清单（见验收 3）。

### T3 残留与全门禁

- 跑全门禁（`00-overview.md` 门禁节的每一条），贴真实输出。
- `git grep -n "COMPOSER_KEYMAP\|mocode_tui.chat\|SlashPalette\|ToolBlock\|EditBlock\|StreamHandle"`
  全仓（含 docs/README）应为空；`Composer`/`Transcript`/`Message` 只允许出现在本 spec 与历史 spec 里。
- 确认 `examples/showcase/` 已不存在、`examples/gallery/` 存在。

### T4 spec 状态与手测清单

- 在 `specs/2026-10-16-base-components/00-overview.md` 头部加 ✅ 全组合并标记
  （格式照 `specs/2026-10-07-showcase-redesign/00-overview.md`），并列出各波分支名与合并事实。
- 把本组「交付后手测清单」重排为最终版（真机可执行、顺序化、含预期结果），留在总纲末节。
- 各波工单头部加「✅ 已合并」状态（若 lead 已合并）。

## 验收（完成前自测，报告真实输出）

1. 全门禁逐条命令 + 关键输出行：
   - `uv run pytest -q` → 数字；
   - `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；
   - `uv run python examples/demo.py --pages` → 12 页头；
   - `uv run python tools/framebench.py` → 新 hash（与说明一致）；
   - `uv run python -c "import mocode_tui"` → exit 0；
   - `uv run pytest tests/test_readme_examples.py -q` → 通过数。
2. `framebench` 两次 hash 相同（确定性证据）。
3. 零残留清单：
   `git grep -n "COMPOSER_KEYMAP\|mocode_tui.chat\|SlashPalette\|ToolBlock\|EditBlock\|StreamHandle" -- . ':!specs'`
   → 空。
4. 文档名字可解析：对 DESIGN/COMPONENTS 里提到的每个公开名做一次 `python -c "import mocode_tui; ..."`
   抽查（或 grep 源码），报告的失败项必须为 0。
5. 真机手测清单已更新，条目可执行且带预期结果。

## 禁触清单

- `src/**`、`tests/**`、`examples/**`（任何代码改动；本波只文档 + 基线注释）
- 其它 spec 组（只登记本组状态）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 全门禁真实输出（逐条）/ `framebench` 新旧 hash 与变更说明 /
零残留清单 / spec 状态更新位置 / 真机手测清单终稿 / 偏差与取舍 / 未决问题。

遇到阻塞（门禁有红、残留无法清零、hash 非确定性）：**停下上报，不越界自救**。
