# Spec audit-fixes · W1：删除 MORE_BELOW 标记（D1，撤销 frame-chrome D8）
> ⏳ 待执行；前置：无；深读：`00-overview.md`（D1 是权威契约）。
> 本波同时消灭 F1——不需要修 ownership，覆盖行为本身被删掉，不变式恢复结构性成立。

## 目标

把 `─ more below ─` 标记从内核、测试、golden、文档中彻底删除。删除后：
每个绘制行要么归属一个 block、要么是空白填充，hit_test 不再有幽灵目标。

## 工单（按序执行；每完成一项跑一遍 `uv run pytest -q -p no:cacheprovider`；本波不 commit）

### T1 `src/motui/kernel/viewport.py`：删常量、导出、写入、docstring

- 删 `:35` 的 `MORE_BELOW = Line.from_text(...)`；从 `:32` 的 `__all__` 移除该名。
- 删 `:194-195` 的条件写入整块（含其上的注释）。删后窗口就是完整内容行，**不要**用空白行或别的东西补位。
- `:111` 附近 docstring 里 "When scrolled away with content left below the window, the
  viewport's last row becomes the 'more below' marker" 整句删除；`layout()` docstring
  中其它处（如 `:110-111` 段落）同步理顺，不留悬空引用。
- 自查：`MUTED` 的 import 若只因标记而存在，一并清掉（先 grep 确认没有别的用处）。

### T2 `src/motui/kernel/__init__.py`：删再导出与 docstring

- 删 `:112` import 行中的 `MORE_BELOW`、`:126` `__all__` 条目。
- 删 `:33-35` docstring 中 "with the `MORE_BELOW` marker row it paints when content waits
  below the window" 的提及，句子理顺。

### T3 测试断言改期望（期望值从实际行为算出，逐个核对，不许机械替换）

- `tests/test_viewport.py`：`:15` import、`:71`（贴底无标记——删该断言或改为"末行是内容行"）、
  `:74-75`、`:114`、`:120`、`:278`（`expect[-1] = MORE_BELOW` 的辅助行删除）、`:373`。
  新期望 = 窗口显示完整内容行（原 `[r5, r6, r7, MORE_BELOW]` → `[r5, r6, r7, r8]` 之类，以真实渲染为准）。
- `tests/test_painter.py`：`:25` import、`:189`。
- `tests/test_app.py`：`:29` import、`:85`、`:118`、`:127`、`:183`、`:205`。注意这些用例测的是
  滚动窗口内容，删标记后窗口多一行真实内容——逐条重算期望。
- `tests/test_api_root.py`：`:40` 的排序 `__all__` 清单字符串里删 `MORE_BELOW`（保持字母序）。
- 每条改动的断言在报告里列：文件:行、旧期望、新期望、为什么。

### T4 golden 重录（受控）

- 先 `uv run python tools/golden.py --check`：预期**只有** themes / streaming / notes 三页失败，
  且差异仅在窗口末行。若其它页动 = 停下报告，说明有范围外行为变化。
- `uv run python tools/golden.py --update`，然后 `git diff --stat tests/golden/` 核对：
  只有那三页、每页只有窗口末几行。`git diff tests/golden/pages/themes.txt` 逐行看过再收手。
- 绝不手改 golden 文件（CONTRIBUTING:182）。

### T5 `docs/DESIGN.md`

- `:88` kernel 行的枚举里删 `MORE_BELOW`。
- `:353-354`（"the viewport's last row becomes `motui.kernel.viewport.MORE_BELOW`…" 整段）
  整段删除，上下文理顺。grep 确认 DESIGN.md 无残留 `more below` 提及。

### T6 全仓清扫

- `grep -rn "MORE_BELOW\|more below" src tests docs` 必须零命中（`specs/` 历史档案与
  `specs/2026-10-19-audit-fixes/ref/` 除外——档案只增不减，不碰）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q -p no:cacheprovider`：贴改后总数与失败数（基线 1539/1）
2. `uv run python tools/golden.py --check` 绿 + `git diff --stat tests/golden/` 只有三页
3. `grep -rn "MORE_BELOW" src tests docs` 零命中
4. `uv run python -m motui < /dev/null` exit 0；`uv run python -m motui --pages` exit 0
5. `git status --porcelain`：只有预期文件，无散落探针

## 禁触清单

- 只改：`src/motui/kernel/{viewport,__init__}.py`、`tests/{test_viewport,test_painter,test_app,test_api_root}.py`、
  `tests/golden/pages/{themes,streaming,notes}.txt`（仅经 `tools/golden.py --update`）、`docs/DESIGN.md`（仅 :88 与 :353-354）。
- 禁触：其它 kernel 文件、任何 widget、interaction、app.py、其它测试、`docs/COMPONENTS.md`、
  `CHANGELOG.md`（W5 的）、`specs/**`、`pyproject.toml`、framebench 的基线（本波**不**跑 framebench，
  render-hash 的变更由 W5 记录）。
- 不 commit / 不建分支 / 不 push / 不碰主检出以外的任何东西。

## 报告格式（最终消息，中文）

工单状态表（T1–T6）/ 测试断言改动清单（文件:行、旧期望、新期望、理由）/ golden diff 统计与抽检 /
自测真实输出（pytest 总数、golden --check、grep、两条 demo 命令）/ 偏差与未决问题。
