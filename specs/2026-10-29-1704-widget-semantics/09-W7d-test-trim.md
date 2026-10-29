# W7d · 测试去重

> 分支 `w2.1.2-w7d-test-trim`；起点 main @ `c692c0b`。
> 写入范围：`tests/**`。不改 `src/`、`docs/`、`tools/`、`pyproject.toml`。
> 与 W7a/W7b/W7c 并行（目录不相交）。

## 目标

在覆盖不降的前提下，删除/合并重复测试，把收集数从 1838 减约 1/4
（目标 ~1380；硬下限 1400）。只删“同一契约被多个组件各测一遍”的重复，
不删独特行为。

## 前置上下文

- 必读：`tests/README.md`、`ref/interfaces.md` §10、本工单。
- 基线：

```bash
uv run pytest -q --collect-only 2>&1 | tail -1
uv run pytest -q -p no:cacheprovider
```

- 已有契约矩阵：`tests/widgets/test_contracts.py`（基类）、
  `test_contract_choice_nav.py`、`test_contract_text_form.py`。
- 不要改源文件；如果发现一个测试暴露了真实 bug，停下来报告，不要
  通过删测试“修”它。

## 去重清单（按类别）

1. **能力断言**：每个组件都重复 `focusable/clickable/hoverable/activatable`
   为 True/False 的用例 → 合并到契约矩阵的参数化；每族留一份。
2. **keymap rebind**：每个 cursor 组件各测一遍“实例 rebind 不污染类表”
   → 保留 `test_contracts.py` 的一份，删除 family 内的重复。
3. **surface/height-budget**：每个组件各测 `max_height=0/1` 和宽度
   → 合并到 `tests/test_invariants.py` 的矩阵；删除组件文件里的重复。
4. **纯改名断言**：只断言“新名字存在/旧名字不存在”的用例 → 删除；
   API 矩阵/签名测试覆盖。
5. **重复构造**：同一个 widget 在多个文件用同一构造和同一断言
   → 保留一个（优先 `test_contract_*`）。
6. **重复 golden**：同一场景被 demo 测试和 golden 测试各渲染一次
   → 保留 golden；demo 测试只断言状态/路由。

## 保留清单（不要删）

- 编辑/选择/撤销、mask、wrap、宽字符。
- 表格网格、排序、列宽、cell_wrap。
- 树的可见行、filter/jump、open/close。
- 滚动几何、sticky、reveal、thumb。
- Markdown block/inline 规则、Diff、语法高亮。
- 焦点/点击/拖拽路由、modal、overlay。
- 像素 Raster/quantize/palette、Drawing 生命周期。
- 每个组件的独特渲染字符（非重复的 golden/文本断言）。

## 工单

### T1 量化

- 跑 `uv run pytest -q --collect-only` 得到每文件用例数；按文件列出
  重复类别，先写一张删除/合并计划（可放 handoff）。
- 优先合并到一个参数化测试，而不是直接删覆盖。

### T2 执行

- 按计划改 `tests/**`；每个 family 一个 commit（`w7d: trim <family> tests`）。
- 每改完一个 family 跑该文件 + `tests/widgets/test_contracts.py`。
- 不改 `tests/golden/semantic/*`。

### T3 终验

- 目标收集数 ~1380（≤1400）；贴 before/after。
- 全量 pytest 全绿；semantic 9/9；api 244。
- `ruff check .` 全绿（tests 可能被 exclude；改动的测试文件单跑
  `--config "exclude=[]"`）。
- 在 handoff 里列出：删除/合并了哪些类别、每个 family 的 before/after、
  为什么剩余重复没有继续删（如有）。

## 验收

1. 全量 pytest 全绿；收集数 ≤1400。
2. semantic 9/9；api 244；ruff/pyright/lint-imports 全绿。
3. 没有源文件 diff。

## 禁触清单

`src/`、`docs/`、`tools/`、`pyproject.toml`、`tests/golden/semantic/*`。
`handoff/W7d-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W7d-<agent>.md`：before/after 用例数、每 family 的去重、
保留的独特覆盖、未继续删的原因、门禁真实结果。
