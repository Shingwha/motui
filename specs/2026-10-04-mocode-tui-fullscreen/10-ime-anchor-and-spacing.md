# Spec W10 · demo 统一边距 + IME 光标锚定（波次 W10，修复单）
> 前置：W9 已合并；深读：`00-overview.md` + `08` + `09`

## 背景（用户 2026-10-04 第四轮真机反馈 + pi 参照图）

1. **每个块的上下应有一行 padding**——pi 参照图里每个逻辑块（user 带/thinking/正文/每个工具块）
   上下都是空行。W9 是手工插 7 个 spacer，不成规则；改为**统一步法**。
2. **流式输出时输入法候选框位置跟着流式文本跑**，不固定在输入框——根因：painter 每帧 diff 后
   光标停留在「最后改写行」（流式文本在屏幕中段），Windows 输入法照着终端光标弹窗。
   修：painter 每帧结束后把光标锚到输入框的光标格（IME 跟位置，与可见性无关）。

## 裁决（lead）

- 边距仍是应用层版式：demo 内统一「每个 transcript 块后跟一个空行 spacer」，
  替换 W9 手工点位；库零改动。
- 光标锚定需要库支持（这是全屏自绘输入框的通用需求，属渲染内核能力）：
  `Input` 暴露光标格几何；`Painter` 支持每帧收尾发锚点转义。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `Input.cursor_position(width) -> tuple[int, int]`（components/input.py）
- 返回光标格在该块渲染结果中的 **(visual_row, col)**：visual_row 是行下标，
  col 是该行内 0 基单元格偏移（visual row 0 含 prompt 前缀宽度，续行按等宽空格占位）。
- 覆盖：空输入（row 0, prompt 宽度处——即反色空格格）、行中/行尾、软换行后的续行、
  超长行 wrap；返回值保证 `0 <= visual_row < len(render(width))` 且 col 在行宽内
  （行满时夹到行尾）。
- `tests/test_components_input.py` 补例：上述各情形 + width 边界。
- 不改任何既有编辑/渲染行为。

### T2 `Painter.set_cursor_anchor(row, col)`（painter.py）
- `set_cursor_anchor(row: int, col: int)`：0 基；flush() 写完 diff 后（live 时）
  追加 `ansi.cursor_position(row + 1, col + 1)`；无 diff 但锚点自上次发射后变过也发
  （内部记 `_anchor` / `_anchor_emitted`）；非 live 一律不发（运行期零写入不变）。
- 锚点越界（row ≥ height 或 col ≥ width）时夹取到屏内；屏尺寸变化不自动清锚点
  （应用负责重算——demo 会）。
- `tests/test_painter.py` 补例：写帧后 output 以锚点 CUP 结尾；零变化帧 + 锚点不变 →
  不重复发；零变化帧 + 锚点变 → 发；非 live → 锚点不出现。

### T3 demo 接线（examples/pi_demo.py）
- **T3a 统一边距**：删掉 W9 的 7 个手工 spacer；改为 `_answer` 内每个 transcript 块
  （user/thinking/Plan/流式 reply/每个 ToolBlock/Table/EditBlock）add 后跟一个
  `tui.add(Text(""))`——即「块 + 空行」均匀节奏；banner 区与 pinned 五件套不加。
- **T3b 光标锚定**：demo 内 `_anchor(tui)`：由 `Input.cursor_position(width)` 取
  (vrow, vcol)，计算 input 块在屏上的起始行 = `height - 3 - (1 if working 槽在显示 else 0)`
  （fixed 尾区自底向上：status、下线、input、[working]、上线），
  `painter.set_cursor_anchor(start + vrow, vcol)`；在 chat 主循环每轮按键处理后、
  working 槽切换（进/出）时、以及首帧后各调一次。
- T3c 门禁：`uv run pytest` 全绿；`python examples/pi_demo.py < /dev/null; echo exit=$?`
  exit 0（贴输出：块间均一空行、无连续双空行）。

## 验收
1. `uv run pytest` → 全绿（贴尾部原文，N ≥ 605）。
2. piped demo exit 0，贴输出确认均匀「块+空行」。
3. `git diff --stat main..HEAD`：`src/mocode_tui/components/input.py`、
   `src/mocode_tui/painter.py`、`tests/test_components_input.py`、`tests/test_painter.py`、
   `examples/pi_demo.py` 五文件。

## 禁触
其余一切文件；不 merge/push/checkout main；不改 spec；sleep 仍只在 example。

## 诚实出口
- 若 anchor 与零字节帧语义冲突无法两全：优先「有写必发锚点 + 锚点变也发」，
  把冲突写报告。
- 真机 IME 跟随属 lead/user 验收（本环境无 console）；实现侧保证锚点转义字节正确即算完成。

## 最终报告格式
工单状态表（T1-T3：commit hash+message+结论）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
