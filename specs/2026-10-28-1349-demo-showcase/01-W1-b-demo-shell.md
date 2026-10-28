# W1-b · demo 新壳：sections 拆分 + Home 瓷砖 + 过渡 + StatusLine + 60Hz
> 分支 `dm-w1b-demo-shell`；前置 无（并行波，与 W1-a 文件不相交）；写入范围 `src/motui/demo/**`、`tests/golden/semantic/*`（重录）、`tests/test_demo_shell.py`（新建）

## 目标

把 900 行的 `demo/showcase.py` 重排为"一壳多节"结构并交付新壳体验：Home 瓷砖导航（即 menu 节）、场景 wipe 过渡、StatusLine 底栏、60Hz、命令面板接 demo 命令。最高约束：**`tests/test_demo_scenes.py` 零修改全绿**——`motui.demo` 公开面与 `motui.demo.showcase` 的可导入名是契约（见 `ref/interfaces.md`）。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → 本工单。无前置 handoff。
- 现状：`showcase.py` 含 Scene 协议 + Splash/Menu/Dashboard/Gallery 四场景 + Showcase 壳；`demo/__init__.py`（221 行）含 `main`/`render_scene`/`scene_output`/`_interactive`（`TICK_HZ=30`）；`snake.py` 独立。
- 基线命令（开工先跑，贴真实输出）：
  `uv run pytest -q`（1641 passed）
  `uv run python -m motui --headless` 与 `uv run python -m motui --pages | head -40`
- 稳定区（勿重读）：`src/motui/app`、`src/motui/kernel`、`src/motui/terminal`——接口以 `ref/interfaces.md` 为准；`demo/snake.py` 本波不改（W4 才迁入 Motion 节）。

## 拍板决策（照做，不现场猜）

| # | 决策 |
|---|---|
| P1 | hub 场景名保留 `"menu"`：Home 瓷砖就是新 menu，`MenuScene` 类名与文件可改，但 `SCENES` 含 `"menu"`、splash 转场目标 `"menu"` 不变 |
| P2 | 场景类**物理文件**迁到 `demo/sections/`（splash/menu/dashboard/gallery 各一文件），`showcase.py` 保留为兼容再导出模块（只 re-export，不写逻辑） |
| P3 | 六节注册表：`menu/components/layout/motion/dashboard/terminal/themes` + `splash`。components/layout/terminal/themes 四节本波为**占位节**（统一"under construction"面板 + 标题 + 返回提示），但必须可进入、可渲染、可回 Home、有 golden |
| P4 | 过渡 wipe：按列揭示，时钟驱动、确定性（phase/clock 推导遮罩列数），约 150ms，头尾帧与静态帧逐字可重放 |
| P5 | 帧率：`_interactive` 的 `TICK_HZ` 30→60 且 `App(throttle=1/60)`；Dashboard 等节逻辑按 TICK_HZ 换算的地方全部跟随（全局 grep `_DASHBOARD_FPS`/`TICK_HZ`） |
| P6 | StatusLine 底栏常驻：左=节名，右=主题名·fps（fps 用 `painter.frames` 差分，确定性模式下显示 `--`） |
| P7 | 命令面板：`app.open_modal` 的 palette 注册 demo 命令——jump to section（每节一条）、toggle status line、quit。用 App 既有公共 API，不改 src |
| P8 | golden 逐场景重录（`uv run python tools/semantic.py --update`），handoff 列出重录原因（menu 重绘、新增占位节）；snake/splash 理论上不应变化，若变了逐字说明原因 |
| P9 | 新测试落新文件 `tests/test_demo_shell.py`（≤4 条）：瓷砖导航路由、wipe 中间帧确定性、占位节进出、SCENES 与 golden 覆盖一致 |

## 工单（按序执行，每项一个 commit）

### T1 sections/ 物理拆分（行为零变化）
- `sections/splash.py / menu.py / dashboard.py / gallery.py` 迁入现类；`sections/__init__.py` 聚合注册表；`showcase.py` 变纯 re-export；`demo/__init__.py` 只动 `main`/`_interactive`（60Hz）不动公开函数。
- 只允许改：`src/motui/demo/**`。验证：`uv run pytest -q tests/test_demo_scenes.py tests/test_smoke.py` 全绿、golden `--check` 绿（此步不应需要重录）。

### T2 Home 瓷砖（menu 节重绘）
- 居中标题（`art.big_text` 小号或纯文本）+ 六块瓷砖（每块：节名、一句话、≤6 行的实时微缩动画），键盘 ↑↓←→/enter 与点击导航；占位节进得出得回。
- 瓷砖微缩动画必须确定性（phase 推导）。验证：`--headless --scene menu --frames 2` 两帧不同且逐字可重放。

### T3 过渡 + StatusLine + 面板命令
- wipe 遮罩在 Showcase 壳层实现（渲染时对目标节行做列裁剪拼接），tick 驱动。
- StatusLine、面板命令按 P6/P7。
- 验证：headless 跑一次含转场的序列（可用 `--scene` + 脚本键？无此机制则以测试驱动 `Showcase.switch` 断言中间帧）。

### T4 golden 重录 + 新测试 + 收尾
- `tools/semantic.py --update`；新测试文件；`demo/showcase.py` 里对已消失符号的引用清零（re-export 之外零逻辑）。
- 验证：全量 pytest + ruff + golden --check。

## 验收

1. `uv run pytest -q` 全绿（贴真实输出；test_demo_scenes.py 16 条零修改通过）
2. `uv run ruff check .` 零告警；`tools/semantic.py --check` 绿
3. `uv run python -m motui --headless` 与 `--pages` 跑通，输出含全部七节名
4. `grep -n "_sync\|showcase" src/motui/demo/showcase.py` 证明 re-export 壳无残留逻辑（或给出等价证据）

## 禁触清单

`tests/test_demo_scenes.py`（零修改）；`examples/**`；`src/motui/` 除 `demo/` 外全部；`tools/**`。golden 只允许因本波视觉变化重录。

## 交接包

分支最后 commit 写 `handoff/W1-b-<agent>.md`。A 节：新 SCENES 全表、sections/ 文件地图、Showcase 壳新公开名（如有）、golden 重录清单。B 节：wipe 的确定性机制、60Hz 改动的连带面、占位节与 W2-b/W3-b 的接手点（占位节文件名与注册方式）、踩坑。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（本波无）/ 探索审计 / 未决问题
