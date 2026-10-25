# W4a1 · TerminalOptions / Terminal / 截止时间定时器

> 分支 `2.0/w4a1-terminal`；前置：W3b3b 已合并（`d779b89`）；写入范围：`src/motui/terminal/{screen,terminal,capability}.py`、`src/motui/app/{driver,application}.py`、`tests/terminal/**`、`tests/app/{test_driver,test_app}.py`、`tools/api-2.0.txt`
> 权威：`ref/source/04-runtime.md` §3–5、`08-terminal-io.md` §3–4、`10-waves/W4-runtime-api.md` §3.1/3.3

## 目标

先交付运行时的配置面与节拍，**不拆 TUI、不改行为**：

1. `MouseMode` + `TerminalOptions`（一份终端配置）；
2. `Terminal` 对象：screen、enter/leave、read_event、resize、live、capability、clipboard；
3. 截止时间定时器：`next_run += period`、`catch_up="skip"|"coalesce"`、`Timer`、`advance(dt)`、`animation(hz, draw)`、`invalidate()/paint_now()`；
4. `App(terminal=TerminalOptions(...))` 生效（旧参数暂留，W4b 删除）；
5. 现有 1531 用例、57 byte/semantic、hash 不变；50ms×1s 达到 19–20 次。

**本波结束：TerminalOptions/Terminal/Timer 可用；定时器精度 ≤5%；旧 API 仍工作；字节不变。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W3b3b-interaction.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1531 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `terminal/screen.py`：`TerminalScreen(mouse, paste, hover, focus_events, color_mode)`、`HeadlessScreen` 同；`enable_mouse_tracking(hover=False)` 用 1002/1003。
  - `app/driver.py:TUI.__init__(screen, keys, throttle, interactive, mouse, hover, focus_events, sync, color_mode, theme)`；`TUI.every` 用 `_Every`（`next_run = now + period`，会漂移）；`TUI.tick(now)`。
  - `TUI.clock()` 是可替换 monotonic；测试用 `tests/testing/clock.py`。
  - `App.__init__` 有 `mouse/hover/color_mode/focus_events/sync/keys/screen` 等旧参数。
  - `TUI.run()` 负责 screen.enter/leave、keys attach/close、pump、read_event。
- 设计：
  - `MouseMode(Enum)`: OFF/BUTTON/DRAG/MOVE；映射：
    - OFF → screen mouse=False；
    - BUTTON/DRAG → screen mouse=True、hover=False（当前 1002）；
    - MOVE → screen mouse=True、hover=True（1003）。
  - `TerminalOptions(frozen, kw_only)`: `stream: TextIO|None=None`、`input: EventSource|None=None`、`mouse=MouseMode.MOVE`、`paste=True`、`focus_events=False`、`color_mode="auto"`、`sync=True`、`screen: Screen|None=None`（为 headless/testing 预留；若给定，优先用 screen）。
  - `Terminal(options, *, screen=None)`：
    - 构造/持有 Screen（`options.screen` 或 `screen`；否则 `TerminalScreen` 按 MouseMode 开关）；
    - `enter()/leave()`、`read_event()`（从 input 读；None=EOF）、`refresh_size()/size/live/capability`、`clipboard`（ScreenClipboard）；
    - **不派发、不聚焦、不滚动、不 paint**。
  - `Timer`（`kernel/layout.py`? 运行时值放 `app/runtime.py` 或 `app/driver.py`）：`period`、`fn`、`next_run`、`catch_up`、`cancelled`；`every(period, fn, catch_up="skip")` 创建并加入 `TUI._timers`；`advance(dt)` 只推进虚拟时钟，不 sleep。
  - 定时器算法：
    ```python
    due = now >= timer.next_run
    if due:
        timer.fn()
        if catch_up == "skip":
            timer.next_run += period
            if timer.next_run <= now: timer.next_run = now + period
        else:  # coalesce
            timer.next_run += period
            while timer.next_run <= now: timer.next_run += period
    ```
    `advance(dt)` 让 `clock()` 返回 base+offset；测试用它跑 1s。
  - `TUI.invalidate()` = `refresh()`；`paint_now()` = `paint()`；`animation(hz, draw)` 创建 `every(1/hz, draw)`。
  - `EveryHandle` 保留为 `Timer` 的别名/子类（W4b 删除旧名）。
  - `App(terminal=...)`：若给 terminal，构造 `TUI` 时用其 options；否则保持旧参数路径（兼容）。`App.terminal` 属性暴露 Terminal。
- 已知坑：
  - `TUI.run()` 目前在 enter/leave 里直接操作 `screen`；改成 `Terminal` 后仍要保持字节顺序/0 字节非 live。
  - `TUI.read_event()` 目前直接从 `keys` 读并处理 exit_event；迁到 Terminal 时要保留 exit 语义与 `None`。
  - 定时器测试不能 sleep；用 `advance` + 可注入 `clock`。
  - `EveryHandle.cancelled`/`cancel` 是公开面；`Timer` 保持同名成员。
  - `App` 旧参数（mouse/hover/keys/screen）暂留；若同时给 `terminal=` 和旧参数，`terminal=` 优先（或抛 ValueError；选显式优先并记录）。
  - 57 golden/hash 不能变；`python -m motui` 默认路径必须仍用 MOVE（当前 App hover=True → 1003），否则字节可能变。
- 不改 Workspace/文档/焦点/交互；不删除 TUI（W4a2）。

## 工单（按序，每步一个 commit）

### T1 `MouseMode` / `TerminalOptions`

- `terminal/screen.py`：新增 `MouseMode`、`TerminalOptions`（frozen/slots/kw_only）；`TerminalOptions.screen: Screen|None=None` 作为 testing/headless 入口。
- 映射 helper：`MouseMode -> (mouse: bool, hover: bool)`（可放 `terminal/screen.py` 或 `terminal/terminal.py`）。
- 测试 `tests/terminal/test_screen.py`：枚举值；TerminalOptions 默认；映射表。
- 只允许改：`terminal/screen.py`、`tests/terminal/test_screen.py`。
- 验证：`uv run pytest -q tests/terminal/test_screen.py`。

### T2 `Terminal`

- 新建 `terminal/terminal.py`：
  ```python
  class Terminal:
      def __init__(self, options: TerminalOptions = TerminalOptions(), *, screen: Screen | None = None)
      screen; input; live; size; capability; clipboard
      def enter(); def leave(); async def read_event(); def refresh_size(); def close()
  ```
  - screen 选择：显式 screen > options.screen > TerminalScreen（按 MouseMode）。
  - `read_event()` 从 `options.input` 读；`None` = EOF。
  - `copy_to_clipboard` 通过 `ScreenClipboard`（若 screen 有 copy_to_clipboard）。
- `terminal/__init__.py` 导出 `Terminal`、`TerminalOptions`、`MouseMode`（不出 `ansi`）。
- 测试 `tests/terminal/test_terminal.py`：HeadlessScreen + ScriptedEvents 的 enter/leave/read_event；MouseMode OFF/MOVE 的 screen 开关；clipboard 转发。
- 只允许改：`terminal/terminal.py`、`terminal/__init__.py`、`tests/terminal/test_terminal.py`。
- 验证：`uv run pytest -q tests/terminal/test_terminal.py`。

### T3 定时器

- `app/driver.py`：
  - 新增 `class Timer`（或 `app/timers.py`）：`period/fn/next_run/catch_up/cancelled`；`cancel()`。
  - `TUI.every(period, fn, *, catch_up="skip") -> Timer`；保留 `EveryHandle` 为别名（`EveryHandle = Timer` 或子类）。
  - `TUI._timers: list[Timer]`；`tick(now)` 按截止时间语义触发。
  - `TUI.advance(dt)`：虚拟时钟偏移；`clock()` 返回 `monotonic()+offset`（可注入 `_clock`）。
  - `TUI.animation(hz, draw)`；`TUI.invalidate()`；`TUI.paint_now()`。
- 测试 `tests/app/test_driver.py`：
  - `every(0.05)` + `advance(1.0)` → 19–20 次（误差 ≤5%）；
  - `catch_up="skip"` 与 `"coalesce"` 的错过 tick 行为；
  - `advance` 两次同脚本结果一致；
  - `Timer.cancel` 后不再触发。
- 只允许改：`app/driver.py`、`tests/app/test_driver.py`（可新增 `tests/app/test_timers.py` 并加入允许列表）。
- 验证：`uv run pytest -q tests/app/test_driver.py tests/app/test_timers.py`。

### T4 App/TUI 接入 Terminal

- `app/driver.py`：
  - `TUI.__init__` 增加 `terminal: Terminal | None = None`；若给，`self._terminal=terminal`、`self._screen=terminal.screen`、`self.keys=terminal.input`；enter/leave/read_event 委托 Terminal。
  - 旧参数路径保持：没有 terminal 时按旧方式构造 screen/keys。
  - `TUI.screen`/`read_event` 行为不变（非 live 0 字节）。
- `app/application.py`：
  - `App.__init__` 增加 `terminal: TerminalOptions | None = None`；给定时构造 `Terminal(options)` 并传给 TUI；旧参数暂留。
  - `App.terminal` 属性。
- 测试 `tests/app/test_app.py`、`test_driver.py`：`App(terminal=TerminalOptions(screen=HeadlessScreen(...)))` 可运行；旧 `App(screen=...)` 仍工作；字节一致。
- 只允许改：`app/driver.py`、`app/application.py`、`tests/app/test_app.py`、`tests/app/test_driver.py`。
- 验证：`uv run pytest -q tests/app`。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `every(0.05)` + 1s → 19–20 次；`advance` 确定性；catch_up 两策略。
5. `TerminalOptions`/`Terminal`/`MouseMode` 可用；旧 App 参数仍工作。
6. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。

## 禁触清单

`kernel/**`、`terminal/{ansi,decoder,keys,win32,clipboard,render,paint,capability}.py`、`widgets/**`、`app/{focus,pointer,gesture,modal,find,overlays,scrollbar,command_palette}.py`、`demo/**`、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/W4a1-terminal.md`：A 节给 TerminalOptions/MouseMode/Terminal/Timer 签名、映射表、定时器精度、门禁；B 节给旧参数兼容路径、enter/leave/read_event 委托、W4a2 拆 Workspace 的边界、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W3b3b 事实）/ 探索审计 / 未决问题。
