# ref：lead 已核实的事实（本组三个 code agent 都只信这份与工单本体）

## 环境与门禁（2026-10-17，main `dae2e7a`）

- Windows 10 / Git Bash；`uv 0.12.21`；venv Python `3.13.16`（`.venv/Scripts/python.exe`）。
- worktree：`C:\Users\shifu\.worktrees\mocode-tui\<分支>`；主检出 `C:\Users\shifu\Desktop\mocode-tui`。
- 基线：`uv run pytest -q` → **1407 passed, 1 skipped**；`golden: 11 pages match`；
  `apidoc: API.md matches the facades (169 entries)`；
  `framebench --frames 40` 的 `render-hash = de48e7473754188e1d68b5520979be3c0cda9b18ab8f3c3170234ed98cb15122`
  （改前 `stream-single` 4.5 / `stream-split` 10.6 / `scroll` 2.7 / `scroll-long` 15.9 / `replay` ~300 ms）。
- demo：`uv run python -m motui < /dev/null` exit 0；`--pages` 11 页。

## 架构事实（决定"每帧"是什么意思）

- 一帧 = `TUI.paint()` → `Frame` 布局 → 每个可见块 `render(width)`；SEALED 块的行被缓存，
  **OPEN 块每帧真重渲**。悬停/鼠标移动 → `tui.invalidate()` → 重画（`interaction/pointer.py:29`），
  所以"每帧"≈"每次鼠标移动"。
- **全仓 `src/` 里 `seal()` 一次也没被调用**（只有 `tests/` 用）→ 现实里每个块都是 OPEN，
  "sealed 才缓存"这条优化默认没生效。这是本组要动的根。
- 缓存今天归 `Viewport`：`_cache`/`_cache_width`（`kernel/viewport.py:83-84`）、
  `_block_rows`（`:248-265`）、`_prune_cache`（`:228-246`）。`_prune_cache` 的 docstring 说
  "at the cache's own size rather than the document's"，代码却每帧构造 `{id: block}` 全量 dict
  ——**docstring 与代码相反**（frame-budget 规范声称已消除的那次 O(document) 构造还在）。
- `Block` 今天没有任何缓存：`__slots__ = ("_component", "_id", "_pin", "_state")`（`kernel/block.py:179`），
  `Block.render(width)` 直通组件（`:223`）。
- `tests/test_viewport.py:175-196` 用调用计数钉住：sealed + 同宽度 → 只渲一次；换宽度 → 重渲一次。
  **这条断言不许改**。
- `kernel/selection.py:283`（`extract`）、`app.py:210-211`（`reveal`/`_body_address`）、
  `interaction/search.py:259`（`Find._recompute` 逐块）、`interaction/gesture.py:367/600/616`
  （双击与拖动 `_walk`）都是**裸 `block.render(width)`** —— 5 处绕开缓存。
- `widgets/decor.py:195`（Panel）、`widgets/layout.py:149` 等容器每帧把子组件的行再 fit/pad 拼接。

## 组件的可变字段（决定快照怎么写）

- `Text`：`text`/`style`/`hover` 是裸字段，另加 `_hover_span`/`_hover_style`/`_rows`
  （`kernel/lines.py:432-437`）。`render` 每次都跑 `_rows_for` → `wrap_text` 全文（`:481-500`）。
- `Table`：`self.rows = [list(row) for row in rows]`（`widgets/table.py:234`）——**宿主可原地改**，
  所以快照必须存副本（`rows == cached` 因同一对象恒真，探不到原地修改）。
- `TextBuffer.visual_rows(width, indent)`（`widgets/textbuf.py:620`）逐行走 `wrap_spans`；
  `Editor.render`（`widgets/field.py:320`）先全量 `visual_rows` 再切窗口。

## lead 实测的改前基线（`ref/probe.py` 原样跑出来的）

```
A. sealed 200 行：无 chrome 0.075 ms/帧 | +Scrollbar 0.987 ms/帧（13.1×）
B. Text 3000 行：render(80) 29.21 ms；SEALED 帧 0.071 ms；OPEN 帧 29.44 ms
C. Table 60×6 render 5.77 ms；240×6 render 24.24 ms；60×6 OPEN 帧 5.92 ms
D. Editor 3000 行（max_rows=20）：冷 9.46 ms；暖 9.10 ms；move_down 9.34 ms/键
E. Markdown 单段流式：200 次追加 307 ms；400 次 1234 ms（二次）
F. 100 个 sealed 块 0.120 ms/帧；1000 个 0.494 ms/帧
I. Markdown 2000 行 render 0.90 ms；Panel(Markdown) render 36.71 ms
F1..F4 sealed 块的 hover 落屏：全部 False（bug）
```

## 审计 agent 提供的、我未逐条复现的数字（引用时注明来源）

（两位只读审计员，脚本在 `%TEMP%\motui_bench*.py`、`%TEMP%\hot*.py`；量与我的同量级）

- 滚动条 24×（180×45、spec fixture、2.60 ms/帧）；垂直 split 1.98 ms/帧。
- `Markdown` 命中路径 1.6 ms/帧 @2000 行（`_stamp_tasks` 0.66 + `_span_index` 0.94）；宽度来回抖
  22.2 ms/次（单条目缓存）。
- 语法高亮 2000 行 51.7 ms/次全染；`Find` 每键 21–24 ms、打开期间 0.9–1.9 ms/帧；
  `reveal` 14.7 ms；`extract` 15–17 ms；gesture `_walk` 16.4 ms/次；selection overlay 457 µs @1000 块；
  10 个 toast +378 µs/帧；`Stats` +80 µs/帧；band 内 OPEN 块每帧渲两遍（`app.py:676` + `:1126`）。
- `List` 前缀跳转 4.94 ms/键 @100k 项（P2，本组不做）；`Tree` 12200 可见节点 35 ms/帧、
  `Radio` 1000 标签 2.4 ms/帧（窗口化是遗留项）；`Select` description 列 0.92 ms @10k 项（不做）。

## 本组不做（写进报告，别顺手做）

`Table`/`Tree`/`Radio` 的真窗口化（需要"块知道窗口"的新协议）；`List` 的跳转索引；
`Select` description 列记忆；`Spinner` 在 sealed 块里冻结算不算 bug（未决）；
`Band` 双渲染那一笔（W3 若要顺带修，必须证明输出字节不变，否则留到下一组）。
