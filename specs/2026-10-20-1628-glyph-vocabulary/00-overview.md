# 00 · Overview — the glyph vocabulary

> 启动：2026-10-20 16:28（UTC+8）

## 目标

把全库的"结构字形"（光标、导航竖条、树枝指示、单选/多选标记、窗口计数、滚动条、任务框）
收敛成一个词汇：**字形是内容不是样式；一处命名常量；一个座位规则；每个字形一个构造参数，
空串即关闭且几何塌缩。** 无向后兼容（用户授权）。

## 非目标

- `Panel` 的边框六字形（`┌─┐│└┘`）：属于边框家族（Rich 的 `box=` 一类），另立项。
- `Tabs` 的指示器：是 SGR underline 属性，不是字形。
- 任何图标/emoji 词汇：超出结构标记的范畴。

## 波次

| 波 | 工单 | 分支 | 前置 |
|---|---|---|---|
| W1 | `01-W1-glyphs.md` — 词汇模块 + 六个行组件的参数化 | `refactor/120-glyphs` | main |
| W2 | `02-W2-periphery.md` — Scrollbar / Markdown / 文档 / CHANGELOG | `refactor/120-periphery` | W1 合并后（JIT 补前置上下文） |

W1 与 W2 文件不相交；W2 的文档描述 W1 的代码，所以串行。

## 全局不变量

1. **默认渲染逐字节不变**：golden 零 diff，render-hash 保持 `f872187a…`。
2. **座位规则唯一**：`seat(glyph)` = 字形 + 一个空格；宽度用 `visible_width`（禁用 `len`）；
   空字形 = 0 格，不留悬空空格。
3. **状态对按较宽者对齐**：`pair_seat(glyph, other)`。
4. **字形不带 band**：只染行文字样式；band 仍由 `fill` 铺在行下。
5. **每个字形参数进入所属组件的 `revision()`**（它们都是行输入）。
6. **旧模块常量无别名删除**，消费者在同一个 commit 更新。
7. 注释与文档英文；commit 风格 `area: statement -- reason`。

## 门禁（两级）

仓库没有快速测试子集、lint 或 typecheck，故 **commit 级 = 波次级 = 全量**：

    uv run pytest -q
    uv run python tools/golden.py --check
    uv run python -c "import re, subprocess, sys; done = subprocess.run([sys.executable, 'tools/framebench.py'], capture_output=True, text=True); sys.stdout.write(done.stdout); sys.stderr.write(done.stderr); raise SystemExit(0 if done.returncode == 0 and re.search(r'^render-hash  : [0-9a-f]{64}$', done.stdout, re.M) else 1)"
    uv run python -c "import subprocess, sys; raise SystemExit(subprocess.run([sys.executable, '-m', 'motui'], stdin=subprocess.DEVNULL).returncode)"
    uv run python -m motui --pages

## 回归红线

- `tests/golden/pages/` 零 diff；render-hash 不变。
- 每个 commit 独立过全量门禁，不留红色中间态。
- 写入范围外零 diff（handoff 文件是唯一例外）。

## 共享文件所有者

| 文件 | 所有者 |
|---|---|
| `src/motui/kernel/glyphs.py`（新） | W1 创建；W2 只读 |
| `src/motui/kernel/mark.py` | W1 |
| `src/motui/widgets/{list,choice,navlist,tree,table}.py` | W1 |
| `src/motui/interaction/scrollbar.py` | W2 |
| `src/motui/widgets/markdown/` | W2 |
| `docs/`, `CHANGELOG.md`, `README.md` | W2 |
| `specs/2026-10-20-1628-glyph-vocabulary/` | lead（worker 只写自己名下的 `handoff/`） |

## 接口索引

`ref/interfaces.md` — lead 在 W1 合并后回写为现实；W2 只读契约，不读实现。
