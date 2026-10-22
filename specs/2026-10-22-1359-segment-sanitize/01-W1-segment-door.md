# W1 · Segment 门净化（内容与指令的分界）
> 分支 `ss-w1-segment-door`；前置 无；写入范围 `src/motui/core/lines.py`、`tests/core/test_lines.py`、`docs/DESIGN.md`

## 目标

`Segment` 构造点成为内容/指令的唯一分界：`text` 与 `link` 净化为 "cells only"
（C0 含 `\n`/`\r` 与 DEL、C1 删除；`\t` 归一为一个空格），注入的终端控制序列从字节流
中消失；正常内容渲染字节零变化（golden / render-hash 逐字不变）。
**这是把字节路径补齐到 motui 自己的 cell 模型（`visible_width` 把控制符算 0 列），
恢复 `ansi.py` 的 escape 独占宪法——一处收口，全仓生效，不加逃生门。**

## 前置上下文

- 必读顺序：`specs/2026-10-22-0847-frame-perf/ref/repo-map.md`（复用）→
  `ref/security-checklist.md`（需求文档；**注意 lead 已推翻其 5.1 的"保留 \t"**，以
  本工单 S3 为准）→ `specs/2026-10-22-1359-segment-sanitize/00-overview.md`（S1–S8 拍板表）→ 本工单。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest -q`（909 passed）；
  `uv run python tools/golden.py --check`（57 topics）；`uv run python tools/framebench.py`
  隔离跑（`render-hash` = `a82f7968…`；记下 `idle-long` / `text-open` 作净化前哨兵基线）。
- 关键代码事实（lead 已核验）：
  - `Segment` 是 `@dataclass(frozen=True, slots=True)`（lines.py:76 附近），`text` 直存
    调用方字符串，无 `__post_init__`；`_width` 是 `init=False` 的派生缓存（构造后经
    `visible_width(self.text)` 惰性求值——净化发生在任何度量之前，宽度自动一致）。
  - 字节路径 `_segment_bytes`：`prefix + seg.text`，link 走 `hyperlink_open(link)` OSC 8 包裹。
  - `with_style()` 重建 Segment（lines.py:120 附近）——净化幂等，重建自动过门。
  - `Line.from_text` 直构 Segment（lines.py:163-167），绕过 wrap 层的 `_normalize_tabs`
    ——S3 的 tab 归一在门上补齐这条缝。
  - `text.py:_normalize_tabs`（:44 附近）："every tab becomes one space"、TAB_WIDTH=1、
    "no tab stops exist"——S3 与它同义，不是新规则。
- 已知约束/坑：
  - **不用 `str.isprintable()` 做判定**（S2）：它把 ZWJ（U+200D）等 Cf 判为不可打印，
    会摧毁 emoji ZWJ 序列。显式 C0+DEL+C1 集对组合标记/肤色/ZWJ 零影响。
  - Segment 的 eq/hash 基于 `(text, style, link)`：净化后"控制符不同但可见内容相同"的
    两段变相等——这是**期望行为**（frame.py 的行备忘录键因此更稳），不必特殊处理。
  - `\r` 可能出现在粘贴文本的行内（`\r\n` 分行后残留）：0 列、删除后不可见，布局不变。
  - framebench 计时对 CPU 竞态敏感：验收数字隔离跑（安静窗口判据 idle-long ≤ 0.7）。

## 工单（按序执行，每项一个 commit）

### T0 预检：fixtures 与测试内容的 tab/控制符审计

- 做什么：审计 golden fixtures（`tests/golden/`）与既有测试内容中，是否存在经
  `Line.from_text`/直构 Segment 进入渲染字节 的裸 `\t` 或 C0/C1/DEL 字符
  （可用临时探针在 `_segment_bytes` 前打印命中，跑一遍 golden 生成路径与 pytest；
  探针用完即删，不提交）。预期零命中（wrap 路径早已归一）；**若有命中**：该内容的字节
  将合法变化（tab→空格），停下上报 lead 定夺（是否属"需要重录 golden"的例外），不自行重录。
- 只允许改：无（只读 + 临时探针，不进 commit）。
- 验证：审计结论（零命中或命中清单）写进最终报告。

### T1 `Segment` 门净化

- 做什么（lines.py）：
  - 模块级私有：控制集正则（S2 的显式集合，如 `_CONTROL_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")`）
    与净化函数（如 `_cells_only(text)`）：先 `"\t" in text` 则 `replace("\t", " ")`；
    正则 `search` 未命中返回原串（零分配快路径）；命中则 `sub("", text)`。docstring 讲清
    契约与理由（内容是 cells；escape 只由 ansi.py 构造；宽度不变论证：0 列删除 + tab 1 列换 1 列）。
  - `Segment.__post_init__`：`object.__setattr__` 净化 `text`；`link` 非 None 时同门净化
    （净化后为空串时置 None 还是保留空串——选**置 None**：空链接没有 OSC 8 意义，
    docstring 说明）。`Segment` 类 docstring 增补"cells only"契约段。
- 只允许改：`src/motui/core/lines.py`。
- 验证：`uv run pytest tests/core -q` 全绿；`uv run python -c` 冒烟复现安全文档 §2.1
  （`Line.from_text("OUT: \x1b[?1000l\x1b[?1006l").styled()` 不含 `\x1b`）。

### T2 新增测试（≤ 4 条，落 `tests/core/test_lines.py`）

- 覆盖：
  1. 注入消除：`Segment("a\x1b[?1000lb").text == "ab"`；`Line.from_text` 后 `.styled()`
     字节不含 `\x1b`（含 OSC 52 / OSC 0 形态各断言一次）。
  2. tab 归一：`Segment("a\tb").text == "a b"`（与 `_normalize_tabs` 同义）。
  3. link 净化：`Segment("x", link="\x1b]8;;evil").link is None`。
  4. 端到端：安全文档 §2.2 的脚本改写为断言——恶意 Document 经
     `Painter(HeadlessScreen).paint` 后 `screen.output` 不含 `\x1b[?1000l` / `\x1b]52;` /
     `\x1b]0;`（若需要 Raw 测试替身，参考 tests/testing 的 doubles 风格）。
  幂等（`with_style` 后仍净）并入 1 或 2 断言，不占独立条目。
- 只允许改：`tests/core/test_lines.py`。
- 验证：`uv run pytest tests/core/test_lines.py -q` 全绿。

### T3 docs/DESIGN.md 契约段

- 做什么：在内容模型相关章节（Segment/Line 所在节）增补契约段："rendered text is
  cells, never terminal commands; escapes are constructed only by ansi.py; a tab
  normalizes to one space at the Segment door"。措辞与仓库 docstring 风格一致，讲
  为什么（安全边界 + 与宽度模型自洽），不写实现细节。
- 只允许改：`docs/DESIGN.md`。

## 验收

1. 波次级全量门禁（贴真实输出；framebench 隔离跑）：
   - `uv run pytest -q`：909 + 新增 passed，0 failed；既有测试零修改。
   - `golden: 57 topics match`（不重录）。
   - `render-hash` 逐字 `a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`；
     `idle-long` / `text-open` 相对开工基线不回退；其余行漂移带内。
2. 端到端抽验：T2 的第 4 条测试即是；另跑安全文档 §2.2 原脚本确认断言成立。
3. `git diff main --stat` 只含写入范围文件（lines.py、test_lines.py、DESIGN.md）+ handoff。

## 禁触清单

`core/ansi.py`、`core/painter.py`、`core/text.py`、`core/screen.py`、`core/block.py`、
`core/viewport.py`、`core/frame.py`、`app/**`、`widgets/**`、`tools/**`、`tests/` 下除
`tests/core/test_lines.py` 外的一切、`pyproject.toml`、`CHANGELOG.md`（lead 收尾统一写）、
`specs/2026-10-22-0847-frame-perf/**`。handoff 文件是唯一允许的写入范围外文件。

## 交接包

完成后在分支最后一个 commit 写 `specs/2026-10-22-1359-segment-sanitize/handoff/W1-d.md`：
A 节贴门禁与哨兵行前后对比；B 节写净化函数最终形态、快路径实测（构造开销）、
T0 审计结论、与安全文档的偏差清单。

## 最终报告

工单状态表 / commit 清单（hash + message）/ 自测真实结论（含 T0 审计结论）/
偏差与取舍 / 交接校验（本波无前置，写"无"）/ 探索审计 / 未决问题。
