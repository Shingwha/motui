# Spec MOTUI · W1：改名 motui + 死代码清理 + KeyRecorder 摘除（波次 W1）

> 分支 `rl1-rename`；worktree `C:/Users/shifu/.worktrees/mocode-tui/rl1-rename`；
> 前置：无；深读：`00-overview.md` + `ref/target-structure.md`（§8 名字替换口径）

## 目标

把发行名 / 包名 / import 名从 `mocode-tui` / `mocode_tui` 全量改为 **`motui`**，
同时摘掉已死的目录与 KeyRecorder 组件，并把仓库卫生清干净。
**除名称与登记删除项之外，渲染与行文行为零变化。**

## 工单（按序执行，每项一个 commit）

### T1 全量改名

- 起手：`uv sync`（在 worktree 内建独立 `.venv`）。
- `git mv src/mocode_tui src/motui`。
- 全仓替换（含 `src/`、`tests/`、`examples/`、`tools/`、`README.md`、`docs/`、`pyproject.toml`、`uv.lock` 生成物）：
  - `mocode_tui` → `motui`
  - `mocode-tui` → `motui`
  - 排除 `specs/2026-*`（历史组不改写；本组 `specs/2026-10-17-motui-launch/` 也不用改，它已经写 motui）。
- `pyproject.toml`：`name = "motui"`，`[tool.hatch.build.targets.wheel] packages = ["src/motui"]`；
  `version`/元数据本波**不动**（W4 统一做）。
- `uv lock && uv sync` 重生成 `uv.lock`（其中 `name = "mocode-tui"` 一节必须变为 `motui`），
  确认 editable 安装指向 `src/motui`。
- 生成物重录：`uv run python tools/apidoc.py --write`（`docs/API.md` 内所有 `mocode_tui.*` 路径）。
- 硬证据：`git grep -n "mocode" -- . ':(exclude)specs'` 输出为空；
  `uv run pytest -q` 全绿（基线 1473 passed, 1 skipped）。

### T2 死代码与仓库卫生

- 删除只剩 `__pycache__` 的死目录：`src/mocode_tui/chat/`（改名后为 `src/motui/chat/`）、`examples/showcase/`。
  （若 `git rm` 报未跟踪，用 `rm -rf`；这两个目录里**没有**任何 `.py`，先在报告里贴 `find` 证据。）
- 清掉工作区里的 `__pycache__/`、`.pytest_cache/` 残留（未跟踪，不产生 commit）。
- `.gitignore` 增加一行 `.zcode/`（用户的本地 agent 工作目录）。
- 验证：`uv run pytest -q` 仍全绿（这一条不该改变任何用例结果）。

### T3 摘除 KeyRecorder / ReplayKeys

- 删 `src/motui/keys/recorder.py` 与 `tests/test_keys_recorder.py`。
- `src/motui/keys/__init__.py`：去掉 `RecordingKeys` / `ReplayKeys` 的导入、`__all__`
  条目与 docstring 中「the recorder」那一段（重写该 docstring，保持文体，讲清
  `decoder` / `keymap` / `sources` / `console` 四件）。
- `tests/test_api_root.py`：`LAYER_ALLS["motui.keys"]` 收敛为
  `DEFAULT_EDITOR_KEYMAP DEFAULT_INPUT_KEYMAP EDITOR_SUBMIT_KEYMAP KeyDecoder Keymap RawTerminalKeys`；
  `DOWN_LISTED["motui.keys"]` 里的 `RecordingKeys ReplayKeys` 一并删掉。
- `README.md`：删掉「录制真实会话再回放」那一节（`## Testing without a terminal` 下的
  编号示例 1/2/3 中关于 record/replay 的部分），并修正该节其余文字里对 recorder 的引用。
  注意 `tests/test_readme_examples.py` 会解析 `## Quickstart` / `## Building your own shell` /
  `## Styling: Theme` / `## Keys and keymaps` 四节下的 python 块并执行——这四节必须保留且可运行。
- `examples/gallery/pages/devtools.py`：删掉/改写提到 `RecordingKeys / ReplayKeys` 的那一行文案
  （该页 golden 帧会随之变化，见 T4）。
- 硬证据：`git grep -n "RecordingKeys\|ReplayKeys\|recorder" -- . ':(exclude)specs'` 只剩
  `core/screen`（kernel/screen）里「in-memory recorder」这类与 KeyRecorder 无关的用法；
  报告里逐条列出剩余命中并说明为何保留。

### T4 golden 重录与全门禁

- 重录：`uv run python tools/golden.py --update`（14 帧）。
- **diff 审查（必须写进报告）**：逐帧 `git diff -- tests/golden/pages/`，确认每一处变化只能是
  - `mocode-tui gallery · <page>` 表头 → `motui gallery · <page>`；
  - 页面文案里的模块路径（如 devtools 的 `API · …`）与库名；
  - T3 删除的那行 devtools 文案。
  任何**其它**像素变化都是行为漂移，必须停下来报告，不得「顺手」接受。
- 全门禁（逐条贴真实输出）：`pytest`、`golden --check`、`framebench`、`demo < /dev/null`、
  `demo --pages`、`apidoc --check`。

## 验收（完成前自测，报告里给真实结论）

1. `uv run pytest -q` 全绿（用例数会因删掉 `test_keys_recorder.py` 而下降，报告里给出前后数字与差值来源）
2. `uv run python tools/golden.py --check` → `golden: 14 pages match`
3. `uv run python tools/framebench.py` → exit 0，含 `render-hash  : <64 hex>`
4. `uv run python tools/apidoc.py --check` → 通过
5. `uv run python examples/demo.py < /dev/null` 与 `uv run python examples/demo.py --pages` → exit 0
6. `git grep -n "mocode" -- . ':(exclude)specs'` → 空

## 禁触清单

- `specs/2026-*`（除本组目录外的历史 spec）
- `docs/DESIGN.md` / `docs/COMPONENTS.md` 的**内容**（W3 重写；本波只允许名字替换带来的机械改动）
- `pyproject.toml` 的元数据段、`LICENSE`、`tests/test_packaging.py`（W4 负责）
- `tests/test_api_root.py` 除 T3 指定的 keys 两条外的内容（根门面与分层断言由 W2 重写）
- `.github/workflows/`（不需要改，若不改也能过门禁就不要动；动了要说明）

## 最终报告格式

工单状态表（T1–T4 + commit hash）/ commit 清单 / 自测真实结论（六条命令的输出）/
golden diff 审查结论（逐帧列出允许的变化）/ 偏差与取舍 / 未决问题。
遇阻塞（例如替换后出现预期外的失败）→ 报告阻塞点后停止，不越界自救。
