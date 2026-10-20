# W2 交接包 — the periphery
> 分支 `refactor/120-periphery` / 起点 `204be3d` / 2026-10-20

## A. 自动事实（命令与代码）

- `git diff --stat 204be3d..HEAD`（不含本文件）：9 files, +236 / -66。
  T1 `9fc6c24` interaction：`Scrollbar(track=glyphs.TRACK, thumb=glyphs.THUMB)`，旧模块常量删除；
  T2 `2d1d982` markdown：`Markdown(task_marks=(TASK_OPEN, TASK_DONE))` → `RenderContext.task_marks`
  → `ListRule`；`TODO_MARK`/`DONE_MARK` 删除；
  T3 `d4fa4ee` docs：DESIGN 宪章 Glyphs 一行、COMPONENTS 八个组件签名 + Scrollbar、CHANGELOG 1.1.9
  Added/Changed；`872adcc` tests：拆回被新测试吞掉函数头的 detach 用例；本文件首版 `8ddcba4`，
  最终修订是最后一个 commit。每个代码 commit 独立跑过五条门禁。
- 最终树门禁（真实输出）：`uv run pytest -q` → `1699 passed, 1 skipped`（基线 1693 + 6）；
  `uv run python tools/golden.py --check` → `golden: 11 pages match`（零重录）；
  framebench exit 0，`render-hash  : f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`；
  `python -m motui`（stdin DEVNULL）exit 0；`python -m motui --pages` exit 0。
- 旧常量清理证明：
  `grep -rnE "^(TRACK|THUMB|TODO_MARK|DONE_MARK|MARKER|EMPTY_MARK|FILLED_MARK|MORE_UP|MORE_DOWN)\s*=" src tests`
  只命中 `src/motui/kernel/glyphs.py:71-76`（词汇模块自己）；`TODO_MARK`/`DONE_MARK` 在
  `src/`、`tests/` 零命中；`scrollbar.TRACK/THUMB` 外部引用零命中。
- 文档声明抽查（代码行号）：
  ① 常量 `glyphs.py:50-80`；② `seat/seat_width/pair_seat` `glyphs.py:83-110`；
  ③ Scrollbar 默认 `scrollbar.py:190-191`；④ strip 用字形 `scrollbar.py:338-339`；
  ⑤ strip 记忆键含字形 `scrollbar.py:320-329`；⑥ Markdown 参数 `component.py:706`、
  ctx 字段 `context.py:38`、pair 座位 `nested.py:234`、空 pair 不建 marker `nested.py:240-241`；
  ⑦ 文档行 `docs/DESIGN.md:161`、`docs/COMPONENTS.md:177/194/195/196/211/213/214/215/601`、
  `CHANGELOG.md:36/65/70`。

## B. 只存在于脑子里的东西

- **T1 空字形语义（有意）**：滚动条没有“关闭”状态，`track=""`/`thumb=""` 保留 chrome 预算列
  （pane 仍在 `width - size` 处换行），但该列的 strip 行文本为空 —— 与 `size=0` 最接近的语义，
  不抛错、不缩 pane。测试 `test_an_empty_glyph_paints_the_reserved_column_empty` 钉死这一点。
- **T1 记忆键**：`track`/`thumb` 进了 `_strip_cache` 的 key（在 size/min_thumb 之后、styles 之前）。
  字形是构造输入，正常换字形要新建 bar，但 key 仍必须含它们；测试用私有槽位改写
  `_track/_thumb` 证明旧条不会被复用。未合并任何既有分段。
- **T2 pair 规则**：任务框用 `glyphs.pair_seat(glyph, other)`，不是裸 `f"{glyph} "`。
  默认 `☐/☑` 宽度相同，字节零变化；自定义宽度不等时两态共享较宽列（全局不变量 3）。
  动作跨度仍是「字形 + 座位空格（含补齐空格）」整段，`"todo:<n>"` 载荷不变。
- **T2 空 pair**：`task_marks=("", "")` 时 marker 文本为空，**不生成空 action Segment**，
  正文从 item 缩进开始；任务仍被识别（bullet 消失），但不可点。只空一个成员时仍按 pair
  补到另一个的座位（与 W1 的 `pair_seat` 语义一致）。
- **T2 续行缩进**：`strip` 从 `len(prefix_text)+len(marker_text)` 改为 `prefix_w`
  （`visible_width` 和），宽字形下续行缩进正确；`drop` 仍被源行前导空格数封顶，ASCII 源无副作用。
- **没有改 README**：grep 确认 README 只枚举组件名，不枚举参数/字形（`README.md:129-130`），
  工单的“若枚举则同步”条件不成立。
- **W1 的 NavList 语义照抄**（docs 已按 handoff 写）：`bar_space` 是 bar 列之后的 separator 宽度，
  `None` 派生 1 空格（`bar=""` 时 0），bar 列自身宽 = 字形 `visible_width`。
- **取舍（如实报告）**：strip 按预算列重复字形（`glyph * size`），CJK 宽字形会超出预算列，
  由 compositor 的 splice 裁掉；不引入 `fit`/省略号，因为滚动条字形是“单元格”而非文本，
  工单只要求空字形语义。`Line.styled()` 的分段未动。
- **测试增量**：T1 4 个（默认词汇、自定义/双列、记忆键、空字形；1693→1697）；T2 2 个（自定义
  pair + 空 pair，1697→1699）。插入 T1 测试时曾把相邻 `test_construct_registers...` 的函数头
  吞进空字形用例（测试仍绿但少一个独立用例），`872adcc` 已拆回——以后在长测试文件中间插入时
  检查 `grep -c "^def test_"`。
- **坑复述**：Windows/CRLF 照旧；`uv sync --locked` 解析到 CPython 3.13.16；golden 只对文本敏感；
  不要为了“整齐”合并 `Segment`。

## C. 指针

- Scrollbar：`src/motui/interaction/scrollbar.py:180-205`（构造/槽位）、`:288-343`（paint + key）。
- Markdown：`src/motui/widgets/markdown/component.py:689-760`（构造 → ctx）、
  `context.py:17-41`（字段）、`nested.py:205-260`（`_render_task`）。
- 契约矩阵/测试：`tests/test_scrollbar.py:214-280`、`tests/test_widgets_markdown.py:713-747`。
- 文档：`docs/DESIGN.md:161`、`docs/COMPONENTS.md:177/194-196/211/213-215/601`、`CHANGELOG.md:34-74`。
- 下一步建议：合并前由 lead 复核 docs 对 W1 六个组件的描述是否与最终代码一致（尤其 NavList）。
