# Spec W2 · 渲染内核（波次 W2）
> ✅ 2026-10-04 已交付合并；终验 585 passed（main）。分支见 git log --merges。
> 分支 `wfs2-render-core`；前置：**W1 已合并**（从合并时刻最新 main 切出）；深读：`00-overview.md` + `01-w1-primitives.md`

## 目标

在 W1 基础件之上实现全屏渲染内核三件套：`screen.py`（alt screen 进出 + 内存录制屏）、
`viewport.py`（视口 + 固定尾区布局）、`painter.py`（全屏逐行 diff 画家），加测试，
并把本波符号补进 `src/mocode_tui/__init__.py`。
最高约束：`Painter.rows()` 永远恰 `screen.height` 行；无变化帧零字节；enter/leave 字节序列精确锁定。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `screen.py`
- `Screen` runtime_checkable 协议：`width` `height` `live` 三个属性 +
  `enter()` `leave()` `write(s)` `flush()` `refresh_size()`。
- `TerminalScreen(stream=None)`：默认 stdout。
  - `_live = stream.isatty() 且 ansi.enable_vt()`（构造时判定一次，之后恒定；VT 探测失败 → live=False）。
  - `enter()`：仅 live 才由驱动调用（驱动是 W4 的事，本模块只管：live 时写
    `enter_alt_screen() + hide_cursor()`；非 live 时 enter/leave 写空串——**不得**写转义到非 live sink）。
  - `leave()`：live 时写 `show_cursor() + leave_alt_screen()`。
  - `refresh_size()`：重读 `terminal_size()`（尺寸缓存由 refresh 更新；painter 每帧前调它）。
- `HeadlessScreen(width=80, height=24)`：内存 `StringIO` 录制；**live 恒 True**；
  `enter/leave/write` 全部录进 `output`（enter 也录真实转义字节，测试据此断言）；`flush()` 空转；
  `clear()` 重置录制缓冲。不得实现任何 escape 解析/仿真——它是录音机不是终端。
- 测试 `tests/test_screen.py`：HeadlessScreen enter/leave 字节形状（`"\x1b[?1049h\x1b[?25l"` /
  `"\x1b[?25h\x11b[?1049l"` 字面以实现为准但必须与 ansi.py 单点一致——断言 `output == enter_alt_screen()+hide_cursor()` 这种形式，
  不硬编码重复字节）；write 录制顺序；clear；TerminalScreen 非 TTY → live=False（monkeypatch isatty）；
  refresh_size 生效（monkeypatch terminal_size）。

### T2 `viewport.py`
- `ScreenLayout`：`rows: list[Line]`（恰 `height` 行）、`viewport_rows: list[Line]`（纯视口行）。
- `Viewport(document)`：
  - `layout(width, height) -> ScreenLayout`：
    1. pinned 块按文档序渲染（`block.render(width)`；sealed 走缓存、open 每次重渲）；
    2. `vh = max(height - pinned_total, 0)`；
    3. 非 pinned 块按文档序渲染拼接成 `all_rows`（同一缓存规则）；
    4. `offset` 夹取 `[0, max(0, len(all_rows) - vh)]`；**贴底语义**：`at_bottom` 为真时 offset 取最大值；
       用户滚离贴底后新内容到达不改变 offset（at_bottom 为假保持假）；
    5. `viewport_rows = all_rows[offset : offset + vh]`；
    6. 非贴底且 `vh >= 1` 且 `offset + vh < len(all_rows)` → `viewport_rows[-1]` 替换为
       `Line.from_text("─ more below ─", MUTED)`；
    7. `rows = viewport_rows + pinned_rows`；长度 < height 补空行；`pinned_total > height` 时
       `rows` = pinned 行按文档序取前 `height` 行（视口为空）。
  - `scroll_up(n=1)`（offset 减小，夹取 0）、`scroll_down(n=1)`（增大，夹取上限）、`scroll_to_bottom()`（回贴底）。
  - 只读：`offset`、`total_rows`、`viewport_height`（当前高度换算值，layout 时更新）、`at_bottom`。
  - sealed 缓存：viewport 持有；`cache_width != width` → 清空重算。
- 测试 `tests/test_viewport.py`（核心，覆盖要全）：短文档顶对齐补空行；长文档贴底与窗口内容；
  scroll_up/down 夹取；滚离贴底后 append 新块 offset 不动；scroll_to_bottom 归位；
  `vh==0`（pinned 撑满）→ rows 恰 height 且只含尾区前 height 行；「more below」行出现/消失条件
  （贴底不出现；滚到顶且下方还有内容才出现）；sealed 缓存命中（seal 后换 component 行不变）与宽度变化失效；
  pinned 与非 pinned 混排的顺序正确性。

### T3 `painter.py`
- `Painter(document, screen, *, throttle=0.030)`：throttle 只为 API 稳定保留，painter 从不自己节流。
- `flush()`：
  1. `screen.refresh_size()`；尺寸相对上帧变化 → `_full = True`；
  2. `layout = Viewport(document).layout(width, height)`（viewport 常驻 painter 私有，跨帧保持 offset）；
  3. `_full` → 先写 `"\x1b[2J"` 再全量写所有行；
  4. 否则逐行与 `self._rows`（上一帧目标行）比较：不同行写 `f"\x1b[{i+1};1H" + "\x1b[K" + row.styled()`；
     全相同 → 不调 `screen.write`（零字节）；
  5. `screen.live == False` → **完全跳过 write/flush**（运行期静默），但 `self._rows` 照常更新（逻辑态可查询）；
  6. 写完统一一次 `screen.flush()`（有写入时）。
- `rows() -> list[Line]`：当前目标屏（恰 height 行；未画过为空列表——首帧前无内容）。
- `scroll_up(n=1)/scroll_down(n=1)/scroll_to_bottom()`：转发内部 viewport。
- 行 `styled()` 为 "" 的：仍发定位+清行（旧内容必须被清掉）。
- 测试 `tests/test_painter.py`：首帧含 `\x1b[2J` 且全量（逐行断言输出中每行都出现）；
  次帧零变化 → `output` 长度不变；单行变化 → 输出恰为 `\x1b[{r};1H\x1b[K`+styled 且无其他行序列；
  行变空 → 该行被清；尺寸变化 → 全量重画且 `rows()` 恰新 height；
  非 live → `output` 空但 `rows()` 有内容；scroll_up 后 flush → 窗口行正确进入 diff；
  pinned 占 2 行时视口高度 = height-2 的窗口正确性。

### T4 `__init__.py` 追加导出 + 门禁
- 追加导出：`HeadlessScreen, Screen, TerminalScreen, Painter`（及必要的 `wrap_line` 等若 W1 未导）。
- `uv run pytest` 全绿（贴尾部输出）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest`：`N passed`，0 失败（贴尾部原文；N ≥ W1 的数）。
2. `uv run python - <<'PY'` 冒烟：Document 加 3 文本块 + 1 pinned；HeadlessScreen 80x24；
   Painter flush 两次，断言第二次 output 零增长、`len(painter.rows()) == 24`、scroll_up(5) 后
   `rows()[0].text` 变化。贴输出。
3. `git diff --stat main..HEAD` 证明写入范围仅在
   `src/mocode_tui/{screen,viewport,painter,__init__}.py` + `tests/test_{screen,viewport,painter}.py`。

## 禁触清单

- `block.py` `style.py` `text.py` `lines.py` `ansi.py`（W1 产物，只读；发现 bug 写报告，不越界改）、
  `keys.py` `app.py` `testing.py` `components/**` `layout.py`、`examples/**`、`docs/**`、
  `README.md`、`pyproject.toml`、`specs/**`。
- 不 merge / 不 push / 不 checkout main / 不碰其他 worktree；不改任何 spec。

## 诚实出口

- 若 `\x1b[2J` 全清与某些终端 alt-screen 首次绘制行为有冲突的担忧：以「首帧必发 `\x1b[2J`」定格
  （无害且确定），不发明条件分支；真机风险写报告。
- 若发现 W1 产物 bug：**不改**，在报告「未决问题」中精确记录（文件:行 + 现象 + 建议），
  由 lead 裁决是否开后续工单。

## 最终报告格式

同 W1：工单状态表（commit hash+message）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
