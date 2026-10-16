# Spec tui-depth · W4 搜索（波次 W4）
> 分支 `td4-search`；前置：W3；深读：`00-overview.md`（D10）。
> **最高约束：搜索是 assembly tier 的控制器 + overlay（照 `Palette`/`Toasts` 形态），不自带回调；
> 「滚到指定块行」是通用能力（`Viewport.scroll_to` / `TUI.reveal`），不为搜索开洞。**

## 目标

1. `Viewport.scroll_to(offset)` 与 `TUI.reveal(bid, row)`（滚到指定文档行/块行）。
2. 新 `mocode_tui/search.py` 的 `Find`：自带查询行（`Input`）、全量匹配、overlay 高亮、
   `enter`/`down` 下一个、`up` 上一个、`escape` 关闭、reveal 当前匹配。
3. gallery 宿主键 `c-f` 接线 + 文档 + 测试。

## 背景（锚点）

| 事实 | 位置 |
|---|---|
| `Viewport` 只有 `scroll_up/down/to_bottom`；`offset` 只读 | `core/viewport.py:267-300` |
| `TUI` 滚动 façade 与 `add_band`/`get`；pane/document 模型 | `app.py:388-398,516-540` |
| 选择高亮纯函数（可对任意地址区间复用） | `core/selection.py:198-251` |
| `Palette` 的「自带查询行」形态与 overlay 生命周期 | `widgets/palette.py`；`examples/gallery/shell.py:211-217,245` |
| `read_key` 先截 `scroll_keys`（wheel 到不了 `handle`） | `app.py:763-772` |
| gallery 宿主键表与 dispatch order | `examples/gallery/session.py:46-57,97,276-331` |
| 文档文本来源：`Document` 的块与 `row.text`（选择 `extract` 的既有做法） | `core/selection.py:254-296` |

## 工单（按序执行，每项一个 commit）

### T1 `core/viewport.py` + `app.py`：`scroll_to` / `reveal`（D10 的地基）

- `Viewport.scroll_to(offset: int)`：把 `offset` clamp 到 `[0, 最大滚动量]` 并设为当前偏移
  （与 `to_bottom` 同源的边界规则）；测试：clamp、越界、与 `to_bottom` 的关系。
- `TUI.reveal(bid: str, row: int) -> bool`：目标块行若在视口外 → 滚动使其可见（居中优先，
  受边界限制）；未知 bid → False；聚焦 pane 语义与 `scroll_*` 一致；测试三态（已在屏内不动、
  上方滚上去、下方滚下来）。
- 文档：`app.py` docstring 与 `docs/COMPONENTS.md` 的 driver 段补两条。

### T2 `src/mocode_tui/search.py`：`Find`（D10）

- 构造：`Find(tui, *, theme=None)`；字段：`input: Input`、`query: str`、`matches`（列表，
  每项 = `(bid, row, start, end)` 的只读元组）、`index: int`、`is_open: bool`。
- 行为：
  - `open()` → 清空查询、`is_open=True`、注册 overlay（挂载期常驻注册建议照 `Toasts`，
    开/关只控绘制与收键）；
  - `handle(event) -> bool`（仅当 `is_open`）：`enter`/`down` → 下一个（回绕）；`up` → 上一个；
    `escape` → `close()`；其余 → `input.handle`，消费则重算 `matches`（大小写不敏感子串，
    按文档顺序）并 `index=0`，返回 True；
  - 打开/查询变化/`index` 变化后：`tui.reveal(match.bid, match.row)` 并 `invalidate`（宿主惯例，
    或返回值提示宿主重绘——与 Palette 同口径，docstring 写明）；
  - `close()` → `is_open=False`（overlay 零绘制）。
- overlay：`paint(frame) -> ScreenLayout`：全部匹配用 `theme.selection` 平铺高亮，
  当前匹配额外 `merge(theme.hover)`；查询行在底部一行（`input.render` + `(i/n)` 计数，
  照 `Palette` 的行拼接）。
- 测试（`tests/test_search.py`）：查询 → 匹配集合与序号；回车/上下回绕；escape 关闭零绘制；
  reveal 被调用（用 `RecordingScreen`/假的 reveal 记录或 spy 宿主回调？——**不引入回调**：
  测试通过 `Find.handle` 后的 `tui.viewport.offset` 断言）；大小写、跨块、无匹配三例。

### T3 gallery + 文档

- `session.py`：`HOST_KEYS` 加 `c-f`；dispatch order 在 `palette` 之后加 `find`（开着时先于
  ring/宿主键）；`c-f` → `find.open()`；`find` 的查询态下宿主键让位（除 `c-c`）。
- `features` 页与 `shell` 的 hint 行补 `c-f find`；`docs/COMPONENTS.md` 新条目 `Find`；
  `README.md` driver 段加 `c-f` 与 `Find` 一行；`docs/DESIGN.md` 命名表加 `Find`/`scroll_to`/`reveal`。
- `tests/test_api_root.py`：`Find` 进 root（或 `DOWN_LISTED`——**decision：进 root**，与 `Palette` 同级），
  同步 `ROOT_ALL`/计数/顺序。

## 验收（完成前自测，报告贴真实输出）

1. `uv run pytest -q` 只增不减（贴 before/after 与新增测试文件）。
2. 探针：一个 3 块文档上的查询/匹配/序号/上下回绕/reveal（`viewport.offset` 变化）；
   关闭后 `Find.paint` 原样返回 layout（零行）。
3. `demo.py < /dev/null` exit 0；`--pages` 12 页头；dump 无 find 行（未打开）。
   回放脚本追加：`c-f` + 输入 + 回车 + Esc 的一段（headless 可过）。
4. `import mocode_tui` 干净；README 块全绿；framebench hash 不变。
5. 真机项（搜索观感、reveal 居中）→ 未执行，列 lead 终验。

## 禁触清单

- `read_key` 的 `scroll_keys` 拦截顺序（搜索自己处理 `up/down` 只在打开时；不抢全局）
- `Palette` 的既有行为；`selection` 的 extract/copy 契约；`specs/**`

## 报告格式（最终消息，中文）

工单状态表 / commit 清单 / 自测真实结论 / 搜索探针 / reveal 探针 / 回放段输出 / framebench hash /
偏差与取舍 / 未决问题 / 真机手测：未执行。
