# Spec W13 · demo 增强：流式思考 + 长样例（波次 W13）
> ✅ 2026-10-04 已交付合并。
> 前置：**W12 与 W14 均已合并**（依赖新 Markdown 引擎的流式安全 + 顶部菜单）；深读：`00-overview.md` + `12` + `14`

## 目标

demo 的假回合更像 pi：**thinking 也流式**；示例输出更长、更多样（markdown 富文本样例 +
长工具输出 + diff 表格齐活）。只改 `examples/pi_demo.py`。

## 工单（一个 commit）

### T1 thinking 流式
- `_answer` 的 thinking 从一次性 `Message("thinking", …)` 改为**逐词流式**
  （与 reply 同机制：`Message.text = acc` + `invalidate()` + sleep）。
- thinking 文本也要有变化（不是每次同一句）：准备 2-3 条不同的 thinking 文案轮换。

### T2 更长更多样的示例输出
- **富 turn（首问）**：assistant 回复改为**流式 Markdown**（`Markdown` 组件逐字赋值），
  内容覆盖：一/二级标题、段落（含行内 code/bold/italic/link）、无序+有序嵌套列表、
  引用块、围栏代码块（python/bash）、GFM 表格（含对齐）、分割线——对齐 W12 的标记表；
  总长 ≥ 24 行（wrap 后）。
- **工具块更长**：bash ToolBlock 的假输出加长（多行目录/多环境行 + 计时尾行）；
  codemode 块同样加长；EditBlock 保持 4-6 行。
- **次问（short turn）**：换一条不同风格的短回复（带一个列表或一句话 + 引用），
  与首问观感不同。
- scripted 脚本（`_script()`）可增加第三条提问以展示多样化（c-c 收尾不变）。
- 假调用编排的节奏（sleep 常量）微调以防总时长过短：整体 6-10s 量级。

### T3 门禁
- `uv run pytest` 全绿（不改 tests）；
- `python examples/pi_demo.py < /dev/null; echo exit=$?` exit 0，贴完整输出
  （确认：thinking 流式不炸、markdown 富文本各块型出现、工具块加长、块间空行/带内
  padding 节奏未被破坏）。
- `git diff --stat main..HEAD` 仅 `examples/pi_demo.py`。

## 禁触
其余一切文件；不 merge/push/checkout main；不改 spec；sleep 只在 example。

## 最终报告格式
commit hash+message / 自测真实结论 / 偏差与取舍 / 未决问题。
