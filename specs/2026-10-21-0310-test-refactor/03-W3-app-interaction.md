# W3 · app + interaction 测试重写

> 分支 `tests-w3-app-interaction`；前置 W0；写入范围 `tests/app/**`、`tests/interaction/**`。

## 目标

把 driver 与交互层的测试重写成**宿主可观察的行为契约**：生命周期、事件路由、命中、坐标、焦点、
指针、拖选、模态栈、overlay、滚动条、命令注册表、Host 协议。
最高约束：**不读私有属性、不测节流内部计时/缓存、不锁完整帧字节**；定时只用 `Clock`；`src/**` 零改动。

## 前置上下文

- 必读顺序：`00-overview.md` → `ref/repo-map.md` → `ref/interfaces.md` §1–§4。
- 基线命令：

```bash
cd C:/Users/shifu/.worktrees/motui/tests-w3-app-interaction
PYTHONPATH=$PWD/src C:/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python.exe \
  -m pytest -q -p no:cacheprovider tests/app tests/interaction
```

（开工时目录未建，先跑全量确认基线。）
- 稳定区：`tests/testing/**`、`src/**`、`tools/**`。
- 已知约束：见 `repo-map.md` §6。

## 工单（按序执行，每项一个 commit）

### T1 建目录与骨架

- `tests/app/__init__.py`、`tests/interaction/__init__.py`；建目标空壳：
  `tests/app/{test_driver,test_hit,test_selection_overlay}.py`、
  `tests/interaction/{test_commands,test_find,test_focus,test_gesture,test_host,test_modal,test_overlays,test_palette,test_pointer,test_scrollbar}.py`。
- 验证：`pytest --collect-only tests/app tests/interaction` 不报错。

### T2 driver（test_app.py 拆分重写）

- `tests/app/test_driver.py`：
  - document facade：add/get/remove/system/pin、split/pane id 唯一性、pane 关闭。
  - scroll/reveal：三种状态、居中、clamp、pinned 区域。
  - `read_event`：scroll keys 吸收、其余返回、无 source/非 live 返回 None。
  - 生命周期：`exit` 立即解除 pending read、`run`/`run_async` 重入、enter/leave bracket、pump 定时
    （用 `Clock`，删 `_last_paint`、throttle 内部断言）。
  - dock：top/bottom 并存、空 dock 不占行、wheel 路由。
  - 非 live dump / snapshot：plain text、footer 顺序、snapshot stanza。
  - 删除：divider 精确 accent 字节、theme divider 内部、focus policy 多样矩阵（保留 1 个替换测试）。
- `tests/app/test_hit.py`：hit/hit_leaf/pane_at、越界 None、pane 内坐标、dock、最后一行窗口行。
- `tests/app/test_selection_overlay.py`：set_selection 标行、scroll 不动 selection、resize 清 selection、
  removed block、painted frame vs document view、theme selection；删 cache/内部 layout 断言。
- 删除旧文件：`tests/test_app.py`。

### T3 焦点 / 指针 / 手势

- `test_focus.py`：注册/循环/wrap/trap 栈/路由顺序（字段 handle → manager 表）/click 首击聚焦二击激活/
  容器内 leaf；删逐动词重复矩阵，收敛为 4–6 个参数化。
- `test_pointer.py`：hover 进入/移动/离开/同格、press+release 派发 leaf、drag 不派发、detach、无
  hover 的 pointer 不碰 flag。
- `test_gesture.py`：press 锚点、拖选范围/反向/跨 block、copy_on_select/OSC52、click 清选择、
  自动滚动（Clock tick 前进/停止/翻转/边界）、双击词/三击行/四击重启、detach/reflow 结束拖拽；
  删 `invalidate exactly once` 之类内部计数。
- 删除旧文件：`tests/test_focus.py`、`tests/test_pointer.py`、`tests/test_gesture.py`。

### T4 模态 / 调色板 / overlay / 滚动条 / 查找

- `test_modal.py`：open/close、scrim/居中/anchor/clip、键盘 body→panel、escape、take_result 一次性、
  focus trap push/pop、两栈恢复；删注册顺序字节。
- `test_palette.py`：query 过滤、导航、enter/escape、清空、detach、modal 集成。
- `test_overlays.py`：
  - Stats：读数、悬停 leaf、pointer 重挂、帧率窗口（Clock）。
  - Toasts：TTL/evict/角/宽度 clamp/点击 dismiss/retile/detach。
  - Tooltip：跟随、翻转、clamp、detach、pointer 重挂。
  - 删逐 corner/逐 narrow 的重复渲染 case，保留语义边界（宽/窄/短/空）。
- `test_scrollbar.py`：strip 几何/thumb、drag 映射、track page 重复、release 停止、detach、retile、
  自定义 glyph；删 memo key/revision 内部。
- `test_find.py`：query 匹配顺序/大小写、enter/up/down wrap、reveal、overlay、detach、宽字符列。
- 删除旧文件：`tests/test_modal.py`、`tests/test_palette.py`、`tests/test_overlays.py`、
  `tests/test_scrollbar.py`、`tests/test_find.py`。

### T5 命令 / Host

- `test_commands.py`：Command 值语义、注册/重复/get/remove、match（大小写/disabled）、by_key、invoke、
  options；删 frozen/slots 内部断言（保留值相等 1 个）。
- `test_host.py`：`TUI` 满足 Host 协议、部分对象拒绝、factory 构建真实控件、copy 委托、root 仍导出
  TUI/FocusManager。
- 删除旧文件：`tests/test_commands.py`、`tests/test_host.py`。

### T6 收口

- 全目录：`pytest -q -p no:cacheprovider tests/app tests/interaction`。
- `grep -R "\._[a-z]" tests/app tests/interaction` 0；`grep -R "sleep("` 0。
- 用例数落在 **150–220**。
- 写 `handoff/W3-app-interaction.md`。

## 验收

1. `tests/app` + `tests/interaction` 全绿，贴数字。
2. 全量 pytest 0 failed。
3. diff 只含 `tests/app/**`、`tests/interaction/**`、删除的旧文件、handoff。
4. 私有属性/sleep grep 为 0。
5. `ref/interfaces.md` §4 的清单逐项覆盖。

## 禁触清单

`src/**`、`tools/**`、`tests/golden/**`、`tests/testing/**`、`tests/__init__.py`、`tests/conftest.py`、
`tests/kernel/**`、`tests/keys/**`、`tests/widgets/**`、根级 `tests/test_*.py`（除删除项）。

## 交接包

分支最后 commit 写 `handoff/W3-app-interaction.md`（A 自动事实 / B 取舍 / C 指针）。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 探索审计 / 未决问题。
