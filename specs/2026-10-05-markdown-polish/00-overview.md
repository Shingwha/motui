# 2026-10-05 markdown-polish · 总纲

> ✅ 全波次(W1-W3)已合并 main(2026-10-05)

> 把 mocode-tui 的 Markdown 渲染对齐 pi 参考观感：块间空行、表格正确性（测量/内联/转义竖线/网格横线）、
> 默认配色多样化（bold 只跟 Markdown 语法）、分割线限宽。全部默认值保持可自定义（Theme / 构造参数）。

## 目标与范围

1. **块间距**：`Markdown` 渲染时相邻块之间插一个空行（`gap` 参数可控，默认 1）。
2. **表格正确性**：修 `ellipsize_tail`/`Line.fit` 双路径测量不一致导致的边框参差；单元格渲染内联
   markup；`\|` 转义竖线不再切错列；数据行之间补 `├─┼─┤` 内部横线（完整网格，对齐 pi）。
3. **默认配色**：标题金色阶梯、链接蓝下划线（不加粗、只显示 label）、行内代码粉、列表标记紫、
   引用正文斜体、表头/首列去 bold。**bold 只出现在 `**…**` 语法本身**。
4. **分割线**：`Divider` 支持 `max_width`；`Markdown(divider_max_width=80)` 默认上限 80 列，`None` = 通栏。

不做：不加新 Markdown 语法（Setext/任务列表/脚注等维持现状降级）；不改 chat 层代码
（新观感经 Theme 与 Markdown 组件自动流入）；不动公共 `render(width) -> list[Line]` 协议。

## 根因档案（lead 已实锤，agent 直接照单施工）

| # | 症状 | 根因位置 |
|---|---|---|
| 1 | 块间无空行 | `widgets/markdown.py:771-790` 丢空行直接堆叠；docstring 722-723；pin 在 `tests/test_widgets_markdown.py:48` |
| 2a | 表格边框参差 | `core/text.py:56-76` `ellipsize_tail` 逐字符测量 vs `visible_width` 整串 `wcswidth` 不一致（`ellipsize_tail("⚠️ Blocked", 4)` 宽 5 超 1 列）；`table.py:152-154` pad 用 `max(...,0)` 掩不住；fixture 在宽度 31–75 实测 45 处参差 |
| 2b | 单元格不渲染内联 | `markdown.py:436-437` 明文"Cells are plain text"；`TableRule` 不走 `_InlineMixin`；`table.py` 每格单 Segment |
| 2c | `\|` 切错列 | `markdown.py:641-650` `_split_row` 见 `|` 就切 |
| 2d | 数据行间无横线 | `table.py:134-141` 只有表头下一条 rule |
| 3 | 全是蓝 | `core/theme.py:99-110` 阶梯全由 accent(蓝 bold)/muted 派生 |
| 4 | 分割线通栏 | `widgets/chrome.py:86-107` 恒用整个 width |
| 5 | 链接噪音 ` (url)` | `markdown.py:243-266` LinkInlineRule 附加 muted ` (url)` 段 |

## 波次表

| 波次 | 名称 | 分支 | 前置 | 并行 |
|---|---|---|---|---|
| W1 | 表格与测量正确性 | `md-w1-tables` | — | 串行 |
| W2 | 块间距 + 分割线限宽 | `md-w2-rhythm` | W1 已合并 | 串行 |
| W3 | 配色 + 文档 + 基线重采 | `md-w3-palette` | W2 已合并 | 串行 |

三波都要碰 `widgets/markdown.py`，必须串行；合并顺序 = W1 → W2 → W3，每波分支从**合并时刻的最新 main** 创建。

## 已拍板的决策（agent 不再猜）

1. **间距策略**：只在相邻块之间插 1 个空行；源文档连续空行不产生多个空行；首块前/末块后不加。
   `Markdown(gap: int = 1)`，负值按 0 处理，`gap=0` 恢复旧的紧贴堆叠。
2. **松散列表**：不单独处理。序号 verbatim 渲染（ListRule 不重编号），空行分隔的项在块间距生效后自然分开。
3. **单元格内联**：`TableRule` 解析每格为 `list[Segment]`（base=NONE），Table 负责把 base 风格
   （表头=header_style、数据行首列=first_column_style）合并到属性型段（fg/bg 全空的段），色段保持绝对——
   与 `inline_segments` 的合并规则一致。`Table` 单元格类型扩展为 `str | tuple[str, Style] | Sequence[Segment]`，
   str/tuple 行为不变（向后兼容）。
4. **对齐**：`Table` 新增 `aligns: Sequence[str] | None = None` 列对齐参数（left/center/right，默认 left），
   对齐移到 Table 内用 pad Segment 实现；markdown 的 `_pad` 失去消费者，顺带拆除。
5. **转义竖线**：`_split_row` 以 `(?<!\\)\|` 切分、格内 `\|` 还原为 `|`；反斜杠紧邻竖线的双重转义
   不做区分（文档化简化，fixture 不覆盖该角落）。
6. **测量**：新增 `core/text.py::fit_text(text, budget)`，后置条件 `visible_width(结果) <= budget`
   对任意输入成立（含 VS16/ZWJ/组合符）；`ellipsize_tail` 与 `Line.fit` 内层都改建在其上。
7. **网格横线**：数据行之间（含表头与首数据行之间已有的那条）每两行之间一条 `├─┼─┤`；空表体不变。
8. **分割线**：`Divider(max_width=None)`（None=通栏，直接使用 Divider 的宿主行为不变）；
   `Markdown(divider_max_width=80)` 默认 80 列、左对齐，`None` 恢复通栏。80 来自 pi 截图像素比例估算。
9. **配色**（W3 落地，全部是 Theme 字段，可 `dataclasses.replace` 覆盖）：
   - 新 token：`heading` 金 `#e3b341`、`link` 蓝 `#58a6ff`+underline、`inline_code` 粉 `#f778ba`、
     `list_marker` 紫 `#bc8cff`（style.py 加同名列常量，跟随现有常量模式）。
   - 标题阶梯改由 `heading`/`muted` 派生（与 accent 解耦）：
     h1=h2=heading，h3=heading+dim，h4=muted+dim，h5=muted+dim，h6=muted+dim+italic；全部不加粗。
   - `LinkInlineRule` 只返回 label 段（样式 `theme.link`），**不再输出 ` (url)`**。
   - `CodeInlineRule` → `theme.inline_code`；`ListRule` 标记 → `theme.list_marker`；`QuoteRule` 正文 base 斜体（bar 不变）。
   - `first_column` 默认 → `NONE`；`DEFAULT_HEADER_STYLE` → `NONE`（token 与参数保留，可自定义）。
   - 色值是 pi 截图的近似；W3 合并后 lead 与截图并排比对，必要时微调一个 commit。
10. **bold 政策**：全库默认样式中 bold 只允许出现在 `**…**` 语法产物上；italic 只在 `*…*` 与引用正文；
    underline 只在链接。syntax 高亮的 keyword=accent（bold）属代码高亮，不算此列。
11. **demo 合一**（W3 执行，用户需求）：`examples/pi_demo.py` 增加 `/md` slash 命令加载
    `examples/Markdown-Rendering-Test.md` 到 transcript；**删除 `examples/markdown_demo.py`**，运行入口只剩
    `uv run python examples/pi_demo.py`。fixture `.md` 保留（渲染验收面 + spec A/B 依据）。
    自 W3 起 piped 门禁只剩 pi_demo 一个。

## 全局不变量（每波每 commit 都必须满足）

1. `uv run pytest -q` 全绿（本组开工基线：**389 passed, 1 skipped**）。
2. `uv run python examples/pi_demo.py < /dev/null` 与 `uv run python examples/markdown_demo.py < /dev/null` 均 exit 0。
   W1/W2 期间 dump 内容变化属预期（空行/网格），W3 收尾统一重基线到本组 `ref/after-*.txt`。
3. 组件协议 `render(width) -> list[Line]` 冻结；流式安全（任意前缀渲染合法、行宽不超 width）不得回退。
4. 零新运行时依赖（pyproject dependencies 保持 `wcwidth` 唯一）；库与测试零 sleep。
5. 注释与文档用英文；commit 小写前缀 `feat:/fix:/refactor:/docs:/spec:`。
6. spec 归 lead 所有：agent 不改本组任何 spec 文件（完成信号 = 最终报告 + 分支 commit）。

## Git / worktree 协议

- worktree 根：`C:\Users\shifu\.worktrees\mocode-tui\<分支名>`，lead 统一创建与销毁。
- 分支从合并时刻的最新 main 创建；agent 不 merge、不 push、不 tag、不 checkout main、不碰主检出与其他 worktree。
- 每个 commit 独立过门禁；lead 用 `git merge --no-ff` 合并，合并前后各跑一次全量门禁。
- 其余细节遵循 spec-team SKILL 约定，不再重复。

## 环境事实

- Windows 10/11 x64 + Git Bash；agent 无交互 TTY，piped demo（`< /dev/null`）是唯一演示冒烟通道。
- worktree 里首次 `uv run` 会自建指向该 worktree `src/` 的 `.venv`，属预期。
- 仓库路径纯 ASCII；fixture 含 emoji/CJK，测试文件一律 `encoding="utf-8"`。

## 验收（终验，lead 收尾）

1. `uv run pytest -q` 全绿，用例数贴真实输出。
2. `ref/after-*.txt` vs `ref/before-*.txt` 逐节 A/B：块间空行、表格网格与内联、分割线 80 上限可见。
3. 渲染观感与 pi 截图逐节比对（结构/间距/配色/表格网格），偏差回对应工单修复后重合并。
4. 不 push、不 bump 版本；清理 worktree、保留分支；汇总报告（做了什么/取舍登记/遗留清单）。
