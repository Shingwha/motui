# handoff · W3-a sections：Terminal 报告 + Themes 换肤

> 分支 `dm-w3a-report-themes`，worktree `C:\Users\shifu\.worktrees\mocode-tui\dm-w3a-report-themes`。
> 基点 = 最新 main（`6de43d1`，W2-b 已合入）。环境 `uv run python --version` = **3.13.16**。
> 开工基线 `uv run pytest -q` = **1653 passed in 33.76s**；波末全量 = **1655 passed**
> （= 基线 + 2 条新测试；原占位 round-trip 测试就地重写，条数不变）。`uv run ruff check .`
> 零告警，`tools/semantic.py --check` = 10 场景 match，`tools/api.py --check` = 198 名
> （未动登记册）。两节 `render_scene` 两次逐字一致已验（phases 0/13/20 × 100x30、80x24，
> `diff` 空）。占位时代结束：`_PLACEHOLDERS` 已删，但 `placeholder.py` 文件按红线零 diff
> 保留，`PlaceholderScene` 仍从 `sections/__init__` 可导入（无引用方）。

## A · 文件地图与公开对象

### A.1 `src/motui/demo/sections/terminal.py`——`TerminalScene`

- 公开对象：`TerminalScene`（`name = "terminal"`，Scene 协议；escape → `"menu"`、
  q → `"quit"`）。2x2 面板格：session/mouse·live 在上，color by capability/marker
  ladder 在下；标题行 + 提示行各占一行。
- **session**（每帧重建）：`size`（本次 render 的 Constraints，随 pane 缩放真变）、
  `sync`（DECSET 2026 对，字面文本 `\x1b[?2026h \x1b[?2026l`）、`color`
  （screen.color_mode，headless dump 即 truecolor——场景不读环境，环境探测属于
  `detect_color_mode` 在 Screen 构造时的一次性事）、`frames`（`tick {phase:04d}`，即
  shell 的相位计数，与 dashboard 同约定）、`budget`（16.7 ms/frame @ 60 Hz，常量注释
  说明来源，**不是测量**——墙钟 fps 是 live runner 用 `Painter.frames` 差分写状态行的）。
- **mouse · live**：headless 空态（enable 三连 `\x1b[?1000h ?1003h ?1006h`——demo 以
  `MouseMode.MOVE` 启动，与 `ansi.enable_mouse_tracking(hover=True)` 逐字对应 + 解码器
  支持的 SGR-1006/X10/urxvt-1015 一行）；`on_click(pos)` 落一条 `click (x, y)`，深度
  4 条，真机点击即实况（golden/pages 无点击 → 空态，确定性不受影响）。
- **色条**：`16`（FG_CODES 顺序 16 格，命名色）、`256`（24 级灰梯 `8+10*step`——
  kernel quantizer 搜索的同一公式 + 蓝通道 6 个 cube 级别）、`rgb`（32 格 24-bit
  渐变，整数插值 #161d27→#53c8f0）。swatch = `GLYPHS.bar_full` 着色 fg。
- **marker ladder**：同一 `_STAIR` 点集分别用 `Canvas(marker="cell"/"half"/"braille")`
  plot（10x1 各一块），cell/half/braille ✓，octant `— not probed (core: half/braille)`
  ——按工单不写任何探测逻辑。
- 状态仅 `_feed`（点击落）；其余帧是 (c, phase) 的纯函数。

### A.2 `src/motui/demo/sections/themes.py`——`ThemesScene`

- 公开对象：`ThemesScene`（`name = "themes"`；escape → `"menu"`、q → `"quit"`）。
- 帧结构：标题行（随所选主题重着色）→ 真 `Tabs` 选择条（dark/light/flat/sepia）→
  样例体（左 `role tokens` 面板：9 行 role 采样线；右 `controls` 面板：真控件
  Input/Checkbox/RadioGroup/Slider/Button）→ 出处行（`dark · Theme.dark() · …`）→ 提示行。
- 键位：`1`-`4` 直选、`←`/`→` 循环、`c` 切 compare（四主题紧凑采样并排，各占 1/4 宽）、
  点击选择条按位换主题。换主题 = `_switch()` → `_mount()` 整树重建（见 B.1）。
- `_SEPIA_PALETTE`：本文件用 `ColorPalette` 现场创作的暖色调，走
  `Theme.from_palette` 派生——展示"创作层 → 角色树"这条纯函数路线；每色带 16 色
  ansi 回退名。
- 无相位消费、无钟：两次逐字重放。

### A.3 `sections/__init__.py` 接线

- `_scenes()` 直接注册 `TerminalScene(theme)` / `ThemesScene(theme)`；`_PLACEHOLDERS`
  元组与循环删除。`PlaceholderScene` import/`__all__` 保留（文件零 diff 红线），
  后续清理波可与其文件一起删。SCENES、瓷砖、golden 工具、`--pages` 全自动跟随（已验）。

### A.4 golden 清单（`tests/golden/semantic/`，仍 10 个）

| 文件 | 动作 | 原因 |
|---|---|---|
| `terminal.txt` | 重录 | 占位面板 → 2x2 报告真帧（色条/marker 梯子的 SGR run 全部钉入） |
| `themes.txt` | 重录 | 占位面板 → 样例 + 选择条 + 出处行真帧 |
| 其余 8 个 | **零变化** | `--update` 曾因 CRLF/LF 重写把 8 个标脏，已 `git checkout --` 还原；内容 diff 为空，`--check` 绿 |

### A.5 测试（`tests/test_demo_shell.py`：1 条就地重写 + 2 条新增，新增 ≤4 红线内）

1. `test_the_report_sections_enter_render_and_return_home`——**重写**原占位
   round-trip 测试（占位已不存在，原断言 `"under construction" in text` 必红）：
   两节非空、无占位残留、esc 回 Home。
2. `test_the_terminal_report_dissects_the_pipe_and_replays`——尺寸自报、DECSET 2026
   字面对、mouse enable 三连、恰好 3 个 ✓、octant not probed、双点击落 feed、
   两次驱动逐字一致。
3. `test_the_themes_section_switches_skins_live`——dark/light/sepia 出处行随键切换、
   四帧两两不同、compare 含全部四名、strip 点击 x=8 选中 light、驱动重放逐字一致。
4. `tests/test_demo_scenes.py` 零修改，16 条仍绿。

## B · 机制与踩坑

### B.1 主题切换机制的取舍（工单要求先读再设计）

- **库的真实机制**：`Widget.theme` 是公开可写属性，theme-group 驱动的控件（Panel 边框、
  Tabs/Table/Button/Checkbox/ProgressBar/…经 `self.group()`）在 render 时解析，赋值即
  重绘——`widgets/base.py` docstring 明文承诺。**但**两类东西不吃这套：(a) 像 `Text`、
  `Sparkline` 这种拿显式 `style=` 的控件，样式是从某个 Theme 对象**捕获的值**，换
  `.theme` 不会重导；(b) 场景自绘 chrome 的 Segment 持有同样的捕获值。
- **Scene 协议的天花板**：shell（StatusLine/wipe/标题）在 `Showcase` 里，对 Scene 不可达；
  `Theme` 是冻结值、无全局注册表可换。即工单预设的降级路线成立：**全局换肤超出 Scene
  能力**，Themes 节的换肤是节局部的。
- **实现选择**：整树重建（`_mount()` 在每次 `_switch` 重建 tabs + 样例控件 + 面板），
  而非逐控件赋 `.theme` + 重导场景 Text 样式。理由：零"陈旧 token"死角（捕获值问题
  整类消失）、`_mount` 十几行、重建成本可忽略。代价：控件实例身份不跨主题保持——本节
  样例无会话状态，无实际损失。若后续波要"真·全局换肤"，正确落点是 App/壳层持有
  theme 并在 switch 时 walk() 全树赋 `.theme` + 对捕获型控件重建——那是壳层波次的活。
- **确定性**：切换只发生在 on_key/on_click；render 是 (state, c, phase) 纯函数。

### B.2 踩坑

1. **golden 的 LF/CRLF 陷阱（Windows + autocrlf）**：`semantic.py --update` 以 LF 落盘，
   10 个 golden 全部被 `git status` 标脏；实际内容 diff 只有本波两节。其余 8 个
   `git checkout --` 还原后 `--check` 仍绿（工具读侧做了归一）。后续波在 Windows
   重录 golden 后照此办理，勿把无关 golden 带进 commit。
2. `demo/` 在 ruff `exclude` 列表里：`uv run ruff check src/motui/demo/...` 显式传路径
   会绕过 exclude 报出 6 个**存量**错误（layout.py 一条 E501 等），但门禁
   `uv run ruff check .` 全仓绿。不要被显式路径的输出吓到，也不要顺手去修存量
   （零 diff 红线）。
3. `Row.children` 里塞非 Widget 适配器（`_Box`，仿 dashboard `_FixedHeight`）可行：
   `Widget.__setattr__` 对 `children` 只对有 `parent` 属性的孩子回指，纯鸭类型直接用。
4. 场景行宽纪律：octant 行初版超右栏 inner 宽被裁（`not probed (pixel core ships
   half/braille)` → `not probed (core: half/braille)`）；compare 紧凑标签宽 6 时
   `accent` 无缝贴样例 → 7。两处都是数格子解决的。
5. `demo.__init__` 的 `TICK_HZ` 不能被 sections import（`demo/__init__ → showcase →
   shell → sections` 会成环）：terminal 节自持 `_FRAME_HZ = 60` 常量并注释指认来源。

## C · 接手点

- 真机人工项（本波无法自动验）：live 下点击 mouse·live 面板事件落位、DECSET 2026
  在真终端的整帧交换观感、色条在 16/256 真机上的降级观感（golden 只钉 truecolor 路径）。
- 若 W3-b/后续波要删 `placeholder.py`：连 `sections/__init__.py` 的 import、
  `__all__` 项一起，`test_demo_shell.py` 无引用，安全。
