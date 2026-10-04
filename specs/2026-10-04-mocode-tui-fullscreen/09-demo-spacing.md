# Spec W9 · demo 间距与输入框占位符（波次 W9，修复单）
> 前置：W8 已合并；深读：`00-overview.md` + `08-demo-ux-fixes.md`

## 背景（用户 2026-10-04 第三轮真机反馈 + pi 参照图）

两件事：
1. pi 界面在**逻辑块之间有一空行**：user 色带 → 空行 → thinking（斜体）→ 空行 →
   正文 → 空行 → 工具块 → 空行 → 工具块……本 demo 的块目前紧贴无间距。
2. 输入框里的 placeholder「Ask mocode-tui… (/menu commands, Ctrl-C quit)」要去掉：
   pi 的空输入框只有光标；placeholder API 保留供后续使用，demo 不再显示。

## 裁决（lead）

间距是应用层版式，不是库行为：库的契约是「块渲染几行就画几行」，
应用用 spacer 块（`Text("")`，渲染一个空行）自控节奏——与 pi 的做法一致。
placeholder 同理：demo 传空串即可，`Input` 的 placeholder 参数与渲染路径不动。
**两件都不改库**，只改 demo。

## 工单（examples/pi_demo.py，一个 commit）

### T1 turn 内间距
`_answer` 的块序列按 pi 参照加空行（每个位置一个 `tui.add(Text(""))` spacer）：
- turn 起始（user 消息之前）——让上一轮的结尾与新一轮 user 带有分隔；
- user 消息之后、thinking 之前；
- thinking 之后、`Plan`/流式回复之前；
- 流式回复结束后、第一个工具块之前；
- bash ToolBlock 与 codemode ToolBlock 之间；
- codemode 与 Table 之间、Table 与 EditBlock 之间。

### T2 输入框 placeholder 置空
`_build_footer` 里 `Input(placeholder=...)` 改为不传 placeholder（或空串）；
输入框空闲时只有 prompt + 光标块，与 pi 一致。`Input` 组件零改动。

### T3 不破坏既有结构
- banner 区已有空行，不动；固定尾区五件套（footer-top/working/input/footer-bottom/footer-status）不加空行；
- W8 的后台 turn / spinner / 盒子行为零变化；piped dump 的尾部空行修剪逻辑不受影响（spacer 在中间，不在尾部）。

### T4 门禁
- `uv run pytest` 全绿（不改 tests）；
- `python examples/pi_demo.py < /dev/null; echo exit=$?` exit 0，贴输出，肉眼确认：
  user 带与 thinking 之间、thinking 与 Plan 之间、回复与 `$ echo` 之间、两个工具块之间、Table 前后均有空行；
  末行输入框只有 `❮` + 光标（无 placeholder 文本）；
- `git diff --stat main..HEAD` 仅 `examples/pi_demo.py`。

## 禁触

其余一切文件；不 merge/push/checkout main；不改 spec。sleep 仍只许在 example。

## 报告格式

commit hash+message / 自测真实结论（命令原文）/ 偏差与取舍 / 未决问题。
