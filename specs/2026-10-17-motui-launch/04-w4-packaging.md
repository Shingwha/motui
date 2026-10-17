# Spec MOTUI · W4：PyPI 上架件（波次 W4）

> 分支 `rl4-packaging`；worktree `C:/Users/shifu/.worktrees/mocode-tui/rl4-packaging`；
> 前置：W2 已合并；深读：`00-overview.md`（D5/D6/D8/D9）与 `ref/target-structure.md`
> 与 W3 **并行**：只写 `LICENSE`、`pyproject.toml`、`src/motui/__init__.py` 的版本行、
> 新增 `tests/test_packaging.py`、可选 `.github/workflows/ci.yml`。

## 目标

让这个仓**可以真的发布到 PyPI**：协议、元数据、版本、构建产物、安装后可跑——每一项都要有
可执行的证据（不是「应该没问题」）。本波**不** push、不打 tag、不执行发布。

## 工单（按序执行，每项一个 commit）

### T1 `LICENSE`

- MIT，全文标准文本；版权行 `Copyright (c) 2026 Shingwha`。
- 文件放仓库根。

### T2 `pyproject.toml` 元数据

在 W1 改名的基础上补齐（保持现有 `[dependency-groups]`、`[tool.pytest.ini_options]` 不动）：

```toml
[project]
name = "motui"
version = "1.0.0"
description = "…"            # 一句：分层全屏 TUI 工具包（block 文档 / alt screen / 视口滚动 / 可寻址组件）
readme = "README.md"
requires-python = ">= 3.12"
license = "MIT"              # PEP 639 表达式
license-files = ["LICENSE"]
authors = [{ name = "Shingwha" }]
keywords = [...]            # tui, terminal, text-ui, console, widgets, alt-screen, markdown, python
classifiers = [
  "Development Status :: 5 - Production/Stable",
  "Environment :: Console",
  "Intended Audience :: Developers",
  "Operating System :: OS Independent",
  "Programming Language :: Python :: 3 :: Only",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Topic :: Software Development :: Libraries :: Python Modules",
  "Topic :: Terminals",
]
dependencies = ["wcwidth>=0.2"]

[project.urls]
Homepage = "https://github.com/Shingwha/mocode-tui"
Repository = "https://github.com/Shingwha/mocode-tui"
Issues = "https://github.com/Shingwha/mocode-tui/issues"

[tool.hatch.build.targets.sdist]
exclude = ["/specs"]          # D8：过程资产不进 sdist，仓内保留
```

**不要**加 `[project.scripts]`：demo 的入口是 `python -m motui`（rich / textual 的惯例，见 `ref/demo.md` §1）。

注意：**不要**再写 `License :: OSI Approved :: MIT License` classifier（PEP 639 下与
`license = "MIT"` 冗余；hatchling 较新版本会报错）。URL 用 D9 的现有地址，不改。

### T3 `motui.__version__`

- `src/motui/__init__.py` 增加 `__version__`（不改 `__all__`，31 名不动）：
  从安装元数据读（`importlib.metadata.version("motui")`），并以
  `PackageNotFoundError` → 源码内置字符串兜底；
- 新增 `tests/test_packaging.py`：断言
  1. `motui.__version__ == "1.0.0"`；
  2. `pyproject.toml` 的 `version` 与 `__version__` 一致（用 `tomllib` 读，防漂移）；
  3. `__version__` 不在 `__all__` 里；
  4. `license` 表达式 / `license-files` / `readme` / `classifiers` 字段存在且 `License ::` classifier 不出现。
- 硬证据：`uv run pytest -q tests/test_packaging.py` 全绿。

### T4 构建与安装实证（本波的核心证据）

- `uv build` → 产出 `dist/motui-1.0.0.tar.gz` 与 `dist/motui-1.0.0-py3-none-any.whl`。
- **sdist 检查**：`tar -tzf` 列表里**不得**出现 `specs/`；应含 `src/motui/**`、`tests/**`、
  `README.md`、`LICENSE`、`pyproject.toml`、`uv.lock`（若有）。
- **wheel 检查**：列出 zip 内容，确认含 `motui/py.typed`、`motui-1.0.0.dist-info/LICENSE`、
  `motui-1.0.0.dist-info/METADATA`；读 METADATA 并贴出这些行的真实值：
  `Name: motui`、`Version: 1.0.0`、`Requires-Python: >=3.12`、`Requires-Dist: wcwidth>=0.2`、
  `License-Expression: MIT`、`Summary:`、`Classifier:` 若干、`Project-URL:` 三条。
- **干净环境安装冒烟**：在 worktree 外建一个临时 venv（`uv venv <tmp>`），
  `uv pip install --python <tmp>/... dist/motui-1.0.0-py3-none-any.whl`，然后：
  1. `python -c "import motui; print(motui.__version__)"` → `1.0.0`
  2. 跑一个最小 headless 会话（用 `motui.testing.headless_tui` + 一个 `Button` + 脚本键，
     把最终一帧 dump 出来），**证明装出来的轮子能真跑**（贴真实输出）。
  3. 再 `import` 一次深层门面（`motui.kernel`、`motui.widgets`、`motui.interaction`、`motui.keys`）
     证明命名空间在轮子里也在。
- 清理：临时 venv 与 `dist/` 不进 commit（`dist/` 已在 `.gitignore`）。

### T5（取消）CI 构建校验

**lead 决定取消**：`.github/workflows/ci.yml` 归 W5（它要改 demo 门禁的两行），两波并行时同一文件必冲突。
CI 里加「构建校验」这一步留作后续可选改进（发版工作流本身会 `uv build`，W4 的 T4 已有真实构建实证），
写进最终报告的遗留清单。

## 验收

1. `uv run pytest -q` 全绿（用例数 = W2 结束时 + `tests/test_packaging.py` 的新增数）
2. `uv build` 成功，且 T4 的四项检查（sdist 无 specs、wheel 内容、METADATA 字段、干净 venv 冒烟）逐条贴真实输出
3. `uv run python tools/golden.py --check` 仍 14 页 match（本波不改渲染）
4. `git grep -n "mocode" -- . ':(exclude)specs'` 仍为空

## 禁触清单

- `README.md`、`docs/**`（W3 负责；`docs/API.md` 是生成物，两边都不改）
- `tests/test_api_root.py`（W2 已定稿；版本断言走新文件）
- `src/**` 除 `__init__.py` 的 `__version__` 一行外一律不动
- `specs/2026-*` 历史目录
- 任何发布动作（push / tag / `uv publish` / `twine upload`）——**禁止**

## 最终报告格式

工单状态表（T1–T5 + commit hash）/ commit 清单 / 自测真实结论（含 METADATA 原文片段与冒烟输出）/
偏差与取舍 / 未决问题（必须含：PyPI 侧一次性配置清单、仓库改名后需要同步的字段）。
阻塞即停。
