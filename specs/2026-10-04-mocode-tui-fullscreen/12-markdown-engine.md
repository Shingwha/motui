# Spec W12 · Markdown 引擎重做（波次 W12）
> ✅ 2026-10-04 已交付合并。
> 前置：W11 已合并；深读：`00-overview.md` + `11`（色板） + `05`（Table 前身）

## 背景（用户 2026-10-04 第六轮反馈 + pi 参照图）

1. 表格应**并入 Markdown**（GFM 管道表格），与其他 markdown 一致渲染；框线要**亮**
   （现 `Table` 用 `BORDER #3d444d` 太暗，「看不清楚」）。
2. **标记与 pi 保持一致**：标题/列表（`-`、`1.`，可嵌套）/引用块（`>` 渲染为 `│` 前缀）/
   围栏代码/表格/分割线；行内：code、**bold**、*italic*、[link](url)。
3. **数学公式不解析**（后续再考虑）——但解析架构要预留扩展点。
4. **可扩展、易用、不打补丁**：用户明确要求整体解析是一个可扩展体系，API 有拓展性，
   代码简洁清晰，禁止在现有 regex 流程上打补丁。

## 裁决（lead）

把 Markdown 从 `components/text.py` 的 regex 堆提升为**规则注册表驱动的行级解析引擎`，
迁到新模块 `components/markdown.py`；`text.py` 只留 `Text`。流式安全是硬约束
（demo 的 Markdown 要逐字流式渲染，半截 fence/半截表格不许炸）。

## 目标架构（lead 定格，agent 在此架构内实现，细节可补但不得改形）

```python
# components/markdown.py

class BlockRule(Protocol):            # 块级规则：匹配 + 渲染
    name: str
    def match(self, lines: list[str], i: int) -> int | None: ...   # 返回消费行数，None=不匹配
    def render(self, lines: list[str], width: int) -> list[Line]: ...

class InlineRule(Protocol):           # 行内规则
    name: str
    def match(self, text: str, pos: int) -> tuple[int, list[Segment]] | None:  # (结束位置, 段)

BLOCK_RULES: list[BlockRule]          # 有序注册表，先匹配先消费；末位必须是 ParagraphRule
INLINE_RULES: list[InlineRule]        # 行内注册表

class Markdown:
    def __init__(self, text: str = "", *, block_rules=None, inline_rules=None): ...
    text: str                         # 可变；流式即反复赋值
    def render(self, width: int) -> list[Line]      # 纯函数，行宽永不超 width
```

- 解析 = 分类（match 链条，table 靠 2 行前瞻区分表头与段落）→ 渲染（每规则自带 render）。
- 扩展 API：`Markdown(text, block_rules=[MyRule(), *BLOCK_RULES], inline_rules=[...])`；
  数学公式 = 未来的 InlineRule/BlockRule（在 docstring 写明该扩展点与示例骨架，不实现）。
- 流式安全：未闭合 fence → 后续全按代码；表格只有「表头行 + 分隔行」齐了才按表格，
  否则按段落；行内未闭合 `**` 按字面。

## 渲染规格（对齐 pi 参照图）

| 元素 | 输入 | 渲染 |
|---|---|---|
| 标题 | `#`..`######` + 空格 | 沿用现梯级：h1 ACCENT bold / h2 ACCENT+underline / h3 MUTED / h4 MUTED dim / h5 h6 MUTED dim(italic for h6) |
| 无序列表 | `- `/`* `（缩进 2 空格/级） | 原样 `- ` 标记（**不打圆点**，与 pi 一致），嵌套按缩进层级 |
| 有序列表 | `N. ` | 原样 `N. ` 标记，嵌套同上 |
| 引用块 | `> ` | 每行 `│ ` 前缀（MUTED） |
| 围栏代码 | ``` 包围 | 代码行 fit(width)，无语言标签 |
| 表格 | `\| a \| b \|` + `\|---\|---\|`（可带 `:--`/`--:`/`:-:` 对齐） | 盒线表格：**亮线**、表头 bold、支持左/中/右对齐 |
| 分割线 | `---`/`***`（独占行） | Divider |
| 段落 | 其他 | wrap + 行内规则 |
| 行内 | `` `code` `` `**b**` `*i*` `[t](u)` | CODE 冰蓝 / bold / italic / ACCENT+underline 文本 + MUTED ` (url)` |

## 工单（按序，每项一个 commit，每 commit 独立过 `uv run pytest`）

### T1 `components/markdown.py` 引擎骨架
- 注册表 + `Markdown` 类（上面架构）；`ParagraphRule`/`HeadingRule`/`ListRule`/
  `QuoteRule`/`FenceRule`/`TableRule`/`ThematicBreakRule` 内置；
  `InlineRule`：code/bold/italic/link。
- `components/text.py`：**移除 Markdown 及相关 regex**（只留 Text）；`components/__init__.py`
  导出改从 `.markdown` import Markdown；根 `__init__.py` 导出不变。
- 测试 `tests/test_components_markdown.py`（新）：每个块规则的形状（标题梯级与旧测试一致）/
  列表标记与嵌套/引用 `│`/围栏未闭合不炸/表格对齐/流式安全（ fence 半截、表格半截、
  行内半截各自赋值递增断言）/注册表扩展性（自定义 InlineRule 与 BlockRule 各一例）。

### T2 `components/table.py` 亮线 + Table 默认值
- 模块常量 `TABLE_BORDER = Style(fg="#9aa4b0")`（比 BORDER 亮一档）；
  `Table` 默认 `style` 由 BORDER 改 TABLE_BORDER；Markdown 的 `TableRule` 复用 `Table` 组件。
- `tests/test_components_table.py`：默认线样式断言改 TABLE_BORDER；形状/收缩/ellipsize 不变。

### T3 清理旧 Markdown 测试
- `tests/test_components_text.py`：删除 Markdown 相关用例（迁去 T1 新文件，标题梯级用例
  **必须等价迁移**——`test_markdown_heading_levels_share_accent_family` 原样搬到新文件）；
  Text 用例保持。
- `docs/COMPONENTS.md`：Markdown 段落重写（新架构、可扩展 API、pi 对齐的标记表、
  数学=预留扩展点）；Table 行补亮线说明。

### T4 门禁
- `uv run pytest` 全绿（贴尾部，N ≥ 651）；
- 冒烟：流式逐字赋值 `Markdown.text`（一个含全部块型的文档，每次加 10 字符）200 次采样
  不炸且行宽 ≤ width，贴前/中/后三态的行文本。
- `git diff --stat main..HEAD`：仅 `components/{markdown,text,table,__init__}.py`、
  `tests/test_components_{markdown,text,table}.py`、`docs/COMPONENTS.md`。

## 禁触
其余一切文件（style.py/keys/app/pi_demo/其他 tests/docs 均不碰）；不 merge/push/checkout main；
不改 spec；sleep 零（引擎无 sleep）。

## 诚实出口
- 表格对齐解析若与某终端盒线渲染有歧义：以「解析出 left/center/right 后按列内文本对齐
  （左/居中/右，空格补齐）」为准，登记取舍。
- 列表嵌套若 2 级以上出现对齐歧义：支持 2 级、更深按 2 级截断并登记。

## 最终报告格式
工单状态表（T1-T4）/ commit 清单 / 自测真实结论 / 偏差与取舍 / 未决问题。
