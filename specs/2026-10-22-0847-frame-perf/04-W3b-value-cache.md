# W3b · TextBuffer.value 缓存（M6）
> 分支 `fp-w3b-value-cache`；前置 W1 已合并（`789da41`；与 W2 并行，文件级不相交）；写入范围 `src/motui/widgets/textbuf.py`、`tests/widgets/`（textbuf/field 所在既有文件）

## 目标

`TextBuffer.value`（textbuf.py:198-201）从"每次访问全文 join"改为按 `version` 缓存
（D6 已有的单调计数），任何编辑置脏。下游每键读 `editor.text` 的宿主不再 O(全文)/键。
语义不变：同样的调用序列返回同样的字符串。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` → 本工单（无前置 handoff 依赖；
  W1 的改动不触及 widgets/**）。
- 基线命令（开工先跑，贴真实输出）：`uv run pytest tests/widgets -q`（全绿）；
  `uv run pytest -q`（897 passed）。
- 稳定区（已验收，勿重读）：`core/**`、`app/**`、`tools/**`、`tests/core/**`、`tests/app/**`。
- 已知约束/坑：
  - `lines` 是公开可变属性（`__slots__` 直存），热路径（编辑方法）高频读写——**不改成
    property**（P8），不为防御第三方付每次访问成本。
  - lead 已核实 motui 内部无对 `TextBuffer.lines` 的外部就地改动/整体赋值
    （`markdown/blocks.py` 的 `self.lines` 是另一类）。worker 开工时用
    `grep -rn "\.lines\[" src/motui` + 各 TextBuffer 消费文件复核一遍，结论写进报告。
  - `_version` 契约（textbuf.py:219-230）：每次内容变更 +1（insert/backspace/delete/
    newline/clear/undo/redo/选区删除），移动/选区不 +1。`value` 缓存键就是它。
  - `set_text`（:551 附近 `self.lines = text.split("\n")`）与 `clear`（:532）必须置脏——
    确认它们 bump version（若不 bump，那是既有 bug，停下上报，不自行改语义）。

## 工单（按序执行，每项一个 commit）

### T1 `value` 按 version 缓存

- 做什么：`__slots__` 加缓存槽（如 `_value_cache: str | None` + `_value_version: int`，
  或直接键值对）；`value` 属性：version 命中返回缓存，否则 join、存、返回。docstring
  讲清"缓存键 version；直接改 `lines` 不 bump version，`value` 不跟随"（P8 措辞）。
  编辑方法零改动（它们已 bump version）。
- 只允许改：`src/motui/widgets/textbuf.py`。
- 验证：`uv run pytest tests/widgets -q` 全绿。

### T2 新增测试（≤ 4 条，落在既有文件）

- 覆盖：重复读返回同一对象（缓存命中、无重复 join——可用对象同一性断言）；一次编辑后
  value 更新且再命中；undo/redo 后正确；`set_text` 后正确。textbuf 的测试在哪个既有
  文件开工时确认（`tests/widgets/` 下找 textbuf/field/form 相关），不新建文件。
- 只允许改：`tests/widgets/` 下那一个既有文件。
- 验证：`uv run pytest tests/widgets -q` 全绿。

## 验收

1. 波次级全量门禁（贴真实输出）：`uv run pytest -q`（897 + 新增 passed）；
   `golden: 57 topics match`；framebench `render-hash` 逐字 `a82f7968…`（本波理论上
   不触渲染路径，跑一遍确认）。
2. `git diff main --stat` 只含 `widgets/textbuf.py` + 一个测试文件。

## 禁触清单

`core/**`、`app/**`、`widgets/` 下除 `textbuf.py` 外的一切、`tools/**`、`docs/**`、
`tests/core/**`、`tests/app/**`、`pyproject.toml`、`CHANGELOG.md`。handoff 文件是唯一
允许的写入范围外文件。

## 交接包

完成后在分支最后一个 commit 写 `handoff/W3b-c.md`。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验（无前置，写"无"）/
探索审计 / 未决问题。

## 依赖

仅 W1 合并（无代码依赖，逻辑上独立成波以保持文件级不相交）。
