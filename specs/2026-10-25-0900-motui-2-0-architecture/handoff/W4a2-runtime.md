# W4a2 交接 · Runtime / Workspace facade / App 组合（删除 TUI）

> 分支 `2.0/w4a2-runtime`；起点 `4f3259d`（W4a1 合并后）。结论：T1–T4 完成；**1576 passed**（1568 基线 + 6 个 test_workspace + test_surface/test_app 各 1 个新用例）；57 byte / 57 semantic / hash `e7ca544b…` 全不变；demo 70 / 4059 行，exit 0。`Runtime` **1544 行 > 450**，W4b 拆分计划见 B4。

## A. 交付面与门禁

### Runtime（`app/runtime.py`，原 `app/driver.py`）

```python
class Runtime:                       # 原 class TUI，__all__ = ["Runtime"]
    def __init__(..., terminal: Terminal | None = None)  # 参数不变
    screen; terminal -> Terminal | None
    workspace -> Workspace           # 缓存：同一 runtime 只造一个 facade
    document/viewport/frame/selection/selection_pane/rows ...
    add/fill/get/remove/system/split/dock/undock/reveal/hit/hit_leaf ...
    every/animation/invalidate/paint_now/advance/clock ...
    read_event/exit/run_session/run_async/run
```

- `Timer` 仍定义在 `app/runtime.py`（不从 `app` 包根导出），继承 kernel `EveryHandle` 不变。
- `repr` 为 `Runtime(screen=..., blocks=..., interactive=...)`。

### Workspace（`app/workspace.py`，新增）

```python
class Workspace:
    def __init__(self, runtime: Runtime)
    # 属性：document viewport frame panes selection selection_pane rows
    # 公开：pane add fill get remove split dock undock dock_region pane_at
    #       visible_range reveal set_selection hit hit_leaf
    # 私有：_document_panes _content_pane _focus_pane _focused_viewport _holder
    #       _panes_holding _next_block_id _focused_id _pane_id _retile
    #       _dock_height _set_selection
```

每个成员 `return self._runtime.<member>(...)`（属性同理）；facade 不复制任何状态，`workspace.document is runtime.document`。`Workspace.add` 返回 block id（Runtime 契约）；`interfaces.md` 的“add 返回 Section”留到 W4b 实拆分时再改签名。

### App（`app/application.py`）

- `self.runtime = Runtime(...)`；`self.workspace = self.runtime.workspace`；`self.terminal = self.runtime.terminal`（App 恒为非 None 的 `Terminal`）。
- **删除 `App.tui`**，无 shim；`App.add/get/remove/split/dock/undock` 走 workspace；pump/selection/hit/协议面走 runtime；theme setter 写 `runtime.theme`。
- `on_selection` 注解 `Callable[["Runtime", Selection], object]`；`terminal` 由 property 改为普通属性。
- app 层控制器（pointer/gesture/overlays/modal/find/command_palette/scrollbar/focus）只在 TYPE_CHECKING 导入 `Runtime`，参数名 `tui` 保留；`find.py` 的私有槽 `tui` 改名 `runtime`（`__slots__`）。

### 测试助手

- `headless_tui` 返回 `Runtime`：`Runtime(terminal=Terminal(TerminalOptions(screen=HeadlessScreen(...), input=source)), interactive=False)`；`snapshot(tui: Runtime)` 输出不变。
- root 删除 `TUI`（`__all__` 同步）；`motui.app` 导出 `Runtime`/`Workspace`、删除 `TUI`。

### 门禁（本 worktree，Python 3.12.14 / uv 0.12.21）

- `pytest -q -p no:cacheprovider`：**1576 passed**
- `golden.py --check`：**57 topics match**；`semantic.py --check`：**57 topics match**
- `framebench.py`：`render-hash e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da`（不变）
- `python -m motui < /dev/null`：exit 0，**70** 行；`--pages`：exit 0，**4059** 行
- ruff All checks passed；pyright 0 errors；lint-imports 4 kept；`api --check` **185 names**；`growth --quick` OK

## B. 实现细节 / 坑

1. **facade 只委托**：Workspace 没有任何字段除 `_runtime`；`Runtime._workspace` 首次访问时创建并缓存。私有成员也代理，因为 App 的 mount/theme/focus 记账要读 pane/holder 表。
2. **`self.tui` 映射**：`add/fill/get/remove/split/dock/undock` → `self.workspace`；`theme/refresh/hit/frame.exit/set_title/pane_at/read_event/run_session/...` → `self.runtime`；`focus_targets/iter_widgets` 接收 runtime（与 workspace 同源）。
3. **TUI 残留**：可执行 `TUI(` 仅剩 2 处展示字符串（`demo/topics/overview.py:35`、`components_text.py:25`，golden 锁字节，**未改**）；`.tui` 在 `src/tests/tools/examples` 为 0；`motui/__init__.py` 仅项目描述 “TUI toolkit”。kernel/widgets/terminal 的 docstring 仍有 `TUI` 引用（禁触文件，未改，仅文档链接过时，W4b/W5 清理）。
4. **行数（如实）**：`runtime.py` **1544**、`workspace.py` **241**、`application.py` **796**。Runtime 超 450 的 W4b 计划：
   - W4b1 `app/runtime/session.py`：`_run/_pump/tick/advance/every/animation/refresh/_paint_at/clock/read_event/exit/_teardown/_dump_final_screen`（约 500 行）；
   - W4b2 `app/runtime/layout.py`：`split/dock/undock/dock_region/pane_at/visible_range/hit/hit_leaf/reveal/_retile/_dock_height/_body_address`（约 380 行）；
   - W4b3 `app/runtime/documents.py`：`add/fill/get/remove/system/_document_panes/_content_pane/_focus_pane/_holder/_panes_holding/_next_block_id/_focused_id/_pane_id`（约 260 行）；
   - W4b4 `app/runtime/protocol.py`：`set_title/set_cursor_shape/copy_to_clipboard`（约 60 行）；`Runtime` 收敛为组合根，Workspace 改委托这些子对象；同时把 `EveryHandle`/`RowRange` 从 kernel 移出并让 `Timer` 脱离继承。
5. **被迫越界的 3 个文件**（行为零变化，仅随改名机械迁移；见 B5）：`tools/framebench.py`（`TUI` import/类名 → `Runtime`）、`tools/semantic.py`（`session.tui` → `session.runtime`）、`examples/snake.py`（`app.tui` → `app.runtime`）。不改则 hash/semantic/examples 门禁直接 ImportError/AttributeError。framebench 一处历史的 “MOTUI” 文案已原样保留。
6. **T1 的前置导入修改**：为了 `import motui` 可用（driver 改名后 application/root/testing 会立即断），T1 一并做了 `application.py` 两行 import、root 删名、testing 返回 Runtime；完整 App 组合留 T2，测试/demo/tools 迁移留 T3。
7. **headless_tui 走 terminal 路径**：`TerminalOptions(screen=...)` 使 `_hover` 由 MOVE 推导为 True，但 headless 不 attach `RawTerminalKeys`，字节与语义均不变；57 golden 全绿为证。
8. `App.terminal` 是 `Terminal`；`Runtime.terminal` 可为 `None`（旧 `screen=`/`keys=` 路径）。`Runtime` 仍同时保留两条构造路径，W4b 只保留 terminal 路径。
9. **未改行为**：渲染/交互/定时器/焦点/手势/overlay 逻辑零改动；root 文档措辞除外。

## C. 位置与 commit

- 源码：`src/motui/app/{runtime,workspace,application,__init__,find,...}.py`、`src/motui/{__init__,testing/__init__}.py`、`src/motui/demo/{__init__,session,script,topics/*}.py`、`tools/{framebench,semantic}.py`、`examples/snake.py`
- 测试：`tests/app/{test_workspace,test_app,test_driver,test_pointer,test_selection_overlay,test_surface}.py`
- 快照：`tools/api-2.0.txt`（删除 `motui:TUI`/`motui.app:TUI`，新增 `motui.app:Runtime`/`Workspace`；总量仍 185）
- commit：
  - `387155c` runtime: the driver becomes the Runtime and the workspace facade delegates it（T1）
  - `a5a6a52` app: the app composes a runtime, a workspace and a terminal（T2）
  - `2de1f7f` test: drive the runtime through tests, the demo, the tools and the example（T3）
  - 本文件 + api 快照（T4，收口）
