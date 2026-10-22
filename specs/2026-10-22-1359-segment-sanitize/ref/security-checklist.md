# motui 安全修复清单：内容注入终端控制序列

> 日期：2026-10-22
> 基线：main `58c5edb`（1.2.1），行号即仓库行号
> 优先级：**P0（用户可见的持续故障 + 终端安全边界；先于性能波 M5）**
> 触发来源：mocode 实测——多轮工具调用后鼠标完全失效（点击、悬停均无反应），键盘正常
> 性质：框架级缺陷，不是 mocode 的回归（重构前同样存在）

---

## 一、现象与影响面

**直接现象**：TUI 运行中，只要某次渲染的文本包含终端控制序列（工具输出、模型回答、
文件内容都算），序列会被**原样写到终端**。最常见的后果是鼠标上报被关闭：

- `ESC[?1000l` 关掉按键上报，`ESC[?1003l` 关掉悬停移动，`ESC[?1006l` 关掉 SGR 格式；
- 模式的开启只在 `Screen.enter()` 发生一次，**没有任何帧级重断言**，所以一旦被关，
  直到应用重启都不会恢复——表现为"鼠标突然全死、键盘照常"。

**同一漏洞的完整影响面**（不止鼠标）：

| 注入的序列 | 后果 |
|---|---|
| `ESC[?1000l/1002l/1003l/1006l` | 鼠标上报关闭（本 bug） |
| OSC 52（`ESC]52;c;...`） | 写用户剪贴板 |
| OSC 0/2（`ESC]0;...`） | 改窗口标题 |
| `ESC[?1049h/l` | 切 alt-screen（界面被顶掉或残留） |
| `ESC[?25l/h` | 隐藏/显示光标 |
| `ESC[?2026h`（不成对的） | 终端进入同步更新，画面停更 |

对 agent 类应用这是**不可信内容直连终端**的问题：`cat` 一个恶意仓库文件、跑一下
`vim/htop/reset` 之类会设置终端的程序、甚至模型在回答里引用 ANSI 序列，都能触发。

---

## 二、证据链（可复现）

### 2.1 行渲染零净化

```python
from motui.core.lines import Line
Line.from_text("OUT: \x1b[?1000l\x1b[?1006l").styled()
# → 'OUT: \x1b[?1000l\x1b[?1006l\x1b[0m'      ← 原样保留
```

### 2.2 字节级：序列真的写向了终端

```python
from motui.core.screen import HeadlessScreen
from motui.core.painter import Painter
from motui.core.viewport import Viewport
from motui.core.block import Document
from motui.core.lines import Line

class Raw:
    def __init__(self, text): self.text = text
    def render(self, width): return [Line.from_text(self.text)]
    def revision(self): return (self.text,)

doc = Document(); doc.add(Raw("OUT: \x1b[?1000l\x1b[?1006l"))
screen = HeadlessScreen(width=80, height=6)
Painter(screen, sync=True).paint(Viewport(doc).layout(80, 6))
assert "\x1b[?1000l" in screen.output        # ← 确实被写向终端
```

### 2.3 上游开启鼠标模式只有一次

`src/motui/core/screen.py:191`（`TerminalScreen.enter`）与 `:332`（`HeadlessScreen.enter`）
是仓库里仅有的 `enable_mouse_tracking` 调用点；`disable` 只在 `leave`。全仓无其它
重断言路径。

### 2.4 实测症状吻合

mocode 侧两条内容链路都原样透传（`ToolCallBlock.append_output` 渲染行、`Markdown` 渲染行
均含 `\x1b`）；键盘走独立解码不受影响，鼠标事件在终端层被关掉后 `App.dispatch` 再也
收不到 `MouseEvent`——与"键盘正常、鼠标全死"完全一致。

---

## 三、根因定位

| 位置 | 现状 | 问题 |
|---|---|---|
| `src/motui/core/ansi.py:1-8` | 模块文档："Every escape byte the toolkit emits is constructed here; no other module builds escape strings by hand." | **内容通道绕过了这个不变量**：`Segment.text` 没有经过任何构造校验 |
| `src/motui/core/lines.py:76-90` | `Segment` 是 `@dataclass(frozen=True, slots=True)`，`text: str` 直接存放调用方字符串 | 没有 `__post_init__`，控制字符原样入库 |
| `src/motui/core/lines.py:125-142`（`_segment_bytes`） | `prefix + seg.text`（或 OSC 8 包裹） | 逐字节写出，无过滤 |
| `src/motui/core/lines.py:93` | `link: str \| None` 参与 OSC 8（`hyperlink_open(link)`） | link 同样可注入控制字节 |
| `src/motui/core/text.py:235,303-304` | `visible_width` 把非打印字符算 0 列，但**文本字符串保留它们** | 与"一个 cell 一个字形"的模型不自洽：宽度说没占列，字节却写出去 |

**结论**：不是某一个 Widget 的锅，是内容模型缺了"文本永远是文本"这一层保证。

---

## 四、为什么修复属于上游（组件库惯例）

1. **补的是框架自己的契约**：Segment 是"带样式的文本段"，样式用 `Style` 表达；
   在 `text` 里塞 ANSI 不是合法用例。`ansi.py` 已声明 escape 只由它构造，内容通道应
   收敛到同一保证。
2. **唯一收口点**：所有内容最终都过 `Segment` 构造（Text / Markdown / Table / Diff /
   第三方组件 / 手工 `Line.from_text`）。修一处覆盖全部；下游逐功能净化必然漏。
3. **安全边界属于终端 sink 的所有者**。不可信内容是常态（工具输出、模型输出、文件内容），
   组件库不能假设每个宿主都记得净化。
4. **行业惯例两派，趋势是 safe-by-default**：
   - 默认转义/剥离（Web 的文本节点、React 默认转义）：库替所有使用方兜底；
   - 原样透传 + 提供 strip 工具（多数底层终端库的历史做法）：灵活，但每个宿主都要记得，
     这正是 TUI 应用里 escape 注入 bug 反复出现的原因。
   - cell 模型如果严格"一个 cell 一个字形"，控制字符本就会在切字形时消失；motui 的
     `visible_width` 已按 0 列处理、文本却保留，净化才是与自身模型一致的方向。
5. **业务上无损**：真正需要"彩色日志"的场景应由显式的 ANSI 解析组件把 SGR 映射为
   `Style`（见 §5.3），而不是允许任意字节透传。

---

## 五、修复设计

### 5.1 方案 A（推荐）：在 `Segment` 构造点净化

`src/motui/core/lines.py`：

```python
#: Control characters a rendered cell may never carry. Tab keeps its
#: meaning (the width walk gives it TAB_WIDTH); everything else in C0/C1
#: and DEL is content that could drive the terminal instead of painting.
_CONTROL = {c for c in range(0x00, 0x20)} | {0x7F} | {c for c in range(0x80, 0xA0)}


def _text_only(text: str) -> str:
    """The run's text as cells, never as terminal commands."""
    if not any(ord(ch) in _CONTROL and ch != "\t" for ch in text):
        return text                      # the fast path: nearly every segment
    return "".join(
        ch for ch in text
        if ch == "\t" or ord(ch) not in _CONTROL
    )
```

`Segment.__post_init__`（frozen dataclass 用 `object.__setattr__`）：

```python
def __post_init__(self) -> None:
    object.__setattr__(self, "text", _text_only(self.text))
    if self.link is not None:
        object.__setattr__(self, "link", _text_only(self.link) or None)
```

要点：

- **保留 `\t`**：宽度逻辑已按 `TAB_WIDTH` 计算，且制表符不构成终端指令。
- **换行**：`\n`/`\r` 在 C0 内，被删除。Segment 是单行模型，换行本就不该出现在这里；
  多行由组件先分行（现有组件都这么做）。若担心删除导致行粘连，可替换为空格——二选一，
  建议**删除**（宽度一致、语义明确）。
- **C1 区（0x80–0x9F）与 DEL** 一并处理：它们同样能构成 8-bit 控制序列。
- **删除而非 U+FFFD**：宽度逻辑已把控制字符算 0 列，删除后宽度不变，不会引入新的
  换行/截断行为。
- **幂等**：`with_style()` 会重建 Segment，二次净化无副作用。
- **成本**：快路径是一次 `any()` 扫描（纯 ASCII 且无控制字符立刻返回）；Segment 不可变
  且按行缓存，只在构造时付一次。全仓测试与 golden 不受影响（内容里本无控制字符）。

### 5.2 方案 B（可选逃生门）：`raw=True`

若确有个别下游要原样透传（mocode 不需要），给 `Segment` 加 `raw: bool = field(default=False, compare=False)`
并在 `__post_init__` 跳过净化。**默认安全，显式危险**——比"默认透传 + 全局开关"好，
因为危险只发生在写明的地方。

### 5.3 后续增强（非必需）：`AnsiText` 组件

把工具输出的 SGR 颜色找回来：解析 `CSI ... m` 映射为 `Style`（前景/背景/粗体/斜体/
下划线），**其余控制序列一律丢弃**（光标、鼠标模式、OSC、清屏）。这是"显示彩色日志"的
正确抽象，参考 Rich 的 `Text.from_ansi` 路线。不要用"允许任意 ANSI 透传"来实现它。

### 5.4 不推荐的修法

- **只在 painter 层过滤**：`Line.styled()` 与 `styled_with()` 两条字节路径，且 `Line.text`、
  宽度、搜索、复制、选区提取仍会看到控制字符。
- **每帧重发鼠标模式**：掩盖症状的 hack；终端会因帧流里反复出现模式切换而闪烁，且挡不住
  OSC 52 等其它注入。

---

## 六、测试（验收标准）

1. **单元（lines）**：
   - `Line.from_text("a\x1b[?1000lb").styled()` 不含 `\x1b`，且 `line.text == "ab"`；
   - `Segment("x\x1b]0;title\x07y").text == "xy"`；
   - `Segment("a\tb").text == "a\tb"`（制表符保留）；
   - `Segment("x", link="\x1b]8;;x").link in (None, "")`（link 不得携带控制字符）；
   - `with_style()` 后仍不含控制字符（幂等）。
2. **字节级不变量**：用 `HeadlessScreen` 全量 paint 一个含恶意序列的 Document，
   `screen.output` 中不出现 `\x1b[?1000l`/`\x1b]52`/`\x1b]0;`（除 ansi.py 自己的合法序列）。
3. **golden / render-hash**：11 页 golden 与 `framebench` 的 `render-hash` **逐字不变**
   （内容无控制字符，净化不该改变任何字节）。
4. **回归**：现有 1422 passed 全绿。

---

## 七、发布与兼容

- 按 **minor** 发布并在 CHANGELOG 记为 security/robustness fix（用户可见行为变化仅限
  "内容里的控制字符不再画到终端"）。
- 发版说明写清契约：**渲染文本永不产生终端控制序列；escape 只由 `ansi.py` 构造**。
- 下游（mocode）升级后无需改代码；若曾依赖透传，用 `raw=True`（5.2）。

---

## 八、mocode 侧配套（轻量，不复制净化逻辑）

1. **端到端回归测试（现在就可以加，不依赖上游发版）**：往 `ToolCallBlock` 和 `Markdown`
   喂含 `\x1b[?1000l` 的内容，用 `HeadlessScreen` 抓 paint 字节，断言输出不含该序列。
   上游修好后自然绿；将来谁再引入透传会被立刻抓住。
2. **发版前的临时兜底（可选，仅止血）**：在 `Transcript` 的内容入口
   （`append_output` + 答案 chunk + 插件消息）加 10 行控制字符剥离；motui 发版后删除。
   默认不做——多入口兜底容易漏，且与"mocode 简单调用"的分工相反。

---

## 九、复现与现场确认

**现场确认（不重启应用）**：鼠标失效时在同一终端执行：

```bash
printf '\033[?1000h\033[?1003h\033[?1006h'
```

鼠标立即恢复 → 确认是上报模式被输出关闭。

**定位触发内容**：会话 JSON 里保存的是工具结果原文，可在最近的会话文件里搜
`\u001b` 或 `\x1b`，找到那条把序列带进来的命令/输出。

---

## 十、风险

- 低。净化是 Segment 构造期的线性扫描（快路径对普通文本零分配），不改任何布局/绘制算术。
- 唯一行为变化：含控制字符的内容不再照原样显示（这正是修复目的）；合法文本零变化，
  golden/哈希可证。
