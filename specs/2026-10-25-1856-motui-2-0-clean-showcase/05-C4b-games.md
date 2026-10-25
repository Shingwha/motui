# C4b · Breakout + Dashboard + examples 收敛 + 5 场景 golden

> 分支 `2.0-clean/c4b-games`；前置：C4a 已合并（`687a9c9`）；写入范围：`src/motui/demo/{showcase,art,__init__}.py`、`examples/**`、`tests/test_examples.py`、`tests/golden/semantic/**`、`tests/golden/README.md`、`.github/workflows/ci.yml`、`tools/semantic.py`（仅 SCENES）
> 权威：用户 2026-10-25 方向（单页互动秀、Breakout、examples 只留 quickstart/code/wide_table）

## 目标

完成互动 Showcase：

1. `BreakoutScene`：可玩的打砖块（Canvas、球拍/球/砖块、分数/命、暂停/返回）；
2. `DashboardScene`：实时 sparkline/进度条/统计/时钟/resize；
3. Menu 接全 4 个选项，删占位场景；
4. `SCENES = splash/menu/breakout/dashboard/gallery`，语义 golden 5 个；
5. `examples/` 只留 `quickstart.py` / `code.py` / `wide_table.py`（删除 snake/dashboard），CI 与测试同步；
6. 全量门禁绿。

**本波结束：`python -m motui --pages` 输出 5 场景；`--scene breakout --frames N --headless` 可玩/可回放；semantic 5；examples 3；全绿。**

## 前置上下文

- 必读：C4a handoff → 本工单；`src/motui/demo/{showcase,__init__,art}.py`。
- 基线：`uv sync --locked`；`pytest`（1615 passed）；`semantic --check`（3 scenes）；`python -m motui --pages` 3 场景。
- 现状：
  - `showcase.py`：`Scene` Protocol（`render(c,phase)`/`tick(phase)->next|None`/`on_key`/`on_click`）、`SplashScene`、`MenuScene`、`_PlaceholderScene`、`GalleryScene`、`Showcase`、`SCENES=("splash","menu","gallery")`。
  - Menu 的 Breakout/Dashboard 走 `_PlaceholderScene`（coming soon）。
  - `demo/__init__.py`：`PAGE_PHASE=8`、`TICK_HZ=30`、`_pages`、`--scene/--frames`、`scene_output`、`main`。
  - `tools/semantic.py` 从 `demo.SCENES` 取；`tests/test_smoke.py`/`test_semantic_golden.py` 通用。
  - `examples/`：quickstart、snake、dashboard、wide_table；`tests/test_examples.py` 跑四个。
  - CI 四个 example steps + semantic + pages。
- 设计：
  - `BreakoutScene`：
    - 场景内 playfield：`w = min(c.width, 80)`、`h = min(c.max_height or 24, 24)`；居中；HUD 上/下。
    - 6×4 砖块，每块 1 格宽/高或 2 格宽；颜色用 `theme.syntax` 的几组或 palette；球拍 7 格；球 1 格。
    - 状态：paddle_x、ball_x/y、dx/dy、bricks set、score、lives=3、paused、launched。
    - tick：未发射时等待 space；发射后每 tick 移动；碰撞墙/拍/砖；砖清空 → 下一关（重置砖块/加速）；球落底 → lives--；0 → game over overlay。
    - 输入：←/→ 或 h/l 移动；space 发射/暂停；esc 返回 menu；q 退出？在 game 里 q 回 menu。
    - 渲染：Canvas 画砖/拍/球；HUD 用 Text/Line；底部提示；game over 覆盖层（Panel/Text）。
    - 确定性：无随机或固定种子；`tick(phase)` 纯状态推进；headless 可回放。
  - `DashboardScene`：
    - 顶部标题/时钟（phase 推导，不读系统时钟）；2×2 面板：Sparkline（正弦+确定性噪声）、ProgressBar（cpu/mem）、Table/List 指标、日志行。
    - 每 tick 推一个采样点；resize 按 c.width/height 重排；80×24 与 100×30 都成立。
  - `MenuScene`：4 项；选择 Breakout/Dashboard/Gallery；Quit；删 `_PlaceholderScene`。
  - `SCENES=("splash","menu","breakout","dashboard","gallery")`；`Showcase.switch` 支持新场景；`--scene` 校验。
  - 语义 golden 5 个；`PAGE_PHASE` 对 breakout/dashboard 取一个稳定帧（例如 breakout 已发射 20 tick、dashboard 20 tick），`scene_output` 用同样 phase。
  - examples：
    - 删除 `examples/snake.py`、`examples/dashboard.py`；
    - 新增 `examples/code.py`（≤60 行）：Markdown 代码块长行 + `WrapMode`/`ScrollPanel` 展示；`--headless` 输出；
    - `tests/test_examples.py` 只跑 quickstart/code/wide_table；
    - CI 删除 snake/dashboard step，加 code。
- 已知坑：
  - 游戏必须确定性；不要 `random` 无种子、不要 `time`；用 phase 或固定种子。
  - `Canvas` 尺寸与居中；每行 ≤ width；不要写 escape。
  - `Showcase` 的 `tick()` 目前自动 splash→menu；新场景的 tick 返回 `None` 或 `"menu"`；`Showcase` 负责 `touch`。
  - `--pages`/semantic 使用 `PAGE_PHASE`；breakout/dashboard 在该 phase 要有内容（不是刚 reset 的空屏）。
  - `scene_output` 的 HeadlessScreen 尺寸 100×30；游戏 playfield 适配。
  - `examples/code.py` 的 headless 输出确定；不要在 CI 等 TTY。
  - `README` 仍提 snake/dashboard，C5 更新；本波不改 docs。
  - 语义 golden 5 个：`semantic --update` 后确认只有新场景文件；旧 3 个可保留并更新。
- 不改 kernel/terminal/widgets/app；不改 docs/README。

## 工单（按序，每步一个 commit）

### T1 BreakoutScene

- 在 `showcase.py` 加 `BreakoutScene`（或独立 `demo/breakout.py` 并在 showcase 导入；文件大小合理）。
- 实现状态/物理/碰撞/关卡/命/分数/暂停/game over；`render` Canvas+HUD；`on_key`；`tick`。
- `SCENES` 加 `"breakout"`；Menu 接真场景；删除 `_PlaceholderScene` 的 Breakout 分支。
- 测试 `tests/test_smoke.py`/新增 `tests/test_demo_scenes.py`：
  - `--pages` 含 breakout；
  - `--scene breakout --frames 30 --headless` exit 0 且输出含 score/砖块；
  - 输入序列（space/right）推进状态（直接调 scene）。
- 验证：`uv run python -m motui --scene breakout --frames 30 --headless`。

### T2 DashboardScene

- 加 `DashboardScene`：Sparkline/ProgressBar/统计/日志；tick 推采样；resize 自适应。
- `SCENES` 加 `"dashboard"`；Menu 接真场景；删除 `_PlaceholderScene` 剩余分支。
- 测试：`--pages` 含 dashboard；`--scene dashboard --frames 30 --headless` exit 0；80×24/100×30 无超宽。
- 验证：同上。

### T3 语义 golden 5 场景

- `PAGE_PHASE` 对 breakout/dashboard 选择稳定非空帧（可在 `render_scene` 内按场景选 phase）。
- `tools/semantic.py` 自动读 `SCENES`（如未自动，更新导入/常量）。
- `semantic --update` 生成 5 个；`tests/golden/README.md` 更新场景列表。
- 验证：`semantic --check` 5。

### T4 examples 收敛

- 删除 `examples/snake.py`、`examples/dashboard.py`；新增 `examples/code.py`（quickstart/wide_table 保留）。
- `tests/test_examples.py` 改跑 quickstart/code/wide_table；CI 更新三个 steps。
- 验证：三个 `--headless` exit 0；`pytest -q tests/test_examples.py`。

### T5 收口

- 全量：pytest、semantic 5、pages、headless、examples、ruff/pyright/lint-imports/api/growth/framebench。
- `python -m motui < /dev/null` exit 0。
- 报告新场景文件/行数；`SCENES` 5。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. `semantic --check` 5；`python -m motui --pages` 5 场景；`< /dev/null` exit 0。
3. `--scene breakout --frames 30 --headless` 与 dashboard 均 exit 0。
4. examples 只剩 quickstart/code/wide_table，三个 `--headless` exit 0；CI 对应。
5. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth.py` full 全绿。
6. framebench replay exit 0；无 >10% 劣化。

## 禁触清单

`kernel/**`、`terminal/**`、`widgets/**`、`app/**`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`、`tools/{framebench,semantic}.py`（semantic 只允许 SCENES 必要行）、`tests/golden/semantic/{splash,menu,gallery}.txt`（只允许 `--update` 重录）。

## 交接包

最后 commit 写 `handoff/C4b-games.md`：A 节给 Breakout/Dashboard 设计、SCENES、examples/CI、semantic 5、门禁；B 节给确定性/碰撞/布局、PAGE_PHASE、examples 取舍、C5 待办、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
