# W2-b · demo sections：Components 游乐场 + Layout 实操（占位，W1-b 合并后补前置上下文再派工）
> 分支 `dm-w2b-sections`（派工时定）；前置 W1-b；写入范围 `src/motui/demo/sections/**`、golden 重录、新测试 ≤4 条

## 目标
把占位节替换为真内容。**Components**：左真实控件（Input/Choice/按钮→toast/modal、Table 排序）+ 右同步代码片段，tabs 分组 inputs/data/overlays。**Layout**：split 键盘调宽、dock 挪位、双轴滚动代码、wide_table 溢出——examples 三故事的可玩合并。

## 范围
只动 W1-b 建立的 sections 骨架内对应文件；每节 150–350 行；确定性动画纪律同全局红线。

## 验收
全量门禁绿；golden 更新；两节 headless 可逐字重放；test_demo_scenes 仍零修改绿。

## 前置上下文
- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md`（demo 内部结构节）→ `handoff/W1-b-shell.md`（B 节：踩坑 9 条与占位节接手点必读）→ 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（**1646 passed**）；`uv run python -m motui --pages` 看 10 页现状。
- 稳定区（勿重读）：`demo/shell.py`、`demo/showcase.py`（re-export 壳，禁改）、`sections/menu.py`、`sections/splash.py`、`sections/dashboard.py`、`sections/gallery.py`、`demo/snake.py`——你只动 `sections/components.py`、`sections/layout.py` 与注册表里这两个名字的接线。
- 接手点：两节现在是 `sections/placeholder.py` 的 `PlaceholderScene` 实例；你把它们替换为真场景类（文件名 `sections/components.py` / `sections/layout.py`，注册进 `sections/__init__.py`），golden 相应重录。
- 已知约束/坑（从 W1-b handoff 摘要）：
  - `Scene` 协议是 `render(c, phase) / tick(phase) -> 转场名|None / on_key / on_click`；确定性靠整数 phase 推导，禁止读墙钟或 `random.Random()` 无种子。
  - 节内 per-tick 动画墙钟速度是 60Hz 下的 ×2（`_DASHBOARD_FPS=30` 被测试钉死的连带），设计动画节奏时按 tick 数思考，不按秒。
  - golden 重录 `tools/semantic.py --update`，handoff 里逐条列原因；`tests/test_demo_scenes.py` 零修改红线不变。
  - palette/命令/StatusLine 由壳层管，节内不要自己注册命令或画底栏。
