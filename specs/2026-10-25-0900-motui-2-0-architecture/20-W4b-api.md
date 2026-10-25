# W4b · 调用面收敛（Section / Axis / Placement / Command / App 代理）

> 分支 `2.0/w4b-api`；前置：W4a2 已合并（`c733acb`）；写入范围：`src/motui/app/{workspace,application,runtime,commands}.py`、`src/motui/kernel/{hit,document}.py`（仅 `EveryHandle` 删除相关）、`examples/dashboard.py`、`tests/**`、`tools/api-2.0.txt`
> 权威：`ref/source/05-api-surface.md` §2–8、`04-runtime.md` §6、`10-waves/W4-runtime-api.md` §3.4

## 目标

把调用面收敛到 2.0 契约，**行为 1:1、字节不变**：

1. `Workspace.add/get/remove -> Section`；`App.add/get/remove -> Section`（`Runtime` 内部仍返回 id 供底层使用）；
2. `split(axis=Axis, weights=...)`、`dock(placement=Placement)`、`undock(placement)`；字符串入口保留为兼容（W5 删）；
3. `Command(group=, kw_only)`；`CommandRegistry.bind(app)`；`App.open_palette(registry)` 直接吃 registry；
4. `App.every/animation/invalidate/paint_now` 代理；`App.walk()` 遍历已挂载树；
5. 删除 `EveryHandle`（用 `Timer`），更新 overlays/gesture/scrollbar；
6. `examples/dashboard.py` headless 可跑（Sparkline + Fill + every/advance）；
7. 现有 1576 用例、57 byte/semantic、hash 不变。

**本波结束：Section 返回、枚举入口、Command 接线、App 代理、dashboard 可用；旧字符串/旧 return 兼容层标注为 W5 删除。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W4a2-runtime.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1576 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `Workspace.add` 委托 Runtime 返回 id；`get/remove` 返回 Component；`fill` 返回 Section。
  - `App.add` 返回 id；`App.get/remove` 返回 Component。
  - `Runtime.split(orientation: str, ratios=...)`；`dock(edge: str)`；`undock(edge)`。
  - `Command(name, description, handler, keys, enabled)` 位置参数可用；`CommandRegistry` 无 `bind`；`App.open_palette(list)`。
  - `App` 无 `every/animation/invalidate/paint_now` 代理；`Runtime` 有。
  - `EveryHandle` 在 `kernel/hit.py`；`Timer(EveryHandle)` 在 runtime；overlays/gesture/scrollbar 注解用 `EveryHandle`。
  - `examples/snake.py`、`wide_table.py` 已有；无 dashboard。
- 迁移规则：
  - `Workspace.add`: `block_id = runtime.add(...)`; `return runtime.document.get(block_id)`（Section）。`Workspace.get`: `runtime.document.get(id)`（Section）。`Workspace.remove`: 先取 Section，再 `runtime.remove(id)`，返回 Section。
  - `App.add`: 调 `workspace.add` 得 Section；`self._mount(component)`；返回 Section。`App.get/remove`: workspace。
  - `split(axis: Axis | str, *, weights=None, ratios=None, ...)`: `Axis.X` ≡ `"vertical"`, `Axis.Y` ≡ `"horizontal"`（注意 1.x 语义：vertical=左右切 → Axis.X）；`weights` 优先，`ratios` 兼容。`dock(placement: Placement | None = None, edge: str = "bottom")`: `Placement.BOTTOM` ≡ `"bottom"`, `Placement.TOP` ≡ `"top"`；`FLOW` 抛 ValueError。`undock(placement=Placement.BOTTOM | None, edge=...)`.
  - `Command`: `@dataclass(frozen=True, slots=True, kw_only=True)`；字段 `name, description="", group="", handler=None, keys=(), enabled=True`。更新测试为关键字参数（`Command(name="save")`）。
  - `CommandRegistry.bind(app)`: 对每个 command 的每个 key，`app.bind(key, lambda name=command.name: self.invoke(name))`；返回 None。
  - `App.open_palette(registry_or_commands)`: 若 `isinstance(x, CommandRegistry)`，`commands = x.options()`；否则保持 list 路径。`CommandRegistry.options()` 的 Option description 可保持 command.description；group 留在 Command 上（palette 分组 W5）。
  - `App.every(period, fn, catch_up="skip") -> Timer`、`App.animation(hz, draw)`、`App.invalidate()`、`App.paint_now()`：代理 `runtime`。
  - `App.walk()`: 遍历所有 pane/dock 文档的组件树（可复用 `focus_targets` 的 `iter_widgets`；导出为 public generator）。
  - `EveryHandle`: 删除 `kernel/hit.py` 的定义与导出；overlays/gesture/scrollbar 的注解改 `Timer`（从 `app.runtime` import；注意循环导入，可用 `TYPE_CHECKING`）。`Runtime.every` 返回 `Timer`。
- 已知坑：
  - `Workspace.add` 返回 Section 会改变 `test_workspace.py` 的断言；`App.add` 返回 Section 会改变 `test_app.py` 两处；更新测试，不要保留旧 return。
  - `Runtime.add` 仍返回 id（内部/测试大量使用）；不要改。
  - `split` 的 `weights` 与 `ratios` 语义一致；`Axis.X` 对应 `"vertical"`，不要按字面颠倒。
  - `Command` kw_only 会破坏位置参数测试；全仓更新。
  - `EveryHandle` 删除要同步 `kernel/__init__.py`/`api`；`Timer` 不要从 kernel 导出（在 app）。
  - dashboard 用 `Sparkline` + `Canvas`/`Fill`；headless 下用 `advance(dt)` 驱动，不 sleep。
  - 57 golden/hash 不变；demo 展示字符串不改。
- 不改渲染/交互/定时器语义；不改 widgets。

## 工单（按序，每步一个 commit）

### T1 Workspace/App 返回 Section

- `app/workspace.py`：
  - `add` → `Section`（`runtime.document.get(block_id)`）；`get` → Section；`remove` → Section（先取再删）。
  - 文档注明 `Runtime.add` 仍返回 id。
- `app/application.py`：
  - `App.add` → `Section`；`App.get/remove` → `Section`；`App.fill` 不变。
  - 所有内部调用 `self.workspace.add` 的返回值若是 id，改为 `section.id`（如需要）。
- 测试：`tests/app/test_workspace.py`、`test_app.py`、`test_driver.py` 更新（`block.id`/`section.widget`）；全量。
- 验证：`uv run pytest -q tests/app`。

### T2 Axis/Placement

- `app/runtime.py` `split`：签名 `split(axis: Axis | str, *, weights: tuple[float,...] | None = None, ratios: tuple[float,...] | None = None, ...)`；`Axis.X`→`"vertical"`、`Axis.Y`→`"horizontal"`；`weights` 优先。
- `dock(component, *, placement: Placement | None = None, edge: str = "bottom", size=None)`：`Placement.BOTTOM`→"bottom"、`TOP`→"top"；`FLOW` 抛 ValueError。
- `undock(placement: Placement | None = None, edge: str = "bottom")`。
- `app/workspace.py` 代理相应签名；`App.split/dock/undock` 接受枚举。
- 测试 `test_driver.py`/`test_app.py`：枚举与字符串等价、weights/ratios 等价、FLOW 报错。
- 验证：`uv run pytest -q tests/app`。

### T3 Command

- `app/commands.py`：
  - `Command` 改 `kw_only=True`，加 `group: str = ""`（位置：name, description, group, handler, keys, enabled）。
  - `CommandRegistry.bind(app)`。
  - `options()` 可在 description 前加 group 前缀？保持 description；group 通过 Command 暴露（palette 分组 W5）。
- `app/application.py` `open_palette(commands)`: 接受 `CommandRegistry`；`registry.options()`。
- 测试 `test_commands.py`/`test_command_palette.py`：关键字构造、group、bind 的 key→invoke、open_palette(registry) 渲染。
- 验证：`uv run pytest -q tests/app/test_commands.py tests/app/test_command_palette.py`。

### T4 App 代理 + walk + EveryHandle 删除

- `app/application.py`：`every/animation/invalidate/paint_now` 代理；`walk()` 生成器（所有挂载组件树）。
- `kernel/hit.py`：删除 `EveryHandle`；`kernel/__init__.py`/`api` 同步。
- `app/{overlays,gesture,scrollbar}.py`：注解 `EveryHandle` → `Timer`（`TYPE_CHECKING` 避免循环）。
- 测试：App every/advance 驱动；walk 覆盖；`EveryHandle` 不再导出。
- 验证：`uv run pytest -q tests/app`。

### T5 dashboard 示例

- 新建 `examples/dashboard.py`（≤120 行）：Sparkline/Canvas + Fill + `App.every` 或 `advance`；`--headless` 跑 N 帧并打印摘要，exit 0。
- `tests/test_examples.py` 加 subprocess 用例。
- 验证：`uv run python examples/dashboard.py --headless`。

### T6 收口

- `tools/api.py --update`；全量验收。
- `grep -rn "EveryHandle" src` → 0。
- `grep -rn "def add(" -A 5 src/motui/app/workspace.py` 返回 Section；`App.add` 返回 Section。
- 行数如实报告（Runtime 仍 >450，W5/后续拆分计划）。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. `Workspace/App.add/get/remove` 返回 Section；`split(Axis.X)`/`dock(Placement.BOTTOM)` 生效；Command group/bind/palette 生效。
5. `App.every/animation/invalidate/paint_now/walk` 可用；`EveryHandle` 删除。
6. `examples/dashboard.py --headless` exit 0。
7. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth --quick` 全绿。

## 禁触清单

`kernel/{cell,layout,frame,overlay,selection,style,glyphs,theme,text,events,keymap,geom}.py`（`hit.py` 仅删 EveryHandle）、`terminal/**`、`widgets/**`、`demo/**`（展示字符串不改）、`tests/golden/**`、`tools/{golden,framebench,semantic}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。

## 交接包

最后 commit 写 `handoff/W4b-api.md`：A 节给 Section/Axis/Placement/Command/App 代理/walk/EveryHandle 删除、dashboard、门禁；B 节给兼容层（字符串入口/旧 return）与 W5 删除计划、Runtime 行数、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W4a2 事实）/ 探索审计 / 未决问题。
