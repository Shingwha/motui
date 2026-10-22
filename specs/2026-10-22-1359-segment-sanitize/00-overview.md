# Spec segment-sanitize · 内容通道的终端控制序列收口（单波 W1）
> 启动：2026-10-22 13:59（本地时间）；基线 main `19df592`（frame-perf 组已收尾）；分支 `ss-w1-segment-door`。

需求文档：`ref/security-checklist.md`（用户提供，权威）。lead 已逐条核验其代码事实并做行业
调研（Rich 实测不拦 ESC；cell-buffer 系全部结构性安全），讨论结论已由用户确认。

## 目标与非目标

**最高约束**：正常内容渲染字节零变化（golden 57 topics、render-hash
`a82f7968…` 逐字不变——净化只删"本来就 0 列"的字符与 tab→空格，宽度模型不变），
同时**注入序列从字节流中消失**（端到端断言）。

**做**：`Segment` 构造点成为内容/指令的唯一分界——`text` 与 `link` 净化为
"cells only"（C0 全集含 `\n`/`\r`、DEL、C1 删除；`\t` 按仓库既有规则归一为一个空格），
恢复 `ansi.py` 的 escape 独占宪法（"Every escape byte the toolkit emits is constructed
here"），修复"内容注入 `ESC[?1000l` 等关掉鼠标上报 / OSC 52 写剪贴板"一族的框架级缺陷。

**不做**（用户已拍板）：
- **不加 `raw=True` 逃生门**——安全门上不留口子；以后加字段向后兼容，删不行。
- **不做每帧重发鼠标模式**（掩盖症状 + 挡不住 OSC 52）。
- **不在 painter 层过滤**（`Line.text`/宽度/搜索/选区仍会看到控制符，治标）。
- **不做 `AnsiText`**（SGR→Style 解析组件）——正确方向但独立立项，不在本组。
- 不动输入侧（键盘解码）、不动版本号（并入 `[Unreleased]`）。

## 拍板决策（照抄执行）

| # | 决策 | 取值 |
|---|---|---|
| S1 | 收口位置 | `Segment.__post_init__`（frozen+slots，`object.__setattr__`）；`with_style()` 重建自动过门，幂等 |
| S2 | 净化集 | 显式集合：C0（0x00–0x1F，含 `\n`/`\r`，**不含 `\t`**）+ DEL（0x7F）+ C1（U+0080–U+009F，防御纵深）。**不用 `str.isprintable()`**（会把 ZWJ 等 Cf 判不可打印，摧毁 emoji 序列）；显式集对组合标记/肤色/ZWJ 零影响 |
| S3 | tab 处理 | **归一为一个空格**（与 `text.py:_normalize_tabs` 同规则同语义，TAB_WIDTH=1、宽度不变），**不是保留**——`Line.from_text` 直构 Segment 绕过 wrap 层归一的既有缺口一并关掉。安全文档 5.1 的"保留 \t"被 lead 推翻，理由：与仓库成文 tab 规则冲突（裸 tab 进终端按 8 列制表位展开 vs 宽度模型 1 列） |
| S4 | 快路径 | 编译正则（如 `re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")`）C 速扫描；干净文本零分配原串返回；`\t` 存在时先 `replace("\t", " ")`。热路径（选区/悬停每帧重建 Segment）必须跑 framebench 哨兵确认零回退 |
| S5 | link | 同门净化（link 进 OSC 8 字节；URL 正常字符不受影响，`\t` 归一与 C0 删除只会去掉 URL 里本就不合法的字符） |
| S6 | 行为变化的口径 | 唯一可见变化 = "内容里的控制字符/tab 不再原样到达终端"。`visible_width` 的 0 列规则不改（它是度量函数不是门）；净化变换宽度不变（0 列删除、tab 1 列→空格 1 列），布局零扰动 |
| S7 | 测试预算 | 新增 ≤ 4 条（含端到端注入断言），落既有文件；既有测试零修改 |
| S8 | 语言/commit | 注释英文，commit 英文一行祈使句；红线照 spec-team SKILL |

## 门禁（波次级，全绿才合并）

1. `uv run pytest -q`：909 + 新增 passed，0 failed；既有测试零修改。
2. `uv run python tools/golden.py --check`：57 topics match（**不重录**）。
3. `uv run python tools/framebench.py`（隔离跑）：`render-hash` 逐字
   `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`；
   `idle-long` / `text-open` 不回退（净化快路径的性能哨兵）；其余行漂移带内。
4. 端到端：安全文档 §2.2 的复现脚本改写为断言——`HeadlessScreen.output` 中不出现
   `\x1b[?1000l` / `\x1b]52` / `\x1b]0;`（除 ansi.py 合法序列）。

## 预检（worker 开工第一步）

- golden fixtures / 测试内容审计：是否存在经 `Line.from_text` 等直构路径进入 Segment 的
  裸 `\t` 或控制符（预期零命中——wrap 路径早已 `_normalize_tabs`；若有命中，字节会合法
  变化，如实上报 lead 再定，不自行重录 golden）。

## 仓库地图与契约

复用 frame-perf 组的 `specs/2026-10-22-0847-frame-perf/ref/repo-map.md`（已随 main 提交，
仍然有效；framebench 测量纪律同文：隔离跑，安静窗口判据 idle-long ≤ 0.7）。
本组新增契约（合并后回写 CHANGELOG，由 lead 收尾执行）：
**渲染文本永不产生终端控制序列；escape 只由 `ansi.py` 构造；`\t` 在 Segment 门归一为
一个空格（全路径与 `_normalize_tabs` 同义）。**

## Git / worktree 协议

照 spec-team SKILL：worktree `C:\Users\shifu\.worktrees\mocode-tui\ss-w1-segment-door`，
lead 统一创建销毁；分支自派工时刻 main 创建；不 push / 不 tag / 不发版。
