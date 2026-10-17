# Spec MOTUI · W3：README / docs 面向公众重写（波次 W3）

> 分支 `rl3-docs`；worktree `C:/Users/shifu/.worktrees/mocode-tui/rl3-docs`；
> 前置：W2 已合并（分层与 31 名根门面生效）；深读：`00-overview.md` + `ref/target-structure.md`
> 与 W4 **并行**：只写 `README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md` 三个文件。

## 目标

把「写给 mocode agent 宿主」的文档，改写成「一个陌生开发者第一次打开 PyPI 页面能读懂并跑起来」
的文档。**语气与文体保留**（本库的文档有辨识度：讲机制、不吹、不说套话），但结构重排：
先安装、再起手、再分层契约、然后才是深水区。

## 工单（按序执行，每项一个 commit）

### T1 README 重写

结构（可微调，但下列要素必须齐备）：

1. **一句话定位**（标题下第一段）：分层全屏 TUI 工具包 —— alt screen、block 文档、视口滚动、
   pinned band、行级 diff 绘制；运行时依赖只有 `wcwidth`；Python ≥ 3.12。
2. **安装**：`pip install motui` / `uv add motui`（二者都给）。
3. **`## Quickstart`**（标题**逐字保留**）：一个最小可运行应用；首个 python 块会被
   `tests/test_readme_examples.py` 解析执行，必须**自包含且 headless 可跑**
   （该测试会把脚本事件喂进去，断言 tab/enter/click/hover 的路径——现块就是为此写的，
   保持同等行为，只是导入名换新）。
4. **导入契约**：根 31 名 vs 层命名空间（ref §6 的例子），说明「一个名字一个家」；
   用一节讲清 `motui` / `motui.kernel` / `motui.widgets` / `motui.interaction` /
   `motui.chrome` / `motui.keys` / `motui.testing` 各自是什么。
5. **特性清单**（保留现有的 alt screen / viewport scrollback / mouse / hover / chrome /
   split panes / toasts / tooltip / pinned tail / keymaps / theme / markdown / syntax /
   headless 这套条目，按新路径与新门面口径校订）。
6. **`## Building your own shell`**、**`## Styling: Theme`**、**`## Keys and keymaps`**：
   标题**逐字保留**（门禁依赖），块内导入按新面更新，行为保持可执行。
7. 深水区链接：`docs/DESIGN.md`（机制）、`docs/COMPONENTS.md`（组件契约）、
   `docs/API.md`（生成的门面清单）。
8. `## Testing without a terminal`：保留 headless 说明，**去掉**已删的录制/回放一节。
9. 结尾：许可证（MIT）一句。

要求：

- 现有 README 里「为 mocode / agent 宿主」的口径（若有）全部改写为「任意 Python 程序」；
  但**不要**新增营销词（no "blazingly fast"、"modern"、"powerful" 这类空词）。
- 行文里所有模块路径、组件名、例子导入按 W2 的新结构（`motui.kernel.*` 等）逐条核对。
- 该加目录就加（README 较长），但不要为了短而删掉机制说明——README 是本库的门面。
- 硬证据：`uv run pytest -q tests/test_readme_examples.py` 全绿（贴输出）+ 全文
  `git grep -n "mocode\|motui\.core" README.md` 为空。

### T2 `docs/DESIGN.md` 更新

- 「The four layers under one driver」一节按新结构重画：目录树（ref §1）、五个层的职责、
  依赖方向（kernel 不依赖任何层；keys 只依赖 kernel；widgets 依赖 kernel(+keymap)；
  interaction/app/chrome/testing 在其上）、根门面 31 名的入选规则。
- 全篇 `core/` → `kernel/`、`~mocode_tui.*` → `~motui.*`、`core.ansi` 之类的相对引用同步。
- 与实现不符的段落（若有）按代码修正——只改口径，不发明新机制。
- 硬证据：`git grep -n "mocode" docs/DESIGN.md` 为空。

### T3 `docs/COMPONENTS.md` 更新

- 组件契约（`render(width) -> list[Line]`、控制器动词、指针层、容器）保持，路径与门面口径按新结构改。
- 「组件在哪一层」的表/列表按 ref §2 的门面清单核对。
- 硬证据：`git grep -n "mocode" docs/COMPONENTS.md` 为空。

### T4 全仓文案断言

- `git grep -n "mocode" -- . ':(exclude)specs'` 必须为空（含 examples 的 docstring；
  若发现 examples 里的 docstring 仍有旧路径，属本波修：它们不在 W2 的禁触范围内时直接改，
  若与本波无关的代码文件需要改动，先在报告里列出再动手）。
- 全门禁逐条跑（pytest / golden --check / framebench / apidoc --check / demo 两档）。

## 验收

1. `uv run pytest -q` 全绿（用例数不变）
2. `uv run pytest -q tests/test_readme_examples.py` 全绿
3. `git grep -n "mocode" -- . ':(exclude)specs'` 为空
4. `uv run python tools/golden.py --check` 14 页 match（本波不改渲染，golden 不应动；
   **若 golden 变了，说明改了不该改的东西，停下报告**）

## 禁触清单

- `src/**`（一个字节都不改；发现源码里有旧文案，列进报告交给 lead）
- `tests/**`（除 `tests/test_readme_examples.py` 里**解析标题**所需的标题名不改动外，一律不动；
  本波不允许改测试来迁就文档）
- `docs/API.md`（生成物，W2 已重录）、`pyproject.toml`、`LICENSE`、`.github/**`

## 最终报告格式

工单状态表（T1–T4 + commit hash）/ commit 清单 / 自测真实结论 / 偏差与取舍（含发现的源码侧旧文案）/
未决问题。阻塞即停。
