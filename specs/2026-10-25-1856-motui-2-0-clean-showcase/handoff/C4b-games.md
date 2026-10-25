# C4b · Breakout / Dashboard / examples / 5-scene semantic · 交接

> 分支 `2.0-clean/c4b-games`；起点 `687a9c9`（含 `5ce3db2` 工单）；4 个工单 commit + 本 handoff。
> 结果：`--pages` 5 场景，Breakout 可玩/可回放，Dashboard 实时采样，examples 3，semantic 5。

## A. 交付面

### 结构（新增/修改）
```
src/motui/demo/breakout.py    453  BreakoutScene: state/physics/input/render
src/motui/demo/showcase.py    +303 DashboardScene / _FixedHeight / menu 4 项 / SCENES 5
src/motui/demo/__init__.py     +13 PAGE_PHASE=20 / 模块文档
examples/code.py                60 Markdown OVERFLOW + 双轴 ScrollPanel
examples/{snake,dashboard}.py  删除（-215）
.github/workflows/ci.yml        示例 3 step，删 snake/dashboard
tests/test_demo_scenes.py      127 场景行为/确定性用例
tests/{test_smoke,test_examples,test_semantic_golden}.py
tests/golden/semantic/*.txt    5（新增 breakout/dashboard，重录 splash）
tests/golden/README.md         5 场景 / PAGE_PHASE=20
```
- **Breakout**：`min(width,80) x min(height,24)` 的块居中；1 行 HUD + 22 行 Canvas（内侧
  78×20）+ 1 行提示；4×12 块 2 格砖（gap 1，level 决定 13 取模孔洞），7 格拍、1 格球；
  轴分离碰撞、拍面三段反弹、清砖升级（speed 1→2→3）、命 3、暂停、game over Panel 覆盖；
  ←/→/h/l、space（发球/暂停/重开）、esc/q 回 menu。
- **Dashboard**：48 点滚动窗口，tick 推 1 点；braille Sparkline + cpu/mem ProgressBar +
  3 行 Table + 事件日志；header 时钟 `mm:ss.t` 由 phase/30 推导；2×2 Panel 网格按
  c.width/height 每帧重排，80×24 与 100×30 都满宽不溢出。
- **Menu**：4 项全部接真场景，`_PlaceholderScene` 与 notice 删除；`_activate` 直接返回
  `option.value`。
- **语义/页面**：`SCENES=("splash","menu","breakout","dashboard","gallery")`；
  `PAGE_PHASE=20`；`--pages` 5 个规则头；semantic 5 文件各 31 行。
- **examples**：quickstart / code / wide_table；code.py 恒 headless，`WrapMode.OVERFLOW` +
  `ScrollPanel(axis="both")`，回放滚到 `x_offset=29` 后断言 `tail-marker`；CI 对应三步。

### 门禁（真实输出）
```
uv run pytest -q -p no:cacheprovider    -> 1626 passed in 13.84s
uv run python tools/semantic.py --check -> semantic: 5 scenes match
uv run python -m motui --pages          -> 5 headers, exit 0
uv run python -m motui < /dev/null      -> exit 0
--scene breakout --frames 30 --headless -> exit 0, HUD score 0010 level 1, 86 brick cells
--scene dashboard --frames 30 --headless-> exit 0, tick 0030, 4 panels
examples {quickstart,code,wide_table} --headless -> all exit 0
uv run ruff check .                     -> All checks passed!
uv run pyright                          -> 0 errors, 0 warnings
uv run lint-imports                     -> 4 kept, 0 broken
uv run python tools/api.py --check      -> 185 names match
uv run python tools/growth.py           -> OK (full probe: pytest/semantic/api pass)
uv run python tools/framebench.py       -> exit 0, replay 400 ms,
  render-hash e7ca544b...652986da（与 C4a 相同；基线 677 ms，未劣化）
```

## B. 实现、确定性与取舍

- **确定性**：无 random/time；两个场景只在 `tick(phase)` 推进，render 先 `_sync(phase)`，
  因此 `render_scene`/`scene_output` 设 phase 后无需外部 tick。phase 回退视为场景重入：
  breakout 重开、dashboard 重新播种。`_MAX_SYNC=4096` 防止异常 phase 卡死。
- **开局/发球取舍**：初始 `launched=True`（球在拍上方直接开球），保证 `--frames`/semantic
  有运动内容；丢球或过关后 `launched=False`，space 发球。space 在球已发射时切换暂停，
  game over 时重开。
- **碰撞/关卡**：砖块存 `(row,col)` 逻辑坐标，渲染/碰撞按当前 `_brick_x/_cols` 换算，
  resize 不丢砖；水平/垂直分轴处理墙、砖、拍；清空后 `level+1`、
  `speed=min(3,1+(level-1)//2)`、重铺砖、停球等待发球。
- **布局**：breakout 用固定 80×24 上限块（100×30 时上下左右留白），80×24 与 100×30 的
  物理场完全一致；dashboard 每个 Panel 的固定行高由 `_FixedHeight` 适配（Panel 只给子
  组件 width），`Row(widths=...)` 精确分宽。
- **语义**：`tools/semantic.py` 未改（本来就从 `demo.SCENES` 读）；PAGE_PHASE 8→20 重录
  splash（扫光位置），menu/gallery 字节未动。README 同步 5 场景。
- **examples 取舍**：code.py 无 live 分支（恒 headless，60 行），把演示点集中在 OVERFLOW +
  双轴滚动；snake/dashboard 的 Canvas/Sparkline 能力已由 demo 场景覆盖。
- **工单外但门禁必需**：`tests/test_semantic_golden.py` 的 `len(found)==3` 改为
  `len(SCENES)`（否则 T1 起必红）；`tests/test_smoke.py` 的 SCENES/页面断言随场景数更新。
- **坑**：Table 4 行在 80×24 的下半 Panel 内放不下（内高 8），改为 3 行 + uptime 放
  summary；`Canvas` 每帧新建，`Panel` memo 依赖子行身份；Dashboard 在 `__init__` 里
  `_seed` 后必须 `_refresh` 才能让真实控件看到初始值。

## C. 路径与提交

关键路径：`src/motui/demo/{breakout,showcase,__init__}.py`、
`examples/{code,quickstart,wide_table}.py`、
`tests/{test_demo_scenes,test_examples,test_smoke,test_semantic_golden}.py`、
`tests/golden/semantic/*`、`.github/workflows/ci.yml`。

commit：`6f1889d` Breakout · `bf56f9b` Dashboard · `c0cb637` semantic 5 ·
`a5333e6` examples/CI · 本 handoff。

C5 待办：README.md（示例表仍指 snake/dashboard）与 CONTRIBUTING.md 的 examples 命令、
`tools/semantic.py` docstring 仍写 “three showcase scenes”（红线内未改）。
