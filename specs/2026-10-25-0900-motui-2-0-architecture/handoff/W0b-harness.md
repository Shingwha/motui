# W0b 交接 · 模拟器、工具与静态护栏（不改变行为）

> 分支 `2.0/w0b-harness`；起点 `2eaf839`（W0a 合并后）。前置：`handoff/W0a-values.md`。
> 结论：T1–T6 全部完成；1002 旧用例 + 15 新用例 = **1017 全绿**；57 golden 与 render-hash 不变；ruff / pyright / lint-imports / api / growth 全绿。

## A. 交付面与门禁

### diff（`git diff --stat main...HEAD`）

```
 .github/workflows/ci.yml                      |  15 +
 pyproject.toml                                |  63 ++++
 src/motui/kernel/cell.py                      |  38 +-
 src/motui/kernel/layout.py                    |   8 +-
 src/motui/{testing.py => testing/__init__.py} |  14 +-
 src/motui/testing/emulator.py                 | 488 +++++++++++
 tests/testing/test_api_tool.py                |  66 ++++
 tests/testing/test_emulator.py                | 143 +++++
 tests/testing/test_growth_tool.py             |  28 ++
 tools/api-2.0.txt                             | 189 +++++++++
 tools/api.py                                  | 201 +++++++
 tools/growth.py                               | 239 ++++++++++
 uv.lock                                       | 191 ++++++++++
```

### 新增公开面

- `motui.testing` 由模块改为包（`git mv` 保留历史）；`__all__ = ["Emulator", "ScriptedEvents", "headless_tui", "snapshot"]`，`from motui.testing import headless_tui, snapshot` 不变。
- `Emulator(width=80, height=24)`：`grid` / `cursor: Pos` / `feed(str|bytes)` / `text()` / `cell(x,y)` / `sgr_at(x,y)` / `resize(w,h)` / `width` / `height`；`Cell(char, style, link)` 是 emulator 自己的冻结值。
- `tools/api.py`：`--check` / `--update` / `--check --allow-additions` / `--snapshot PATH`；快照 `tools/api-2.0.txt` 共 189 名。
- `tools/growth.py`：默认全量；`--quick`（tests/kernel + golden）、`--keep`（保留探针目录）。
- `pyproject.toml`：dev 组加 ruff/pyright/import-linter；`[tool.ruff]` / `[tool.pyright]` / `[tool.importlinter]`。
- `.github/workflows/ci.yml`：ruff/pyright/import-linter 在 pytest 前，api/growth 在 golden 后；仍为 ubuntu + windows、Python 3.12。

### 门禁实测（2026-10-25，本 worktree）

- `uv sync --locked`：Resolved/Checked 20 packages；`import motui` 指向本 worktree `src/motui/__init__.py`。
- `pytest -q -p no:cacheprovider`：**1017 passed**（1002 旧 + emulator 10 + api 4 + growth 1）。
- `tools/golden.py --check`：**57 topics match**。
- `tools/framebench.py`：`render-hash a82f7968ed986ef2fa99bb9ec25e724b99ca03e26aa75f607e6219ee25a4f379`（不变）。
- `ruff check .`：All checks passed（0）。
- `pyright`：0 errors, 0 warnings（strict；kernel/testing/tools）。
- `lint-imports`：`kernel has no I/O KEPT` / `kernel is a leaf KEPT`，2 kept / 0 broken。
- `tools/api.py --check`：`api: 189 names match`。
- `tools/growth.py`（全量）：副本 pytest **1017 passed**、golden **57 topics match**、api `189 names present, 0 additions, signatures unchecked`、`growth: OK (full probe)`。
- 反向演练：kernel/geom.py 临时 `import os` → `kernel has no I/O BROKEN`（1 broken，exit 1），恢复后 2 kept；篡改快照一行 → `~ motui:App (shape changed)`（exit 1），`git checkout` 后 189 match。
- `python -m motui < /dev/null`：exit 0，70 行；`python -m motui --pages`：exit 0，4059 行。

## B. 偏差与取舍

1. **模拟器支持面**：CUP（`H`/`f`）、EL（`K` 0/1/2）、ED（`J` 0/1/2/3）、SGR（0/1/2/3/4/7/9、22/23/24/27/29、30-37/40-47/90-97/100-107、38/48 的 `5;n` 与 `2;r;g;b`、39/49）、`\r \n \b \t`、自动换行、DECSET/DECRST（`?1049` 清屏归位、`?2026` 忽略、鼠标/粘贴/焦点忽略）、OSC（BEL/ST；OSC 8 记录 link）。字节走 UTF-8 增量解码，分片可落在序列或码点中间。
2. **换行语义**：立即换行（无 pending-wrap）；末行 LF 上滚一行并丢弃顶行（无 scrollback）。Painter 每行都用 CUP，帧不受影响；测试固定该行为，20 列喂 40 个 A 显式断言第 0 行 20、第 1 行 20、第 2 行空。
3. **T1 包化**：T1 先给可实例化的网格骨架，T2 补解析器；两项各自可跑绿。
4. **`tools/api.py`**：工单签名外加 `--snapshot PATH`（测试与演练用临时副本）；`--allow-additions` 只比较 `(module,name)`，删除必失败（有单测）；kind 判定顺序 module→class→function→value。
5. **`tools/growth.py` 复制面**：工单列 src/tests/tools/pyproject；实际多复制 `LICENSE`、`README.md`（`tests/test_packaging.py` 会读）。pytest 前先把**副本内**快照 `--update`（套件自身精确比对），再恢复原快照跑 `--check --allow-additions`，确保增长是对“旧快照”成立的。失败打印临时目录，`--keep` 保留。
6. **ruff ratchet**：全局 `exclude` = `specs`、`src/motui/{core,widgets,app,demo,__init__.py}`、`tests/{core,widgets,app,golden}`；`per-file-ignores` = `tests/kernel/test_surface.py` I001、`tests/testing/clock.py` UP037、`tests/test_invariants.py` I001+E501、`tools/framebench.py` E402+F401+I001。清理波次：core→W1、root facade→W2、widgets→W3、app→W4、demo/framebench→W5；kernel 测试 I001 与 clock UP037 随 W2.5/W1。未批量 `# noqa`，未全局忽略 E501。
7. **pyright 收敛**：`include` 仅 kernel/testing/tools，`strict`；`ignore` 仅 `tools/golden.py`、`tools/framebench.py`（禁触的 1.x 工具，W5 收编）。`tools/api.py`/`growth.py` 用 `callable` 收窄、`cast(Sequence[object])`、`DESCRIPTION` 常量消错，无 `# type: ignore`。
8. **kernel 最小改动（T5 允许范围）**：10 处 UP037 去引号（future annotations 下无行为变化）；`Line` 的 3 个 slot 注解 + `text/width` 改用局部变量返回（同一缓存语义）；`_text_width` 去掉 `wcswidth` 不会返回的 `None` 分支（负数分支保留）。未改任何 1.x 文件。
9. **未决**：SGR 的 `:` 子参数未解析；无行回卷历史/图片协议/终端查询；`--allow-additions` 的“新增名字”实演要等真实增长（本次探针只改签名）；W1 后 `motui.core` 消失时需 `--update` 快照。

## C. 位置与 commit

- `src/motui/testing/emulator.py:73` Cell、`:128` Emulator、`:164` feed、`:378` SGR、`:464` text、`:474` resize；`src/motui/testing/__init__.py:28` 导出。
- `tools/api.py`（模块契约见文件头）、`tools/growth.py`、`tools/api-2.0.txt`。
- 测试：`tests/testing/test_emulator.py`、`test_api_tool.py`、`test_growth_tool.py`。
- 配置：`pyproject.toml:45` dev 组、`:66` ruff、`:94` pyright、`:101` importlinter；`.github/workflows/ci.yml:43`。
- commit：`b05387d` testing 包化、`e43b16d` Emulator、`113946e` api 快照、`71b0c42` growth、`5f6e963` 静态门、`1883489` CI、本文件（最后一个 commit）。
