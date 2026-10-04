# Spec W6 · pi 式 demo 与文档（波次 W6）
> ✅ 2026-10-04 已交付合并；终验 585 passed（main）。分支见 git log --merges。
> 分支 `wfs6-pi-demo-docs`；前置：**W5 已合并**（从合并时刻最新 main 切出）；深读：`00-overview.md` + `05`

## 目标

用 W5 新组件做一个「pi 式全屏编码助手」demo：视口 transcript + 固定尾区（输入框 + 双侧状态栏），
交互路径 TTY 真跑、非 TTY 走 ScriptedKeys 同函数体 + 假调用（流式回复、假 bash 工具块、表格、diff），
并补齐 README / docs/DESIGN.md / docs/COMPONENTS.md。风格要求：**简洁高效**——信息密度高、装饰少、
一屏说清状态。最高约束：example 只用 `import mocode_tui` 根符号；不改任何 src/tests。

## 界面定格（对齐用户给的 pi 截图）

整体三段：**视口 transcript（滚）+ 固定输入区 + 固定状态栏**。

1. **启动区**（视口首批块）：头部行（`π` 字符亮色 + 版本 + 一组 dim 快捷键提示，一行排不下就两行）；
   dim 介绍段；`[Skills]` 段（黄色粗体标题 + dim 列表）；黄色 Divider + 「Update Available」通知
   （黄粗体标题 + 白正文 + 洋红链接）+ Divider。
2. **对话区**：user 消息 = `Message("user", …)` 色带；assistant thinking = `Message("thinking", …)`；
   assistant 正文 = `Message("assistant", …)`（支持粗体小节标题，用 Text/Segment 组合或 Markdown 子集）；
   工具调用 = `ToolBlock("$ echo …", [...], tone="tool", footer="Took 0.1s")`；
   codemode = `ToolBlock("codemode", [...], tone="code")`；edit = `EditBlock(path, context=[…], removed=[…], added=[…])`；
   汇总 = `Table(["tool", "result"], [[("write", …), "✓ 创建 …"], …])`；
   节与节之间空行分隔，`⋮ Working`（dim）+ Divider 表示工作进行中。
3. **固定尾区**（pinned）：上 Divider（蓝色系输入框顶边框）→ `Input`（占位符即 user 消息样式）→
   状态栏一行（左：`19.9k ↓1.4k R32k CH98.0% $0.003 1.0%/1.0M (auto)` 式 dim 文本；
   右：`(commandcode) deepseek/deepseek-v4.1-flash-fast • medium` 式 dim 文本；手工计算中间空格右对齐，
   **不新增组件**）。
4. **交互**：输入回车 → 追加 user Message → 0.4s 后追加 thinking Message → 逐词流式 assistant 回复
   → 0.6s 后 `⋮ Working` + Divider → 假 bash ToolBlock（含假输出与计时）→ Table 汇总 → EditBlock。
   `/menu` 唤出 slash 菜单（`Select`，title="/ commands"，选项 hint 给描述；↑↓ 选择、Enter 关闭）。
   `Ctrl-C` 退出。page_up/page_down 已被驱动拦截（demo 不用碰）。
5. **非 TTY**：`main()` 分流：interactive `TUI().run(chat)`；否则 headless TUI + `ScriptedKeys`
   （脚本含两条提问 + /menu + c-c），同一个 `chat` 函数体；run() 的 dump 即输出。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `examples/pi_demo.py` — demo 主体
- 上述界面定格全部落地；假调用用 `asyncio.sleep` 做时间感（**只在 example 里允许 sleep**，
  库与测试仍零 sleep）；流式逐词 `invalidate()`。
- 输入区/状态栏的 pinned 组装；`print()` 不用（demo 全走块）。
### T2 文档 `README.md` + `docs/DESIGN.md` + `docs/COMPONENTS.md`
- README：定位（full-screen block-document TUI toolkit：alt screen / viewport 滚动 / pinned 尾区；
  运行时依赖仅 wcwidth）；30 行内 quickstart；组件表（补 Message/ToolBlock/EditBlock/Table 四块）；
  链接 `examples/pi_demo.py`（piped 即 smoke test：`python examples/pi_demo.py < /dev/null`）。
- DESIGN：屏幕模型（alt 进出序列、光标策略、VT 探测降级）；文档与块（id 寻址、open→sealed、
  无 committed、溢出内容 pgup 可回看）；视口（offset/贴底/夹取/more-below 指示/pinned 与 vh）；
  画家（逐行 diff、首帧 `\x1b[2J`、无变化零字节、resize 全清）；驱动（run 生命周期、pump/throttle/
  every、page 键拦截与 `tui.keys` 逃生口、print=系统块）；键盘（覆盖集与「完整序列一 feed」假设、
  POSIX raw/Windows console record/cooked 三路径）；非 TTY 契约（运行期静默+退出 dump、read_key 返 None）。
- COMPONENTS：协议说明（宽度 = screen.width；sealed 只影响缓存；无 inline/committed 表述）+
  ProgressBar 完整示例 + 每组件能力表（含 4 新组件）+ 自定义组件章节。
### T3 终验自跑
- 全量 pytest；`python examples/pi_demo.py < /dev/null; echo exit=$?` exit 0 且输出含 demo 各区块文本；
  `uv run python -c "import mocode_tui"`；README/文档引用的每个公共符号逐个 import 验证（贴命令输出）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest` → `N passed`（N ≥ W5 合并后数），0 失败（贴尾部原文）。
2. `python examples/pi_demo.py < /dev/null; echo exit=$?` → exit 0（贴输出前 20 行 + 后 10 行）。
3. `git diff --stat main..HEAD`：写入范围仅 `examples/pi_demo.py`、`README.md`、`docs/DESIGN.md`、`docs/COMPONENTS.md`。
4. 文档 API 符号逐个 import 验证输出。

## 禁触清单

- `src/**`、`tests/**`、`pyproject.toml`、`specs/**`、其他 example 文件。
- 不 merge / 不 push / 不 checkout main / 不碰其他 worktree；不改任何 spec。

## 诚实出口

- 真机 TTY 交互验收本环境做不了：TTY 分支只做走查 + piped 同路径回归，真机风险写报告交 lead/user。
- 16 色拍不出截图精确暗色：沿用 W5 的最近命名色，不引入扩展色。
- `asyncio.sleep` 只许出现在 example 的假调用编排里；tests/src 零 sleep 是红线。

## 最终报告格式

同前波：工单状态表（T1..T3：commit hash + message + 结论）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
