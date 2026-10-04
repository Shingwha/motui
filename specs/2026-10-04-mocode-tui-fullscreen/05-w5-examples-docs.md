# Spec W5 · 示例与文档（波次 W5）
> 分支 `wfs5-examples-docs`；前置：**W4 已合并**（从合并时刻最新 main 切出）；深读：`00-overview.md` + `01`~`04`

## 目标

交付可用性证明：两个 example（全屏 chat demo + 组件 showcase）与全套文档
（README / docs/DESIGN.md / docs/COMPONENTS.md），并跑整组终验。
最高约束：example 只用公共面（`import mocode_tui`）；非 TTY 下两 example 都必须 exit 0
（自动走 HeadlessScreen + ScriptedKeys，`run()` 的非 live dump 即其输出）。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `examples/chat_demo.py` — 全屏聊天 demo
- 交互版（TTY）：TUI() + run(chat)：transcript 走视口滚动；底部 pinned 输入框（Input）+ pinned 状态栏
  （StatusBar，显示模式/滚动状态）；流式回答（Text 块逐词追加 + invalidate）、工具块
  （Spinner open → Text 定稿 + seal）、选择菜单（Select，/menu 唤出）、粘贴、Ctrl-C 退出。
- 无头版（非 TTY 或 stdin 非 TTY）：同一 chat 函数 + ScriptedKeys 脚本（含 /menu、翻页键演示），
  `run()` 的 dump 即输出；`main()` 里判断 isatty 分流，其余代码共用。
- demo 中演示 page_up/page_down（驱动已拦截，demo 只需在状态栏体现 at_bottom 变化——
  用 `tui.painter` 的只读状态或轮询 rows；不得新增驱动 API）。
- 验收命令：`python examples/chat_demo.py < /dev/null; echo exit=$?` → exit 0 且输出含最终屏文本。

### T2 `examples/showcase.py` — 组件无头展示
- 每个组件渲染帧（Text/Markdown/Input（填示例文本）/Select/Confirm/Spinner（advance 数次）/
  StatusBar/Notice 三级/Divider/Panel/Row/Column 嵌套）进同一个 TUI（非 live），
  走 `run()` dump 输出全部组件。exit 0。

### T3 `README.md`
- 定位段：full-screen block-document TUI toolkit（alt screen、viewport、pinned regions），
  运行时依赖仅 wcwidth；对比一句「不是 inline 工具」。
- Quickstart：30 行内可跑的带输入框全屏示例（照抄可运行）。
- 组件表（本组交付的 11 个 + Row/Column）。
- 文档与 demo 链接；非 TTY 行为说明一句。

### T4 `docs/DESIGN.md`
- 屏幕模型：alt screen 进出（enter/leave 序列）、光标策略（隐藏、输入自绘光标）、VT 探测与降级。
- 文档与块：有序块、id 寻址、open→sealed（缓存承诺）、**无 committed**（全屏下无终端历史；
  溢出内容在视口上沿之外仍在内存，可 pgup 回看）。
- 视口：offset/贴底/滚动夹取、「more below」指示行、pinned 固定尾区与 vh 计算。
- 画家：逐行 diff 协议（`\x1b[{r};1H\x1b[K`+行）、首帧 `\x1b[2J`、无变化零字节、resize 全清重画。
- 驱动：run 生命周期、pump/throttle/every、page 键拦截与 `tui.keys` 逃生口、print=系统块。
- 键盘：KeyDecoder 覆盖集与「完整序列一 feed」假设、POSIX raw / Windows console record 三路径。
- 非 TTY 契约：运行期静默 + 退出 dump 最终屏；`read_key()` 返 None；demo piped 即 smoke test。
- 与 mocode 的关系：独立包，集成是另一方的事。

### T5 `docs/COMPONENTS.md`
- 保留组件协议说明与 ProgressBar 完整示例（Protocol 段落按本实现校准措辞：
  宽度 = screen.width；sealed 只影响缓存不影响可重画性；删除任何 inline/committed 表述）。
- 每组件一行能力表 + 「自定义组件 = 有状态的 render」章节。

### T6 终验（lead 合并后执行；agent 在分支上先自跑一遍并贴输出）
- `uv run pytest` 全绿；`python examples/chat_demo.py < /dev/null`、`python examples/showcase.py`
  均 exit 0；`python -c "import mocode_tui"` 冒烟；统计用例总数（目标 ≥ 220）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest`：`N passed`，0 失败（贴尾部原文；N ≥ W4 的数）。
2. 两个 example piped 实跑退出码与输出尾部（各贴 10 行）。
3. `git diff --stat main..HEAD` 证明写入范围仅
   `examples/**`、`README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`。
4. Markdown 文档行文中引用的每个 API 符号真实存在（`python -c` 逐个大写开头符号 import 验证，贴输出）。

## 禁触清单

- `src/**`、`tests/**`、`pyproject.toml`、`specs/**`。
- 不 merge / 不 push / 不 checkout main / 不碰其他 worktree；不改任何 spec。

## 诚实出口

- 真机 TTY 交互验收本环境做不了：chat_demo 的 TTY 分支只做**代码走查 + piped 同路径回归**，
  真机风险写进报告「未决问题」交 lead/user。
- 文档中如需引用未确证的终端行为（如某些终端 alt-screen 细节）：以 factual 描述本实现序列为准，
  不写「所有终端都…」式断言。

## 最终报告格式

同前波：工单状态表（commit hash+message）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
