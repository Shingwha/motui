# W7a · Docstrings: widgets / pixel / testing

> 分支 `w2.1.2-w7a-docstrings-widgets`；起点 main @ `c692c0b`（W6 合并）。
> 写入范围：`src/motui/widgets/**`、`src/motui/pixel/**`、
> `src/motui/testing/**` 的 **docstring only**（零代码改动）。
> 与 W7b 并行：W7b 只碰 app/kernel/terminal/demo/root，目录不相交。

## 目标

把 widgets/pixel/testing 的 docstring 从“论文”改成“契约卡”，基线 6312 行
（AST 统计），目标 ≤ 3150 行（约减半）。

## 前置上下文

- 必读：`ref/interfaces.md` §1–§8（新契约）、本工单。
- 基线命令：

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/semantic.py --check
```

- 基线事实：1838 tests；semantic 9/9；`api.py --check` 244 names。
- 稳定区（勿读勿改）：`kernel/`、`app/`、`terminal/`、`demo/`、`docs/`、`tests/`。

## 规则

- 模块 docstring：1–2 句，说明职责 + 依赖边界。
- 类 docstring：≤ 6 行，说明渲染什么 + 关键不变量。
- 公开方法/属性：≤ 6 行；只写非显然行为、返回/异常、状态副作用。
- 私有方法：默认删掉 docstring；只有隐藏约束/坑点才留 1–3 行。
- 禁止：版本历史（1.x/2.0/W1/W2…）、参数复述、实现流水账、重复
  `docs/CONTRACT.md`/`docs/WIDGETS.md` 已写的契约。
- 语态：类用第三人称现在时；方法用祈使句。
- 保留 `__all__`、类型、代码、空白行为不变；只改字符串字面量 docstring。
- 如果某段 docstring 是唯一解释某个非显然算法的注释，压到 1–3 行而不是
  全删。
- 不要为了凑行数删除“为什么”的约束说明；删的是复述和流水账。

## 工单

### T1 `widgets/` 大文件优先

按 docstring 行数从高到低处理（基线）：`table.py` 533、`textfield.py` 482、
`textbuf.py` 388、`markdown/component.py` 382、`choice.py` 354、`layout.py` 351、
`dialog.py` 266、`diff.py` 258、`tree.py` 239、`base.py` 235、`list.py` 226、
其余 ≤200。每改完 3–4 个文件跑一次对应测试。

### T2 `widgets/` 其余 + `pixel/` + `testing/`

- `pixel/` 112 行、`testing/` 132 行，按同一规则压到 ≤ 60/≤ 70。
- 保留 `Raster`/`PixelPalette`/`Marker` 的公开契约句；删实现细节。

### T3 量测与门禁

- 用下面的脚本量总行数（只统计 `src/motui/widgets|pixel|testing`）：

```bash
uv run python - <<'PY'
import ast, pathlib
total=0
for base in ('src/motui/widgets','src/motui/pixel','src/motui/testing'):
    for p in pathlib.Path(base).rglob('*.py'):
        if '__pycache__' in p.parts: continue
        tree=ast.parse(p.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                d=ast.get_docstring(node,clean=False)
                if d: total+=len(d.splitlines())
print(total)
PY
```

- 目标 ≤ 3150；贴 before/after。
- 全量 pytest、`ruff check .`、改动文件 no-exclude ruff、`pyright`、
  `lint-imports`、`semantic.py --check` 全绿。
- `api.py --check` 必须仍是 244 names（docstring 不改签名）。

## 验收

1. docstring 统计 ≤3150，贴真实数值。
2. 全量门禁全绿；semantic 9/9；api 244。
3. `git diff --stat` 只含 `src/motui/widgets|pixel|testing` 的 .py 文件
   （外加 handoff）。

## 禁触清单

`src/motui/kernel/`、`app/`、`terminal/`、`demo/`、`src/motui/__init__.py`、
`tests/`、`docs/`、`tools/`、`pyproject.toml`。
`handoff/W7a-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W7a-<agent>.md`：before/after 行数、每目录剩余最长的 5 个
docstring、哪些“为什么”说明被保留、门禁真实结果。
