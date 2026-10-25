# W4 · 运行时与调用面

> 上级：`README.md`　依赖：`W3-tree-interaction.md`　下一波：`W5-docs-release.md`
> 状态：ready

## 1. 目标

交付 2.0 的运行时与调用面：

- `TerminalOptions` + `MouseMode`（替代三份开关）；
- `Terminal` / `Runtime` / `Workspace` / `Router` / `App` 拆分；
- 截止时间定时器；
- `Section` 返回类型；
- `Axis` / `Placement`；
- `Command.group` + `bind` + `open_palette(registry)`；
- `take()` / `walk()` 接入；
- `App.every` / `invalidate` / `paint_now`。

## 2. 为什么

- `driver.py` 1,333 行；`App` 14 参数、`TUI` 11、`Screen` 6，开关重复。
- `dispatch` 是 10 层 if 链；`auto=False` 只能整块关。
- `every` 漂移 10–28%；`EveryHandle` 在 `hit.py`。
- `add/get/remove` 返回三种类型；`split("vertical")` 反直觉。
- `Command.keys` 声明了但没接线；`open_palette` 接受 `list[object]`。

## 3. 任务

### 3.1 TerminalOptions / MouseMode

- `terminal/screen.py` 加 `TerminalOptions`、`MouseMode`（W1 已占位）。
- `Terminal` 构造：`Terminal(options)`；`screen` 由 options 造。
- `App.__init__` 删除 `mouse/hover/color_mode/focus_events/sync/keys/screen`，改 `terminal=`。
- `interactive` 由 `terminal.live` + `input` 推导；`headless()` 接管。
- `throttle` 移到 `Runtime`。

### 3.2 拆分 driver

- `app/runtime.py`：clock/timers/invalidate/paint/run_session/teardown。
- `app/workspace.py`：frame/panes/content/split/dock/focus/overlays/mount。
- `app/router.py`：`Handler` + `DEFAULT_HANDLERS`。
- `app/app.py`：组合 + 默认 tiers + `on_start/on_stop`。
- `TUI` 名字删除；`App.tui` 删除；需要底层时用 `app.runtime` / `app.workspace` / `app.terminal`。

### 3.3 定时器

- `next_run += period`；`catch_up="skip"|"coalesce"`；落后上限。
- `EveryHandle` → `runtime.Timer`；`RowRange` → `layout.RowSpan`。
- `advance(dt)` 虚拟时钟。
- 帧预算：`fps`/`frame_budget`；超时丢帧。
- 测试：50ms × 1s 19–20 次。

### 3.4 调用面

- `Workspace.add/get/remove -> Section`；`App.add` 代理。
- `split(axis=Axis.X, weights=(...))`；`dock(placement=Placement.BOTTOM)`；`undock(placement)`。
- `Command` 加 `group`，`kw_only`；`CommandRegistry.bind(app)`；`App.open_palette(registry)`。
- `take()` / `HasResult` / `walk()` 已在 W3；本波接 `App`。
- `App.every/animation/invalidate/paint_now` 代理。

### 3.5 控制器约定

- `Find(host)` / `Tooltip(host)` / `Stats(host)` / `Scrollbar(host, pane=..., axis=...)`。
- `host` 暴露 `frame/pointer/clock`；theme 继承 host。
- 删除 `Scrollbar` 的 `style/thumb_style/track/thumb`。

### 3.6 CLI / demo

- `python -m motui` 使用新 App/TerminalOptions。
- demo 的 `_read_picks` 改用 `walk()`。
- `examples/` 新增 snake/dashboard/wide_table（部分已在 W2/W2.6）。

## 4. 门禁

- 全量 `pytest`；交互行为 1:1；
- 定时器精度测试；
- `App` ≤250 行；`Runtime/Workspace/Terminal` ≤450 行；
- `pyright`（app）0；`lint-imports`；
- `examples/dashboard.py` headless 回放；
- 非 live 0 字节 + dump；
- `api.py --check` 更新。

## 5. 退出条件

- [ ] `TUI` / `App.tui` 不存在；
- [ ] `TerminalOptions`/`MouseMode` 生效；
- [ ] `Section`/`Axis`/`Placement`/`take()`/`walk()` 生效；
- [ ] `Command.group` + `bind` + `open_palette(registry)`；
- [ ] 定时器误差 ≤5%；
- [ ] `dispatch` if 链变成 `DEFAULT_HANDLERS`。

## 6. 回滚

- 3.1/3.2/3.3/3.4 分子任务合并；每子任务一个 PR。
- 拆分 driver 可用“新文件 + 旧 `TUI` 转发”临时桥，但合并前必须删除桥（不留 shim）。

## 7. 交接

`W4-handoff.md`：App 参数表、handler 顺序、定时器实现、Section/Axis/Command 的最终签名、示例状态。
