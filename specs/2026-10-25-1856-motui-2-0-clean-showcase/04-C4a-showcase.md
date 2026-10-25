# C4a · 新 Showcase 骨架：Splash / Menu / Gallery + 场景语义 golden

> 分支 `2.0-clean/c4a-showcase`；前置：C2b 已合并（`7a6b46d`）；写入范围：`src/motui/demo/**`（整体替换）、`src/motui/__main__.py`、`tools/semantic.py`、`tools/golden.py`（删除）、`tests/test_{smoke,semantic_golden}.py`、`tests/golden/**`、`.github/workflows/ci.yml`
> 权威：`../2026-10-25-0900-motui-2-0-architecture/ref/source/10-waves/W5-docs-release.md` §3.3、用户 2026-10-25 方向

## 目标

把 57-topic 的旧 tour 替换成**单页互动 Showcase**的第一阶段，并换掉旧 golden 体系：

1. 新 `motui.demo`：`Showcase` 状态机 + `Splash` / `Menu` / `Gallery` 三个场景；
2. `python -m motui`：TTY 上运行互动秀；无 TTY / `--headless` 确定性输出；`--pages` 输出各场景文本；
3. 删除旧 tour（topics/session/shell/stage/registry/script/model/assets）与 57 个字节 golden + `tools/golden.py`；
4. `tools/semantic.py` 改为场景语义快照（splash/menu/gallery 3 个）；
5. 1610 用例、其余门禁全绿；新场景可跑、可看、可 headless 回放。

**本波结束：`python -m motui --pages` 输出 3 个场景；semantic --check 3 个；旧 tour/golden 删除；pytest/ruff/pyright/lint/api/growth 全绿。**

## 前置上下文

- 必读：`../2026-10-25-0900-motui-2-0-architecture/handoff/W5-final.md` → C1/C2a/C2b handoff → 本工单。
- 基线：`uv sync --locked`；`pytest`（1610 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `src/motui/demo/` 是 57-topic master-detail tour（~3,000 行）；`python -m motui` 的 `main()` 在 `demo/__init__.py`。
  - `tools/golden.py` 用 `demo.render_topic` + `TOPICS`；`tools/semantic.py` 同样。
  - `tests/test_smoke.py`、`tests/test_semantic_golden.py`、`tests/golden/**`、CI 的 `golden` step 都绑旧体系。
  - `tools/framebench.py` 读 `src/motui/demo/fixture.md`（保留该文件），`replay` 子进程跑 `python -m motui`。
  - Widgets 2.0 面：`render(Constraints)->Surface`、`Canvas`、`Fill`、`App.fill`、`App.every`、`on_key/on_click`、`Theme`/`Style`。
- 新 Showcase 设计（必须实现）：
  - 单文件/少量文件：`demo/showcase.py`（`Showcase` + `Scene` Protocol + 3 场景）、`demo/art.py`（大字号 logo/渐变/居中 helper）、`demo/__init__.py`（main/render_scene/scene_output/SCENES）、`demo/__main__.py`。
  - `Showcase(Widget)`：`focusable=True`、`clickable=True`；`scene` 状态、`phase` 整数；`render(c)` 委托场景；`on_key/on_click`；`tick()` 推进 phase 并 `touch()`；`switch(name)`。
  - `Splash`：
    - 居中大字号 `motui`（5×7 像素字，`█`；两色渐变 + 扫光列，phase 驱动）；
    - 副标题 `a terminal UI kernel · 2.0.0`；底部脉冲点；
    - 约 60 tick 后自动进 menu；任意键进 menu。
  - `Menu`：
    - 居中面板（约 48 列），标题、版本、4 个选项：`Breakout`、`Dashboard`、`Gallery`、`Quit`（C4a 中 Breakout/Dashboard 可先显示但进入时回 menu 并 toast/提示；C4b 接真场景）；
    - 上下键/鼠标点击选择；enter 进入；q/esc 退出/回 splash；
    - 底部键位提示。
  - `Gallery`：
    - 用真实 2.0 组件拼一页：`Markdown`（短说明）、`List`/`Tree`、`Table`、`ProgressBar`/`Slider`/`Input`、`Panel`/`Divider`；
    - 2–3 栏/上下分区，在 80×24 与 100×30 都成立；有焦点/选中演示；`esc` 回 menu。
  - 视觉：`Theme.dark()`（Ink & Signal）；无外依赖；只产 Surface；内容不带 escape。
- 运行模式：
  - `main(argv)`：
    - `--pages`：依次输出 `── /splash ──`、`── /menu ──`、`── /gallery ──` + 场景文本（100×30，固定 phase）。
    - `--scene NAME [--frames N] --headless`：确定性输出该场景第 N tick 的文本；exit 0。
    - 无 TTY / stdin 非 TTY：默认输出 menu 文本并 exit 0（CI/`< /dev/null`）。
    - TTY：`App(terminal=TerminalOptions(mouse=MouseMode.MOVE))` + `app.fill(showcase)` + `app.focus(showcase)` + `app.every(1/30, tick)`（tick 后 `app.invalidate()`）+ `app.run()`。
  - `render_scene(name, width, height, phase) -> str`（文本）；`scene_output(...) -> str`（真实 Painter 字节，用于语义 golden）。
- 语义 golden：
  - `SCENES = ("splash","menu","gallery")`；每场景一个 `tests/golden/semantic/<name>.txt`。
  - `tools/semantic.py` 改为用 `scene_output` + `Emulator`；`--update/--check/--snapshot` 保留；格式与现有相同（text + SGR runs + cursor header）。
  - 删除 `tools/golden.py` 与 `tests/golden/topics/**`；CI 删除 golden step，保留 semantic step。
  - `tests/golden/README.md` 重写为场景语义快照说明。
- 已知坑：
  - `App.fill` 替换 pane 文档；`Showcase` 的 `render(c)` 必须填满 `c`（`Fill` 传 `max_height=剩余`）。
  - `app.every` 的回调要 `app.invalidate()`，否则画面不重绘；不要 sleep。
  - headless `scene_output` 用 `Runtime(Terminal(TerminalOptions(screen=HeadlessScreen(...))), interactive=False)` + `fill` + `paint`；不启动 pump。
  - `python -m motui < /dev/null` 必须 exit 0；`--pages`/`--headless` 不读 stdin。
  - 大字号 logo 用 Canvas 逐点写，宽字符只用单宽块；居中按 `constraints.width`。
  - `Gallery` 的组件必须有真实约束（`Constraints(width=...)`），不要用固定宽度假设。
  - 删除旧 demo 文件后，`tools/framebench.py` 仍读 `demo/fixture.md`；保留该文件（或迁移并同步）。
  - `tests/test_smoke.py`/`test_semantic_golden.py` 重写；不再引用 `TOPICS/Session/registry`。
  - 行数限制：demo 文件不强制；但别把 3 个场景写成 2,000 行。
- 不改 widgets/kernel/terminal/app；不改 examples（C4b）。

## 工单（按序，每步一个 commit）

### T1 新 demo 包与 Showcase 骨架

- 删除旧 `demo/topics/**`、`demo/{assets,model,registry,script,session,shell,stage}.py`（保留 `dot demo/fixture.md`）。
- 新建 `demo/showcase.py`：`Showcase`、`Scene` Protocol、`switch`、`tick`、`on_key/on_click`。
- 新建 `demo/art.py`：`big_text`（5×7 font）、`center`、`gradient_styles`。
- `demo/__init__.py`：`SCENES`、`render_scene`、`scene_output`、`main`。
- `demo/__main__.py` 更新。
- `__main__.py` 仍 `from motui.demo import main`。
- 验证：`uv run python -c "from motui.demo import SCENES; print(SCENES)"`；场景骨架可 import。

### T2 Splash + Menu

- `SplashScene`：logo/副标题/脉冲/扫光；60 tick 自动进 menu；按键进 menu。
- `MenuScene`：标题/版本/四选项/光标/键位提示；up/down/enter/click；Breakout/Dashboard 在 C4a 回 menu 并显示提示（C4b 接真场景）；Gallery 进入；q/esc 退出。
- `render_scene("splash"/"menu", 100, 30, phase)` 文本确定性。
- 验证：`uv run python -m motui --pages` 能看到 splash/menu。

### T3 Gallery

- `GalleryScene`：真实组件 2.0 组合（Markdown/List/Table/ProgressBar/Slider/Input/Panel/Divider），响应 80×24/100×30；esc 回 menu。
- 组件交互焦点：List/Tree 选中、Slider 值、Input 可输入（headless 不需要）。
- 验证：`--pages` 输出 gallery 且无超宽/换行错位。

### T4 工具与 golden

- `tools/semantic.py` 改场景；`SCENES` 3 个；`scene_output` 字节 + Emulator；格式不变。
- 删除 `tools/golden.py`、`tests/golden/topics/**`；CI 删除 golden step。
- `tests/test_smoke.py`/`tests/test_semantic_golden.py` 重写；`tests/golden/README.md` 重写。
- 生成 `tests/golden/semantic/{splash,menu,gallery}.txt`。
- 验证：`semantic --check` 3；`pytest -q tests/test_smoke.py tests/test_semantic_golden.py`。

### T5 运行模式收口

- `main` 的 `--pages`/`--headless`/`--scene`/TTY 分支；`python -m motui < /dev/null` exit 0。
- CI 更新：删除 golden，保留 semantic；`python -m motui --pages` 仍跑。
- `tools/framebench.py` 的 replay 用新 main；保留 fixture。
- 验证：全量验收。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字；旧 topic 测试删除/重写）。
2. `semantic --check` 3 个；`golden.py`/`tests/golden/topics` 已删除。
3. `python -m motui < /dev/null` exit 0；`--pages` exit 0；`--scene splash --headless` exit 0。
4. `python -m motui --pages` 输出 splash/menu/gallery 三个场景，无超宽/换行错位。
5. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth.py` full 全绿。
6. `framebench` replay exit 0；记录新 hash/性能。

## 禁触清单

`kernel/**`、`terminal/**`、`widgets/**`、`app/**`、`examples/**`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`、`tools/framebench.py`（只允许必要的 replay 兼容修复）。

## 交接包

最后 commit 写 `handoff/C4a-showcase.md`：A 节给新 demo 结构/场景/运行模式/语义 golden/门禁；B 节给视觉实现、headless 确定性、旧 tour 删除清单、C4b 待接（Breakout/Dashboard/examples）、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
