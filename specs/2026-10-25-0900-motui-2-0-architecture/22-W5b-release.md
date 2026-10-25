# W5b · 示例、CI、demo 文案清理与 2.0 终验

> 分支 `2.0/w5b-release`；前置：W4b 已合并（`14756cb`）；写入范围：`examples/**`、`tests/test_examples.py`、`.github/workflows/ci.yml`、`src/motui/demo/**`（仅可执行代码/展示文案）、`src/motui/app/{application,commands}.py`（仅删除兼容 shim）、`tests/**`（相应调用）、`tests/golden/{topics,semantic}/**`、`tests/golden/README.md`、`tools/api-2.0.txt`
> 权威：`ref/source/10-waves/W5-docs-release.md` §3.3–3.6、`12-acceptance.md`

## 目标

交付可执行的 2.0 示例、清理兼容 shim、重录展示文案相关 golden，并跑完整终验：

1. `examples/quickstart.py`（≤30 行）+ 现有 snake/dashboard/wide_table 全部 `--headless` 可跑；
2. CI 增加四个示例步骤；
3. demo 展示文案从 `TUI`/`take_result`/`activate` 迁到 2.0 名（golden 重录 + 分类）；
4. 删除 `Command` 位置参数 shim、`App.remove(str)` shim（demo/tests 先迁移）；
5. 全量门禁 + 版本/示例/语义 golden 终验。

**本波结束：四个示例 exit 0；pytest/语义 golden/framebench/demo/ruff/pyright/lint-imports/api/growth 全绿；版本 2.0.0（W5a 负责）；无兼容 shim（除已记录的字符串入口）。**

## 前置上下文

- 必读：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W4b-api.md` → 本工单。
- 基线：`uv sync --locked`；`pytest`（1592 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `examples/snake.py`、`dashboard.py`、`wide_table.py` 已 `--headless`；无 quickstart。
  - `tests/test_examples.py` 只跑 snake/wide_table/dashboard（按现状检查）。
  - demo 展示文案含 `TUI`/`take_result`/`activate`（`api_line`/code fence），golden 锁字节。
  - `Command` 有位置参数 metaclass shim（W4b 为 demo 保留）；`App.remove` 接受 `str | Section`。
  - demo 的 `_stage_ids` 现持有 `Section`（W4b）或 id；需检查。
- 清理规则：
  - demo 可执行代码与展示字符串都改为 2.0（`App`/`Runtime`、`take()`、`on_action`、`Section`、`Axis`/`Placement`）；展示字符串变更会导致对应 golden 变化，重录并分类为“showcase text”。
  - `Command` demo 调用改 `Command(name=..., group=..., description=..., keys=..., handler=...)`；删除 metaclass/`__signature__` shim；`CommandRegistry.options()` 保持 description（分组展示 W6+，如需把 group 放 description 会改变 palette golden，先不做）。
  - `App.remove` 只接受 `Section`（或 id? 目标说 Section；内部 `_forget` 用 component）。demo/tests 全迁移后删除 str 分支。
  - `split("vertical")`/`dock(edge=)` 字符串入口本轮**保留**（大量测试/示例使用）；在 handoff 标记为已知兼容层，W5 之后可删。不要为了删它改 100+ 测试。
  - `App` 旧构造参数（mouse/hover/keys/screen）保留；文档只推 TerminalOptions。
- 已知坑：
  - golden 重录后 `render-hash` 会变（展示文案变化）；记录新 baseline，分类只允许 showcase text / 命令分组（若发生）。
  - `semantic --update` 会重写 57 文件（CRLF 噪声）；只提交真实内容变化。
  - `tests/golden/README.md` 增加“2.0 showcase text”节。
  - CI 双平台：示例用 `subprocess`/`--headless`，不依赖 TTY；Windows 路径用 `sys.executable`。
  - `quickstart.py` 的 headless 输出要确定；不要 sleep。
  - 不要删除 `tools/golden.py`/字节 golden（保留为额外回归门禁；在 handoff 说明与源 spec 的偏差）。
- 不改 kernel/terminal/widgets 行为；不改 docs（W5a）。

## 工单（按序，每步一个 commit）

### T1 `examples/quickstart.py`

- 新建 `examples/quickstart.py`（≤30 行）：
  - 使用 `App` + `TerminalOptions` + `HeadlessScreen`（`--headless`）+ `Text` + `Input`；
  - `app.add(Text(...))`、`app.add(Input(...))`；`app.paint_now()`；打印前三行；
  - `--headless` exit 0；默认（无 TTY）也走 headless（不要在 CI 卡住）。
- `tests/test_examples.py` 加 subprocess 用例；运行 `uv run python examples/quickstart.py --headless`。
- 只允许改：`examples/quickstart.py`、`tests/test_examples.py`。
- 验证：`uv run python examples/quickstart.py --headless`；`uv run pytest -q tests/test_examples.py`。

### T2 CI 示例步骤

- `.github/workflows/ci.yml` 在 demo 步骤后加：
  `quickstart / snake / dashboard / wide_table` 四个 `uv run python examples/<name>.py --headless`。
- 只允许改：`.github/workflows/ci.yml`。
- 验证：本地逐条跑 exit 0。

### T3 demo 文案与 shim 清理

- `src/motui/demo/**`：
  - 展示字符串 `TUI(...)`/`TUI().run()` → `App(...)`/`App().run()` 或 `Runtime(...)`（选与示例/README 一致的 `App`）；
  - `take_result()` → `take()`；`activate()` → `on_action("activate")`（展示文案按 2.0 API 改写）；
  - `Command(...)` → 关键字 + `group=`；
  - `_stage_ids`/`App.remove` 改用 Section。
- `src/motui/app/commands.py`：删除位置参数 metaclass/`__signature__` shim；`Command` 保持 `kw_only`。
- `src/motui/app/application.py`：`App.remove` 只接受 `Section`（demo/tests 迁移后删除 str 分支）。
- `tests/**`：同步 `Command`/`App.remove`/文案断言。
- 只允许改：`demo/**`、`app/{commands,application}.py`、`tests/**`。
- 验证：`uv run pytest -q -p no:cacheprovider`；先不重录 golden，记录失败 topics。

### T4 golden 重录与分类

- `golden.py --update`、`semantic.py --update`。
- 逐 topic 分类：只允许 `showcase-text`（TUI/take_result/activate/Command 文案）与 `command-group`（若 palette 展示变化）；其它变化停下修代码。
- `tests/golden/README.md` 记录 2.0 showcase text 与新的 `render-hash`。
- 只允许改：`tests/golden/**`、`tests/golden/README.md`、handoff。
- 验证：`golden --check`、`semantic --check`；新 hash 记录。

### T5 终验

- 全量：`pytest`、`golden --check`、`semantic --check`、`framebench`、`python -m motui < /dev/null`、`--pages`、四个示例、`ruff`、`pyright`、`lint-imports`、`api --check`、`growth.py`（全量）。
- `motui.__version__`（W5a 完成后）应为 `2.0.0`。
- `grep -rn "TUI" src/motui --include=*.py` 只剩历史/注释/展示串（列出）；`take_result`/`activate` 可执行 0。
- `Command` 位置参数 shim 删除；`App.remove(str)` 删除。
- 记录 Runtime/Workspace 行数与已知偏差。
- 只允许改：`tools/api-2.0.txt`、handoff。
- 验证：全部真实输出。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. `semantic --check` 57；`golden --check` 57（重录后）；`framebench` 记录新 hash 且无 >10% 劣化。
3. `python -m motui < /dev/null` / `--pages` exit 0（行数记录）。
4. 四个示例 `--headless` exit 0；CI 含四步。
5. `Command` kw_only 无位置 shim；`App.remove` 只收 Section；demo 展示文案为 2.0。
6. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth.py`（full）全绿。
7. golden 分类只含 showcase-text/command-group；新 hash 已记录。

## 禁触清单

`kernel/**`、`terminal/**`、`widgets/**`、`docs/**`、`README.md`、`CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`、`tools/{golden,framebench,semantic}.py`、`tests/golden/README.md` 仅 T4 允许。

## 交接包

最后 commit 写 `handoff/W5b-release.md`：A 节给四个示例/CI/清理/golden 分类/新 hash/终验；B 节给保留的字符串入口兼容层、字节 golden 保留偏差、Runtime 行数、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（W4b 事实）/ 探索审计 / 未决问题。
