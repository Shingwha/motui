# Spec W8 · demo 体验修复（波次 W8，修复单）
> ✅ 2026-10-04 已交付合并（A: wfs8a-demo-ux / B: wfs8b-tool-palette）；605 passed + 2 skipped；A 修实时输入+盒子尾区+动画 spinner，B 修 ToolBlock 配色。

## 背景（用户两轮真机反馈，2026-10-04）

用户在 PowerShell 真机跑 `examples/pi_demo.py`，反馈四点 + 一张 pi 参照图：

1. **流式出字时下面打字不能实时预览**——demo 的 `_answer` 阻塞在 chat 主循环里，
   `read_key` 停摆，键入无法上屏。
2. **配色优化**——白色字打满绿底的 ToolBlock 过于刺眼（用户截图里 tool 色带是亮绿）。
3. **spinner 有点问题**——当前 "⋮ Working" 是静态文本，不是动画。
4. **Working 状态应放在输入框内；输入框是上下两条线的盒子**（pi 参照图：
   盒内 = Working 行（工作时）+ 输入行；空闲时只有输入行）。

## 目标

修好 demo 的实时输入体验与视觉：输入后台化、输入框盒子化 + 内置 Working 动画、
ToolBlock 配色降燥。最高约束：库的组件协议与驱动行为零变化（除 T4 的常量配色）；
pytest 全绿；piped demo exit 0。

## 工单 A · demo（examples/pi_demo.py，一个 agent）

### A1 输入实时预览（架构修复）
- `_answer` 改为**后台任务**：`asyncio.create_task(...)`，chat 主循环继续
  `read_key()` + `invalidate()`，键入即时进 Input、pump 30ms 节流刷帧。
- Enter 提交即时清空输入框并可见；turn 进行中再回车 = 再起一个并发 turn
  （各自写各自的块；demo 不要求串行，但不允许块交叉错位到别的 turn 里——
  每个 turn 的块在创建时连续追加即可）。
- 流式逐词逻辑不变（仍是 `Message` + `invalidate` + sleep；sleep 只许在 example）。

### A2 输入框盒子化
- 固定尾区（pinned，文档序即屏序）改为：
  `footer-top`（蓝色 Divider）→ `working`（占位块，见 A3）→ `input`（Input）→
  `footer-bottom`（蓝色 Divider）→ `footer-status`（双侧状态栏）。
- 空闲时 `working` 渲染 **0 行**（demo 内置 `_Nothing` 组件：`render(width) -> []`），
  盒子 = 上线 + 输入行 + 下线；工作时有 1 行 Working，盒子高一格——与参照图一致，
  禁止用「常驻空行」方案。

### A3 真 Spinner
- `working` 占位块工作期间 `set_component(Spinner("Working", ...))`（braille 帧动画），
  用 `tui.every(0.08, ...)` 驱动 `advance()` + invalidate；工作结束 `set_component` 回
  `_Nothing()` 并取消 every 句柄。
- 工作时段定义：turn 的工具调用阶段（流式回复之后、ToolBlock/Table/EditBlock 期间），
  回复流式期间不显示（文字本身即反馈）。删除静态 "⋮ Working" 文本。

### A4 门禁
- `uv run pytest` 全绿（不改 tests）；`python examples/pi_demo.py < /dev/null; echo exit=$?`
  exit 0；贴输出尾部。
- `git diff --stat main..HEAD` 仅 `examples/pi_demo.py`。

## 工单 B · 配色（src/mocode_tui/components/tools.py，另一个 agent，与 A 并行）

### B1 ToolBlock 降燥
- `TOOL_BG`：`Style(bg="green")` → `Style(bg="bright_black")`（暗灰底；亮绿白字是刺眼源）。
- tool tone 标题段改 `TOOL_BG.merge(SUCCESS).merge(Style(bold=True))` 系（绿色粗体标题），
  body 段落只带 `TOOL_BG`（默认前景），footer 维持暗斜体。
- `CODE_BG` 维持 `bg="black"`（暗终端上已足够subtle，参照图观感）。
- `tests/test_components_tools.py`：更新受影响 SGR 断言（bright_black bg = 100；
  green fg = 32），其余断言不动；行宽/结构/空行省略语义零变化。

### B2 门禁
- `uv run pytest` 全绿（贴尾部）；`git diff --stat main..HEAD` 仅
  `src/mocode_tui/components/tools.py` + `tests/test_components_tools.py`。

## 共同红线

- 不动对方文件（A 只碰 `examples/pi_demo.py`；B 只碰 `components/tools.py` + 其测试）；
  不 merge/push/checkout main；不改 spec；不改库的公开行为（B 仅常量取值）。
- 发现疑似 bug 写报告交 lead，不越界。
