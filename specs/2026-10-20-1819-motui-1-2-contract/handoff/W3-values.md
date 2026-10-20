# W3 handoff · 值语义、缓存所有权与 selection 主题

## A · 交付

分支 `w3-values`；实现 commit（本 handoff 之前）：

| commit | 内容 |
|---|---|
| `a437bf0` | kernel：Pane 可变、ScreenLayout tuple、只读表、slots、Text 去 memo、Painter 行数、highlight style |
| `ca14ea9` | app：selection overlay 传 `theme.selection` |
| `d41049a` | docs：DESIGN/COMPONENTS 与 T1–T7 对齐的断言 |

`git diff --stat main...HEAD`：18 files changed, 367 insertions(+), 173 deletions(-)，无 golden 变化。

公开签名（新增/变更）：

```python
Pane                                      # @dataclass(eq=False)：身份相等/身份 hash，可变
ScreenLayout.rows/body_rows/row_blocks/block_order: tuple[...]   # __post_init__ 归一
Frame.with_pane_rows(pane_id, rows: Sequence[Line]) -> ScreenLayout
highlight(layout, selection, *, style: Style = SELECTION) -> ScreenLayout
FG_CODES: Mapping[str, int]               # MappingProxyType
Theme.notice_levels: Mapping[str, tuple[str, Style]]   # MappingProxyType
Style / Segment                           # dataclass(frozen=True, slots=True)
Painter.rows                              # paint 后恰好 screen.height 行
```

基线真实结果（HEAD `d41049a`，Windows）：

- `uv sync --locked`：Resolved 11 / Checked 10。
- pytest：**1742 passed, 2 skipped**（基线 1733 + 9 新用例）。
- golden：`golden: 11 pages match`。
- framebench：exit 0；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`（未变）。
- demo：`python -m motui < /dev/null` exit 0 / 70 行；`--pages` exit 0 / 792 行。

## B · 偏差、踩坑与约束

- `Pane` 用 `@dataclass(eq=False)` 而未加 `slots=True`（工单二选一）：全仓无 Pane hash/eq 依赖；
  保留 `__dict__` 避免给运行时对象增加额外风险。identity `==`/`hash` 生效。
- `ScreenLayout.block_order` 也在 `__post_init__` 归一为 tuple（工单要求“保持 tuple”；list 输入同样接受），
  四个行容器都不可变。
- `Painter.paint` 在**写入前**归一（不只保存前），超长 layout 不会被写到屏幕高度之外；非 live 路径同样归一，
  `painter.rows` 恒为屏幕高度。
- `Text.render` 现在每次重 wrap；`Block.rows` 的 sealed/open 缓存语义不变：sealed 按宽度缓存，
  open 仅在有 revision 时缓存，revision 变化失效（新测试覆盖）。`Text._rows` 保留为 last-render 几何。
- `highlight` 默认 `SELECTION` 不变；driver 传 `theme.selection`，与 `Find` 同 token。
- 测试改动（文件:行 → 旧→新）：
  - `tests/test_viewport.py`：`row_blocks` 断言 list→tuple；原“fresh list”测试改为 immutable tuple；
    新增 hand-built list 归一与四容器 tuple 测试。
  - `tests/test_frame.py`：pass-through 的 `composed.rows/row_blocks` 断言 list→tuple。
  - `tests/test_selection.py`：`before = list(layout.rows)`→`before = layout.rows`；新增 style 参数测试。
  - `tests/test_core_text.py`：memo 测试重写为“render 不记忆 + Block 缓存”；新增 revision 快照、
    Segment slots 测试。
  - `tests/test_style.py` / `tests/test_theme.py`：FG_CODES/notice_levels 只读、Theme hash/eq、slots 缓存。
  - `tests/test_painter.py`：短/长 layout 归一测试。
  - `tests/test_app.py`：selection overlay 使用 driver theme 的测试（首帧 reflow 会清 selection，先 paint 一次）。
- 未决（无阻塞）：framebench 墙钟在本机波动大（首次 stream-split 12.5ms vs 基线 4.7ms，复跑 11.7ms，
  全项同比变慢，疑似环境负载）；render-hash 未变，本波不做性能结论。

## C · 关键位置与稳定区

- `src/motui/kernel/frame.py:326`（Pane）、`:484`（split）、`:546`（close）、`:685`（_place）、
  `:1046`（_adopt）、`:1249`（compose）、`:1473`（with_pane_rows）。
- `src/motui/kernel/viewport.py:35`（ScreenLayout）、`:92`（__post_init__）、`:121`（layout）。
- `src/motui/kernel/style.py:44`（FG_CODES）、`:124`（Style）。
- `src/motui/kernel/theme.py:170`（notice_levels）。
- `src/motui/kernel/lines.py:75`（Segment）、`:418`（Text）、`:538`（render 无 memo）。
- `src/motui/kernel/painter.py:140`（paint 归一）。
- `src/motui/kernel/selection.py:198`（highlight style 参数）。
- `src/motui/app.py:165`（_SelectionOverlay）。
- 稳定区（未触碰）：`kernel/events.py`、`keys/**`、`widgets/**`、`tests/golden/**`、
  `docs/CONTRACT.md`、`pyproject.toml`、`uv.lock`、W2 的 driver/pane/dock 语义。
