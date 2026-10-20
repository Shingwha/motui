# W1 · 事件模型与终端解码
> 分支 `w1-events`；前置：W0 已合并；写入范围见下。深读：`00-overview.md` D2/D3/D4、`ref/interfaces.md` §1。

## 目标

把 `Key`/`Paste`/`MouseEvent` 的旧模型换成 `Event` 基类 + 五个值类型，补齐终端解码覆盖和 source
生命周期；**除事件模型与解码外，行为零变化**。渲染字节必须不变，golden 不得移动。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §1 → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1699 passed / 1 skipped；11 页 match；render-hash `de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`。
- 稳定区（已验收，勿重读）：`src/motui/widgets/markdown/**`、`src/motui/demo/pages/**` 的渲染逻辑。
- 已知约束：Windows console 与 POSIX 必须同时通过；库与测试不 sleep；不引入兼容 shim。

## 工单（按序执行，每项一个 commit）

### T1 `kernel/events.py`：新事件模型 + 来源协议

- 定义 `Event` 基类（无字段）和冻结 dataclass：
  `KeyEvent(key, char="", modifiers=frozenset(), kind="press")`、
  `MouseEvent(button="none", x=0, y=0, kind="press", modifiers=frozenset())`、
  `PasteEvent(text)`、`ResizeEvent(width, height)`、`FocusEvent(focused)`。
- `MouseEvent`/`PasteEvent`/`ResizeEvent`/`FocusEvent` **不得**继承 `KeyEvent`。
- `KeySource` 改名 `EventSource`，`read() -> Event | None`。
- `ScriptedKeys` 改名 `ScriptedEvents` 并移到 `src/motui/testing.py`；`headless_tui` 改用它；
  `tests/_doubles.py` 如仍需自定义 source，改成 `EventSource`。
- 更新 `kernel/__init__.py`：导出 `Event`, `KeyEvent`, `MouseEvent`, `PasteEvent`, `ResizeEvent`,
  `FocusEvent`, `EventSource`；删除 `Key`/`Paste`/`KeySource`；`ScriptedKeys` 从 kernel facade 移除，
  `ScriptedEvents` 从 `motui.testing` 导出。
- `src/motui/__init__.py`：根事件三件套改为 `KeyEvent`/`MouseEvent`/`PasteEvent`，保持 34 名。
- `tests/test_api_root.py` 同步 pin。
- 验证：`uv run pytest -q tests/test_api_root.py tests/test_events.py -p no:cacheprovider`（新文件见 T5）。

### T2 `keys/decoder.py`：解码器重写

按 `ref/interfaces.md` §1.2–§1.5 实现：

- 输出 `KeyEvent`/`MouseEvent`/`PasteEvent`/`ResizeEvent`/`FocusEvent`。
- `\r` → `enter`；`\n` → `c-j`（修 `EDITOR_SUBMIT_KEYMAP` 的可达性）。
- CSI 字母 A/B/C/D/H/F、Z→`s-tab`、P/Q/R/S→`f1`..`f4`。
- CSI `~`：home/insert/delete/end/page_up/page_down/f1..f12。
- SS3：`ESC O A/B/C/D/H/F/P/Q/R/S`。
- 修饰符参数 `1;m` 与 `n;m`；m=2..8 解析 `s-`/`a-`/`c-`，顺序 `c-a-s-`。
- kitty `CSI codepoint;mods u`、`CSI codepoint;mods:event u`、modifyOtherKeys `CSI 27;mod;code~`。
- bracketed paste（跨 chunk）；`finish()` 吐出未完成 paste/UTF-8。
- focus `CSI I/O`；resize `CSI 8;rows;cols t`。
- 鼠标：SGR 1006、X10 `ESC [ M`、urxvt 1015；`button` 字符串、`kind` press/release/motion/wheel、
  `modifiers`；坐标 0-based；水平 wheel 解析为 `wheel_left/right`。
- `feed` 只接受 bytes（非 bytes 抛 TypeError）；其他输入不得崩。
- 保持 `pending()`/`settle()`/`finish()` 的现有调用约定。

只允许改 `src/motui/keys/decoder.py`；新增测试放 T5。

### T3 `keys/sources.py` + `keys/console.py`：来源生命周期

- `RawTerminalKeys` 实现 `EventSource`；`read()` 返回 `Event | None`。
- EOF 后重复 `read()` 返回 `None`，不得挂起；reader 在 EOF 调用 `decoder.finish()`。
- `start()` 可在 `close()` 后再次调用；每次 start 重置 EOF/decoder/队列状态。
- `close()` 尽力解除阻塞中的 `read()`：POSIX self-pipe（`select` 同时等 stdin 与 pipe）；
  Windows 用轮询标志 + 短间隔。
- Windows console 保留 `wRepeatCount`：重复次数产生多个 `KeyEvent(kind="repeat")`。
- Windows 的 focus/resize records 产生 `FocusEvent`/`ResizeEvent`（不再跳过）。
- `keys_from_console_events` 返回新事件类型。
- 只允许改 `src/motui/keys/{sources,console}.py`；新增测试放 T5。

### T4 调用点迁移（机械但全覆盖）

把全仓对旧事件模型的依赖迁到新模型：

- `src/motui/app.py`：`read_key` → `read_event`；`event.name` → `event.key`（仅 KeyEvent）；
  `isinstance(event, MouseEvent)` 不再被 KeyEvent 命中；`_BUTTONS`/`focus_policy`/`scroll_keys` 用新字段。
  **不要**在本波改 `stop`/`run`/坐标/作用域（W2 的）。
- `src/motui/interaction/**`：KeyEvent 读 `.key`；MouseEvent 读 `.button`/`.kind`；
  `event.name == "left"` → `event.button == "left"`；`_DRAG_NAMES` 用 button 名；wheel 用 `.kind == "wheel"`。
- `src/motui/widgets/**`：`List.handle`、`Dialog.handle`、`ComboBox.handle`、`TextBuffer.handle`、
  `keymap` 查找全部用 `.key`；`MouseEvent` 的 early-return 顺序不要丢。
- `src/motui/demo/**`：脚本事件构造、`event.name`、`Key`/`Paste`/`MouseEvent` import。
- `src/motui/testing.py`、`tests/**`：所有构造/断言/import。
- `docs/`：README/DESIGN/COMPONENTS 中事件 API 示例与键名说明同步；不重写整篇文档。

验证：`uv run pytest -q -p no:cacheprovider`；预期仍 1699+ 通过。若某个测试必须改期望，逐条在报告列
文件:行、旧期望、新期望、理由。

### T5 新测试（契约矩阵）

新增/扩展：

- `tests/test_events.py`：值语义、frozen/hash、`MouseEvent` 不是 `KeyEvent`、`EventSource` 协议。
- `tests/test_keys.py`：SS3、F1–F12、shift-tab、insert、修饰符矩阵、kitty、modifyOtherKeys、
  `\n`→`c-j`、跨 chunk paste、finish。
- `tests/test_keys_sources.py`：EOF 重复读、重启、finish、close 解除阻塞（POSIX 可 skip）、
  Windows repeat records（纯函数单测）。
- `tests/test_decoder_fuzz.py`：更新为新事件类型；保持“不崩、不丢字节”的断言。
- `tests/test_app.py` / interaction 测试：事件构造与 `.key`/`.button` 断言迁移。

### T6 文档与 API 面

- `src/motui/__init__.py` 的 docstring：事件三件套名字。
- `kernel/__init__.py` 的 docstring/`__all__`。
- `keys/__init__.py`：`KeyDecoder`/`RawTerminalKeys`/`Keymap` 不变；如有 `KeySource` 提及则改。
- `docs/DESIGN.md` 的 naming charter（Key event names、`read_event`）与 `docs/COMPONENTS.md` 的 dispatch 表。
- `README.md` 的 quickstart/例子：`Key`→`KeyEvent`、`key.name`→`key.key`、`read_key`→`read_event`。
- 在 `docs/CONTRACT.md` 已有规范，不重复写。

### T7 全量门禁 + handoff

- 跑 `## 验收` 全部命令，贴真实输出。
- 最后一个 commit 写 `specs/2026-10-20-1819-motui-1-2-contract/handoff/W1-events.md`，按 Handoff 协议
  A/B/C 三节。
- 不 merge / push / tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1699（新增事件测试）
2. `uv run python tools/golden.py --check`：11 页全 match（事件改动不应移动渲染）
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`：exit 0
5. `uv run python -m motui --pages`：exit 0
6. `grep -rn "event\.name\|isinstance(event, Key)\|from .* import .*\\bKey\\b" src/motui`：
   零命中（MouseEvent 内部字段/文档历史除外）
7. `uv run python -c "from motui.kernel import Event, KeyEvent, MouseEvent, PasteEvent, ResizeEvent, FocusEvent, EventSource"`：
   exit 0
8. `uv run python -c "from motui import TUI; assert hasattr(TUI, 'read_event')"`：exit 0
9. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`pyproject.toml`、`uv.lock`、`specs/**`（handoff 除外）、`docs/CONTRACT.md`、`tests/golden/**`
  （本波不应移动 golden）、`src/motui/kernel/frame.py` 的几何/所有权逻辑、`TUI.stop/run/split/hit_test`
  的语义、组件渲染逻辑、`Theme`/`Style` 值语义（W3）。
- 禁加：兼容 alias、`_deprecated` 转发、旧名字 re-export。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W1-events.md`（60–80 行）：

- A：`git diff --stat`、新增/变更公开签名、基线命令真实结果
- B：与 spec 的偏差、踩坑、下一波必须遵守的隐含约束、未决问题
- C：关键文件:行号、commit、稳定区

## 最终报告

工单状态表（T1–T7）/ commit 清单（hash + message）/ 自测真实输出（pytest 总数、golden、framebench
hash、两条 demo）/ 事件 API 变更清单 / 测试改动清单（文件:行、旧→新、理由）/
偏差与取舍 / 交接校验 / 探索审计（handoff 外读了哪些文件、为什么）/ 未决问题。
