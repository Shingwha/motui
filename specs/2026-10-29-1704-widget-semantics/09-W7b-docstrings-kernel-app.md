# W7b · Docstrings: app / kernel / terminal / demo

> 分支 `w2.1.2-w7b-docstrings-kernel-app`；起点 main @ `c692c0b`。
> 写入范围：`src/motui/app/**`、`src/motui/kernel/**`、
> `src/motui/terminal/**`、`src/motui/demo/**`、`src/motui/__init__.py`、
> `src/motui/__main__.py` 的 **docstring only**（零代码改动）。
> 与 W7a 并行：W7a 只碰 widgets/pixel/testing。

## 目标

同 W7a 的规则，基线 6692 行（app 2836 / kernel 2583 / terminal 958 /
demo 225 / root 90），目标 ≤ 3340 行。

## 前置上下文

- 必读：`ref/interfaces.md` §1–§9、本工单。
- 基线命令：

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/semantic.py --check
```

- 基线事实：1838 tests；semantic 9/9；api 244 names。
- 稳定区（勿读勿改）：`widgets/`、`pixel/`、`testing/`、`docs/`、`tests/`。

## 规则

- 模块：1–2 句职责 + 依赖边界。
- 类：≤6 行，渲染/状态不变量。
- 公开方法：≤6 行，非显然行为/返回/异常/副作用。
- 私有方法：默认删；只留隐藏约束 1–3 行。
- 禁止版本历史、参数复述、实现流水账、重复 CONTRACT/WIDGETS。
- 语态：类第三人称现在时；方法祈使句。
- 保留 `__all__`、类型、代码、空白；只改 docstring 字符串。
- 关键“为什么”（缓存键、sticky 滚动、行缓存、focus trap）压到 1–3 行保留。

## 工单

### T1 `kernel/`

基线：`frame.py` 781、`cell.py` 392、`layout.py` 351、`text.py` 227、
`document.py`/`selection.py`/`theme.py`/`style.py` 等。优先 frame/cell/
layout/text；公开值类型（Line/Surface/Style/Theme/Scroll/Viewport）的契约
句保留，实现细节删。目标 kernel ≤ 1300。

### T2 `app/`

基线：`workspace.py` 387、`overlays.py` 333、`scrollbar.py` 308、
`runtime.py` 283、`gesture.py` 272、`application.py` 220、`focus.py` 等。
保留生命周期/路由/焦点规则的“为什么”，删参数表和重复。目标 app ≤ 1400。

### T3 `terminal/` + `demo/` + root

- terminal 958 → ≤ 480；demo 225 → ≤ 120；root 90 → ≤ 40。
- demo 的 scene docstring 只保留“这个场景展示什么、键位、重置语义”。
- root `__init__.py` 的模块列表压到 2 段以内（curated face + layers）。

### T4 量测与门禁

```bash
uv run python - <<'PY'
import ast, pathlib
total=0
for base in ('src/motui/app','src/motui/kernel','src/motui/terminal','src/motui/demo'):
    for p in pathlib.Path(base).rglob('*.py'):
        if '__pycache__' in p.parts: continue
        tree=ast.parse(p.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                d=ast.get_docstring(node,clean=False)
                if d: total+=len(d.splitlines())
for p in (pathlib.Path('src/motui/__init__.py'), pathlib.Path('src/motui/__main__.py')):
    tree=ast.parse(p.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
            d=ast.get_docstring(node,clean=False)
            if d: total+=len(d.splitlines())
print(total)
PY
```

- 目标 ≤3340；贴 before/after。
- 全量 pytest、ruff（含改动文件 no-exclude）、pyright、lint-imports、
  semantic --check 全绿；api 244 names。

## 验收

1. docstring 统计 ≤3340。
2. 全量门禁全绿；semantic 9/9；api 244。
3. diff 只含上述目录的 .py 文件（外加 handoff）。

## 禁触清单

`src/motui/widgets/`、`pixel/`、`testing/`、`tests/`、`docs/`、`tools/`、
`pyproject.toml`。`handoff/W7b-<agent>.md` 是唯一例外。

## 交接包

写 `handoff/W7b-<agent>.md`：before/after、每目录最长 5 个 docstring、
保留的关键“为什么”、门禁真实结果。
