# Spec W7 · Windows 输入修复（波次 W7，修复单）
> ✅ 2026-10-04 已交付合并；修复后 605 passed + 2 skipped（POSIX-only 端到端用例）。
> 分支 `wfs7-windows-input`；前置：无（从合并时刻最新 main 切出）；深读：`00-overview.md` + `04-w4-driver.md`

## 背景（用户真机实测，2026-10-04）

用户在 PowerShell + Windows Terminal 跑 `examples/pi_demo.py`：
**PageUp/PageDown 不滚动、Backspace 不删字、Enter 不提交**；截图显示输入框里出现
`[A[A[B[B` 字面量。根因（lead 已定性，铁证）：

1. `windows_input_mode` 置了 `ENABLE_VIRTUAL_TERMINAL_INPUT`——该位语义是
   **控制台把输入以 VT 字节流交付**：`ReadConsoleInputW` 返回的是逐字节的 KEY_EVENT
   record（`UnicodeChar` = 单个字节，VK=0），而不是 VK 编码的按键 record。
2. 而 `_read_console_records` 走 `_key_from_console_event`（VK 码映射表）：
   - `\x1b`（0x1B < ' '）→ 丢弃 → `\x1b[A` 被降级成插入字面 `[`、`A`（截图实况）；
   - `\r`（Enter）→ 丢弃 → **不提交**；
   - `\x7f`（Backspace）→ 显式排除 → **不删字**；
   - `\x1b[5~`（PageUp）→ ESC 丢 + 字面 `[5~` → **不滚动**。
3. 另外 W5 时代 abandoned 尝试的「VT 序列跨 read 拆分」问题在本路径**必然发生**
   （每个 record 只有 1 字节，`\x1b` 与 `[A` 是两次 feed），但现 decoder 在 feed 末尾
   就把遗留 escape 判成孤立 escape 键——必须修。

## 目标

让 Windows 控制台路径在全屏真实终端里可用：**record 的 VT 字节喂给 `KeyDecoder`**，
decoder 支持跨 feed 组装序列 + 静默期 settle；POSIX 字节路径同样获得 settle。
最高约束：ScriptedKeys/cooked 回退/piped 路径行为零变化；全部现有测试语义只准增强不准削弱。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `KeyDecoder` 跨 feed 状态（keys.py）
- `feed()`：**不再**在 feed 末尾解决 pending escape/CSI 状态——状态跨 feed 保留
  （下一 feed 的字节继续拼序列）。paste 状态语义不变（跨任意 chunk 聚合）。
- 新增 `pending() -> bool`：state ∈ escape/csi 时为真（paste 永不为 pending）。
- 新增 `settle() -> list[Key|Paste]`：静默期裁决——pending 裸 escape → `Key("escape")`；
  pending CSI → `Key("escape")` + 已收集参数按 ground 字节重读（保持现降级语义）；
  paste 状态不动。
- `flush()` = `settle()` + 未闭合 paste 原文交付（EOF 语义不变）。
- docstring 重写「完整序列一 feed 到达」旧假设：改为「字节流任意分片，跨 feed 组装；
  孤立 escape 由调用方静默期 settle 裁决」。
- 更新 `tests/test_keys.py`：旧「feed 末尾遗留 escape 即孤立 escape」断言改为新语义；
  新增：跨 feed 组装（`feed(b"\x1b")` + `feed(b"[A")` → `[Key("up")]`）；
  settle 两条路径；`flush()` EOF 收尾；pending() 时序。语义变化处注释说明理由。

### T2 控制台 record → 字节流喂 decoder（keys.py `_read_console_records`）
- 每个 KEY_EVENT record（只要 `bKeyDown`；key-up 跳过）：
  - `ch = UnicodeChar`；`ch != '\x00'` → `self._decoder.feed(ch.encode("utf-8"))`（**主路径**，
    覆盖 VT 字节语义：ESC/CR/BS/可打印/多字节 UTF-8 全走 decoder）；
  - `ch == '\x00'` 且 VK 在 `_VK_NAMES` → 直接入队对应 Key（**兜底**：另一种控制台语义下
    方向键等以 VK record 交付且无字符时仍可用）；
  - Ctrl+字母 VK 且 `ch == '\x00'` → `c-a..c-z` 兜底。
- 抽出**纯函数**供单测：`keys_from_console_events(events) -> list[Key|Paste]`
  （或等价形态），输入为 `(bKeyDown, vk, char, ctrl)` 元组序列，内部逻辑与 reader 共用；
  让测试在无真机环境下覆盖两种语义（字节流语义全路径；VK 兜底路径）。
- `tests/test_keys_windows.py` 扩充：字节流语义（ESC[ A → up；\r → enter；\x7f → backspace；
  ESC[5~ → page_up；`你` 多字节原样）；VK 兜底（char='\x00' + VK_LEFT → left）；
  保留现有 `windows_input_mode` 与结构体尺寸断言。

### T3 控制台 reader 的静默 settle（keys.py）
- `_read_console_records` 改为 **PeekConsoleInputW 轮询**（不能阻塞在 ReadConsoleInputW 上，
  否则孤立 ESC 永远 pending）：
  - 有记录 → `ReadConsoleInputW` 批量读（数组 32）→ 逐个喂字节/兜底入队；
  - 无记录且 `decoder.pending()` 且静默 ≥ 50ms（单调时钟）→ `settle()` 入队；
  - 无记录无事 → `sleep(0.005)`；循环检查 `_closed` 保证 close 即时。
- EOF/close 语义不变（`_reader` 的 finally 投 None sentinel）。

### T4 POSIX/字节路径 settle（keys.py `_read_bytes`）
- `decoder.pending()` 时用 `select.select([fd], [], [], 剩余静默时间)` 替代无限阻塞读：
  - 可读 → `os.read` 喂 decoder；
  - 超时且静默 ≥ 50ms → `settle()` 入队。
- cooked 回退（管道行）不受影响：行到达时整条 feed，pending 由 settle/close 兜底。

### T5 `windows_input_mode` docstring + 门禁
- docstring 改写：阐明 VT input 位是「字节流交付」语义（本文件依赖该语义）；
  函数体不变（LINE/ECHO 清除、VT 位置位、PROCESSED 透传）。
- 全量 `uv run pytest` 绿（贴尾部输出，N ≥ 585 或因语义修订持平）；piped demo 仍 exit 0。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest` → 全绿（贴尾部原文；T1 的语义修订允许总数持平或微降，但
   **每个被改断言必须有替代新语义用例**，覆盖率只增不减）。
2. `python examples/pi_demo.py < /dev/null; echo exit=$?` → exit 0。
3. 冒烟：用 T2 纯函数模拟「用户截图那一串输入」（ESC[A ESC[A ESC[B ESC[B ESC[B + `你好` +
   ESC[A … + 退格 + ESC[5~）→ 断言 up/up/down/… + chars + page_up 齐全、无 `[`/`A` 字面量。
   贴输出。
4. `git diff --stat main..HEAD`：写入范围仅 `src/mocode_tui/keys.py`、`tests/test_keys.py`、
   `tests/test_keys_windows.py`。

## 禁触清单

- 其余一切 src/tests/docs/examples/README/pyproject/specs；不 merge/push/checkout main；
  不碰其他 worktree；不改任何 spec。

## 诚实出口

- `PeekConsoleInputW` 若签名/可用性与预期不符：以等价轮询手段达成「非阻塞探测 + 批量读」，
   在报告登记实际签名与处理；不得回到全阻塞读（那会失去 settle 能力）。
- 若发现控制台字节语义与 VK 语义在某环境混存（同一 record 同时带 VK 与 char）：
   规则已定——**char 优先喂字节，char 为 NUL 才走 VK 兜底**；不许双重入队。

## 最终报告格式

工单状态表（T1..T5：commit hash + message + 结论）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
