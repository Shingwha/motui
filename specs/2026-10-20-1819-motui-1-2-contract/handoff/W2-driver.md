# W2 handoff · driver 生命周期、坐标与 pane/dock
## A · 交付
分支 `w2-driver`，8 个实现 commit + 本 handoff：

| commit | 内容 |
|---|---|
| `a9d5167` | T1：`exit`/`run_session`/`run_async`/`run`、每次 run 重置、owned source、pump 唤醒修复、`refresh`、只读 `screen/document/viewport` |
| `99eff17` | T2：`Hit(pane,block,row,col,leaf,leaf_row,leaf_col)`、`hit`/`hit_leaf`/`pane_at`、严格边界、inner-rect 列、`FrameTable.resolve` 不 snap |
| `755a369` | T3：`Pane.add/get/remove`、`TUI.pane`、`add(pane=)`、全 pane 搜索/歧义报错、全局 block id、单调 pane id、嵌套 close、`split(pane=)` |
| `64a2da5` | T4：`Frame._docks`/`set_dock/dock/docks`、`TUI.dock/undock/dock_region`、top+bottom、空 dock 无行、`RowRange`/`visible_range`/`viewport_start`、`body_rows` |
| `2c7bcd3` | T5：`Frame.on_change` 自动 `refresh` |
| `38b7071` | T6：`Screen.copy_to_clipboard`（flush）、`size`/`encoding`/`close`、gesture 调用点 |
| `8dfa7e1` | T7：全仓迁移、README/DESIGN/COMPONENTS、验收测试 |
| `9657e82` | 文档/类型收尾 |

公开签名（新增/变更）：

```python
tui.read_event() -> Event | None       # exit() 可立即唤醒并返回 None
tui.exit() -> None; tui.refresh() -> None
async tui.run_session(body); async tui.run_async(); tui.run()
tui.hit(x, y) -> Hit | None            # Hit(pane, block, row, col, leaf, leaf_row, leaf_col)
tui.hit_leaf(x, y) -> (Component, row, col) | None
tui.pane_at(x, y) -> Pane | None; tui.pane(id) -> Pane
tui.add(component, *, id=None, pin=None, pane=None); tui.split(orientation, *, ..., pane=None)
tui.dock(viewport, *, edge="bottom", size=None) -> Pane; tui.undock(edge) -> Pane | None
tui.dock_region(edge) -> Rect | None; tui.visible_range(pane=None) -> RowRange | None
Pane.add/get/remove; Frame.set_dock/dock/docks/on_change/next_pane_id/is_dock
Frame.retile(rect, *, docks: Mapping[str, Rect | None] | None = None)
Screen.copy_to_clipboard(text); Screen.size / encoding / close; ScreenLayout(body_rows, viewport_start)
```

删除：`stop`、`invalidate`、`run(body)`、`hit_test`、`hit_component`、`focus_at`、`add_band`、
`remove_band`、`TUI.band`、`TUI.viewport_rows`、`Frame.band/set_band`、`Screen.copy`、
`Hit(block,row,col,pane_id)`。无 alias / re-export。

基线真实结果（HEAD，Windows）：

- `uv sync --locked`：Resolved 11 / Checked 10。
- `uv run pytest -q -p no:cacheprovider`：**1733 passed, 2 skipped**（+14 新用例；两个 POSIX-only 仍 skip）。
- `uv run python tools/golden.py --check`：`golden: 11 pages match`。
- `uv run python tools/framebench.py`：render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（未变）。
- `python -m motui < /dev/null`：exit 0，70 行；`python -m motui --pages`：exit 0，792 行。
- 验收 grep（`hit_test|hit_component|focus_at|add_band|remove_band|viewport_rows|invalidate(|.stop(`）：
  0 命中；`import motui, motui.kernel, motui.keys, motui.widgets, motui.interaction` 通过。

## B · 偏差、踩坑与约束
- `ScreenLayout.viewport_rows` 字段也改名 `body_rows`（验收 grep 要求子串零命中），并加
  `viewport_start`（pane rows 内的 body 起点）。
- `exit()` 置位当前 `_exit_event`，不替换新 Event：替换会挂死等待旧 event 的 `read_event()`；
  每次 run 开始才新建。teardown 关闭 owned source 后把 `self.keys` 置回 `None`（工单只说
  `_owned_source=None`），否则第二次 run 复用已关闭 source、永远 EOF。
- `_pump` 先 clear 再 `tick`；`_wake()` 保护已关闭 loop（headless demo 在 `asyncio.run` 结束后
  `tooltip.detach()` → `on_change` → 旧 loop，曾直接炸掉 `python -m motui < /dev/null`）。
- `Frame.retile(docks=None)` 把 dock 放到 0×0 而不注销（`undock` 仍拿得回）；`_regions` 跳过
  空 Rect，因此没有幽灵行。top+bottom 各自 clamp 后，bottom 再 clamp 到 `height-top_h` 防止重叠
  （工单只写了各自 clamp）。
- `hit()` 对 chrome 列返回 `None`（`col` 相对 inner rect，chrome 无合法 block 坐标）；dock 行可命中。
  dock id 用 frame 的 `pane-N` 计数器（不是 `"band"`），满足永不复用。
- `Painter.reset()` 每次 run 都调用（含 non-live）；non-live dump 不受影响。`Pane` 仍是 frozen
  dataclass（D7 归 W3），W2 只加委托方法。
- 下一波必须遵守：`add` 默认目标是 focused pane，不是 `tui.document`；`frame.pane()` 含 dock，
  `frame.panes` 不含；改 frame 结构后不要额外 `refresh()`；`Screen` 实现必须带
  `size`/`encoding`/`close`/`copy_to_clipboard`。
- 未决：`run_async` 只由 `exit()` 结束（无 body）；dock 只支持 top/bottom；`Hit.leaf` 在命中时
  总是 descend 后的组件。

## C · 关键位置与稳定区
- driver：`src/motui/app.py:130`（RowRange）、`:138`（Hit）、`:432`（pane）、`:476`（add）、
  `:747`（visible_range）、`:775`（dock）、`:831`（_retile）、`:996`（read_event）、
  `:1073`（exit）、`:1088`（hit）、`:1318`（run_session）、`:1354`（run_async）、`:1374`（run）。
- frame/pane：`src/motui/kernel/frame.py:372`（Pane facade）、`:478`（split id）、`:540`（close
  子树）、`:1033`（_touch/on_change）、`:1096`（docks）、`:1205`（retile）、`:1379`（_regions）。
- layout：`src/motui/kernel/viewport.py:35`（ScreenLayout）、`:77`（body_rows）、`:84`（viewport_start）。
- screen：`src/motui/kernel/screen.py:91/218/351`（copy_to_clipboard）、`:100/241/368`（close）。
- 测试入口：`tests/test_app.py`、`tests/test_frame.py`、`tests/test_viewport.py`、
  `tests/test_screen.py`、`tests/test_gesture.py`。
- 未触碰：`kernel/events.py`、`keys/**`、`widgets/markdown/**`、widgets 渲染逻辑、interaction 的
  selection/modal/overlay 策略、`tests/golden/**`、`pyproject.toml`、`uv.lock`。
