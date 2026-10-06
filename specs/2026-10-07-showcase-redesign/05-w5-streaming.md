# Spec showcase-redesign · W5 流式展品（波次 W5）
> 分支 `sr5-streaming`；前置：**W4 已合并**；深读：`00-overview.md`（设计定稿 D/E 节、决策 D4/D8/D9）、
> `ref/capabilities.md` 第 3 节（流式是第二主角）。
> **最高约束：流式必须"可把玩"（play/pause/step/replay）且 **dump-safe**（非交互路径构造即完整）。**

## 目标

把 `streaming` 展品做成一份 **346 行 fixture 按块流入**的可控展品：单项 `Select` 控制条
（D6 配方）+ 页面内进度/块类型读数；聊天页的回复改用同一套"按块流式"；`--pages` 与 piped 回放
永远 dump 出完整文档。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| 现状流式：`_stream()` 逐行前缀赋值 + `_beat()` 节奏 | `session.py:384-419` |
| `Markdown.text` 是普通属性，改后需 `invalidate()` | `widgets/markdown/component.py` |
| fixture 346 行、每种构造 | `examples/Markdown-Rendering-Test.md` |
| `--pages` 不跑循环/tick（dump-safe 的事实来源） | `examples/demo.py:61-69`、`ref/showcase-audit.md:3` |
| 单项 Select 的 D6 配方（activate → chosen） | `00-overview.md` 决策 D10、`docs/COMPONENTS.md` |
| `PageBody.note`/`Showcase.log` 反馈通道 | W2/W4 落地 |

## 工单（按序执行，每项一个 commit）

### T1 分块器 + Streamer（`content.py` + 新 `streaming.py`）

- `content.py`：`blocks_of(text: str) -> list[str]`——把源文本切成"块"（标题 / 段落 / 围栏代码
  整体 / 表格 / 引用 / 列表组各算一块），块边界按空行与围栏状态判定，**不许把围栏代码切碎**；
  `fixture_text() -> str` 读 `Markdown-Rendering-Test.md`。
- 新 `examples/showcase/streaming.py`：`MarkdownStream` 控制器（页面侧、host 驱动）——
  持有目标 `Markdown` 组件、块列表、游标、状态（`playing/paused/done`）、速度；
  `advance(n)` 追加 n 块、`replay()` 归零重来、`finish()` 一次补全；
  **`interactive=False` 时不启动，页面构造即 `finish()`**（dump-safe）。
- 页面本体：`header("streaming", "一份 346 行的 Markdown，按块流入 —— 可暂停、单步、重播")` +
  `try_line("激活控制条的按钮：play / pause / step / replay / speed")` + 控制条 + 进度行
  （`streaming: 12/48 blocks · paragraph`）+ 被流的 `Markdown` 块 + `api_note`（
  `markdown.text = …` + `tui.invalidate()`、`tui.every(PAGE_TICK, …)` 的节奏）。
- 控制条 = 单项 `Select`，选项固定五项（`▶ play` / `⏸ pause` / `⇥ step` / `⟲ replay` / `× speed`）；
  宿主读 `chosen` → 调用 `MarkdownStream` 对应动作；**禁止**给 Select 加回调。

### T2 页面接线与 `PageBody.tick`

- `PageBeat`：页面通过 `PageBody.tick` 每拍推进（`PAGE_TICK` 已是 0.1s）——按"每拍多少块 × 速度"
  推进；播放到末尾自动 `pause` 并把控制条/进度行更新到 `done`。
- `markdown` 页（W1 起名为 `streaming`）描述最终定稿：`"a 346-line Markdown document, streamed block by block"`。
- 页面在**每次进入**时重播（`show()` 重建页面天然满足；在报告里确认）。

### T3 聊天页复用同一套流式

- `session._stream()` 改为调用分块器：正文按**块**追加（保留原来的观感节奏），thinking 逐词不动；
  聊天页的回复仍写进 `Transcript` 的 `Markdown` 块（`transcript.stream` 思路不变）。
- 验证：探针 —— 一次问答结束后，聊天块文本 == `REPLY_LONG`（逐字符相等），且过程中至少出现过
  3 个不同前缀（证明是"长出来"的）。

### T4 回放、文档与基线

- `script.py`：追加——切到 `/streaming` → 控制条激活 `pause` → 激活 `step` 两次 → 激活 `replay`；
  使 piped 回放覆盖控制条与流式路径。
- `README.md`：`## The demo` 段的 `streaming` 行改成"流式展品"的描述；
  段内加一句"`--pages` 与 piped 路径永远显示完整文档（dump-safe）"。
- `examples/demo.py` docstring 同步（把"streaming"写进三条路的说明）。

## 验收（完成前自测，报告真实输出）

1. `uv run pytest -q` → **一字不变** `948 passed, 1 skipped`。
2. **dump-safe 硬验收**：`demo.py --pages` 的 `/streaming` 页 dump 与"直接渲染 fixture 的静态文本"
   逐行相同（贴对比命令与结论，例如把两侧文本各写临时文件后 `diff`），页头 **12** 个。
3. `demo.py < /dev/null` → exit 0，且 dump 里 `/streaming` 页为完整文档（同上证据）。
4. 流式探针：交互模式探针（monkeypatch `sleep`）——`advance(1)` 后文本严格变长且仍是已知前缀；
   `replay()` 后归零；`pause` 后 tick 不再推进（贴输出）。
5. 聊天复用探针：T3 的前缀计数证据。
6. `framebench` hash 逐字符一致；`test_readme_examples.py` 6 passed；`src/` 零 diff。
7. 真机项（看文档长出来的节奏、控制条手感）**无法执行** → "lead 终验项"。

## 禁触清单

- `src/`（任何文件——尤其 `widgets/markdown/*` 与 `chat/transcript.py`：**复用现有 API，不改库**）
- `examples/showcase/{components,styles,features,chat}.py` 的既有展品内容（`chat.py` 仅允许 docstring/
  展品语法行；流式接线在 session）
- `specs/`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + 页头清单）/
dump-safe 的 diff 证据 / 流式探针输出 / 聊天复用证据 / 偏差与取舍（尤其分块粒度与节奏）/
未决问题 / 真机手测：未执行（lead 终验）。

遇到阻塞（例如分块器会切碎表格、`--pages` 里 streaming 页不完整）：**停下上报，不越界自救**。
