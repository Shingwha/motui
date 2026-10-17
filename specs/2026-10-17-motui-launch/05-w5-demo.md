# Spec MOTUI · W5：demo 随包发布 + 左轨版面重构（波次 W5）

> 分支 `rl5-demo`；worktree `C:/Users/shifu/.worktrees/mocode-tui/rl5-demo`；
> 前置：W2 已合并；深读：`00-overview.md` + `ref/target-structure.md` + **`ref/demo.md`（逐字契约）**
> 与 W3、W4 **并行**：W3 写 README/docs，W4 写 pyproject/LICENSE；**你拥有** `src/motui/demo/**`、
> `src/motui/__main__.py`、`examples/**`（删除）、`src/motui/widgets/tabs.py`、`tests/golden/**`、
> `tests/test_gallery_protocol.py`、`.github/workflows/ci.yml`。

## 目标

把 demo 变成**随包发布的产品门面**：`pip install motui` 之后 `python -m motui` 就能看到的
一个**分类清晰、不啰嗦**的组件展览馆；版面从「顶部 tab 条」改成「左轨 + 右内容」。
同时把 demo 代码从 3649 行压到 **≤ 2000 行**。

## 工单（按序执行，每项一个 commit）

### T1 `Tabs` 纵向轴向

- 按 `ref/demo.md` §4 实现 `Tabs(orientation="horizontal"|"vertical")`。
- 横向渲染**字节不变**（先跑 `uv run pytest -q tests/test_widgets_*.py tests/test_golden_frames.py` 取证）。
- 纵向：一行一标签、行内左对齐；`click`/`hover_at` 按行解析；越界 `False`/`None`。
- 补少量纵向用例到现有 `tests/test_widgets_*.py` 里 Tabs 所属的那个文件（不要新建一个测试文件）。
- 硬证据：`uv run pytest -q` 全绿；golden 仍 14 页 match（本波尚未重录）。

### T2 demo 搬进包里

- `git mv examples/gallery src/motui/demo`；`git mv examples/Markdown-Rendering-Test.md src/motui/demo/fixture.md`；
  删 `examples/demo.py` 与空的 `examples/`。
- 新增 `src/motui/demo/__main__.py`（`main()`）与 `src/motui/__main__.py`（转调 demo 的 `main()`）。
- 内部导入按 `ref/target-structure.md` §6 的导入口径改写：**只许公开面**（允许 `motui.kernel.frame.splice_row`
  这类文档化深缝，按现状）。
- fixture 读取路径改为相对本模块（`Path(__file__).with_name("fixture.md")`）。
- `tools/golden.py` / `tests/test_golden_frames.py` / `tests/test_demo_protocol.py`（原 gallery 版）
  的 import 与路径同步到 `motui.demo`。
- 硬证据：`uv run python -m motui --pages` exit 0（此时还是旧版面）；
  `git grep -n "gallery"` 只剩 specs 历史与「gallery」作为**词**的散用（逐个说明或改掉）。

### T3 左轨版面重构（本波主体）

- 按 `ref/demo.md` §2 落地：左轨 pane（`split("vertical", ratios=(1, 4))`）+ 右内容 pane；
  头部 band 保留「motui · <页标题>」与右侧状态；提示行保留快捷键清单；**取消顶部标签条**。
- **取消壳级 `/` 命令面板**（`ref/demo.md` §5.1）：删掉 `/` 前缀解析、命令表、面板 overlay 及其
  注册/注销与过期逻辑；`Palette` 改作 `chrome` 页上的展品（点开或按键打开）。这一条是本波
  「瘦身」的主要来源，报告里给出删除前后的行数对比。
- 页表按 `ref/demo.md` §3 收敛为 11 页（合并 `navigation`→`data`、`diff`→`content` 或 `data`、
  `structure`→`layout`、`features`+`devtools`→`chrome`，`feedback` 吸收 `Notice`/`Collapsible` 的
  归属按表执行）。
- 每页只讲一件事：标题 + 一句说明 + 展品 + echo 行。
- 代码体量按 `ref/demo.md` §6 压到 ≤ 2000 行：合并重复的页骨架、删掉只为旧版面存在的代码、
  把重复的文案收进 `content.py` 一类的小模块。
- 保留 `ref/demo.md` §5 的全部能力（逐条自测并在报告里打勾）。
- 若左轨 pane 路线与 `/split` 展品或滚轮路由冲突 → 走 `ref/demo.md` §2 的诚实出口，报告里写证据与代价。

### T4 门禁与文档面同步

- `uv run python tools/golden.py --update` → **11** 帧；逐帧 diff 审查（允许：版面重排 + 页面拆分；
  不允许：组件渲染本身的退化）。
- `tests/test_gallery_protocol.py` → `tests/test_demo_protocol.py`，按 `ref/demo.md` §7 重写。
- `.github/workflows/ci.yml`：两条 demo 门禁改为 `python -m motui < /dev/null` 与 `python -m motui --pages`
  （包装器写法沿用现有步骤，别引入平台分支）。
- 硬证据：全门禁六条（`ref/demo.md` §7 的口径）。

## 验收（报告里逐条贴真实输出）

1. `uv run pytest -q` 全绿（用例数：横向 Tabs 用例保留 + 纵向少量新增 + demo 协议测试重写后的数字，
   基线 = W2 结束时的用例数）
2. `uv run python tools/golden.py --check` → `golden: 11 pages match`
3. `uv run python tools/framebench.py` → exit 0 + hash 行（hash 会变，值本身不比对）
4. `uv run python -m motui < /dev/null` → exit 0，dump 稳定
5. `uv run python -m motui --pages` → exit 0，11 页
6. `uv run python tools/apidoc.py --check` → 通过（本波不改门面）
7. `find src/motui/demo -name "*.py" | xargs wc -l | tail -1` → **≤ 2000**
8. `git grep -n "examples/demo.py\|examples/gallery" -- . ':(exclude)specs'` → 空

## 禁触清单

- `README.md`、`docs/**`（W3 负责；`docs/API.md` 生成物两边都不改）
- `pyproject.toml`、`LICENSE`、`tests/test_packaging.py`（W4 负责；`[project.scripts]` 由 W4 写）
- `src/motui/kernel/**`、`src/motui/keys/**`、`src/motui/widgets/**`（**除 `tabs.py`**）、
  `src/motui/app.py`、`src/motui/chrome.py`、`src/motui/interaction/**`、`src/motui/testing.py`
- `tests/` 里除 `test_golden_frames.py`、`test_gallery_protocol.py`（重命名为 demo 版）与 Tabs 所属文件外的任何文件
- `specs/2026-*` 历史目录

## 最终报告格式

工单状态表（T1–T4 + commit hash）/ commit 清单 / 自测真实结论（八条）/ golden diff 审查结论（逐帧）/
demo 能力清单打勾（`ref/demo.md` §5）/ 左轨实现选择与证据（含是否走了诚实出口）/ 偏差与取舍 / 未决问题。
阻塞即停。
