# W4a2 · TUI → Runtime + Workspace facade（删除 TUI）

> 分支 `2.0/w4a2-runtime`；前置：W4a1 已合并（`4f3259d`）；写入范围：`src/motui/app/{driver→runtime,workspace,application,__init__}.py`、`src/motui/__init__.py`、`src/motui/testing/__init__.py`、`src/motui/demo/**`（仅可执行代码，不改展示字符串）、`tests/**`（TUI 构造与 `.tui` 引用）、`tools/api-2.0.txt`
> 权威：`ref/source/04-runtime.md` §1–8、`10-waves/W4-runtime-api.md` §3.2

## 目标

删除公开 `TUI`，把运行时拆成 `Terminal` / `Runtime` / `Workspace` / `App` 四个对象，**行为与字节不变**：

1. `app/driver.py` → `app/runtime.py`，`class TUI` → `class Runtime`；
2. 新增 `app/workspace.py:Workspace`，作为 frame/document/pane/content/scroll/selection/hit 的门面，委托 Runtime（W4a2 先 facade；方法体拆分见偏差）；
3. `App` 组合 `terminal`/`runtime`/`workspace`；删除 `App.tui`；`App.add/get/remove/split/dock/...` 走 workspace；
4. `headless_tui` 返回 `Runtime`（测试驱动）；`snapshot` 不变；
5. 全仓删除 `TUI` 名称（可执行代码）；demo 可执行代码迁移，**展示字符串/金标文案不动**；
6. 现有 1568 用例、57 byte/semantic、hash 不变。

**本波结束：`TUI` 在 src/tests 可执行代码中 0；`App.runtime/workspace/terminal` 可用；全量门禁绿；bytes 不变。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W4a1-terminal.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1568 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `app/driver.py` 1,353 行（已含 Terminal 接入）；`TUI` 类持有 screen/keys/painter/frame/document/viewport/timers/session。
  - `App.__init__` 构造 `self.tui = TUI(...)`；内部大量 `self.tui.*`；`app/application.py` 762 行。
  - `headless_tui` 返回 `TUI`；139 处测试使用；22 处直接 `TUI(...)`；112 处 `.tui`。
  - `demo/session.py` 持有 `self.tui`；demo 页面构建器使用 `session.tui`。
  - `demo/topics/overview.py`/`components_text.py` 的 `TUI()` 在展示字符串/code fence 内，属于 golden 文案，**不要改**。
- 设计：
  - `Runtime` = 原 `TUI` 的类名与实现（screen/keys/painter/frame/document/viewport/timers/session 都在）；新增 `workspace` property（缓存的 Workspace facade）。
  - `Workspace` facade：
    ```python
    class Workspace:
        def __init__(self, runtime): self._runtime = runtime
        @property document/viewport/frame/panes/selection ...
        def pane/add/fill/get/remove/split/dock/undock/...
        def hit/hit_leaf/visible_range/rows/scroll_*/reveal/set_selection
    ```
    每个方法 `return self._runtime.<method>(...)`；属性同理。不复制状态。
  - `App`：`self.runtime = Runtime(...)`；`self.workspace = self.runtime.workspace`；`self.terminal = self.runtime.terminal`（或 `Runtime.terminal` 属性）；删除 `self.tui`。
  - `Runtime` 保留 `screen`/`read_event`/`run` 等；`App` 需要的方法通过 `runtime`/`workspace` 代理。
  - `headless_tui`：`Runtime(terminal=TerminalOptions(screen=HeadlessScreen(...), input=source), interactive=False)`；返回 Runtime。
- 已知坑：
  - 测试里 `tui = TUI(...)` 的变量名可保留，构造函数改名 `Runtime`；`tui.add` 等方法仍在 Runtime 上。
  - `App` 内部 `self.tui` 全部改 `self.runtime`（或 `self.workspace` 对内容操作）；不要留 `App.tui` 属性。
  - `demo/session.py` 的 `self.tui` 改 `self.runtime`；所有 `session.tui` 引用同步；demo 页面构建器可能通过 `session` 间接用，检查。
  - `App.on_selection` 回调类型注解 `TUI` → `Runtime`。
  - `Pointer`/`Gesture`/`Toasts`/`Tooltip` 构造参数名 `tui` 可以保留（内部），但类型注解改 `Runtime`；它们调用 runtime 的方法，行为不变。
  - `TUI` 在 docstring/展示字符串中可保留（golden），但 `grep "TUI(" src tests` 的可执行代码必须 0；`grep "TUI" src/motui/app` 的类名/注解改 Runtime。
  - `api.py` 的快照：root/app 的 `TUI` 删除、`Runtime`/`Workspace` 新增；`--update`。
  - `App` 的旧参数（mouse/hover/...）W4a1 已折叠进 TerminalOptions；保持。
  - 行数：W4a2 先 facade；`Runtime` 仍可能 >450、`Workspace` facade 很小。handoff 必须如实记录，并给出 W4b 拆分计划；不要伪报。
- 不改 widgets/kernel/terminal（除必要导入）；不改渲染/交互/定时器行为。

## 工单（按序，每步一个 commit）

### T1 Runtime 改名与 Workspace facade

- `git mv src/motui/app/driver.py src/motui/app/runtime.py`。
- 类 `TUI` → `Runtime`；`__repr__` 文案 `Runtime(...)`；所有类型注解/内部引用改名。
- 新增 `app/workspace.py`：`Workspace` facade，委托 Runtime；方法/属性覆盖：
  `document viewport frame panes pane selection selection_pane add fill get remove split dock undock dock_region pane_at visible_range rows reveal set_selection hit hit_leaf _document_panes _content_pane _focus_pane _focused_viewport _holder _panes_holding _next_block_id _focused_id _pane_id _retile _dock_height _set_selection`（私有方法也代理，供 App 内部使用；文档注明 facade）。
- `Runtime.workspace` property（缓存）。
- 测试 `tests/app/test_workspace.py`（新建）：facade 的 add/get/remove/split/dock/hit 与 Runtime 方法一致；`workspace.document is runtime.document`。
- 只允许改：`app/runtime.py`（改名）、`app/workspace.py`、`tests/app/test_workspace.py`、`app/__init__.py`（导出 Runtime/Workspace，删 TUI）。
- 验证：`uv run pytest -q tests/app/test_workspace.py`。

### T2 App 组合与 TUI 删除

- `app/application.py`：
  - `self.runtime = Runtime(terminal=...)`；`self.workspace = self.runtime.workspace`；`self.terminal = self.runtime.terminal`；
  - 删除 `self.tui`；所有 `self.tui.*` 改 `self.runtime.*`（内容操作可用 `self.workspace.*`）；
  - `App.add/get/remove/split/dock/undock/focus/...` 走 workspace/runtime；
  - `App.runtime`/`workspace`/`terminal` 属性；删除 `App.tui`；
  - 类型注解 `TUI` → `Runtime`。
- `src/motui/app/__init__.py`：导出 `Runtime`、`Workspace`，删除 `TUI`。
- `src/motui/__init__.py`：root 删除 `TUI`，可选加 `App`（已有）；不加 `Runtime` 到 root（app 层）。
- `app/{pointer,gesture,overlays,modal,find,command_palette,scrollbar,focus}.py`：类型注解/文档中的 `TUI` → `Runtime`（参数名 `tui` 可保留）；行为不变。
- 测试 `tests/app/test_app.py`：`app.runtime`/`app.workspace` 可用；`app.tui` 不存在。
- 只允许改：上述 app 文件、`tests/app/test_app.py`。
- 验证：`uv run pytest -q tests/app/test_app.py`。

### T3 测试/测试助手迁移

- `src/motui/testing/__init__.py`：`headless_tui` 返回 `Runtime`（`TerminalOptions` + `HeadlessScreen` + input）；`snapshot` 不变。
- 全仓 `TUI(` → `Runtime(`（可执行代码）：`tests/**`；`headless_tui` 内部；`demo` 可执行代码。
- `.tui` 引用：`App` 内部已改；测试若有 `app.tui` 改 `app.runtime`/`app.workspace`；demo `session.tui` 改 `session.runtime`。
- 展示字符串/code fence（如 `TUI()` 文案）不动。
- 测试全量跑；修复导入/类型。
- 只允许改：`testing/__init__.py`、`tests/**`、`demo/**`（仅可执行代码）。
- 验证：`uv run pytest -q -p no:cacheprovider`。

### T4 收口

- `grep -rn "TUI(" src tests` 的可执行代码 0（展示字符串除外，列出）；`grep -rn "class TUI\|TUI\b" src/motui/app src/motui/__init__.py` 只剩 docstring/展示串。
- `tools/api.py --update`。
- 全量门禁；记录 `runtime.py`/`workspace.py` 行数；如 >450，写清 W4b 拆分计划。
- 只允许改：`tools/api-2.0.txt`、handoff。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `TUI` 公开名删除；`App.runtime/workspace/terminal` 可用；`headless_tui` 返回 Runtime。
5. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。
6. 行数如实报告（Runtime/Workspace/App）；超 450 的给出 W4b 拆分计划。

## 禁触清单

`kernel/**`、`terminal/**`、`widgets/**`、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`；`demo/**` 的展示字符串/文案（只改可执行代码）。

## 交接包

最后 commit 写 `handoff/W4a2-runtime.md`：A 节给 Runtime/Workspace/App 面、TUI 删除清单、门禁；B 节给 facade 委托、`self.tui`→runtime/workspace 映射、行数与 W4b 拆分计划、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W4a1 事实）/ 探索审计 / 未决问题。
