# W1-b handoff · demo 新壳（shell/wipe/StatusLine/60Hz/examples 退场）

> 分支 `dm-w1b-demo-shell`，worktree `C:\Users\shifu\.worktrees\mocode-tui\dm-w1b-demo-shell`。
> 基线 1641 passed；交付时 **1642 passed**（1641 − 3 条 test_examples + 4 条 test_demo_shell；
> 工单"1638"的算式漏了 P9 自己要求的新测试文件，见「踩坑」第 6 条）。

## A 节 · 交付清单

### A.1 新 SCENES 全表（`sections/__init__.py`）

```python
SCENES = ("splash", "menu", "components", "layout", "motion",
          "dashboard", "terminal", "themes", "snake", "gallery")
```

| 名 | 实现对象 | 说明 |
|---|---|---|
| `splash` | `SplashScene`（sections/splash.py，未动） | 入口；on_key/on_click → `"menu"` 不变 |
| `menu` | `MenuScene`（sections/menu.py，重绘） | Home 瓷砖，hub 名保留（P1） |
| `components` | `PlaceholderScene(name="components")` | 占位节（W2-b 接手） |
| `layout` | `PlaceholderScene(name="layout")` | 占位节 |
| `motion` | `SnakeScene`（与 `snake` **同一个对象**） | 本波 motion 即贪吃蛇；W4 迁入独立文件 |
| `dashboard` | `DashboardScene`（未动） | `_DASHBOARD_FPS=30` 保留（见 B.2） |
| `terminal` | `PlaceholderScene(name="terminal")` | 占位节 |
| `themes` | `PlaceholderScene(name="themes")` | 占位节（W3-b 接手） |
| `snake` | 同 `motion` 的对象 | 契约名：`render_scene("snake",…)` 必须可用 |
| `gallery` | `GalleryScene`（未动） | 契约可导入；不在瓷砖上，`--pages`/`--scene gallery` 可达 |

### A.2 sections/ 文件地图

```
src/motui/demo/
  __init__.py        入口 main/render_scene/scene_output/PAGE_PHASE/TICK_HZ=60/_commands/_interactive
  shell.py           Showcase 壳：phase、switch/tick/on_key/on_click、wipe、StatusLine
  showcase.py        纯 re-export 壳（契约导入路径；除 docstring 外零逻辑，grep _sync 零命中）
  sections/
    __init__.py      Scene 协议、SCENES、_PLACEHOLDERS、_scenes(theme, seed)
    splash.py        SplashScene（交接 commit 迁入，本波未动）
    menu.py          MenuScene：masthead + 6 瓷砖（每块 ≤6 行 phase 动画）+ footer
    placeholder.py   PlaceholderScene：under-construction 面板 + 相位点动画
    dashboard.py     DashboardScene（未动）
    gallery.py       GalleryScene（未动）
  snake.py           SnakeScene（本波不改，W4 迁入）
  art.py             big_text（未动；本波标题走纯文本）
```

### A.3 Showcase 壳公开名（新/变）

- `Showcase(scene="splash", theme=None, *, seed=0, status_line=False)` —— 新增 `status_line` 关键字。
- 新公开属性：`status_line: bool`（是否画底栏）、`status_note: str`（底栏右 note，默认 `"--"`，live 跑法由 runner 写成 `Ink & Signal · N fps`）。
- `START_PHASE`、`switch/tick/on_key/on_click/on_quit` 签名不变；`switch` 现在在换节时启动 wipe。
- `demo/__init__` 新增模块私有：`TICK_HZ=60`、`_THEME_LABEL`、`_NON_SECTIONS`、`_commands(app, showcase)`。
- `motui.demo` 公开面（`SCENES/main/render_scene/scene_output/PAGE_PHASE`）与 `motui.demo.showcase`
  可导入名全部原样；`tests/test_demo_scenes.py` 16 条零修改通过。

### A.4 golden 重录清单（`tests/golden/semantic/`，5→10 个）

| 文件 | 动作 | 原因 |
|---|---|---|
| `menu.txt` | 重录 | Home 瓷砖重绘（T2 视觉变化，P8 预告项）；终态又经两轮打磨：迷你动画收进边框内（174f0e3）、瓷砖间隙列落位（d3dea78），每次 `--update` 后重录 |
| `components.txt` `layout.txt` `terminal.txt` `themes.txt` | 新增 | 新注册占位节（P3"有 golden"） |
| `motion.txt` | 新增 | motion 节入册；内容=snake 同相位帧（同一对象） |
| `splash.txt` `snake.txt` `dashboard.txt` `gallery.txt` | **零变化** | `--update` 的 LF 重写造成的假 modified 已 `git checkout` 还原，逐字未变（P8 预告"不应变化"成立） |

### A.5 examples 清扫清单

- 删除：`examples/{quickstart,code,wide_table}.py`（本分支无 pixel.py，并行波未落）、`tests/test_examples.py`（3 条）。
- `README.md`：quickstart 段改指 `python -m motui`；能力矩阵 wide table/code view 两行改指
  `--scene gallery`；"three shipped examples" 段改写为七节导览；"The demo" 节同步为新壳描述（瓷砖/wipe/状态栏/ctrl+p）。
- `.github/workflows/ci.yml`：3 个 example 步 → 3 个 demo replay 步（dashboard/snake/components headless）。
- `tools/growth.py`：`COPIED` 去掉 `"examples"`（docstring 首段本就未列 examples，未动）。
- `docs/MIGRATION.md`：第 10 条改指 demo。
- `docs/releases/2.0.0.md`：showcase 表更新为 10 场景；"Examples" 节改写为 "Showcase scripts"；
  Release facts 计数改为 1638 passed / 10 golden / 10 pages（该文件是发布说明，计数随分支真实值走）。
- `pyproject.toml`：本就无 examples 引用，未动。
- 残留解释：`docs/adr/ADR-009.md:9` "provide a migration table, recipes and executable examples"
  是对 2.0 断代策略的泛指文本，非 `examples/` 目录引用；已采纳的 ADR 不改写。

## B 节 · 机制与接手点

### B.1 wipe 确定性机制（shell.py）

- `Showcase._wipe_from`：换节时（`switch(name)` 且 `name != self.scene`）记旧节名；`_WIPE_TICKS = 9`（60Hz 下 ≈150ms）。
- 遮罩列数是 phase 的纯函数：`cols = min(width, width * (phase + 1) // _WIPE_TICKS)`；
  渲染时 `cut_line(新帧, 0, cols) + cut_line(旧帧, cols, width)` 逐行拼接；`tick()` 到 `phase >= 9` 清除。
- 保证：同 switch 序列 + 同 tick 数 → 12 帧逐字重放一致；尾帧 == 静态 dashboard 帧（test_demo_shell 钉死）。
- 契约帧零影响：`render_scene`/`scene_output` 直接构造 Showcase、不走 `switch`，永不触发 wipe。

### B.2 60Hz 连带面（W4/lead 需知）

- `_interactive`：`TICK_HZ 30→60`、`App(throttle=1/60)`；fps 用 `app.workspace.painter.frames` 差分，
  每 ≥1s 采样一次写 `showcase.status_note`；headless/确定性路径从不写 → 底栏显示 `"--"`。
- **所有节内 per-tick 动画的墙钟速度 ×2**（贪吃蛇 4 tick/步、dashboard 逐 tick 采样、splash 旋转）。
  这些节奏全部被 `tests/test_demo_scenes.py` 按 phase 钉死（零修改红线），**不能**在本波换算；
  若 W4/W3-b 要把观感速度调回，只能改工单/契约（例如 snake 改 8 tick/步需连契约测试一起改）。
- `_DASHBOARD_FPS = 30` 保留：`test_dashboard_clock_is_derived_from_phase` 钉 `phase=30 → "00:01.0"`，
  面板文案 "30 Hz · clock from phase" 是它自身的语义；与 TICK_HZ 无推导关系。

### B.3 占位节接手点（W2-b/W3-b）

1. 写真节文件 `sections/components.py`（等），实现 Scene 协议（`name/render/tick/on_key/on_click`，
   escape → `"menu"`、q → `"quit"` 的既有惯例）。
2. `sections/__init__.py`：从 `_PLACEHOLDERS` 元组删掉对应 `(name, blurb)`，在 `_scenes()` 里换成真类构造——
   其余（SCENES、瓷砖、golden 工具、--pages）全自动跟随。
3. `uv run python tools/semantic.py --update` 重录该节 golden；`menu.py` 的 `_TILES` 里改瓷砖 blurb（可选）。
4. `PlaceholderScene`（sections/placeholder.py）等四节全迁完后可整体删除，连同 `_PLACEHOLDERS`。

### B.4 踩坑

1. `tests/test_smoke.py:17` 曾钉死 `SCENES == 旧五元组`，与 P3 注册表扩容不可兼得；经用户拍板改为
   成员断言（`{"splash","menu","snake","dashboard","gallery"} <= set(SCENES)`），保护意图不变。
2. `kernel.cell.Line` **不可迭代**也**不加 tuple**：取段用 `line.segments`，宽度用 `line.width`；
   拼行先拼 `tuple[Segment, ...]` 再 `Line(...)`，`Line + Line` 可用，`cut_line(line, start, end)` 按显示列切。
3. `tools/semantic.py --update` 以 LF 重写**全部** golden；Windows autocrlf 下内容未变的文件也会显示
   modified（`git diff` 为空）。只 commit 真变的，其余 `git checkout --` 还原；`--check` 对换行归一化，仍绿。
4. `--pages` 现在输出 10 页（P3 注册表 + snake/gallery 契约保留）；`--headless` 默认仍落 Home（menu）帧。
5. `App.bind` 的键名形如 `"ctrl+p"`（decoder 规范形）；palette 由宿主 `app.open_palette(CommandRegistry)` 打开，
   命令 handler 用零参闭包（`jump(name)`/`toggle`/`app.quit`）。
6. 计数口径：验收"1638" = 1641 − 3（examples），但 P9 同时强制新增 ≤4 条测试；本波新增恰 4 条
   （`tests/test_demo_shell.py`），故真实全量 = **1642 passed**。
7. `Widget` 子类若声明 `__slots__`，新属性（`status_line`/`status_note`/`_wipe_from`）必须一并列入。
8. 瓷砖几何：`_TILE_H=10`、`_GAP=1`、3 列；`_grid()` 逐行拼接 `Line + Line`，间隙列是真实的空 Segment
   （tile_w 在 80/100 宽下分别为 24/30）；点击 rect 在 `render` 里随排版重算，与视觉逐列对齐（间隙列死区）。
   W2-b 若改瓷砖尺寸，两处（`_TILES/_TILE_H/_GAP` 与 `rects` 公式）同源，改 `_tile()` 内容不必动 rect。
9. 验收后返工记录：174f0e3（迷你动画行宽占用满 content 槽导致压边框，全部收 1 列余量）、
   d3dea78（`_GAP` 只进了 rect 计算没进 `_grid` 拼接，瓷砖贴死且点击错位 1 列）。
