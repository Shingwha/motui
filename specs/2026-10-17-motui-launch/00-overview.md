# Spec MOTUI · 通用 TUI 库重启（换名 motui + 分层重构 + 上架 PyPI）

> 操作启动日 **2026-10-17**（组内 slug `motui-launch`）。
> 本组把一个「为 mocode agent 而生」的 TUI 工程改造成一个可以公开发布的通用 TUI 库：
> 换名 **motui**、按命名空间分层重排模块、摘掉内核之外的死重量、补齐 MIT 许可与 PyPI 元数据。
> 11 个历史 spec 组（`specs/2026-*`）是过程资产，**本组不改写它们**。

## 目标与范围

一句话：**除了「名字、模块路径、导入面、本组登记的两处删除」之外，渲染与行为零变化。**

四件事：

1. 发行名 / 包名 / import 名 `mocode-tui` / `mocode_tui` → **`motui`**（全仓 244 个文件含该串，其中非 specs 约 230 个）。
2. 结构重排为**命名空间分层 + 精简根**：`core/` → `kernel/`，新建 `interaction/`（收 `focus`/`gesture`/`pointer`/`search`），根门面从 73 名收敛到 **31 名**，其余全部留在各层门面（**一个名字都不消失**，只是换了导入路径）。
3. 摘除登记的两处：**KeyRecorder / ReplayKeys**（`keys/recorder.py` 及其测试、门面、README 章节、gallery 文案）与**只含 `__pycache__` 的死目录**（`src/mocode_tui/chat/`、`examples/showcase/`）。
4. 交付一个**能上 PyPI 的仓**：MIT `LICENSE`、完整 `pyproject` 元数据、`__version__`、sdist 排除 `specs/`、`uv build` 产物可安装并跑通的真实证据，以及面向公众重写的 README。

不在范围内：新功能、渲染变更、性能优化、`specs/` 历史改写、push / tag / 发版。

## 决策登记（lead 已拍板，worker 不复议）

| # | 决策 | 内容 |
|---|---|---|
| D1 | 名称 | **`motui`**（PyPI 未占用；GitHub 无 Python/TUI 同名项目；import 名与发行名同为 `motui`） |
| D2 | 结构 | 命名空间分层 + 精简根：`kernel/`、`keys/`、`widgets/`、`interaction/` + 顶层 `app.py` / `chrome.py` / `testing.py`（见 `ref/target-structure.md`） |
| D3 | 根门面 | **31 名**，逐字见 `ref/target-structure.md`；其余名字留在各层门面，不删除 |
| D4 | 裁剪 | 只删 **KeyRecorder/ReplayKeys**；其余组件与层级全部保留 |
| D5 | 许可 | **MIT**（版权行 `Shingwha`） |
| D6 | 版本 | **1.0.0**（换名即重开版本线；`motui.__version__` 从安装元数据读） |
| D7 | 死代码 | 删 `src/mocode_tui/chat/`、`examples/showcase/`、全部 `__pycache__`/`.pytest_cache` 残留；`.gitignore` 增加 `.zcode/` |
| D8 | specs/ | 不改写，但从 sdist 排除（仓内保留） |
| D9 | 仓库元数据 | `pyproject` 的 `[project.urls]` 暂用现有仓库地址 `https://github.com/Shingwha/mocode-tui`（用户改名仓库时同步改这一行，本组不猜新地址） |
| D10 | demo | **随包发布**：`examples/gallery/` → `src/motui/demo/`（`examples/` 目录消失）；入口 `python -m motui` + 控制台脚本 `motui`；版面改**左轨 + 右内容**（取消顶部 tab 条）；页表 14 → **11** 页；demo 代码 ≤ **2000** 行（详见 `ref/demo.md`） |
| D11 | Tabs 纵向 | `Tabs` 新增 `orientation="horizontal"(默认)|"vertical"`（横向字节不变，纵向按行解析索引）；这是本组唯一的新增能力，为左轨而设 |
| D12 | 测试层 | **大幅精简**：只留高价值核心（内核原语 / 渲染核心 / 选择内核 / 解码器 / 各组件契约与交互动词 / 驱动核心路径 / 交互层 / chrome / markdown / demo 接线 / 五条门禁契约）。脆弱、冗余、低信号、重复参数化的用例**直接删**；逐文件的裁剪清单由 lead 在 `06-w6-tests.md` 里给定，worker 不自行发挥 |

## 目标结构（细节与逐字清单见 `ref/target-structure.md`）

```
src/motui/
├── __init__.py        精简根门面（31 名）
├── kernel/            原 core/：primitives · events · block · render core · frame · selection
├── keys/              decoder · keymap · sources · console
├── widgets/           组件库 + widgets/markdown/
├── interaction/       新：focus · gesture · pointer · search
├── app.py             TUI 驱动（composition root）
├── chrome.py          Scrollbar · Toasts · Tooltip · Stats
└── testing.py         headless_tui · snapshot
```

导入契约（README 与 DESIGN 都要讲这一条）：

```python
from motui import TUI, Input, Markdown            # 根：31 个高频名，一行起手
from motui.widgets import Row, Panel, Diff        # 层命名空间：完整组件库
from motui.kernel import Style, Line, Selection   # 内核深缝
from motui.keys import DEFAULT_INPUT_KEYMAP
from motui.interaction import FocusRing, Pointer, SelectionGesture, Find
from motui.chrome import Scrollbar, Toasts
```

## 波次表

| 波 | 主题 | 分支 | 前置 | 并行 |
|---|---|---|---|---|
| W1 | 改名 motui + 死代码清理 + KeyRecorder 摘除 | `rl1-rename` | — | 串行 |
| W2 | 分层重构（core→kernel、interaction/）+ 精简根门面 | `rl2-structure` | W1 | 串行 |
| W3 | README / docs 面向公众重写 | `rl3-docs` | W2 | ∥ W4 ∥ W5 |
| W4 | PyPI 上架件（LICENSE / 元数据 / 构建与安装实证） | `rl4-packaging` | W2 | ∥ W3 ∥ W5 |
| W5 | demo 随包发布 + 左轨版面重构 | `rl5-demo` | W2 | ∥ W3 ∥ W4 |
| W6 | 测试层精简（按 lead 给定的逐文件清单） | `rl6-tests` | W3+W4+W5 | 串行 |
| W7 | lead 终验 + 汇总 | — | W6 | — |

W3 / W4 / W5 写入范围文件级不相交：

- **W3 拥有**：`README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`
- **W4 拥有**：`LICENSE`、`pyproject.toml`、`tests/test_packaging.py`
- **W5 拥有**：`src/motui/demo/**`、`src/motui/__main__.py`、`src/motui/widgets/tabs.py`、`examples/**`（删除）、
  `tests/golden/**`、`tests/test_gallery_protocol.py`、`.github/workflows/ci.yml`

三者都**不得**触碰 `docs/API.md`（生成物，W2 已重录）、`tests/test_api_root.py`（W2 已定稿）、
`tests/test_api_doc.py`、`src/motui/kernel|keys|interaction|chrome|app|testing`。

W6 要在 W3/W4/W5 全部合并后开工（它裁的就是最终的测试集），开工前 lead 会把实测基线（用例数与文件清单）写进 `06-w6-tests.md`。

## 全局不变量（每个 commit 都要满足）

1. **行为零变化**：除名称、模块路径、登记删除项外，渲染输出与运行行为不变。W1/W2 重录 golden 时，帧内 diff 必须**只有**可解释的名称/路径差异，写进报告。
2. **门禁全绿**（在各自 worktree 内逐条跑，贴真实输出）：
   - `uv run pytest -q`（基线：1473 passed, 1 skipped）
   - `uv run python tools/golden.py --check`（基线：`golden: 14 pages match`；W5 起为 11 页）
   - `uv run python tools/framebench.py`（要求 exit 0 且含 `^render-hash  : [0-9a-f]{64}$` 行；hash 值本身不比对）
   - `uv run python tools/apidoc.py --check`（W2 起）
   - demo 门的命令按波次口径：W1–W4 用 `uv run python examples/demo.py …`，**W5 起**改为
     `uv run python -m motui …`（`< /dev/null` 与 `--pages` 两档都是 exit 0 要求）
3. **grep 断言**（各波完成时的硬证据）：
   - W1 后：`git grep -n "mocode" -- . ':(exclude)specs'` 为空。
   - W2 后：`git grep -n "motui\.core"` 为空；`git grep -n "mocode" -- . ':(exclude)specs'` 仍为空。
   - W4 后：`git grep -n "mocode" -- . ':(exclude)specs'` 仍为空。
4. **不 push、不打 tag、不 checkout main、不 merge**；worker 不碰主检出与其他 worktree。
5. **commit 粒度**：一个工单一个（或更细的）commit，每个 commit 独立过门禁；message 沿用仓库风格（英文、`type(scope): 祈使句`，见 `git log`）。
6. 代码注释与 docstring 用**英文**（沿用现状）；spec 文档用中文（本组）。
7. 新增能力不新增兼容补丁；发现旧 shim 失去消费者时顺带拆除（本组没有这类目标，不要顺手扩大范围）。
8. 端口/共享资源：本组不需要网络服务；`uv sync` 在各自 worktree 内建独立 `.venv`，互不共享。

## Git / worktree 协议（本组沿用 spec-team 约定）

- worktree 根：`C:/Users/shifu/.worktrees/mocode-tui/<分支名>`，由 lead 创建与销毁。
- 分支从**合并时刻的最新 main** 创建（lead 负责；worker 不 rebase、不 merge）。
- 合并顺序 = 波次顺序；并行波内先 W3 后 W4（文件不相交，顺序只为日志清晰）。
- 全程不 push、不打 tag；版本号变更写在 `pyproject`（W4），但不触发任何发布动作。

## 收尾口径

- lead 逐分支 `merge --no-ff`，合并前后各跑一次全量门禁。
- 终验（W5）：全门禁 + 三入口抽验（`examples/demo.py` 交互档起序、`--pages` 全页 dump、`uv build` 产物在干净 venv 中 import 并跑一个最小会话）。
- 遗留清单里必须列明：`[project.urls]` 待用户改名仓库后同步、89 个已合并旧分支是否清理、`specs/` 历史保留策略。

## 报告格式（每个 worker 的最终报告都要有）

1. 工单状态表（T1..Tn：done/未完成 + commit hash）
2. commit 清单（hash + message）
3. 自测真实结论（逐条命令 + 真实输出片段：用例数与失败项、golden 行、hash 行、diff 审查结论）
4. 偏差与取舍（与 spec 不一致处，逐条说明）
5. 未决问题 / 阻塞（阻塞即停，不越界自救）
