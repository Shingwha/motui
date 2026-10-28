# repo-map · motui（2026-10-28，lead 实测）

## 目录职责

```
src/motui/
  kernel/      纯值层：geom/cell(Line,Segment,Surface)/layout(Constraints)/style(Style,Theme)/events/event 文档模型。零 I/O，零 os/sys 导入
  terminal/    终端层：screen(HeadlessScreen,TerminalOptions,MouseMode)、keys(RawTerminalKeys 读线程)、decoder(SGR-1006/X10/urxvt)、paint(Painter 逐行 diff + DECSET 2026)、win32
  app/         Runtime(pump/Timer/every/animation/clock/advance 虚拟时钟)、App(默认 handler 链 router.DEFAULT_HANDLERS 12 级,bind 在第 11 级)、workspace、pointer/gesture/focus/overlays
  widgets/     Canvas(marker: cell/half/braille, put/text/box/plot, 行缓存)、Text/Input/Panel/Table/Select/Markdown/Sparkline/…
  demo/        __init__(入口 main/render_scene/scene_output/PAGE_PHASE=20/TICK_HZ=30)、showcase.py(900 行:Scene 协议+Splash/Menu/Dashboard/Gallery+Showcase 壳)、snake.py、art.py(big_text 5×7 字体)
  testing/     headless_tui(Harness)/Emulator/snapshot
examples/      quickstart.py / code.py / wide_table.py（自包含、--headless 可验）
tools/         semantic.py(golden --check/--update)、framebench.py(性能)、api.py+api-2.0.txt(公共 API 面板)、growth.py
tests/         test_demo_scenes.py(16 条,直接 import showcase 场景类)、test_examples.py(subprocess 跑 examples)、test_semantic_golden.py(逐场景 golden)、app/core/kernel/terminal/widgets/testing/ 各目录
specs/         历史操作组（本组：2026-10-28-1349-demo-showcase）
```

## 入口点

- `python -m motui` / `python -m motui.demo` → `motui.demo.main`（`--headless`/`--pages`/`--scene`/`--frames`）
- `examples/*.py` 各自 `main(argv) -> int`

## 构建/测试/lint 命令（全部实测可跑）

```
uv run pytest -q                    # 2026-10-28 基线：1641 passed in 13.26s
uv run ruff check .                 # 零告警要求；ruff format --check 同
uv run python tools/semantic.py --check    # golden；重录: --update
uv run python tools/framebench.py   # 帧性能
uv run python -m motui --headless   # demo 无头全场景
```

依赖仅 `wcwidth`，Python 3.12+；**禁新增运行时依赖**（像素层必须 stdlib）。

## 关键类型/数据流

- 渲染契约：组件 `render(Constraints) -> Surface`；Runtime.pump: timers→`_paint_at`(retile→compose→overlays→Painter.diff)
- 时间：`runtime.clock()`=`monotonic+offset`；`Timer` 绝对 deadline（`every`/`animation(hz)`）；`advance(dt)` 确定性重放（测试核心手法）
- 事件：`App.dispatch` 走 12 级 `DEFAULT_HANDLERS`，`bind` 是第 11 级；**替换链会砍断按键**（扩展不替换）
- Scene 协议（demo 内）：`render(c, phase) / tick(phase) -> transition|None / on_key / on_click`；整数 phase + `Showcase._sync` 确定性
- Canvas：整格写入（put/text/box/plot），行级脏缓存；marker 只有 plot 用（cell/half/braille）

## 约定

- 注释/docstring 英文；commit 英文一行祈使句；值冻结不可变；测试命名场景句（"test_the_splash_waits…"）
- golden：`tests/golden/semantic/<scene>.txt`，逐场景钉文本；`SCENES` 增删必须同步重录
- 每波新增测试 ≤ 4 条，落既有文件或明确的新文件

## 环境陷阱

- Windows + Git Bash；一切经 `uv run`；demo 转储需 UTF-8 stdout（locale codepage 会炸 box 字符，demo 已处理）
- 盲文/块字形渲染随字体/终端变化（WT 1.22 才有 octant；Direct2D 块元素有缝隙 bug）——**golden 只钉文本不钉字形观感**
- 主检出有一个未跟踪 `.zcodeignore`（用户文件，勿动勿加）
- 鼠标坐标是格子粒度（SGR-1006），无 1016
- `App(throttle=…)` 默认 0.030（≈33fps 上限）；像素场景要 `1/60`

## 找 X 去哪

- 渲染/节流/时钟 → `app/runtime.py`；输入解码 → `terminal/keys.py`+`decoder.py`；默认分发链 → `app/router.py`
- 画布 → `widgets/canvas.py`；主题 → `kernel/theme.py`；demo 场景机制 → `demo/showcase.py`（Scene 协议 + Showcase 壳）
- 像素模式现状参考实现 → `examples/pixel.py`（Raster/quantize/PixelDemo，本轮 W1-a 升级对象）
