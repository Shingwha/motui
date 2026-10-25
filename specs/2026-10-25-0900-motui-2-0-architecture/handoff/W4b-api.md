# W4b 交接 · 调用面收敛（Section / Axis / Placement / Command / App 代理）

> 分支 `2.0/w4b-api`；起点 `4e521ed`（W4a2 合并后）。T1–T6 完成：**1592 passed**（1576 基线 + 16 个新用例）；57 byte / 57 semantic / hash `e7ca544b…` 全不变；demo 70 / 4059 行；`examples/dashboard.py --headless` exit 0。`Runtime` **1617 行 > 450**，拆分仍待 W5（B4）。

## A. 交付面与门禁

### Document facade

- `Workspace.add/get/remove -> Section`；`App.add/get/remove -> Section`。
  `Workspace.add` 先取 `Runtime.add` 的 id，再经持有 pane 的文档解析 Section（`_holder`），因此 `pane=right` 返回 right 的 Section，而不是主文档。
- `Runtime.add/get/remove` **仍是 id / Component**（低层契约不变，测试与工具大量使用）。
- `App.fill` 不变；`App.remove` 额外接受 `Section`（读 `.id`），因为未改动的 demo 把 `App.add` 的返回值存进 `_stage_ids` 再回传；W5 收窄为 `str`。
- `App.focus(id)` 经 `workspace.get(id).widget` 取组件。

### Split / Dock

- `split(axis: Axis | str, *, weights=None, ratios=None, min_size=1, separator=True, pane=None)`：
  `Axis.X ≡ "vertical"`（左右切），`Axis.Y ≡ "horizontal"`；`weights` 优先于 `ratios`；未知字符串 ValueError。
- `dock(component, *, placement=None, edge="bottom", size=None)`：`Placement.BOTTOM/TOP` 映射到同名 edge，`FLOW` 抛 ValueError；`edge` 字符串兼容。
- `undock(placement=None, edge="bottom")`：接受 Placement 或字符串；demo 的 `undock(edge)` 位置参数照常工作。
- Workspace/App 的代理签名同步；`dock_region`/`_dock_height` 仍用 edge 字符串（内部面）。

### Command

- `@dataclass(frozen=True, slots=True, kw_only=True)`；字段 `name, description="", group="", handler=None, keys=(), enabled=True`。
- `CommandRegistry.bind(app)`：每个 key 绑定 `invoke(name)`，闭包捕获命令名；disabled 命令仍绑定、invoke 拒绝。
- `App.open_palette(registry)`：`isinstance(CommandRegistry)` 时取 `options()`；list 路径保留（W5 删）。
- **兼容层**：demo（禁触）仍以 `Command(name, description)` 位置参数构造。用 metaclass 把前两个位置参数映射到关键字，再走 kw_only 生成器；`__signature__` 只暴露 kw_only 签名，API 快照保持干净。W5 随 demo 迁移删除。
- palette 本轮仍渲染 description，`group` 只在 Command 上（分组是 W5）。

### App 代理 / walk / EveryHandle

- `App.every/animation/invalidate/paint_now` 代理 runtime，`every` 返回 `Timer`。
- `App.walk()`：`iter_widgets(runtime)` 的公开生成器，覆盖所有 pane/dock 文档树、去重、前序。
- `kernel/hit.py` 删除 `EveryHandle` 与导出；`kernel/__init__.py` 同步；`Timer` 独立实现 `cancelled/cancel`（保留 `__slots__`）。
- overlays/gesture/scrollbar 的注解改 `Timer`（TYPE_CHECKING，避免循环）；pointer/modal 仅把 “EveryHandle convention” 文案改为 timer-handle（为 `grep -rn EveryHandle src == 0`，超出工单点名文件但零行为变化）。

### Example 与门禁（本 worktree，Python 3.12.14 / uv 0.12.21）

- `pytest -q -p no:cacheprovider`：**1592 passed**
- `golden.py --check`：**57 topics match**；`semantic.py --check`：**57 topics match**
- `framebench.py`：**e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da**（不变）
- `python -m motui < /dev/null`：exit 0，**70** 行；`--pages`：exit 0，**4059** 行
- `ruff` All checks passed；`pyright` 0 errors；`lint-imports` 4 kept
- `api --check`：**184 names**（原 185，删 `motui.kernel:EveryHandle`）；`growth --quick` OK
- `python examples/dashboard.py --headless`：`dashboard: 40 frames at 20 fps, 64 points, last=0.668, painted_rows=20`，两次运行一致

## B. 兼容层、W5 删除计划与坑

1. **W5 删除名单**：`split("vertical"|"horizontal")` 字符串；`dock/undock` 的 `edge` 字符串（含位置参数）；`App.remove(Section)`；`Command` 位置参数 metaclass shim；`App.open_palette(list)`；`pin=`；`Document.add(pin=)`。
2. **demo 零 diff**：`demo/**` 未改。它存 Section 到 `list[str]`（运行时无碍，pyright 不检查 demo）并以位置参数构造 Command。W5 迁移 demo 时一并删除两个兼容层。
3. **Runtime 行数如实**：`runtime.py` **1617**（W4a2 1544 + 本轮 split/dock/Timer/docstring 增长），`workspace.py` 285，`application.py` 891，`commands.py` 207，`dashboard.py` 95。仍超 450 目标；W4a2 的 `runtime/{session,layout,documents,protocol}` 拆分计划未执行，建议 W5 优先。
4. **Command metaclass**：显式 `__signature__` 属性返回 dataclass 生成 init 的参数（去掉 self），否则 `inspect.signature` 会显示 metaclass `__call__(*args, **kwargs)` 并污染 API 快照。
5. **边框/枚举语义**：`Axis.X` 对应 1.x `"vertical"`（竖分隔线），不要按字面翻转；`split` 的权重只在 `weights is not None` 时覆盖 `ratios`。
6. **测试增量**：T1 +1、T2 +6、T3 +6、T4 +2、T5 +1；其中 `test_remove_accepts_the_section_the_demo_keeps` 明确记录 W5 收窄点。
7. **字节不变**：demo 的 Command 描述仍是 `topic.group`（未迁移到 `group=`），palette 表格 golden 因此保持原字节；任何 demo 迁移都必须押到 W5 并重录 golden。

## C. 位置与 commit

- 源码：`src/motui/app/{workspace,application,runtime,commands,overlays,gesture,scrollbar,pointer,modal}.py`、`src/motui/kernel/{hit,__init__}.py`、`examples/dashboard.py`
- 测试：`tests/app/{test_workspace,test_app,test_driver,test_commands,test_command_palette}.py`、`tests/kernel/test_kernel_imports.py`、`tests/test_examples.py`
- 快照：`tools/api-2.0.txt`（184 names）
- commit：
  - `63e4566` workspace: add, get and remove answer the Section a caller keeps（T1）
  - `5cdf7d0` app: split speaks Axis and docks speak Placement（T2）
  - `e7fd726` commands: a command is a keyword-only value with a group; a registry binds an app（T3）
  - `6fad336` app: the app proxies the pump, walks its tree, and the timer owns its handle（T4）
  - `7503149` examples: a headless dashboard fills a sparkline from every/advance（T5）
  - `c6a03c2` test: the api snapshot records the converged call surface（T6）
  - 本文件（收口）
