# Spec base-components · W5b 无按键 motion 的 wire 解码（lead 授权修复波）
> 分支 `bc5b-motion`；前置：W5（已合并）。深读：`00-overview.md`（D2、harness 事实）、
> `02-w2-pointer-primitives.md`（`Pointer` 的 button 契约）、`pyproject` 无关。
> **本波是 lead 在合并复核时发现的前提错误修复：总纲「现状」第 1 条断言「decoder 已能把无按键 motion
> 解码出来」——经源码核实为**假**，导致 hover 在任何真机上都收不到 motion 报告（headless 单测直接喂
> `MouseEvent` 才过）。本波把这条 wire 缝补上，默认路径零行为变化。**

## 事实（已核实，不要再怀疑）

1. **SGR-1006 的 motion 报告 Cb = 32 | button | 修饰位（4/8/16）**；button 低位：`0` = 左、`1` = 中、
   `2` = 右、**`3` = 无按键**。所以 1003 下「指针只移动」的报文是 **35**（带修饰位为 39/43/51/63），
   1002 下按住左键拖动是 32。
2. **VT 路径现在把这些报文丢掉**：`keys/decoder.py` 的 `_BUTTON_NAMES = {0: "left", 1: "middle",
   2: "right"}`，`low == 3` → `name is None` → 事件被丢弃。`tests/test_keys.py` 只测了 32/34/38。
3. **console 记录路径也不会产生裸 motion**：`keys/console.py` 的 `_console_mouse_report` 只在
   `held`（有键按住）时合成 motion（`code + _SGR_MOTION`），无按键的 `MOUSE_MOVED` 记录被静默丢弃。
4. 因此真机（VT 或 console 记录路径）上 `Pointer` 永远收不到「无按键 motion」——hover 不可用。
   三处文档写了错误口径（「read 0 with none held」）：`docs/DESIGN.md:463-464`、
   `core/events.py:55-57`、`keys/decoder.py:60-61`。

## 设计定稿（lead 已拍板，不再反复）

- **归一化**：wire 的低位 3（无按键）→ 库内既有的「无按键 motion」表示
  `MouseEvent("none", button=0, kind="motion")`。
  - `name="none"`：0/1/2 的名字 left/middle/right 都指「按住的键」，裸移动不属于任何一个；
    全仓已有约定（`tests/test_pointer.py` 的 `motion()` helper 注释「button 0 = none」、
    `Pointer` 的 `button == 0 → hover` 分支）都以 `button=0` 表示无按键，故 `button` 归一化为 0，
    `Pointer`/`gesture` 的代码路径零改动。
  - `press`/`release` 里出现低位 3 是畸形报告（SGR 在 press/release 里必须指名按键）：**继续丢弃**。
  - wheel 分支（`b & 0x40`）不动。
- **console 桥**：`MOUSE_MOVED` 且无按键、无按下/释放过渡 → 合成 `_SGR_MOTION | 3`（= 35）报告；
  **由 `hover` 开关门控**（默认 `False` 零行为变化），与 D2 的「1003 只在 `TUI(hover=True)`」同源。
  console 记录路径没有 1002/1003 之分，`TUI(hover=...)` 就是它的等效开关。
- **默认路径零行为变化是硬约束**：不开 hover 时 decoder 不新增可见事件（1002 下真机根本不发 35）、
  console 桥输出与改前逐字节一致。

## 工单（按序执行，每项一个 commit）

### T1 `keys/decoder.py`：低位 3 的 motion 归一化

- 在 `_parse_mouse`（`if motion and b & _MOTION_BIT:` 之后）加分支：`low == 3` 且 `kind == "motion"`
  → `MouseEvent("none", button=0, x=x, y=y, kind=kind)`；否则（press/release 的畸形 3）照旧丢弃。
- 更新 `_REPORT_CLASSES` 注释与 `_BUTTON_NAMES` 一带的注释：写清 wire 事实（低位 3 = 无按键，
  motion 的 35/39/43/51/63）与「decoder 把无按键 motion 归一化为 button 0、名字 none」。
- 测试（`tests/test_keys.py`，追加）：
  - `feed(b"\x1b[<35;2;5M")` → `[MouseEvent("none", button=0, x=1, y=4, kind="motion")]`；
  - `feed(b"\x1b[<39;2;5M")`（shift + 无按键）→ 同形状（名字/按键不受修饰位影响）；
  - `feed(b"\x1b[<3;5;5M")` → `[]`（press 无按键：仍丢）；
  - `feed(b"\x1b[<3;5;5m")` → `[]`（release 无按键：仍丢）；
  - 既有 32/34/38 断言逐字不动。

### T2 `keys/console.py` + `sources.py` + `app.py`：console 桥的裸 motion（hover 门控）

- `_console_mouse_report(record, decoder, bits, *, hover: bool = False)`：在既有 `held and ...`
  分支之后加
  `elif hover and not held and flags & _MOUSE_MOVED: events.extend(decoder.feed(_sgr_report(_SGR_MOTION | 3, x, y)))`；
  注意过渡记录（`pressed`/`released` 非零）不走这条。
- `keys_from_console_events(events, *, hover: bool = False)` 透传；docstring 补一句
  「裸移动是记录路径的 1003 对应物，随 `hover` 开关生效」。
- `RawTerminalKeys.__init__(fd=None, *, hover: bool = False)` 存字段并在 `_read_console_records`
  的批量喂事件处透传。
- `app.py`：`TUI.__init__` 存 `self._hover = hover`；`run()` 里 `source = RawTerminalKeys(hover=self._hover)`；
  类 docstring 的 `hover` 说明补一句「默认 screen 之外的 key source 记录路径也随它开合」。
  **自定义 `screen=` + 自带 `keys=` 的契约不变**（调用方自管）。
- 测试（`tests/test_keys_sources.py`，追加）：
  - 裸 `MOUSE_MOVED` 记录（`button_state=0, flags=MOUSE_MOVED`）+ `hover=True` → 一条
    `MouseEvent("none", button=0, kind="motion")`；
  - 同记录 + `hover=False`（默认）→ `[]`；
  - 按住键的拖拽记录在两种开关下输出与改前一致（钉一条断言）。

### T3 端到端探针 + 文档口径（合并为一个 commit）

- 探针测试（放 `tests/test_pointer.py` 末尾）：`KeyDecoder().feed(b"\x1b[<35;c;rM")` 的**原始事件**
  喂 `Pointer.handle` → 命中 `Button` 时 `button.hover is True`、返回 `True`；再喂空白格的 35 →
  `hover is False`、返回 `True`。证明「wire → decoder → Pointer → 组件」全链路不需要真机。
- 文档同步（grep `none held` 逐处清）：
  - `core/events.py` MouseEvent docstring：motion 的低位含义（0/1/2 = 按住的键，3 = 无按键）+
    归一化句（`button 0`、名字 `none`）；
  - `docs/DESIGN.md` 的 Mouse 段：同上口径 + 一句「裸 motion 在 VT 路径靠 1003，在 console 记录路径
    随 `TUI(hover=True)` 开合」；
  - `keys/console.py` 模块/`_console_mouse_report` docstring；
  - `README.md` / `docs/COMPONENTS.md` 如重复旧口径一并改（grep 决定）。
- 不改 `Pointer`、`gesture`、任何组件的代码路径（纯 wire + 文档 + 测试）。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` → 只增不减（before `981 passed, 1 skipped`；贴 after 与新增测试文件/条数）。
2. `uv run python tools/framebench.py` → `render-hash` 与 `5bcfdf16…aba9a` **逐字符一致**（wire 不碰渲染）。
3. `uv run python examples/demo.py < /dev/null; echo exit=$?` → exit 0；`--pages` → 12 页头。
4. 探针原文：decoder 的 35/39/3M/3m 四例输出；`Pointer` 走 35 事件的三态（进→同格→出）；
   console 桥 `hover=True/False` 两态 + 拖拽记录对照。
5. 默认零变化证据：`enable_mouse_tracking(hover=True)` / 默认 的字节原文不变；
   `RawTerminalKeys()`（默认 `hover=False`）在裸 MOVED 记录下输出 `[]`。
6. 真机项：悬停观感 → 无法执行，列「lead 终验项」（本波只保证 wire 层可解）。

## 禁触清单

- `examples/**`、`tests/test_readme_examples.py`、README 的 Quickstart/库章节 demo 之外段落
- `Pointer` / `gesture` / 组件的既有代码路径与契约（本波不改它们的代码）
- `_BUTTON_NAMES` 的 0/1/2 三名、press/release 的既有解码
- `specs/**`（spec 归 lead）
- 未开 hover 时**任何**新增事件（默认零行为变化是硬约束）

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论（逐条 + 关键输出行 + pytest 数）/ decoder 四例探针 /
Pointer 端到端探针 / console 桥两态探针 / 默认零变化证据 / framebench hash / 偏差与取舍 /
未决问题 / 真机手测：未执行（lead 终验）。
