# W3-a · Terminal 报告节 + Themes 节（占位，W2-b 合并后补前置上下文再派工）
> 分支 `dm-w3a-report-themes`（派工时定）；前置 W2-b；写入范围 `src/motui/demo/sections/**`、golden 重录、新测试 ≤4 条

## 目标
**Terminal**：尺寸/色模式/DECSET 2026/鼠标实况（移动区回显最近事件）/16·256·truecolor 色条/marker 阶梯自检（octant 探测联动 W2-a，未合并则显示未探测）/帧计数与 ms/帧。**Themes**：同一样例布局 + 快捷键/面板即时切主题，展示主题系统贯穿全部控件。

## 范围
只动对应 section 文件；探测展示优先消费 W2-a 的公共能力（未合并则留桩位）。

## 验收
全量门禁绿；golden 更新；两节确定性重放（鼠标区 headless 下显示脚本注入事件或空态）。

## 前置上下文
- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → `handoff/W2-b-sections.md`（B 节：真实节的结构/盘点方法/踩坑）→ 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（**1653 passed**）；`uv run python -m motui --pages` 看 terminal/themes 两页占位现状。
- 稳定区（勿重读）：`demo/shell.py`、`demo/showcase.py`、`sections/menu.py`、`sections/splash.py`、`sections/components.py`、`sections/layout.py`、`sections/dashboard.py`、`sections/gallery.py`、`demo/snake.py`——你只动 `sections/terminal.py`、`sections/themes.py` 与 `sections/__init__.py` 里这两个名字的接线（现指向 `placeholder.py` 实例，替换之）、golden。
- 探测现实：PixelCanvas（W2-a）只实现了 half/braille，**octant 未实现**——Terminal 节的 marker 阶梯自检按"half ✓ / braille ✓ / octant 未探测"展示，不要自己写探测逻辑。
- 已知约束/坑：确定性纪律同全仓（整数 phase、无墙钟、无未播种随机）；鼠标实况区在 headless 下显示空态即可，真机行为由终验人工看；`test_demo_scenes.py` 零修改；golden 重录逐条说明。
