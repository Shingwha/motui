# Spec W1 · 基础件（波次 W1）
> ✅ 2026-10-04 已交付合并；终验 585 passed（main）。分支见 git log --merges。
> 分支 `wfs1-primitives`；前置：无（从 main 切出）；深读：`00-overview.md`（模块契约表以那里为准）

## 目标

从零建立工具包的五块基础件：`style.py` / `text.py` / `lines.py` / `ansi.py` / `block.py`，
配结构化测试，并在 `src/mocode_tui/__init__.py` 中导出本波公共面。
最高约束：`Component` 协议 `render(width) -> list[Line]` 本波定型，之后永不改；
display width 唯一真源是 `text.visible_width`；无第三方依赖（wcwidth 除外）。

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `style.py` — 样式值类型
- `FG_CODES: dict[str, int]`：16 个命名色（black/red/green/yellow/blue/magenta/cyan/white +
  bright_ 八色）→ ANSI SGR 码（30-37 / 90-97）。`RESET = "\x1b[0m"`。
- `Style` frozen dataclass：`fg: str|None`、`bg: str|None`、`bold/dim/italic/underline/reverse: bool = False`。
  `prefix()`：生成 SGR 前缀（属性码 1/2/3/4/7 + fg + bg+10），无属性时返回 `""`；
  每实例至多算一次（frozen 值语义可缓存）。未知色名直接 KeyError（内部错误，不兜底）。
- `merge(other)`：other 的非 None 字段覆盖 self；bool 字段取 or。
- 语义常量（组件默认取的）：`NONE/DIM(dim)/MUTED(bright_black)/ACCENT(cyan,bold)/SUCCESS(green)/
  ERROR(red,bold)/WARNING(yellow)/BORDER(bright_black)/CODE(yellow)/CURSOR(reverse)/SELECTION(reverse,dim)`。
- 测试 `tests/test_style.py`：prefix 各种组合与空样式；prefix 缓存同一实例只算一次；
  merge 语义（None 透传 / bool or）；16 色码表完整。

### T2 `text.py` — 宽度与换行工具
- `visible_width(text)`：`wcswidth` 为主，非打印/None 时回落逐字符 `wcwidth` 求和；空串 0。
- `one_row(text)`：去 tab→空格、去 `\r`/`\n`。
- `ellipsize_tail(text, width)` / `ellipsize_middle(text, width)`：宽度不足用 `…` 标记；
  width<=0 → `""`；width==1 → `…`；`…` 占 1 格。
- `wrap_text(text, width) -> list[str]`：**词感知**换行——优先在空格断、CJK 连续与超长词硬断；
  空输入 `[""]`；`width<=0` → `[""]`。必须保证 width=1 且字符宽于行时也终止（宽字符独占一行）。
  tab 一律按 1 空格（`TAB_WIDTH` 常量只为文档说明存在，不实现制表位）。
- `terminal_size() -> (cols, rows)`：`shutil.get_terminal_size(fallback=(80,24))`。
- 测试 `tests/test_text.py`：visible_width 中英混排/emoji/控制字符；ellipsize 边界；
  wrap_text 词感知、硬断、空行、width=1 终止性（含性能卫——构造 200 字符 CJK 断言不挂）。

### T3 `lines.py` — 行模型
- `Segment(text, style=Style())` frozen dataclass。
- `Line(segments)`：不可变的一可视行。`from_text(text, style=None)`；`segments`；`width`（各段
  visible_width 之和）；`text`（纯文本视图）；`styled()`（每段 style.prefix()+文本，末尾 RESET，空行返回 ""）；
  `fit(width)`（超宽截断加 `…`，不足原样返回，`width<=0` 空行）；`pad_to(width)`（补空格；
  已够宽返回 self）；`__add__` 拼接；`__eq__/__hash__` 按段比较。
- `wrap_line(line, width) -> list[Line]`：词感知换行（与 wrap_text 同断点规则），保段样式跨断点；
  断点空白被丢弃；空行 `[Line()]`；`width<=0` → `[Line()]`。
- 内部 `ELLIPSIS = "…"`；实现可复用 `text.py` 助手，不得重复造宽度逻辑。
- 测试 `tests/test_lines.py`：fit/pad_to 边界；styled 输出形状（含 RESET 收尾）；
  wrap_line 断点/硬断/样式保持/CJK/width=1；Line 相等与哈希。

### T4 `ansi.py` — 转义构造与能力探测
- 常量和函数（名字总纲表已锁）：`ESC/CLEAR_LINE/RESET`、`move_up(n)`（n<=0 为 ""）、
  `move_to_column(col)`（默认 0）、`clear_line()`、`delete_lines(n)`（n<=0 为 ""）、
  `erase_down()`、`hide_cursor()`、`show_cursor()`、`enter_alt_screen()`、`leave_alt_screen()`。
- `strip_ansi(text)`：去转义（可见文本断言用）。正则：`\x1b\[[0-9;?]*[A-Za-z]` 加孤立 `\x1b.`。
- `enable_vt() -> bool`：Windows 下对 STD_OUTPUT_HANDLE 置 `ENABLE_VIRTUAL_TERMINAL_PROCESSING`；
  成功或已开启返回 True；非 Windows 返回 True；任何失败（无 console/ctypes 不可用/被拒）返回 **False**
  （调用方据此把 screen 判为非 live）。注意：返回值语义相对旧实现是新增，本仓库从零写，直接按此实现。
- `stdout_isatty()`。
- 测试 `tests/test_ansi.py`：各转义函数字节形状；strip_ansi；`enable_vt()` 在本机 POSIX 语义
  （os.name != nt → True）。

### T5 `block.py` — 文档模型
- `Component` runtime_checkable 协议：`render(self, width: int) -> list[Line]`。
- `BlockState` enum：只 `OPEN = "open"` / `SEALED = "sealed"`。**不得出现 COMMITTED 或任何提交语义**。
- `Block(id, component, *, pinned=False)`：`state` 初为 OPEN；`component` 属性；
  `set_component(c)`（无状态限制）；`seal()`（OPEN→SEALED，重复/非法调用 raise ValueError）；
  `render(width)` 转发组件；`is_open`；`pinned` 只读。
- `Document()`：`add(component, *, id=None, pinned=False)`（id 缺省 `b{n}` 自动且唯一，重复 id raise）；
  `get(id)`（缺失 raise KeyError 带信息）；`remove(id)`（摘除，返回块）；`blocks()`（文档序快照）；
  `__len__`。
- 测试 `tests/test_block.py`：id 自动/唯一/冲突 raise；get/remove；pinned 标记透传；
  seal 一次性与 ValueError；is_open 状态迁移；render 转发。

### T6 `__init__.py` 导出本波面 + 全量门禁
- 导出：`Block, BlockState, Component, Document, Line, Segment, Style, wrap_line, wrap_text,
  visible_width, Screen（此时还不存在——不得导入不存在的模块）`……
  **规则**：只导出本波真实存在的符号；`screen/painter/keys/app/components/testing` 属于后续波，
  W1 的 `__init__.py` 不得提前 import 它们。最终导出面以总纲「模块契约」表为准，W4 收口。
- `uv run pytest` 全绿（贴尾部输出：总数/失败项）。
- `uv run python -c "import mocode_tui; print(sorted(mocode_tui.__all__))"` 贴输出。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest`：`N passed`，0 失败（贴尾部原文）。
2. import 冒烟命令输出。
3. `git diff --stat main..HEAD`：证明写入范围仅在
   `src/mocode_tui/{style,text,lines,ansi,block,__init__}.py` 与 `tests/test_{style,text,lines,ansi,block}.py`。

## 禁触清单

- 本波之后任何模块（`screen.py` `viewport.py` `painter.py` `keys.py` `app.py` `testing.py`
  `components/**` `layout.py`）、`examples/**`、`docs/**`、`README.md`、`pyproject.toml`、`specs/**`。
- 不 merge / 不 push / 不 checkout main / 不碰其他 worktree；不改任何 spec。

## 诚实出口

- `wrap_text`/`wrap_line` 若在 CJK 硬断上发现无法同时满足「词感知」与「width=1 终止」：
  以「宽字符独占一行」保终止，把语义取舍写进报告。
- 任何模块行数/口径与总纲契约表冲突：**契约表优先**，实现服从；冲突点写报告交 lead。

## 最终报告格式

工单状态表（T1..T6：commit hash + message）/ commit 清单 / 自测真实结论（命令原文）/
偏差与取舍 / 未决问题。
