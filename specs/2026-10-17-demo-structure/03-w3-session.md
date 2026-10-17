# Spec demo-structure · W3 session 瘦身与符号锚（波次 W3）

> 分支 `demo3-session`；前置：W2（10 页就位、kit 全覆盖）；深读：`00-overview.md`
> （D4/D5）、`demo/kit.py`、`demo/session.py`、`demo/script.py`。
> **最高约束：session 的页面特例全部删除，留下的每一个分支都必须对"任何页面"成立；
> 行为（按键响应、翻页、换肤、标记、过滤）逐条保持不变。**

## 目标

`session.py` 零页面特例；`script.py` 从手算坐标改为符号锚；每页 hints 生效。

## 工单（按序执行，每项一个 commit）

### T1 session 去特例

- `_read_picks` 完全委托 kit 的解析（W1/W2 已接好）；删除 `BY_NAME` 翻页与
  `THEME_INDEX` 换肤两个特例（翻页/换肤已是页面的 `Action.run`）。
- `_cycle_tree_filter` 改为**通用**形态：`c-t` 的槽位保留在 session，
  实现为「聚焦叶子若有 `filter` 方法 → 用页面提供的下一个查询」——查询序列由
  页面通过 kit 登记（`Exhibit.watch` 或 slot 元数据），页面没有就不响应。
  若此形态在 W2 的实际页面上无法表达，**停下来报告**，不要塞回页名判断。
- `_mark_cursor_row` 已是 `getattr(target, "toggle", None)` 的通用形态，保留；
  确认它对新页面（views/forms）工作。
- `_sync_cursor_shape` / `_modal` / `_retarget_pointer` 检查是否仍需要页名/类型判断：
  `_modal` 从「`body.modal` 且 `is_open`」改为 kit 登记的一致口径（若有差异）。
- `_report` 的调用点全部改结构化（接受 `Pick`）；页面 `note` 的入参统一为 `Pick`。
- 结果：`session.py` 行数下降（目标 ≤ 320 行），且 `grep "BY_NAME\|THEME_INDEX"` 零命中。

### T2 每页 hints

- `session.show()`：打开页面后按 `page.hints` + session 全局键重建 `self.hint_bar`
  （`ShortcutBar`）；`set_theme` 重建时保持当前页的 hints。
- 每页 `hints` 的文案要与该页 TRY 行一致（页面能玩的键都列出来，列不下的删）。
- golden：底部提示条变化必然移动页面 → `--update` 全量重录 + 逐页解释。

### T3 `script.py` 符号锚

- 把 `BUTTON_ROW`/`TASK_BOX`/`PALETTE_CELL`/`COMBO_CELL`/`EDITOR_CELL`/`PROBE_CELL`/
  `ASIDE_CELL`/`TOAST_CORNER` 之类手算坐标，改为**按页面展位解析**：
  `script.py` 只写「第 N 页、展位名 `slot`、行内第几行」，坐标在回放时由
  `Session`/`demo` 侧按当前布局解析（`tui.hit_component` 与展台登记的行号）。
  实现可用一个 `anchor(page, slot, row=0, col=None)` 助手；解析失败要**显式报错**
  （回放输出里指出缺哪个锚），不许静默偏移。
- `tests/test_demo_protocol.py` 对锚点的解析断言随之改为走同一助手（该文件的
  整体重写仍留 W4）。
- 验收：`uv run python -m motui < /dev/null` 的最终 dump 与重录前逐字节一致
  （若脚本路径微调导致 dump 变化，逐条解释）。

## 验收

1. `uv run pytest -q` 全绿
2. `uv run python tools/golden.py --check` → 11 页全等（重录后）
3. `uv run python tools/framebench.py` → hash 逐条解释
4. demo 两入口 exit 0；piped 回放的 dump 与 `--pages` 的页数/内容正常
5. `session.py` 内 `grep -n "BY_NAME\|THEME_INDEX\|isinstance(Tree)"` 零命中

## 禁触清单

`src/motui/{kernel,keys,widgets,interaction,app.py,testing.py}`、`demo/kit.py`（只读）、
`demo/pages/**`（除 hints 元数据与必要的最小适配）、`README.md`、`docs/**`、
`tests/golden/**` 除 `--update` 产物、`specs/**`。

## 最终报告格式

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
