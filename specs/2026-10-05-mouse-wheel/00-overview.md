# Spec 组 · 鼠标滚轮滚动（2026-10-05）

> ✅ 2026-10-05 交付并合并：W16 `wfs16-mouse-wheel`，merge commit `a6cddcd`。
> 终验：716 passed / 2 skipped（基线 707 + 9 新增）；`examples/pi_demo.py < /dev/null` exit 0；51 符号导出面。
> 遗留：真机 TTY 滚轮验收（Windows Terminal / ConEmu / iTerm2 / tmux）待用户跑 `uv run python examples/pi_demo.py`。
> 本组是 2026-10-04 全屏 TUI 组的后续单项波（W16），修订旧组「明确不做」中的鼠标滚轮条目
> （先例：W11 真彩色修订旧「16 色封顶」）。Git / worktree 协议见 spec-team SKILL.md，本组不重复。

## 用户决策（2026-10-05，已拍板写死）

| # | 决策 | 选择 |
|---|---|---|
| D1 | 事件模型（用户明确要求为「未来组件可鼠标点击触发功能」深入考虑） | 新增 `MouseEvent`，**作为 `Key` 的冻结 dataclass 子类**（携 `button`/`x`/`y` 坐标）：不改 `KeySource.read()` 联合类型、不改 `ScriptedKeys`/`headless_tui`/宿主 `event.name` 分发；未来点击事件沿同一命名空间 + 坐标扩展，零重构 |
| D2 | 平台覆盖 | 字节路径单一实现（POSIX + Windows VT 输入 / Windows Terminal）；Windows console record 路径零改动；真机验收留用户，失败有写死的诚实出口（见「风险与诚实出口」） |
| D3 | 定制缝 | `TUI(mouse=True)` 总开关 + `tui.scroll_keys` 公开字典（键名 → 带符号行数，负数向上）；`TerminalScreen(mouse=)` 供自定义屏幕场景 |
| D4 | 执行形态 | 单 spec 组、单 worker、单分支串行（T1 内核 → T2 驱动 → T3 文档），lead 门禁合并 |
| D5 | 滚动条 | **本波不做**：拖拽滚动条依赖 1002 动态跟踪 + 命中测试（hit-test），属已后置的「组件点击」波地基；移动端/tmux 用户靠滚轮（tmux `mouse on` 时滚轮事件透传给开启跟踪的应用）+ 已有 pgup/pgdn（Termux 附加键行可发）滚动；登记为后续候选波 |

## 目标与范围

鼠标滚轮上下滚动**整个 TUI**：库层 `TUI.read_key()` 拦截滚轮事件并滚动视口，任何宿主
（含 `examples/pi_demo.py`）零改动即获得滚轮能力。范围 = 输入解码 + 追踪序列开关 + 驱动绑定 + 文档 + 测试。

非目标（本波明确不做）：滚动条/拖拽、组件鼠标点击与 `hit_test`、1002/1003 动态跟踪、
Windows `MOUSE_EVENT_RECORD` 原生建模（见诚实出口）、pgup/pgdn 之外的新键盘绑定、
任何渲染/布局路径改动。

## 架构设计（四层，全部落在既有缝上）

**L1 `ansi.py`**（转义单源）新增两个函数：

- `enable_mouse_tracking()` = `\x1b[?1000h\x1b[?1006h`——按键+滚轮上报，SGR 扩展坐标；
  不用 1002/1003（避免动态事件洪泛，也为将来拖拽波留出明确的升级位）
- `disable_mouse_tracking()` = `\x1b[?1006l\x1b[?1000l`——逆序收尾

**L2 `screen.py`** 追踪字节与 alt screen 同生命周期配对：

- `TerminalScreen(stream=None, *, mouse=True)`：`enter()` = alt + hide cursor + 开启追踪；
  `leave()` = 关闭追踪 + 显光标 + 离 alt；**仅 live**，非 live 仍零字节
- `HeadlessScreen`：enter/leave 镜像录制真实字节（保持「录制真实会话」语义）

**L3 `keys.py`** 解码器 `_emit_csi` 增加 `<` 私有参数分支（约 20 行）：

```python
# CSI < b ; x ; y M/m  (SGR 1006)
b, x, y = map(int, params[1:].split(";"))            # 畸形 → 照旧丢弃
if b & 0x40 and (b & 0x03) in (0, 1):                # 竖向滚轮；横轮(低2位2/3)显式丢弃
    events.append(MouseEvent("wheel_up" if (b & 0x03) == 0 else "wheel_down",
                             button=b & 0x03, x=x, y=y))
# 修饰位(4/8/16)掩掉，与 Key 模型「无修饰符」一致
# 其余（按键/释放/移动）维持丢弃——这正是未来点击事件的扩展缝
```

- `MouseEvent(Key)`：`name` 路由（`"wheel_up"`/`"wheel_down"`）、`button`（报告低 2 位）、
  `x`/`y`（1-based 报告坐标；未来 hit-test 减 1 索引 `Painter.rows()`）；docstring 注明
  「坐标为未来组件命中测试而留，滚轮忽略」
- Windows 零改动：VT 输入下鼠标报告即以 KEY_EVENT 字节到达，走同一解码；
  `windows_input_mode` 不动

**L4 `app.py`** 把 read_key 的两个硬编码 if 泛化成表（比现状更简单且可定制）：

```python
_DEFAULT_SCROLL_KEYS = {"page_up": -1, "page_down": 1, "wheel_up": -3, "wheel_down": 3}
# read_key: rows = self.scroll_keys.get(event.name)
#           rows < 0 → scroll_up(-rows)，否则 scroll_down(rows)
TUI(..., mouse: bool = True)   # 转发给默认 TerminalScreen；自定义 screen 自带设置
```

- 每格默认 3 行（vim/less 惯例），运行时可改：`tui.scroll_keys["wheel_down"] = 5`；
  收回绑定宿主自收事件：`del tui.scroll_keys["wheel_up"]`
- page_up/page_down 逐行滚动语义不变

**L5 `__init__.py`**：仅新增 `MouseEvent` 一个导出。

**L6 文档**：README 特性清单/driver 小节/「Not on purpose」删鼠标条；DESIGN.md screen 配对、
Keys 段（MouseEvent + SGR）、driver 段（scroll_keys）、out-of-scope 修订说明。

## 未来扩展为什么不用重构（模型验证）

| 后续波 | 落点 | 是否动今天的设计 |
|---|---|---|
| 组件鼠标点击触发 | 解码器同分支加 `press/release` 类（数行）+ `TUI.hit_test(x, y) -> Block` + 宿主按 `name`+坐标分发 | 否 |
| 拖拽/滚动条 | 开 1002 动态跟踪 + 解码 move + 滚动条组件 + `scroll_keys` 接管 | 否 |
| 自定义鼠标语义 | 换 `keys` 源（KeySource 协议）或改 `scroll_keys`/`mouse=False` | 否 |

`MouseEvent` 携坐标 + 解码器完整解析 SGR（今天只路由滚轮类）= 缝已留实，无 speculative API。

## 全局不变量

引用 2026-10-04 组 7 条（组件协议恒定；仅依赖 wcwidth；painter 独写 sink + enter/leave 成对；
逐行 diff 零字节；rows() 恰 height 行；非 live 静默+dump；wcwidth 唯一宽真源）。本波新增：

8. 鼠标追踪字节仅在 live 会话的 enter/leave 成对出现；非 live 零字节。
9. 非滚轮鼠标报告（按键/释放/横轮/畸形）继续被 `KeyDecoder` 丢弃——是未来点击事件的扩展缝，本波不打开。
10. 公开导出面本波仅新增 `MouseEvent`；`KeySource.read()` 联合类型不改。
11. Windows VT 输入路径零改动（`windows_input_mode` 不变，`ENABLE_MOUSE_INPUT` 位保持既有语义）。

## 回归红线

- 每个 commit 独立 `uv run pytest` 全绿；合并前后各跑一次全量门禁贴真实输出。
- 用例总数只增不减（基线见合并记录；W16 新增 7 个、改 3 个）。
- 既有两条反向断言保持有效：`tests/test_keys.py`（点击报告被丢弃）、
  `tests/test_keys_windows.py`（`ENABLE_MOUSE_INPUT untouched`）——它们是行为兼容的证据。
- 被改断言必须按 W7 纪律替换为同强度新语义用例（替换而非弱化）。
- `python examples/pi_demo.py < /dev/null` exit 0；`python -c "import mocode_tui"` 冒烟。
- commit 英文，风格 `feat:` / `fix:` / `refactor:` / `docs:` / `test:`；注释与文档同英文。

## 测试计划（减量、禁脆弱冗余）

新增 7：`test_keys.py` +滚轮解码参数化（M/m、修饰位、坐标回填、横轮/畸形/点击丢弃）+
跨 feed 拼接 1；`test_ansi.py` +开关序列精确形状 1；`test_screen.py` +live 配对含鼠标字节 1、
+`mouse=False` 省略 1；`test_app.py` +read_key 拦截滚轮并滚动 1、+`scroll_keys` 定制 1。
修改 3：`test_screen.py` 三处 enter/leave 字节精确断言改为含鼠标字节的完整配对。
无 golden、无裸 sleep、无 TTY 依赖。

## 风险与诚实出口

1. Windows conhost/快速编辑模式下鼠标报告可能被吞（本环境无 TTY 不可验）：真机验收若不过，
   下一波补 `MOUSE_EVENT_RECORD` 原生记录建模（约 40 行 ctypes），字节路径不变。
2. 终端不支持 1000/1006：静默无滚轮，pgup/pgdn 兜底，行为不劣化。
3. 真机 TTY 交互验收（滚轮在 Windows Terminal / ConEmu / iTerm2 / tmux 的实际手感）
   由用户本机跑 `uv run python examples/pi_demo.py` 完成，不占本波。

## 环境事实（lead 校准，2026-10-05）

- Windows 10/11 + Git Bash；Python via uv；`.venv` 已 `uv sync`。
- **本验证环境无 TTY**：验收面 = pytest + piped/dump 路径 + import 冒烟。
- worktree 根：`C:/Users/shifu/.worktrees/mocode-tui/<分支>`（lead 统一创建销毁）。
- 路径全英文；不假设字体。

## 波次表（串行）

| 波 | 工单 | 内容 | 分支 | 前置 |
|---|---|---|---|---|
| W16 | 01 | 鼠标滚轮滚动：ansi/screen/解码 + 驱动 scroll_keys + 文档 + 测试 | `wfs16-mouse-wheel` | 无（从 main HEAD，含本 spec） |

## 收尾

- lead 终验（全门禁 + piped 冒烟 + import 冒烟）→ 各工单头部补状态行 → 汇总报告。
- **不 push、不发版、不打 tag**——等用户指令。清理 worktree，保留分支。
