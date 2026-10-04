# Spec W14 · 顶部固定区 + pi 式菜单（波次 W14）
> ✅ 2026-10-04 已交付合并。
> 前置：W11 已合并；深读：`00-overview.md` + `10`（IME 锚定）

## 背景（用户 2026-10-04 第六轮反馈 + pi 参照图）

pi 的 `/` 菜单是**屏幕顶部通栏面板**（命令紫色 + 描述灰 + `❯` 选中标记），不受滚动位置影响。
现 demo 的菜单是流内块（tail 贴在输入框上方）。用户问「放下方更好还是怎样」——
**lead 裁决：与 pi 对齐，做顶部固定面板**。内核需要与底部 pinned 对称的「顶部固定区」。

## 目标

`Document.add(..., pin=...)` 取代布尔 `pinned`（无兼容垫片——本包未发布，铁律 5）；
`Viewport.layout` 支持 top/bottom 双固定区；`Select` 增 `label_style`；
demo 的 `/menu` 改为顶部通栏面板。最高约束：IME 锚定行为不变（锚点仍在输入框）。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `block.py`：pin 参数（布尔 → 三态）
- `Document.add(component, *, id=None, pin=None)`：`pin ∈ {"top", "bottom", None}`；
  `Block.pin` 属性（`"top"`/`"bottom"`/`None`）。**删除旧 `pinned: bool` 参数**
  （无 shim；同步更新一切调用点：app.py、tests、demo）。
- `tests/test_block.py`：对应改写（含 pin 三态、互斥/重复 id 等旧断言等价迁移）。

### T2 `viewport.py`：双固定区
- `layout(width, height)`：top 区行（pin="top" 按文档序）+ 视口行 + bottom 区行；
  `vh = max(height - top_total - bottom_total, 0)`；任一区超高时的截断规则：
  **bottom 优先保**（状态栏/输入框不能丢），其次 top，视口可空——与现行 bottom 超高
  语义一致地扩展，写进 docstring。
- `tests/test_viewport.py`：top-only / both / 仅 bottom（旧用例等价迁移）/ 双区高度账。

### T3 `Select` 增 `label_style`（components/choice.py）
- `Select(options, *, title="", label_style=NONE, selected_style=..., ...)`：
  未选中行的 label 段用 `label_style`（默认 NONE，行为不变）；选中行仍 marker+selected_style；
  hint 仍 hint_style。
- `tests/test_components_choice.py`：补 label_style 用例；旧用例不变。

### T4 `app.py` 透传 + demo 顶部菜单（examples/pi_demo.py）
- `TUI.add(component, *, id=None, pin=None)` 透传。
- demo：`/menu` 打开时把 `Select(list(_MENU), title="", label_style=柔紫(#bc8cff))`
  以 `pin="top"` 入文档；`↑↓` 移动、Enter/Esc 移除；面板绘制在屏幕顶部通栏
  （由 T2 布局自动完成）；选中项逻辑不变。输入框 IME 锚定不变（锚点仍在 input 行）。
- `tests/test_app.py`：`add(pin=...)` 透传断言；IME 锚定用例保持绿。

### T5 门禁
- `uv run pytest` 全绿（贴尾部，N ≥ 651）；`python examples/pi_demo.py < /dev/null; echo exit=$?`
  exit 0（贴输出：菜单脚本段不炸）。
- `git diff --stat main..HEAD`：`src/mocode_tui/{block,viewport,app}.py`、
  `components/choice.py`、`tests/test_{block,viewport,app,components_choice}.py`、
  `examples/pi_demo.py`。

## 禁触
其余一切文件（markdown/text/table/其他 tests/docs/README/specs 不碰——W12 并行中，
`examples/pi_demo.py` 只许改 menu 组装相关行，**不许**顺手改 demo 其他行为）；
不 merge/push/checkout main；不改 spec。

## 诚实出口
- 双固定区都超高时若 bottom 保住后 top 仍超高：top 截断（视口为空）——docstring 写明。
- `pin` 三态若与既有 `pinned` 语义在测试迁移中产生歧义：以「top/bottom/None」新语义为准，
  旧布尔断言逐个翻译，不许保留布尔参数。

## 最终报告格式
工单状态表（T1-T5）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
