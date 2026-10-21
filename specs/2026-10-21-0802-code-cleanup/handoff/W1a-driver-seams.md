# W1a 交接包
> 分支 cleanup/w1a-driver-seams / 起点 main / 2026-10-21

## A. 自动事实（从命令与代码生成）

- `git diff --stat main..HEAD` 变更地图：8 个文件、+163/−125。
  - `docs/CONTRACT.md` 4、`docs/DESIGN.md` 4（只改 Host 协议块的两个返回类型）
  - `src/motui/app.py` 123、`src/motui/kernel/host.py` 59
  - `src/motui/interaction/find.py` 5、`palette.py` 8、`overlays.py` 83、`modal.py` 2
- 新增/变更接口（仅类型层）：
  - `motui.kernel.host.OptionLike` / `QueryInput` / `FilterList`（`Protocol`，host.py:101-141），并加入该模块 `__all__`。
  - `Host.make_input(**kwargs) -> QueryInput`；`Host.make_autocomplete(options, **kwargs) -> FilterList`（host.py:194-200）。
  - `TUI.make_input` / `TUI.make_autocomplete` 返回类型同步；运行时仍返回 `widgets.textfield.Input` / `widgets.autocomplete.Autocomplete`。
- 私有合并：
  - `TUI._run(body: Callable[[], Awaitable[None]])`（app.py:1295），`run_session` 传 `lambda: body(self)`，`run_async` 传 `lambda: self._exit_event.wait()`。
  - `TUI._holder(id) -> Pane`（app.py:485），`get`/`remove` 共用。
  - `interaction.overlays._MountedOverlay(Themed)`（overlays.py:417），`Tooltip`/`Stats` 继承。
- 调用顺序未变：驱动 refresh → pump tick → `_paint_at` → compose → apply_overlays → paint；构造注册、detach 注销的 overlay 顺序未动。
- 行为契约零变化：`get`/`remove` 的 `KeyError`/`ValueError` 文本逐字保留；`dock` 的 `ValueError` 文本逐字保留；overlay layer 不变（Tooltip=`tooltip`、Stats=`overlay`）。
- 写入范围核对：diff 仅涉及工单允许的 8 个文件；`tests/`、`tests/golden/`、`pyproject.toml`、`uv.lock`、`widgets/`、`demo/`、`kernel/`（`host.py` 除外）零 diff。
- 基线命令与当前真实结果（worktree 根，`PYTHONPATH="$PWD/src"`，主 venv python）：
  - `pytest -q -p no:cacheprovider` → **824 passed**
  - `tools/golden.py --check` → **golden: 58 topics match**
  - `tools/framebench.py` → **render-hash f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1**（replay 墙钟波动不具契约性）
  - `python -m motui < /dev/null` → exit 0
  - `python -m motui --pages` 重定向到文件 → exit 0（4130 行）
  - `pytest tests/app/test_driver.py` → **31 passed**

## B. 只存在于脑子里的东西

- 偏差：无。唯一工单未点名的是把三个 Protocol 加入 `kernel.host.__all__`；它们是 seam 的公开类型，facade 冻结清单不含 `kernel.host`，零风险。
- 生命周期合并后必须保持的细节（已由 T1 与 test_driver 验证）：
  1. `_enter_run` 必须先于 pump task 与 body；`_exit_event` 已由 `_reset_run` 建好，所以 `run_async` 的 lambda 不会在 None 上取 `.wait()`。
  2. `KeyboardInterrupt` → `exit()`；其他 `BaseException` 存入 `body_error`；重抛顺序是 body 优先、pump 次之。
  3. `_teardown` 在 `finally` 只调用一次，仍负责 exit、等待 pump、清 wake、关 owned source、最终帧与 dump。
- Host 协议静态检查结果：
  - `tests/interaction/test_host.py` 7 项全绿：`TUI` 结构性满足 `Host`、Partial 对象被拒、两个工厂返回真控件。
  - 结构核对通过：`Input` 具备 text/clear/insert/handle/render；`Autocomplete` 具备 set_query/move/activate/take_result/render；`Option` 具备 label/value。
  - 依赖方向未变：`kernel.host` 只 import kernel 内部模块（新增 `.lines`）；`interaction` 仍未 import `widgets`。
- overlay 基类的 layer 归属：layer 由子类以 keyword 传入（Tooltip=`tooltip`、Stats=`overlay`），基类不写死；`Toasts`/`Modal`/`Find` 生命周期语义不同，未并入。
- 坑（按踩坑成本排序）：
  1. Windows/Git Bash 下 `python -m motui --pages | head` 会以 `OSError: [Errno 22]` + exit 120 结束（head 提前关管道，不是回归）；验收须重定向到文件再判 exit code。
  2. `--pages` 输出约 4130 行，不要用管道截断判定。
  3. framebench 的 replay 是墙钟，ms 每次不同；只认 render-hash。
  4. worktree 必须 `PYTHONPATH="$PWD/src"` 覆盖主检出的 editable 安装；并行 pytest 带 `-p no:cacheprovider`。
- 看起来相关、其实不用碰：`widgets/textfield.py`、`widgets/autocomplete.py`、`kernel/frame.py`（只借 `DOCK_EDGES` 常量）、`tests/`、`demo/`。
- 下一波隐含约束：
  - 三个 Protocol 只用于类型，不得引入运行时 shim、别名或转发模块。
  - 不要改 `_holder` 的错误文本与 pane 列表顺序（测试按文本匹配）。
  - `_MountedOverlay.__init__` 的 `layer` 是 keyword-only；新增 overlay 子类照此传入。
  - `_run` 的 body 是零参 callable；公开入口的 `(tui)` 契约由 `run_session` 的 lambda 适配。
- 未决问题：无。

## C. 指针

- `app.py`：64-78 导入分组；375/388 工厂；485 `_holder`；772 `DOCK_EDGES`；1295 `_run`；1324 `run_session`；1344 `run_async`。
- `kernel/host.py`：101-141 三个协议；194-200 Host 工厂签名。
- `interaction/find.py`：101、186 去 cast；`palette.py`：81-84 去 cast；`overlays.py`：417 基类；`modal.py`：78 删 `PasteEvent`。
- commits：`712361c` T1、`0450555` T2、`6ed7db8` T3、`88b6fd4` T4、`91e6283` T5。
- 稳定区（已验收，不必重读）：`tests/`（未改）、`src/motui/widgets/`、`src/motui/demo/`、`kernel/` 除 `host.py` 外全部文件。
