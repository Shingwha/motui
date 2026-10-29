# W4b 交接包

> 分支 `w2.1.2-w4b-choice-nav` / 起点 main @ `ccf1c08`（W4a + spec）/ 2026-10-29

## A. 自动事实（命令与代码生成）

`git log --oneline main..HEAD`（6 个 commit）：

```
a9d2eaf w4b: lock the choice and navigation contract matrix
c7160d0 w4b: rename the tree fold state to open under the shared cursor
e3837ae w4b: put the data views on the shared cursor and rows-first tables
d629f8e w4b: move the nav rail onto the shared cursor
3394f6a w4b: put the choice family on the shared cursor and open state
2f46dc1 w4b: move the label strips onto the shared cursor
```

`git diff --stat main...HEAD`：28 files changed, 1244 insertions(+), 1341
deletions(-)。写入范围的 10 个源文件全部迁移；新增
`tests/widgets/test_contract_choice_nav.py`（53 用例）。

门禁（真实输出）：`pytest -q -p no:cacheprovider` **1790 passed, 1 failed**
（唯一失败 `tests/testing/test_api_tool.py::test_check_accepts_the_recorded_surface`，
它跑 `api.py --check`，快照由 lead 在 W8 更新）；`semantic.py --check`
`9 scenes match`；framebench render-hash
`e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da` 不变；
`ruff check .` 与 28 个改动文件的 no-exclude ruff 全绿；`pyright` 0 errors；
`lint-imports` 5 kept；`api.py --check` 12 个 shape 变化（Select/Table/Tree/
CheckboxGroup/ComboBox/ContextMenu/RadioGroup/Tabs/TreeNode 及 facade 镜像）。

**偏差（必读）**：为让 T3 的 `Table(rows, headers=...)` 与全量门禁同时成立，
机械更新了写入范围外、其中两个在禁触清单里的调用点：
`src/motui/widgets/markdown/tables.py`（仅 Table 调用 + ruff 排序 import）、
`tools/framebench.py`（仅 Table 调用）；另有 `demo/sections/layout.py`、
`dashboard.py`、`tests/demo/test_scenes.py`、`tests/widgets/test_action.py`、
`test_invalidation.py` 的调用点，以及 `tests/widgets/test_contracts.py` 的
`_pick_combo` 一行（`combo.open()` → `combo.open = True`，T2 要求查全仓调用点）。
其余禁触文件零 diff；`base.py` 未改。若不接受这两个禁触 diff，需回退并同步
调整 W4c/W8 的调用点计划。

## B. 只存在于脑子里的东西
1. **Table fresh 语义**：`index` 读 `0`、`selected` 读第 0 行；是否画 cursor
   band 由 `_cursor_armed` 决定。`select/move/home/end/on_click/index setter`
   先 `_arm()`（首次 arm 会 `touch()`，保证 memo 重建）；`activate` 要求
   armed。行是构造时的副本，`take()` 返回 `table.rows[index]`。
2. **Select.take 返回 Option（已被 lead 修正）**：原实现让 `Select.take()`
   返回 Option，以迁就 `CommandPalette`；lead 按 interfaces §5 改为返回
   option 的 value（`_chosen_of` → `_option_value`），并同步
   `command_palette.py` 与相关断言。RadioGroup 的 take 本来就是 value；
   `selected` 一律 Option。
3. **ComboBox** 改为 `ResultWidget`；`open` 是可读写 property（`_open`），
   setter 打开时清 pick + 重算窗口 + `set_query`，关闭只隐藏（不吞掉刚 emit
   的 pick）。`toggle()` 恒 True；`activate()` 关闭时打开、打开时 `_take()`。
4. **构造器 index 不走 select**：Tabs/MenuBar/NavList/RadioGroup/
   CheckboxGroup 用 `_sync_cursor(); _cursor.index = clamp(index)` 安装初始
   index，保留“显式 disabled index 保留 / 初始化不清 pending”；之后的
   `index =` 委托 `select()`，拒绝 disabled。
5. **移动清 pending 由基类完成**；只有 `activate/toggle` 写结果。List/Table
   的 `toggle` 不 emit；MultiSelect/CheckboxGroup 用 `_sync_result()`（空集合
   `_clear_result()`，不是 `_emit(None)`）。
6. **Tree**：三个钩子各自调 `_visible()`；`activate` 翻 `open` 后 emit node，
   `toggle` 只翻；`on_action` 覆盖 `open/close` 后委托基类；`filter` 用
   `_cursor.index = 0`；`left/right` 是 close/open，`enter` 不在组件 keymap。
7. **page 步长**：Select `min(size,max_rows)`，List `min(size,window)`；其余
   默认整段。ContextMenu 无 `**kwargs`，显式签名，内部 `window=False`。
8. 新契约测试覆盖：签名矩阵（唯一位置参数、keyword-only、
   glyphs<theme<styles）、能力、index/selected、disabled、动词/take、
   CURSOR_KEYMAP、Tree 折叠、ComboBox open、fresh Table band、page、click
   不写 pick。

## C. 指针

- 基类（未改）：`widgets/base.py` `CursorWidget`/`ResultWidget`/`CURSOR_KEYMAP`。
- 家族：`strip.py` 钩子；`tabs.py`/`menubar.py`/`navlist.py` activate；
  `choice.py` 钩子 + `_chosen_of` + `_sync_result`；`combobox.py` open property；
  `list.py`/`table.py` `_entry_*` + `_cursor_armed`；`tree.py` `_visible`。
- 测试：`tests/widgets/test_contract_choice_nav.py`；各 family 文件已按新语义
  更新。W4c 注意：不要再引用 `commit`/`is_open`/`labels`/`root_nodes`/
  `expanded`；Table 构造用 `Table(rows, headers=...)`。
- 未决：`tools/api-2.1.txt` 由 lead 在 W8 更新；更新前
  `tests/testing/test_api_tool.py` 保持 1 失败是预期状态。
