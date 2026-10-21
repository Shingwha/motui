# W1a · Driver lifecycle and Host seam

> 分支 `cleanup/w1a-driver-seams`；起点 `main`；写入范围见下。

## 目标

在不改变任何公开行为的前提下，删除 `TUI` 两份几乎相同的 run 生命周期，给 interaction
层的组件工厂补上真实类型，合并 Tooltip/Stats 的注册与 detach，并清掉 `app.py` 的导入
与常量重复。

最高约束：**测试、golden、render-hash 三者零变化**。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：

```bash
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m pytest -q -p no:cacheprovider
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/golden.py --check
```

- 稳定区（不要重读）：`widgets/`、`tests/widgets/`、`demo/`。
- 已知约束：本机 venv 的 editable 安装指向主检出，worktree 必须用上面的 `PYTHONPATH`。

## 工单（按序执行，每项一个 commit）

### T1 合并 run 生命周期

- `src/motui/app.py`：新增私有 `_run(body: Callable[[], Awaitable[None]])`，
  `run_session` 传入 `lambda: body(self)`，`run_async` 传入等待 `_exit_event` 的协程。
- 必须保留 `ref/interfaces.md` 的五条语义（Enter/pump/body、KeyboardInterrupt、
  body error 优先、pump error 次之、teardown 一次）。
- `run_session` 的 `body` 类型改为 `Callable[["TUI"], Awaitable[None]]`。
- 只允许改：`src/motui/app.py`。
- 验证：`pytest tests/app -q -p no:cacheprovider`。

### T2 统一 block id 解析

- `src/motui/app.py`：抽 `_holder(id) -> Pane`，`get` / `remove` 共用；错误类型与消息
  保持现状。
- 只允许改：`src/motui/app.py`。
- 验证：`pytest tests/app -q -p no:cacheprovider`。

### T3 类型化 Host 工厂

- `src/motui/kernel/host.py`：按 `ref/interfaces.md` 新增 `OptionLike`、`QueryInput`、
  `FilterList`，并让 `Host.make_input` / `make_autocomplete` 返回它们。
- `src/motui/app.py`：`make_input` / `make_autocomplete` 的返回类型同步；方法内仍延迟
  import widgets。
- `src/motui/interaction/find.py`：删除 `Any, cast`，`input` 直接用 `QueryInput`。
- `src/motui/interaction/palette.py`：删除 `Any, cast`，`input` / `list` 用协议类型；
  `option.value` 通过 `OptionLike` 读取。
- `docs/DESIGN.md`、`docs/CONTRACT.md`：只改 Host 协议代码块里的两个返回类型。
- 只允许改：上述五个文件。
- 验证：`pytest tests/interaction/test_host.py tests/interaction/test_find.py tests/interaction/test_palette.py -q -p no:cacheprovider`。

### T4 合并 Tooltip/Stats 的挂载生命周期

- `src/motui/interaction/overlays.py`：新增私有 `_MountedOverlay(Themed)`，持有
  `_tui`、`_detached`，构造函数完成 `add_overlay`，`detach()` 幂等。
- `Tooltip`、`Stats` 继承它，删除各自的重复字段与方法；layer 由子类传入
  （`tooltip` / `overlay`）。
- `Toasts` 保持现状。
- 只允许改：`src/motui/interaction/overlays.py`。
- 验证：`pytest tests/interaction/test_overlays.py -q -p no:cacheprovider`。

### T5 导入与常量清理

- `src/motui/app.py`：合并 `kernel.lines` 的重复导入；删除 `_DOCK_EDGES`，改用
  `kernel.frame.DOCK_EDGES`；按 `kernel.*` / `keys` 分组排序。
- `src/motui/interaction/modal.py`：删除未使用的 `PasteEvent` import。
- 只允许改：`src/motui/app.py`、`src/motui/interaction/modal.py`。
- 验证：`pytest -q -p no:cacheprovider`。

## 验收

1. 全量门禁：

```bash
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m pytest -q -p no:cacheprovider
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/golden.py --check
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  tools/framebench.py
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m motui < /dev/null
PYTHONPATH="$PWD/src" /c/Users/shifu/Desktop/mocode-tui/.venv/Scripts/python \
  -m motui --pages
```

2. 三个数字：`824 passed`、`58 topics match`、`render-hash` 等于
   `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
3. 核心抽验：`tests/app/test_driver.py` 的 run/teardown 用例全绿。

## 禁触清单

- `tests/`、`tests/golden/`、`pyproject.toml`、`uv.lock`、`src/motui/widgets/`、
  `src/motui/demo/`、`src/motui/kernel/` 下除 `host.py` 外的文件。
- 不得运行 `tools/golden.py --update`。
- 不得 merge / push / tag / checkout main。

## 交接包

最后一个 commit 写 `handoff/W1a-driver-seams.md`，按 SKILL 的 A/B/C 模板，
60–80 行；重点写：生命周期合并后哪些细节必须保持、Host 协议的静态检查结果、
overlay 基类的 layer 归属。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
