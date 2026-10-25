# C4a · Showcase 骨架（Splash / Menu / Gallery）· 交接

> 分支 `2.0-clean/c4a-showcase`；起点 `fec3a68`；5 个工单 commit + 本 handoff。
> 旧 57-topic tour 已整体删除；新 demo 是单页三场景 Showcase。

## A. 交付面
### 结构（925 行）
```
src/motui/demo/__init__.py    208  SCENES / render_scene / scene_output / main
src/motui/demo/__main__.py      8  python -m motui.demo
src/motui/demo/art.py         186  FONT_5X7 / big_text / center / gradient_styles
src/motui/demo/showcase.py    523  Scene Protocol / Showcase / Splash / Menu / Gallery
src/motui/demo/fixture.md    保留（framebench 读）
```
- **Showcase(Widget)**：`focusable/clickable`；`scene` + `phase`；`switch`；`tick` 推进
  phase、应用 transition 并 touch；`on_key/on_click` 委托场景并消费输入；`"quit"` 只调
  宿主 `on_quit`（`main` 接 `App.quit`）；`render` 把场景结果补齐到 `c.max_height`。
- **Splash**：29 列 5×7 `█` logo，`#53c8f0 -> #c4b5fd` 24-bit 渐变，phase 驱动白色扫光列
  （每 2 tick 一格）、副标题 `a terminal UI kernel · 2.0.0`、五点脉冲、`press any key`；
  任意键/点击或 60 tick（30 Hz ≈ 2s）进 menu。
- **Menu**：48 列 `Panel(title="showcase")` 内是真实 `Select`（4 个带 description 的
  Option）+ 标题/版本/提示；↑↓/jk、enter、点击经 `Panel/Column.child_at -> Select.on_click`
  选中；Gallery 进真场景，Breakout/Dashboard 显示 `… — coming in this build`（≈3s），
  Quit/q 退出，esc 回 splash。
- **Gallery**：`Row` 三栏（各 `Panel`）：真实 `Tree`、`Table`（光标 index 1）、controls 栏
  （`Markdown` + 动画 `ProgressBar` + `Slider` + `Input`）。tab/shift-tab 切换焦点，
  方向键/键入转发；点击沿 `child_at` 链聚焦；esc 回 menu。80×24 与 100×30 实测最大行宽
  80/100、行数不超屏。

### 运行模式

- `--pages`：3 个全宽规则头 + 场景文本（100×30，`PAGE_PHASE=8`）。
- `--scene NAME [--frames N] --headless`：每 tick 走一次状态机（splash 60 帧进 menu），
  输出当前场景文本；无 TTY / stdin 非 TTY 时默认输出 menu 文本并 exit 0，不读 stdin。
- TTY：`App(terminal=TerminalOptions(mouse=MOVE))` + `fill` + `focus` +
  `every(1/30, tick->invalidate)` + `run()`；不 sleep。

### 语义 golden

- `SCENES=("splash","menu","gallery")`；`tests/golden/semantic/*.txt` 各 31 行，格式同旧版
  （`# <scene> 100x30 cursor=x,y` + `text\tstart-end:<sgrhex>[:L<link>]`）；`tools/semantic.py`
  用 `scene_output` + `Emulator`。删除 `tools/golden.py`、`tests/golden/topics/**`、57 个旧
  semantic 文件与 CI golden step；`tests/golden/README.md` 重写。

### 门禁（真实输出）

```
uv sync --locked                       -> motui==2.0.0 (editable, this worktree)
uv run pytest -q -p no:cacheprovider   -> 1615 passed in 24.49s
uv run python tools/semantic.py --check -> semantic: 3 scenes match
uv run python -m motui --pages         -> exit 0, 72 lines, max width 100, 3 headers
uv run python -m motui < /dev/null     -> exit 0
uv run python -m motui --scene splash --headless -> exit 0
uv run ruff check .                    -> All checks passed
uv run pyright                         -> 0 errors, 0 warnings
uv run lint-imports                    -> 4 kept, 0 broken
uv run python tools/api.py --check     -> 185 names match
uv run python tools/growth.py          -> pytest/semantic/api pass, OK (full probe)
uv run python tools/framebench.py      -> exit 0, replay 677 ms,
  render-hash e7ca544b051b8b3229b2ecbca03bc6c1e821908ad3ac278024e6a645652986da
```
## B. 实现、确定性与删除清单

- **视觉取舍**：logo 用 5×7 位图逐格写 `Segment`（单宽 `█`），渐变按列插值真彩；扫光只改
  该列样式不新增字符，语义快照可见 SGR 变化。menu 用真实 `Select` 而非自绘。gallery 三栏
  全真实组件，ProgressBar 每 tick 由 `sin(phase/7)` 驱动；显式 `Theme.dark()`，只产 Surface。
- **headless 确定性**：`render_scene`/`scene_output` 只接受显式 `phase`，不读时钟、不读
  stdin、不用随机数；`scene_output` 是 `HeadlessScreen + Runtime(interactive=False) +
  fill + paint`，不启动 pump。文本 dump 右剥行尾空格、丢尾部空行；semantic 保留 30 行。
- **删除清单**：`demo/topics/**`、`demo/{assets,model,registry,script,session,shell,stage}.py`、
  `tools/golden.py`、`tests/golden/topics/**`、57 个旧 semantic 文件、CI golden step。
  `demo/fixture.md` 保留；`tools/framebench.py` 零修改。
- **工单外但门禁必需**：`tools/growth.py` 的 golden gate 换成 semantic（被调工具已删），
  `tests/testing/test_growth_tool.py` 断言改为 `growth: semantic -> 0`。pyproject 里
  `tools/golden.py` 的 ruff per-file ignore 成为惰性条目（pyproject 禁触，未改）。
- **C4b 待接**：Breakout/Dashboard 仍是提示；`examples/**` 未动；若场景要进 App focus ring，
  需要把子控件挂到 `Showcase.children`（当前刻意只有一个焦点目标）。
- **坑**：public 属性赋值自动 touch；Menu 点击要减居中偏移并用 `child_at` 下钻；Input 键入
  需 `KeyEvent(key, char)`；Gallery 的 `q` 在 Input 聚焦时是普通字符；`render` 必须补齐
  `max_height`，否则 FILL 下方留旧帧。

## C. 路径与提交

关键路径：`src/motui/demo/{__init__,__main__,art,showcase}.py`、`tools/{semantic,growth}.py`、
`tests/{test_smoke,test_semantic_golden}.py`、`tests/testing/test_growth_tool.py`、
`tests/golden/semantic/*` 与 `README.md`、`.github/workflows/ci.yml`。

commit：`1c45ba8` 骨架与旧 tour 删除 · `6c51045` Splash/Menu · `5bd9218` Gallery ·
`b3ab239` semantic/golden/CI · `97f0925` growth 测试 · 本 handoff。
