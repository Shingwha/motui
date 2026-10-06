✅ 2026-10-06 @ rr/w6-demo

# Spec root-refactor · demo.py + 可观测性 + 收尾（波次 W6）

> 分支 `rr/w6-demo`；前置：W5 已合并（API 面定稿、文档收口）。
> 深读：`specs/2026-10-06-root-refactor/00-overview.md`（总纲，必读）+
> `specs/2026-10-06-root-refactor/ref/audit-keys-api.md`（第 4 节 pi_demo 审计与
> "没展示到的能力"清单）+ 现仓库 `examples/pi_demo.py`（作为驱动模式参考，然后删除）。

## 目标

**用 `examples/demo.py` 取代 `examples/pi_demo.py`**：一个对话式界面，全面展示当前 TUI
库的基础能力（不模仿 pi、不带 pi 包袱），并新增**实时刷新率（FPS）展示**。
配套给 Painter 加帧计数（库的可观测性能力），framebench 门禁改跑 demo，README demo 段落地。
本波是全组唯一允许渲染哈希变化的波次（新 demo = 新基线）。

写入范围（范围外零 diff）：
- `examples/demo.py`（新建）、`examples/pi_demo.py`（删除）、`examples/Markdown-Rendering-Test.md`（保留不动）
- `src/mocode_tui/core/painter.py`（frames 计数）、`tests/test_painter.py`（对应断言）
- `tools/framebench.py`（replay 指向 demo.py；docstring 与 main 输出对齐）
- `README.md`（The demos 段 + Quickstart 的运行命令若有涉及）
- `specs/2026-10-06-root-refactor/ref/demo-hash-baseline.txt`（新基线）

禁触：`src/` 其他一切文件、`tests/` 其他一切、`docs/`、`specs/` 其他文件、pyproject.toml。

## 工单（按序执行，每项一个 commit）

### T1 Painter.frames 计数
- `Painter` 加公开属性 `frames: int`：每次 `paint()` 调用 +1（含无变化的帧——它度量的是
  帧率，不是字节差量）。线程无关（单泵）。
- `tests/test_painter.py` 加断言：连续 paint 后 frames 递增。
- 渲染字节不变（计数器不进任何输出）。

### T2 demo.py 编写（本波主体）
**定位**：库的活门面——"20 行能起对话，600 行见全貌"。对话式界面（用户输入 → 流式回复），
每个能力都有斜杠命令或自然触达。目标 ≤ 600 行（pi_demo 849 行，无包袱应显著更短）。

**必备结构**：
1. `main()`：`sys.stdout.isatty()` 分流——活终端 `asyncio.run(TUI(theme=...).run(chat))`；
   否则 headless 回放（ScriptedKeys 脚本 + dump 最终屏幕，参考 pi_demo._headless）。
2. `chat(tui)` 交互循环（参考 pi_demo:667-781 的骨架，按新契约）：
   - 挂载：`Composer(tui, commands=COMMANDS)`、`Transcript(tui)`、`Scrollbar(tui)`、
     `SelectionGesture(tui, on_end=...)`（OSC52 复制成功 → Toasts 弹一条）、`Toasts(tui)`。
   - dispatch：chrome → overlays → 手势 → palette（`palette.handle(event)` + `palette.chosen`）
     → editor.handle → tab 切焦点 / enter 提交 / c-c 退出。
   - 提交后 `tui.system(...)` 可选、`create_task` 后台流式回复。
3. 伪回复：本地 fake（不联网），流式 Markdown（逐块 append，含代码 fence 触发语法高亮、
   一个 GFM 表格），结束 `handle.seal()`。回复内容自拟（讲"这个 TUI 能做什么"的自述最自然）。
4. **FPS 展示**：`tui.every(0.5, tick)` 里读 `tui.painter.frames`，与上次差值除以间隔，
   写入 `composer.statusline.right`（如 `f"{fps:.1f} fps"`）。流式回复期间帧率可见
   （伪流式每 chunk 间不 sleep——用 `asyncio.sleep(0)` 或极短 sleep？**库与 demo 的 headless
   路径禁 sleep**；活终端的伪流式允许 `await asyncio.sleep(0.02)` 让动画肉眼可见——
   pi_demo 的 _stream 同款；headless 回放路径不得 sleep）。开关命令 `/fps`。

**斜杠命令（全走 SlashPalette）**：
- `/help` — 命令列表（Message 或 system 行）
- `/components` — 组件全家桶渲染进 transcript：Table（带样式单元格）、Tree（含展开态）、
  Tabs、Panel（嵌 Text）、Row/Column 组合、ProgressBar（几档 fraction）、Spinner 快照
  （frame+text 手拼一行，展示 Spinner 用法）、Select/Confirm（静态展示含选中态）、
  Input（静态展示）、Notice、Divider、Spacer/Padding——**audit C §4 的"没展示"清单逐项
  销账**（Tree/Tabs/Panel/Row/Column/ProgressBar/Select/Confirm/Input/Autocomplete 经
  /components 或 palette 本身覆盖）。
- `/md` — 渲染 `examples/Markdown-Rendering-Test.md` 全文为 sealed Markdown 块
  （文件保留不动，读法参考 pi_demo）。
- `/split` — `tui.split("vertical", ratios=(2, 1))`：右栏开"组件预览"（几个组件实时渲染 +
  自己的滚轮可滚）；再次 `/split` 或 `/close` 关闭右栏（`Pane.close()`）。tab/点击切焦点。
- `/theme` — 循环切换两三套 `dataclasses.replace(DEFAULT_THEME, accent=..., heading=...)`
  主题；替换后重建 Composer 或按现状可行的方式重刷（若整组件重刷代价大，就换 banner/
  Divider/Notice 这类轻组件的颜色 + 报告说明边界——**以诚实展示"replace 主题"为目标，
  不追求全局热切换的假象**）。
- `/fps` — FPS 显示开关。
- `/clear` — `transcript.clear()`。

**验收要点（写进测试外，demo 内部自查）**：
- `uv run python examples/demo.py < /dev/null` 退出码 0，输出最终屏幕纯文本，
  其中可见：banner、对话轮次、组件样例、状态行（含 fps 数字或 fps 关闭态）。
- headless 回放脚本覆盖：help → 一轮对话 → /components → /md → /split → tab → /close →
  /theme → /fps → /clear → 退出。

### T3 删 pi_demo + framebench 迁移
- 删 `examples/pi_demo.py`（git rm）。
- `tools/framebench.py`：`replay_workload` 子进程改跑 `examples/demo.py`；
  docstring 的测量项清单与 main 输出对齐（6 项如实列出）；其余逻辑不动。
- 跑通后把新 `render-hash` 与各耗时记录到
  `specs/2026-10-06-root-refactor/ref/demo-hash-baseline.txt`（格式仿 render-hash-baseline.txt，
  注明"demo.py replaces pi_demo.py; new baseline"）。

### T4 README demo 段落地
- "The demos" 段（W5 留白处）写 demo.py：一句话定位、能力清单（与 /help 一致）、
  运行方式 `uv run python examples/demo.py`、piped 冒烟 `uv run python examples/demo.py < /dev/null`。
- README 其他段落若引用 pi_demo（grep 确认 W5 已清）——核对清零。
- Quickstart 的运行提示若有 `python examples/pi_demo.py` 字样，改 demo.py。

### T5 终验预备
- `uv run pytest -q` 全绿；`uv run python tools/framebench.py` 正常输出（哈希为新基线，
  **写入 ref/demo-hash-baseline.txt**）；
- `uv run python -m compileall src examples -q` 通过（语法兜底）。
- 报告里给出 demo.py 的行数、命令清单、headless dump 的前 20 行（证明对话轮次存在）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 零失败。
2. `uv run python tools/framebench.py` 正常完成，`render-hash` 与 ref/demo-hash-baseline.txt
   记录值一致。
3. `uv run python examples/demo.py < /dev/null` 退出码 0，dump 含对话与组件内容。
4. `test -f examples/pi_demo.py && echo FAIL || echo OK`（已删）。
5. `grep -rn "pi_demo\|pi-style\|pi rhythm" README.md docs/ src/ examples/` 零命中
   （库与文档去 pi 化完成）。
6. demo headless 脚本回放的 dump 中肉眼可核对：fps 字样出现（/fps 开启段）、
   Table/Tree/Tabs/Panel 内容出现。

## 禁触清单

见上。特别地：`src/mocode_tui/` 除 painter.py 一文件外不动；W1–W5 建立的一切 API 名
不再改动（发现问题的唯一出口是报告）。

## 最终报告格式

工单状态表（T1–T5）/ commit 清单 / 自测真实结论（六条命令输出摘要）/ demo 命令清单与
行数 / 新基线哈希 / 偏差与取舍（/theme 的切换边界、伪流式的 sleep 说明）/ 未决问题。
阻塞即停：报告阻塞点后停止，不越界自救。
