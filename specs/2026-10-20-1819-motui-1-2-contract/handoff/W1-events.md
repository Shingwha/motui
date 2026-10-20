# W1 handoff · 事件模型与终端解码

## A · 交付

分支 `w1-events`，2 个 commit：

| commit | 内容 |
|---|---|
| `b58be28` | events: the 1.2 model lands -- typed events, decode matrix, source lifecycle（代码 + 测试 + 文档，T1–T6） |
| 本文件 | specs: the W1 handoff |

公开签名（新增/变更）：

```python
class Event: ...
@dataclass(frozen=True, slots=True) class KeyEvent(Event): key; char=""; modifiers=frozenset(); kind="press"
@dataclass(frozen=True, slots=True) class MouseEvent(Event): button="none"; x=0; y=0; kind="press"; modifiers=frozenset()
@dataclass(frozen=True, slots=True) class PasteEvent(Event): text
@dataclass(frozen=True, slots=True) class ResizeEvent(Event): width; height
@dataclass(frozen=True, slots=True) class FocusEvent(Event): focused
@runtime_checkable class EventSource(Protocol): async def read(self) -> Event | None
async def TUI.read_event(self) -> Event | None
```

`motui.kernel` 新增 `Event/EventSource/FocusEvent/KeyEvent/PasteEvent/ResizeEvent`；
删除 `Key/Paste/KeySource/ScriptedKeys`。根仍是 34 名，事件三件套为
`KeyEvent/MouseEvent/PasteEvent`。`ScriptedEvents` 在 `motui.testing`。

基线真实结果（HEAD，Windows）：

- `uv sync --locked`：Resolved 11 / Checked 10。
- `uv run pytest -q -p no:cacheprovider`：**1719 passed, 2 skipped**（两个 POSIX-only 用例在 Windows skip）。
- `uv run python tools/golden.py --check`：`golden: 11 pages match`。
- `uv run python tools/framebench.py`：render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（与基线一致）。
- `python -m motui < /dev/null`：exit 0，70 行；`python -m motui --pages`：exit 0，792 行。
- 验收 grep（`event.name` / `isinstance(event, Key)` / 旧 `Key` import）：0 命中。
- `git diff --stat main...HEAD`：55 文件，只含工单写范围；无 golden、pyproject、uv.lock、CONTRACT、frame.py。

## B · 偏差、踩坑与约束

- **提交形状是 2 个 commit。** T1–T6 的实现、测试与文档压成 commit A，handoff 单独成
  commit B：每个 commit 的树都能单独 checkout 并通过全量门禁。工单 T1–T7 的分项状态
  仍见最终报告。
- `CSI R` 现在按冻结契约是 `f4`：xterm 的 cursor-position report
  `CSI row;col R` 会被解释成带修饰符的 f4，不再被丢弃。这是 interfaces §1.2 的必然结果。
- SGR 低 2 位 = 3 的 press/release 现在产出 `MouseEvent(button="none")`，不再丢弃；
  依据 §1.3 的位映射。X10 的 low-3 release 同样落到 `button="none"`。
- `wRepeatCount=N` 解释为 **1 个 press + (N-1) 个 kind="repeat"**（N=1 仍是 press）；
  若 lead 期望 N 个全为 repeat，只需改 `keys/console.py:_repeated`。
- X10 仍是文本层解析（三字节经 UTF-8 解码后回读）；ASCII 坐标完全正确，
  两个高位字节恰好构成合法 UTF-8 的极端组合可能失真。urxvt 1015 无此限制。
- kitty 的 `CSI 97;2u`（shift+a）保留 codepoint 身份：key/char=`a`，modifiers 含 shift；
  不推断大写。Ctrl/Alt/Super 的和弦不填 `char`。`super` 的键名前缀为 `super-`（契约未规定）。
- `\n` 现在解码为 `c-j`（`\r` 仍是 `enter`），`EDITOR_SUBMIT_KEYMAP` 的 `c-j` 因此可达。
- `RawTerminalKeys.start()` 在 close 后可重入；旧 reader 若仍阻塞在 Windows cooked
  `os.read` 上，重启会因线程存活而 no-op——这是“尽力解除阻塞”的平台边界。
  幂等性由显式 `_started` 标志决定（不是线程存活探测），所以 reader 快速读到 EOF
  后的第二次 `start()` 不会重置队列。
- 下一波必须遵守：不要再引入 `Key`/`Paste`/`KeySource`/`ScriptedKeys`；
  滚轮判断用 `MouseEvent.kind == "wheel"` + `.button`；键盘判断只认 `KeyEvent`；
  `TUI.stop/run/split/hit_test` 语义本波未动，留给 W2。

## C · 关键位置与稳定区

- 事件模型：`src/motui/kernel/events.py:42`（Event）、`:47`（KeyEvent）、`:68`（MouseEvent）、`:116`（EventSource）。
- 解码：`src/motui/keys/decoder.py:458`（CSI dispatch）、`:530`（kitty）、`:635`（共享鼠标码）。
- 来源：`src/motui/keys/sources.py:126`（start）、`:158`（close，self-pipe）、`:176`（read，sticky EOF）。
- 控制台：`src/motui/keys/console.py:277`（record fields）、`:312`（repeat）、`:329`（record events）。
- 驱动：`src/motui/app.py:887`（`read_event`，wheel 用 kind=="wheel"）。
- 测试入口：`tests/test_events.py`、`tests/test_keys.py`、`tests/test_keys_sources.py`、`tests/test_decoder_fuzz.py`。
- 未触碰的稳定区：`widgets/markdown/**`、`demo/pages/**` 渲染逻辑、`kernel/frame.py` 几何、golden。
- 已知未决：`wRepeatCount` 的 press/repeat 语义（见 B）；水平 wheel 只解析不消费
  （`scroll_keys` 未绑定 `wheel_left/right`，跨 pane 横向滚动仍是 1.2 non-goal）。
