# W7b handoff · 文档整体重写

## A · 交付

分支 `w7b-docs`；实现 commit `a02e475`（本文件所在 commit 为 handoff）。
改动范围仅 `README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`、
`docs/CONTRACT.md`、`CONTRIBUTING.md`、`tests/test_readme_examples.py`、
新增 `tests/test_docs_claims.py`。

**新文档结构**

- `README.md`（481 行）：定位/三卖点 → Install → Quickstart（可运行
  Input/Button/FocusManager/Pointer）→ 60 秒心智模型 → 分组 Features →
  六组组件表（覆盖 `motui.widgets.__all__` 44 名）→ Interactions（tier
  表 + 挂载代码 + dispatch order）→ Build your own shell（可运行
  footer/dock 配方）→ Styling → Markdown/syntax → Keys/keymaps → Demo
  （6 sections/58 topics）→ Docs/License。
- `docs/DESIGN.md`（560 行）：问题 → 分层/Host → 坐标/命中 → 事件/解码
  → driver 生命周期 → document/Revisioned/缓存 → viewport/dock →
  frame/overlay LAYERS → painter → selection/focus → 值语义 → non-goals；
  每节“问题 → 机制 → 取舍”，并给出扩展落点。
- `docs/COMPONENTS.md`（1127 行）：协议 → driver 调用顺序 → 六组任务
  目录（44 widget + Modal/Palette），固定 `purpose → signature → verbs
  → result → protocols → notes` → RowBands/disabled/read_only →
  Container/child_at → 交互控制器 → CommandRegistry/Clipboard →
  Theme/glyphs/keymaps → 5 个 build-your-own 配方 → testing。
- `docs/CONTRACT.md`（325 行）：短规范；事件、坐标、driver、panes/
  docks、组件协议、focus/selection/overlays、分层 + Host、缓存、命名
  charter、non-goals、gates；教程内容链接出去。
- `CONTRIBUTING.md`（191 行）：单向依赖图、gates、加组件/topic、SemVer
  与“发版等用户测试重构 + 单独指令”。
- 测试：`test_readme_examples.py` 执行新 README 的 quickstart、shell、
  Markdown、Theme、keymap 示例（11 tests）；`test_docs_claims.py` 锁定
  root 34、widgets 44、固定模板、LAYERS、Host 字段、demo 6/58、过期名
  与相对链接（11 tests）。

**真实自测（worktree 根）**

- `uv run pytest -q -p no:cacheprovider`：**2190 passed, 2 skipped**
  （W7a 基线 2178 + 12 个新文档测试）。
- `uv run python tools/golden.py --check`：`golden: 58 topics match`。
- `uv run python tools/framebench.py`：exit 0；render-hash
  `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`
  （与 W7a 后一致）。
- `uv run python -m motui < /dev/null`：exit 0，70 行；`--pages`：exit 0，
  4130 行，58 topic header + 6 section header。
- 过期名 grep（`FocusRing`、`chosen`、`hit_test`、`add_band`、
  `viewport_rows`、`invalidate(`、`stop()`、`read_key`、`CheckGroup`、
  `Radio(`、`cursor_style`、`selected_style`）零命中（exit 1）。
- `motui.__version__` 仍 **1.1.8**；`pyproject.toml`、`uv.lock`、
  `CHANGELOG.md`、`docs/releases/**`、`src/motui/**`、`tests/golden/**`
  均未改动。

## B · 偏差、取舍与约束

- README 比旧版长（481 行），但顺序按读者路径重排：安装、可运行
  quickstart、心智模型在前；机制细节留 DESIGN，组件细节留 COMPONENTS。
- 文档不写发布号/迁移叙事；CONTRACT 也不带版本号。版本策略在
  CONTRIBUTING 用 SemVer 描述，并注明发版等待用户测试重构与单独指令。
- docs claims 测试阻止组件目录漏项、LAYERS 顺序漂移和过期名回流；
  相对链接检查只覆盖本地文件。
- README 的 Interactions 挂载代码块可构造但未被测试执行（只创建控制器、
  不进入 run）；执行的是 quickstart、shell、Markdown、Theme、keymap。
- 未修改库代码，未发现本波需修的代码 bug；签名以 `inspect.signature`
  和源码 docstring 为准。

## C · 关键位置与稳定区

- 入口 `README.md`；机制 `docs/DESIGN.md`；目录 `docs/COMPONENTS.md`；
  规范 `docs/CONTRACT.md`；流程 `CONTRIBUTING.md`。
- 事实测试 `tests/test_docs_claims.py`；示例执行
  `tests/test_readme_examples.py`。
- 稳定区（未触碰）：`src/motui/**`、`pyproject.toml`、`uv.lock`、
  `CHANGELOG.md`、`docs/releases/**`、`tests/golden/**`、`specs/**`
  （本文件除外）。
- 未决问题：无阻塞项。新增 widget 需同步 COMPONENTS 模板条目与
  docs claims 的名字/数量断言；新增 overlay layer 需同步 DESIGN 的
  LAYERS 代码块。
