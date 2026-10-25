# W0b · 模拟器、工具与静态护栏（不改变行为）

> 分支 `2.0/w0b-harness`；前置：W0a 已合并（`72084c1`）；写入范围：`src/motui/testing/**`、`tests/testing/**`、`tools/**`、`pyproject.toml`、`uv.lock`、`.github/workflows/ci.yml`
> 权威：`ref/source/10-waves/W0-harness.md` §4.4–4.6、`09-testing-tooling.md`、`01-architecture.md` §4

## 目标

交付 2.0 的可验证性底座，仍不改变任何生产行为：

1. VT 模拟器（`motui.testing.Emulator`）：消费 Painter 的一帧字节，维护 cell 网格，能对 1.x 固定帧做语义断言；
2. `tools/api.py`：公开面快照（`--check` / `--update` / `--allow-additions`）；
3. `tools/growth.py`：给 `Surface`/`Constraints`/`Scroll` 追加默认字段后跑全量门禁，证明可增长性；
4. `ruff` / `pyright` / `import-linter` 配置与 CI 阶梯；
5. `motui.testing` 从单文件变成包（保持 `headless_tui`/`snapshot` 导入不变）。

**本波结束：1002 个用例全绿；57 golden 逐字节不变；render-hash 不变；`ruff check .` / `pyright` / `lint-imports` / `api.py --check` / `growth.py` 全部可跑且通过。**

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W0a-values.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider     # 期望 1002 passed
  uv run python tools/golden.py --check    # 期望 57 topics match
  uv run python tools/framebench.py        # 期望 hash a82f7968…
  ```
- 稳定区（已验收，勿改）：`src/motui/core/**`、`widgets/**`、`app/**`、`demo/**`、`kernel/**`、`tests/core/**`、`tests/widgets/**`、`tests/app/**`、`tests/kernel/**`、`tests/golden/**`、`tools/golden.py`、`tools/framebench.py`。
- 已知事实（已核实）：
  - Painter 的一帧字节格式：可选的 `ESC[2J`，然后每行 `CUP(row,1) + ESC[K + <styled row>`；整帧可被 `ESC[?2026h` / `ESC[?2026l` 包裹；光标锚点是末尾 `CUP`；非 live 屏不写字节。
  - `HeadlessScreen.enter()` 额外写 `ESC[?1049h ESC[?25l`、鼠标/粘贴/焦点 DECSET；`leave()` 反向写。模拟器要忽略这些模式序列。
  - `Line.styled()` 已缓存 SGR 字节；SGR 可能包含 truecolor `38;2;r;g;b`、256 `38;5;n`、16 色、bold/dim/italic/underline/reverse/strike。
  - `Segment.link` 渲染为 OSC 8（`ESC]8;;url ESC\ ... ESC]8;; ESC\`）；模拟器可解析但只需不崩、并可选记录 link。
  - 1.x `core/lines.py` 的 `Segment` 宽度走 `visible_width`；模拟器用 `wcwidth` 计算宽字符，组合字符宽度 0。
- 环境：Windows Git Bash / Python 3.13 本地；CI 3.12 双平台。`ruff`/`pyright`/`import-linter` 当前**未安装**，需要写进 `pyproject.toml` 的 `[dependency-groups].dev` 并 `uv lock`。
- 已知坑：
  - `src/motui/testing.py` 是模块；改成包时用 `git mv` 保留历史，`from motui.testing import headless_tui, snapshot` 必须继续可用。
  - `tests/test_api.py` 校验 `motui.testing.__all__` 的可解析性；新增 `Emulator` 要进 `__all__`。
  - `tools/golden.py` 会把 `ROOT/src` 插到 `sys.path`；`tools/api.py` / `growth.py` 沿用同一约定，保证未安装也能跑。
  - CI 的 `uv sync --locked` 会在依赖变更后失败；必须提交 `uv.lock`。
  - ruff 规则在 1.x 全仓会有大量历史债；**不要在本波大改生产代码**。允许在 `pyproject.toml` 用显式 ratchet（`exclude`/`per-file-ignores`）让 `ruff check .` 为 0，并在 handoff 写清“哪些目录尚未纳入、W? 清理”。

## 工单（按序执行，每项一个 commit）

### T1 `motui.testing` 包化

- `git mv src/motui/testing.py src/motui/testing/__init__.py`（保留原 docstring/helpers，更新模块路径引用）。
- 新建 `src/motui/testing/emulator.py`，`__init__.py` 增加 `from .emulator import Emulator` 并进 `__all__`。
- 只允许改：`src/motui/testing/**`、`tests/testing/**`、`src/motui/__init__.py`（只改 `from .testing import ...` 的导入路径如需）。
- 验证：`uv run pytest -q tests/testing tests/test_api.py tests/test_smoke.py`。

### T2 `Emulator`（W0 最小 VT）

- 在 `src/motui/testing/emulator.py` 实现：
  ```python
  class Emulator:
      def __init__(self, width: int = 80, height: int = 24) -> None
      grid: list[list[Cell]]       # Cell 是 emulator 自己的冻结值：char, style, link
      cursor: Pos
      def feed(self, data: str | bytes) -> None   # 增量解析，可跨多次调用
      def text(self) -> str                        # 每行 rstrip，去掉尾部全空行
      def cell(self, x: int, y: int) -> Cell
      def sgr_at(self, x: int, y: int) -> Style    # 用 core.style.Style（testing 层可依赖）
      def resize(self, width: int, height: int) -> None
  ```
- 支持：`CUP`（`CSI H` / `CSI r;cH`）、`EL`（`K`）、`ED`（`2J`、`J`）、SGR（0 重置、1/2/3/4/7/9、30-37/40-47/90-97/100-107、38;5;n / 48;5;n、38;2;r;g;b / 48;2;r;g;b）、`\r`、`\n`、自动换行（写满 width 后下一字符到下一行首列）、光标显示/隐藏、alt screen（`?1049h/l`：清屏并重置光标）、同步更新（`?2026h/l` 忽略）、OSC（`]...BEL` / `]...ESC\` 忽略，OSC 8 可选记录 link）。
- 宽字符：CJK/emoji 占 2 列，第二列写占位（char=""）；组合字符宽度 0 附加到前一 cell。写入超出最后一行的换行按“滚动/停在末行”处理并写进 docstring（任选一种，测试固定）。
- 不做：图片协议、鼠标事件、真正的终端查询、行回卷历史。
- 测试 `tests/testing/test_emulator.py`：
  1. `CUP + "hello"` 落在正确坐标；
  2. `SGR 31;1` 后 `sgr_at` 的 fg/bold 正确，`SGR 0` 重置；
  3. `EL` 清到行尾、`2J` 全清；
  4. **20 列屏喂 40 个 A：第 0 行 20 个 A、第 1 行 20 个 A**（这是规格点名的回归）；
  5. CJK/emoji 占 2 列；
  6. 分片 feed（把一个帧拆成 3 段）结果一致；
  7. 1.x 固定帧：`headless_tui(20, 6)` + 一个已知文档，`paint()` 后 `Emulator(20,6).feed(screen.output)`，`text()` 与 `tui.rows()` 的逐行文本一致（尾部空白按各屏规则处理）。
- 只允许改：`src/motui/testing/emulator.py`、`src/motui/testing/__init__.py`、`tests/testing/test_emulator.py`。
- 验证：`uv run pytest -q tests/testing/test_emulator.py`。

### T3 `tools/api.py`

- 新建 `tools/api.py`：
  - 面：`motui`、`motui.kernel`、`motui.core`、`motui.widgets`、`motui.app`、`motui.testing`（不存在的面跳过；W1 后 core 消失、kernel/terminal 出现，快照随之更新）。
  - 每行：`<module>\t<name>\t<kind>\t<signature>`；`kind` 为 `class`/`function`/`module`/`value`；签名用 `inspect.signature`，失败时用 `repr` 的稳定形式（剥掉 `0x...` 地址）。
  - 排序稳定；`--update` 写 `tools/api-2.0.txt`；`--check` 逐行精确比较；`--allow-additions` 只比较 `(module,name)` 集合（允许新增名字/签名变化，不允许删除）。
  - `sys.path.insert(0, ROOT/"src")`，未安装可跑；退出码 0/1；打印 `api: N names match` 或差异清单。
- 生成初始快照（当前 1.x 面）并提交。
- 测试 `tests/testing/test_api_tool.py`（或 `tests/core/test_api_tool.py`，避免动已有目录就放 `tests/testing/`）：用临时目录复制 `tools/api.py` 的快照，断言 `--check` 通过；篡改一行后 `--check` 失败；`--allow-additions` 对新增名字通过。
- 只允许改：`tools/api.py`、`tools/api-2.0.txt`、`tests/testing/test_api_tool.py`。
- 验证：`uv run python tools/api.py --check`。

### T4 `tools/growth.py`

- 新建 `tools/growth.py`：
  1. 把 `src/`、`tests/`、`tools/`、`pyproject.toml` 复制到临时目录（`tempfile.TemporaryDirectory`）；
  2. 用 `ast` 给以下类各加一个带默认值的字段（插在最后一个字段后）：
     - `kernel.cell.Surface`: `_growth_probe: int = 0`
     - `kernel.layout.Constraints`: `_growth_probe: int = 0`
     - `kernel.layout.ScrollAxis`: `_growth_probe: int = 0`
     - `kernel.layout.Scroll`: `_growth_probe: int = 0`
  3. 在临时目录以 `PYTHONPATH=<temp>/src` 跑：
     - `python -m pytest -q -p no:cacheprovider`
     - `python tools/golden.py --check`
     - `python tools/api.py --check --allow-additions`
  4. 三者都 0 才通过；打印每条的真实结果；失败时打印临时目录保留路径（用 `--keep` 选项）。
  - 提供 `--quick`（只跑 `tests/kernel` + golden）便于本地；CI 默认全量。
  - 不修改真实仓库；不在临时目录里递归调用自己。
- 只允许改：`tools/growth.py`、`tests/testing/test_growth_tool.py`。
- 验证：`uv run python tools/growth.py --quick` 与一次全量（贴结果）。

### T5 静态护栏（ruff / pyright / import-linter）

- `pyproject.toml`：
  - `[dependency-groups].dev` 增加 `ruff>=0.8`、`pyright>=1.1.400`、`import-linter>=2.3`（或当时可用的稳定版）。
  - `[tool.ruff]`：`line-length = 100`、`target-version = "py312"`、`select = ["E","F","I","UP","B","SIM","RUF"]`。
    - 先跑 `uv run ruff check .` 记录基线；若 1.x 历史债过多，用显式 ratchet（`exclude` 或 `per-file-ignores`）把尚未迁移的目录排除，**不得**用 `# noqa` 批量糊；handoff 写清剩余目录与清理波次。
    - `E501` 若因历史长行无法清零，可 `ignore = ["E501"]` 并记录（W5 前处理）；其余规则必须 0。
  - `[tool.pyright]`：`include = ["src/motui/kernel", "src/motui/testing", "tools"]`、`typeCheckingMode = "strict"`；先只覆盖 kernel/testing/tools，后续波扩大。若 strict 报错，修代码或对第三方未类型化 API 加最小 `# type: ignore[...]`（逐条、带原因）。
  - `[tool.importlinter]`：`root_package = "motui"`；contract 1 `kernel has no I/O`（forbidden: os/sys/io/ctypes/termios/tty/select/asyncio）；contract 2 `kernel is a leaf`（forbidden: motui.core, motui.widgets, motui.app, motui.terminal）。
- 反向演练（写进 handoff）：临时给 `kernel/geom.py` 加 `import os`，`lint-imports` 必须失败；恢复。
- `uv lock` 更新 `uv.lock`。
- 只允许改：`pyproject.toml`、`uv.lock`（`src/motui/kernel/**` 仅在 strict 修类型时允许最小改动，且需在报告说明）。
- 验证：`uv run ruff check .`、`uv run pyright`、`uv run lint-imports` 全部 0。

### T6 CI 阶梯

- `.github/workflows/ci.yml` 在 `uv sync --locked` 之后、`pytest` 之前插入：
  ```yaml
  - name: ruff
    run: uv run ruff check .
  - name: pyright
    run: uv run pyright
  - name: import-linter
    run: uv run lint-imports
  ```
  在 golden 之后追加：
  ```yaml
  - name: api snapshot
    run: uv run python tools/api.py --check
  - name: growth
    run: uv run python tools/growth.py
  ```
- 保持双平台矩阵；不新增平台。
- 只允许改：`.github/workflows/ci.yml`。
- 验证：本地等价命令全跑一遍；YAML 语法用 `uv run python -c "import yaml..."` 无法依赖 PyYAML，改为人工检查缩进。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴真实数字；期望 1002 + 新工具用例）。
2. `uv run python tools/golden.py --check` → `57 topics match`。
3. `uv run python tools/framebench.py` → render-hash `a82f7968…` 不变。
4. `uv run ruff check .` → 0（若 ratchet，贴 ratchet 范围）。
5. `uv run pyright` → 0 error。
6. `uv run lint-imports` → 0 broken。
7. `uv run python tools/api.py --check` → 通过。
8. `uv run python tools/growth.py` → 三条全绿（贴输出）。
9. 反向演练：临时 `import os` 让 `lint-imports` 红、篡改快照让 `api.py --check` 红（完成后恢复）。
10. `python -m motui < /dev/null` / `--pages` exit 0。

## 禁触清单

`src/motui/core/**`、`src/motui/widgets/**`、`src/motui/app/**`、`src/motui/demo/**`、`src/motui/kernel/**`（类型注解微调除外，见 T5）、`tests/core/**`、`tests/widgets/**`、`tests/app/**`、`tests/kernel/**`、`tests/golden/**`、`tools/golden.py`、`tools/framebench.py`、`README.md`、`docs/**`、`CHANGELOG.md`。

## 交接包

最后 commit 写 `specs/2026-10-25-0900-motui-2-0-architecture/handoff/W0b-harness.md`：A 节给新增文件/签名/命令真实结果；B 节写模拟器支持的 escape 列表、ruff ratchet 范围与理由、pyright 收敛范围、growth 的临时目录策略、未决项；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍（尤其 ruff ratchet 与 pyright 范围）/ 交接校验（W0a 哪些事实被验证）/ 探索审计 / 未决问题。
