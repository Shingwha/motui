# Spec MOTUI · W2：分层重构 + 精简根门面（波次 W2）

> 分支 `rl2-structure`；worktree `C:/Users/shifu/.worktrees/mocode-tui/rl2-structure`；
> 前置：W1 已合并（`motui` 名字生效）；深读：`00-overview.md` + `ref/target-structure.md`（**逐字清单的唯一来源**）

## 目标

把 `motui` 从「core + 顶层散模块 + 73 名根门面」改成「命名空间分层 + 31 名精简根」，
**一个名字都不删**：`core/` → `kernel/`，新建 `interaction/` 收 `focus`/`gesture`/`pointer`/`search`，
根只留 31 名，其余全部留在各层门面。渲染与行为零变化（模块路径与导入面除外）。

## 工单（按序执行，每项一个 commit）

### T1 `core/` → `kernel/`

- `git mv src/motui/core src/motui/kernel`。
- 全仓 `motui.core` → `motui.kernel`（import、docstring 交叉引用 ``~motui.core.…``、测试、examples、tools、docs）。
- `kernel/__init__.py` 的 `__all__` **逐字保持**今天 `motui.core` 的 60 名与顺序（见 ref §2），
  只改 docstring 里的包名与「the kernel」表述。
- 硬证据：`git grep -n "motui\.core"` 为空；`uv run pytest -q` 全绿。

### T2 新建 `interaction/`

- `git mv src/motui/focus.py src/motui/gesture.py src/motui/pointer.py src/motui/search.py src/motui/interaction/`。
- 修正包内相对导入（`from .app import TUI` → `from ..app import TUI`；
  `from .core.block import …` → `from ..kernel.block import …`；`from .widgets.input import …`
  → `from ..widgets.input import …` 等，按实际逐一核对；`TYPE_CHECKING` 分支同样处理）。
- 新建 `src/motui/interaction/__init__.py`：门面 `__all__ = ["Find", "FocusRing", "Pointer", "SelectionGesture", "copy_on_select"]`
  （顺序即 ref §2；docstring 写清「四个策略层：焦点环、鼠标选区的姿态、悬停与定点点击、搜索」）。
- 硬证据：`git grep -n "motui\.focus\|motui\.gesture\|motui\.pointer\|motui\.search"` 为空；
  `uv run pytest -q` 全绿。

### T3 精简根门面

- 重写 `src/motui/__init__.py`：`__all__` 逐字为 ref §3 的 31 名（顺序按 `_groups` 规则）；
  导入按层组织（`from .app import TUI`、`from .kernel import …`、`from .widgets import …`、
  `from .interaction import …`、`from .chrome import …`、`from .testing import …`）。
- docstring 按 ref §7 的四点要求重写（定位一句 / 五个层各一句 / 导入契约 / 依赖方向），
  文体沿用仓库现状（英文、克制、讲机制）。
- 确认 `motui.__version__` 本波**不加**（W4 负责）。
- 硬证据：`python -c "import motui; print(len(motui.__all__))"` → 31；
  `python -c "import motui; [getattr(motui,n) for n in motui.__all__]"` 无误。

### T4 门面清单与 API 页同步

- `tools/apidoc.py`：`FACADES` 改为 ref §5 的九项（顺序即页面顺序），并把文件头注释里
  的 `mocode_tui` 例子改掉。
- `uv run python tools/apidoc.py --write` 重录 `docs/API.md`；随后 `--check` 必须通过。
- `tests/test_api_root.py` 全面更新：
  - `ROOT_ALL` = ref §3 的 31 名；`len(...) == 31` 的断言同步。
  - `LAYER_ALLS` 覆盖九个门面（`motui`、`motui.kernel`、`motui.keys`、`motui.widgets`、
    `motui.app`、`motui.chrome`、`motui.interaction`、`motui.testing`；`motui.widgets.markdown`
    不在 LAYER_ALLS 里就保持现状，只在 DOWN_LISTED 里验路径）。
  - `DOWN_LISTED` 按 ref §4 的表重写（42 名各自的落点）。
  - `test_the_selection_mechanism_imports_from_the_root` 之类的**机制断言**：若某条断言
    依据的名字已不在根（如 `Selection`/`extract`/`highlight`），改为从 `motui.kernel` 导入并
    重命名该测试，说明它验证的是「内核机制在层门面可达」。
  - 文件头 docstring 里「73 names today」等口径同步。
- 硬证据：`uv run pytest -q tests/test_api_root.py tests/test_api_doc.py` 全绿。

### T5 消费者导入口径

- 按 ref §6 更新 `examples/`（gallery 各页、shell、registry、session、script、content、demo）与
  `tests/` 里对下放名字的导入：能走根就走根，其余走最浅的层门面；
  需要内核深缝时保持 `motui.kernel.<module>`。
- gallery 页面里**写死的模块路径文案**（`examples/gallery/pages/devtools.py` 的 `API · …` 行、
  `page.py` / `shell.py` / `session.py` / `script.py` 的 docstring 交叉引用）同步成新路径。
- 硬证据：`uv run python examples/demo.py --pages` exit 0；`git grep -n "motui\.core"` 仍为空。

### T6 golden 重录 + 全门禁

- `uv run python tools/golden.py --update`；**diff 审查**：只允许模块路径/库名文案变化
  （devtools 页会因 `motui.kernel.*` 文案变化），任何渲染漂移都要停下报告。
- 全门禁逐条跑并贴真实输出（同 W1 的六条）。

## 验收

1. `uv run pytest -q` 全绿（与 W1 结束时的用例数一致——本波只改导入面，不增删用例）
2. `golden --check` 14 页 match；`framebench` exit 0 + hash 行；`apidoc --check` 通过
3. `demo < /dev/null`、`demo --pages` exit 0
4. `git grep -n "motui\.core"` 为空；`git grep -n "mocode" -- . ':(exclude)specs'` 仍为空
5. `python -c "import motui; print(motui.TUI is __import__('motui.app', fromlist=['TUI']).TUI)"` → True

## 禁触清单

- 任何**功能与渲染逻辑**：本波只改路径、门面与导入；`kernel/`、`widgets/`、`interaction/` 的
  函数体一律不动（import 行除外）。
- `README.md`（W3）、`pyproject.toml` 元数据与 `LICENSE`（W4）
- `specs/2026-*` 历史目录
- `tests/golden/pages/*.txt` 除 T6 重录外不得手改

## 最终报告格式

工单状态表（T1–T6 + commit hash）/ commit 清单 / 自测真实结论 / golden diff 审查结论（逐帧）/
偏差与取舍 / 未决问题。阻塞即停。
