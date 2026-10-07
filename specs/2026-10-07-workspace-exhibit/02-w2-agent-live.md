# Spec workspace-exhibit · W2 agent 视图 live（波次 W2）
> 分支 `ws2-agent-live`；前置：**W1 已合并**；深读：`00-overview.md`（D5 与"扩展点"节）、
> `01-w1-aside.md`（W1 的视图字典与 `sync` 机制）、`ref/workspace-audit.md` 第 7 节（确定性与 dump-safe 的边界）。
> **最高约束：live 只发生在交互模式；非交互路径构造即完整（dump-safe）。切换仍只由 `sync` 驱动。**
> ✅ **2026-10-07 已合并** @ `ws2-agent-live`（agent 视图 live + 重播 + dump-safe；顺带 T4：分屏页 banner 窗口化，
> 窗口条 26 列、短提示 62 列、标题带 `(i/n)`）。

## 目标

把 `/workspace` 右栏的 `agent` 视图从静态变成 **live 子代理消息流**：canned 的 6~8 条消息
（`Message` / `ToolBlock`）按 `tick` 逐条长出，切走再回来重播；`--pages` 与 piped 路径下
**构造即完整**。同时把"真宿主怎么接"的扩展点写进模块 docstring 与 README。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `PageBody.tick`（页面节拍，`tui.every(PAGE_TICK=0.1s)` 驱动；`--pages` 不跑循环 → 无 tick） | `page.py`、`session.py` |
| 流式展品的分块器与"非交互即完整"先例 | `examples/showcase/streaming.py`、`content.py` 的 `blocks_of` |
| W1 的 `VIEWS` 字典与 `sync` 换视图 | `examples/showcase/workspace.py` |
| `Message` / `ToolBlock` 的真实构造 | `examples/showcase/chat.py`、`src/mocode_tui/chat/message.py`、`tools.py` |
| `Transcript.stream` / `StreamHandle`（宿主侧增量思路） | `src/mocode_tui/chat/transcript.py` |

## 工单（按序执行，每项一个 commit）

### T1 `agent` 视图 live 化

- 在 `workspace.py` 里加一个页面侧的小控制器（形态照 `streaming.py` 的 `MarkdownStream`）：
  持有 canned 消息列表（6~8 条，`(kind, text)` 之类的形状）、游标、`playing/done`；
  `advance()` 挂下一条（`Message`/`ToolBlock` 视 kind 而定）；`restart()` 清空重来；
  **非交互构造即 `finish()`**（一次性挂满）。
- 挂载方式：`agent` 视图的内容块是一个 `Column`（或等价的容器）：
  头部是一行进度 `agent: 3/7 messages`（随 tick 更新），其下是已长出的消息块。
  每拍挂一条；挂满后停表并把进度行写成 `done`。
- **确定性边界**：live 只影响 `agent` 视图的**内容**；视图切换仍只由 `sync` 驱动，
  不许让 tick 触发换视图（D4）。
- **重播**：切走再回到 `agent`（`strip.active` 变化 → `sync` 重挂该视图）时从头开始；
  报告里贴"切走再回来 → 进度回到 0/N"的探针输出。
- 验证（探针，逐条贴）：交互模式下 1 拍后进度 `1/7`、3 拍后 `3/7`；`--pages` 的 `/workspace` 段
  `agent` 视图（若它是当前视图）为 `7/7 · done` 或完整内容。

### T2 回放覆盖

- `script()`：在 W1 的 `/workspace` 步骤后追加——切到 `agent` 标签（点或 `←→`），
  让 piped 回放覆盖"进入 live 视图"的路径；dump 里该视图必须是**完整**的（非交互即完成）。
- 复核 piped 墙钟仍 < 2s（不许因为 live 引入 sleep）。

### T3 扩展点文档定稿

- `workspace.py` 模块 docstring 增加"接真 subagent"的一节：拿到消息就
  `append` 到 agent 视图的列表 + `tui.invalidate()`；消息块与 `chat` 层的组件是同一批；
  `Transcript.stream` 的 `StreamHandle` 路子同样适用；**不引入回调/事件总线/异步组件**。
- `README.md` 的 `## The demo` 段：`/workspace` 行补"the right pane's `agent` tab streams a canned
  subagent report -- the hook a real host would feed"；`docs/COMPONENTS.md` 不必动
  （没有新组件），若认为需要一句交叉引用可加一行（并在报告里说明）。

### T4 分屏页的导航条窗口化（lead 裁决，修 W1 上报的几何缺陷）

**问题**（W1 实测）：banner 的三块 pin 在主 document（= 左栏），`/workspace` 分屏后左栏只有
71 内容列，而导航条要 104 列 → 在该页被 `fit` 截断（`interact`/`work`/`stream`/`chat` 点不到），
提示行（97 列）折成两行。框架只有一个**底部** band，没有跨栏区域，banner 无法跨两栏。

**修法（复用库自己的窗口惯例，不发明新组件）**：当当前页 `aside` 非空时，
- 导航条换成**以当前页为中心的 3 标签窗口**（两端夹取：首页给前 3 个、末页给后 3 个），
  仍是同一个 `Tabs` 组件、仍可点；点击映射回真实页号（`PAGES[窗口起点 + tab 下标]`）；
- 提示行换**短版**（≤ 70 列，例：`↑↓/enter: inspector tabs · tab focus · enter sends · c-c quits`，
  把 `click a tab · c-n / c-p exhibits` 交给窗口条与 `/`）；
- 计数放进标题行：`mocode-tui showcase · workspace (12/13)`（沿用 Select 的 `(i/n)` 惯例）；
- 其它页一字不变（全量 13 标签、长提示），`show()` 时按新页重建 banner。
- 验证：`/workspace` 上 `tabs.render(<左栏内容宽>)` 无 `…`、提示行单行；窗口条的三个标签
  点第 2 个 → 打开对应页；`c-n` 翻到下一页后窗口跟着滑；`/chat` 上仍 13 标签。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **948 passed, 1 skipped**（一字不变）。
2. **dump-safe 硬验收**：`demo.py --pages` 的 `/workspace` 段里，`agent` 视图内容**完整**
   （贴`agent: 7/7 · done`或全部消息行的原文）；总行数与基线一并报告。
3. `demo.py < /dev/null` → exit 0，墙钟 < 2s；dump 两栏可见。
4. live 探针：交互模式（monkeypatch `sleep` 或直接驱动 tick）——1/3/N 拍的进度与消息条数；
   切走再回来 → 归零重播；`done` 后不再增长。
5. `framebench` hash 逐字符一致；`test_readme_examples.py` 6 passed；`src/` 零 diff。
6. 真机项（看消息一条条长出来的观感）**无法执行** → "lead 终验项"。

## 禁触清单

- `src/`（任何文件）
- W1 定稿的机制与其它视图：`page.py`、`session.py` 的 aside/sync **机制**（本波只允许改 session 的
  banner 文案层，即 T4 的窗口化）、`tools`/`edits`/`reads` 三个视图的内容
  （本波只动 `workspace.py` 的 agent 视图部分 + banner 文案 + 文档 + 回放）
- `examples/showcase/streaming.py`、`content.py`（流式展品的实现；**可以读、可以借用思路，
  不许为了复用去改它**——若确实要抽公共助手，先上报）
- `specs/`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + 页头数/行数）/ dump-safe 证据 /
live 探针输出（含重播）/ 扩展点文档的落点（贴 docstring 片段）/ **T4 的窗口条与短提示实测**
（`/workspace` 无 `…`、单行；点窗口标签换页；其它页不变）/ 偏差与取舍 / 未决问题 /
真机手测：未执行（lead 终验）。

遇到阻塞（非交互路径下 agent 视图不完整、live 与 `sync` 抢刷新、必须改 `streaming.py` 才能复用）：
**停下上报，不越界自救**。
