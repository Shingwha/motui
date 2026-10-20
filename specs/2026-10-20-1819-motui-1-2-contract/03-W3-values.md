# W3 · 值语义、缓存所有权与 selection 主题
> 分支 `w3-values`；前置：W2 已合并 @ `041e270`；写入范围见下。
> 深读：`00-overview.md` D7、`ref/interfaces.md` §2、`docs/CONTRACT.md` §5/§6/§8。

## 目标

让“frozen”名副其实，并收掉多余缓存：`Pane` 成为普通可变类；`ScreenLayout`/`Theme` 派生表/`FG_CODES`
真正只读；`Style`/`Segment` 加 slots；`Text` 的组件 memo 删除，缓存只由 `Block.rows` 拥有；
`Painter.rows` 恒为 `screen.height` 行；主选区使用 `Theme.selection`。**渲染字节不变**，golden 不动。

## 前置上下文

- 必读顺序：`ref/repo-map.md` → `ref/interfaces.md` §2 → `handoff/W2-driver.md` → 本工单。
- 基线命令（开工先跑，贴真实输出）：
  ```bash
  uv sync --locked
  uv run pytest -q -p no:cacheprovider
  uv run python tools/golden.py --check
  uv run python tools/framebench.py
  ```
  期望：1733 passed / 2 skipped；11 页 match；render-hash `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`。
- 稳定区（勿重读）：`kernel/events.py`、`keys/**`、`widgets/markdown/**`、W2 的 driver 语义。
- W2 已知约束：`TUI.screen/document/viewport` 只读；`add` 默认 focused pane；frame 结构变更自动 refresh；
  `ScreenLayout.body_rows` / `viewport_start`；`Hit` 带 pane/leaf；`Pane` 仍是 frozen（本波改）。

## 工单（按序执行；每个波次 HEAD 全绿即可，commit 粒度不限）

### T1 `kernel/frame.py`：`Pane` 改普通可变类

- `@dataclass(frozen=True)` → `@dataclass(eq=False)`（或 `eq=False, slots=True`，但先确认没有测试/代码
  依赖 `Pane` 的 hash/eq；`Pane` 是运行时对象，身份相等是正确语义）。
- 删除 `frame.py` 中所有 `object.__setattr__(... "chrome"/"division"/"children"/"viewport"/"rect"/
  "_negotiation"/"_frame" ...)`，改成普通赋值。
- `replace(self, ...)` 在 `Pane.split` 里的用法仍要工作；非 frozen dataclass 支持 `replace`。
- `Pane.__repr__` 保留；`_frame`/`_negotiation` 仍是 `compare=False, repr=False` 的内部字段。
- 检查 tests 是否用 `Pane` 做 set/dict key；若有，改成 id。
- 验证：`uv run pytest -q tests/test_frame.py tests/test_app.py -p no:cacheprovider`。

### T2 `kernel/viewport.py`：`ScreenLayout` 不可变容器

- `ScreenLayout` 保持 `@dataclass(frozen=True)`，但 `rows` / `body_rows` / `row_blocks` 改为
  `tuple[...]`；`__post_init__` 把传入的 list/tuple 统一转成 tuple（兼容现有构造点）。
- 默认值改 `field(default_factory=tuple)`；`block_order` 保持 tuple。
- 更新 `Viewport.layout` 与 `Frame.compose` 的构造；`Painter`/`Frame.with_pane_rows`/overlays 读取时
  不再假设 list；需要 list 的地方显式 `list(...)`。
- 测试改为 tuple 断言，或 `list(layout.rows) == [...]`。
- 验证：`uv run pytest -q tests/test_viewport.py tests/test_frame.py tests/test_painter.py tests/test_selection.py -p no:cacheprovider`。

### T3 `kernel/theme.py` + `kernel/style.py`：只读表

- `Theme._tables.notice_levels` 改为 `Mapping[str, tuple[str, Style]]`；`__post_init__` 用
  `types.MappingProxyType` 包住。
- `Theme.notice_levels` 返回只读 mapping；`Notice` 的 `.get(level, ...)` 必须继续工作。
- `FG_CODES` 改为 `MappingProxyType`（类型 `Mapping[str, int]`）；`style.py` 内部所有读写只读。
- 测试：`DEFAULT_THEME.notice_levels["info"] = ...` 必须抛 `TypeError`；`FG_CODES["red"] = ...` 抛
  `TypeError`；`Theme` 仍可 hash/比较（`_tables` compare=False 不变）。
- 验证：`uv run pytest -q tests/test_theme.py tests/test_style.py -p no:cacheprovider`。

### T4 `kernel/style.py` + `kernel/lines.py`：`Style`/`Segment` slots

- `Style` / `Segment` 改 `@dataclass(frozen=True, slots=True)`。
- 检查隐藏缓存字段（`Style._prefix`、`Segment._width`）仍能工作；`object.__setattr__` 的缓存写入
  在 slots 下仍合法。
- 检查 `replace()`/`copy`/pickle（如有测试）不受影响。
- 跑性能冒烟：`uv run python tools/framebench.py`，render-hash 必须不变。
- 验证：`uv run pytest -q tests/test_style.py tests/test_core_text.py -p no:cacheprovider`。

### T5 `kernel/lines.py`：`Text` 的组件 memo 删除

- 删除 `Text._memo_rows` / `_memo_width` / `_memo_revision` 及 `render` 里的 memo 分支；
  `render(width)` 每次调用 `_rows_for(width)`。
- **保留** `Text._rows`：它是 `click`/`hover_at` 的最后一次 render 几何，不是缓存。
- 保留 `_revision()` 作为 `Revisioned` 快照；`Block.rows` 仍是唯一缓存所有者。
- 更新 `Text` 的 docstring：说明缓存由 `Block.rows` 负责，standalone `render` 不做记忆。
- 测试：`Block.rows` 的 sealed/open 缓存行为不变；`Text.render` 直接调用仍正确；
  `Text` 的 revision 仍随 text/style/hover 变化。
- 验证：`uv run pytest -q tests/test_core_text.py tests/test_block.py tests/test_viewport.py -p no:cacheprovider`。

### T6 `kernel/painter.py`：`rows` 长度契约

- `paint(layout)` 在保存 `self._rows` 前把行数规范到 `self._screen.height`：
  - 多出的行截断；
  - 不足的行用空白 `Line()` 补足。
- `Painter.rows` 继续返回 list copy；docstring 的“exactly screen.height rows”变成事实。
- 测试：手造 `ScreenLayout(rows=[one_line], body_rows=[])` 在 4 行屏幕上，`painter.rows` 必须是 4 行。
- 验证：`uv run pytest -q tests/test_painter.py -p no:cacheprovider`。

### T7 selection 主题

- `kernel/selection.py:highlight(layout, selection, *, style: Style = SELECTION)`：用传入 `style`
  替代固定 `SELECTION` 常量；默认行为不变。
- `app._SelectionOverlay.paint` 调用 `highlight(..., style=self._tui.theme.selection)`。
- `Find` 已用 `theme.selection`，保持；确认主选区与 Find 使用同一 token。
- 测试：自定义 `Theme(selection=Style(reverse=False, underline=True))`，`highlight(..., style=...)`
  产出的行带 underline；TUI 的 selection overlay 使用主题。
- 验证：`uv run pytest -q tests/test_selection.py tests/test_app.py tests/test_find.py -p no:cacheprovider`。

### T8 文档、全量门禁、handoff

- 更新 `docs/DESIGN.md` 中“frozen / style resolution / cache”相关段落与 `docs/COMPONENTS.md` 的
  Selection/Theme 说明；W7 会重写整篇，本波只改与 T1–T7 冲突的断言。
- 跑 `## 验收` 全部命令，贴真实输出。
- 最后一个 commit 写 `specs/2026-10-20-1819-motui-1-2-contract/handoff/W3-values.md`（A/B/C）。
- 不 merge / push / tag。

## 验收

1. `uv run pytest -q -p no:cacheprovider`：0 failed；总数 ≥ 1733 + 新增
2. `uv run python tools/golden.py --check`：11 页全 match（值语义不应移动渲染）
3. `uv run python tools/framebench.py`：exit 0；render-hash 不变（贴值）
4. `uv run python -m motui < /dev/null`：exit 0
5. `uv run python -m motui --pages`：exit 0
6. 新增测试覆盖：Pane 可变/身份相等、ScreenLayout tuple、Theme/FG_CODES 只读、Style/Segment slots、
   Text 无 memo、Painter 行数、selection style 参数
7. `git diff --stat main...HEAD`：范围 = 本工单写范围并集，无 golden 变化

## 禁触清单

- 禁改：`pyproject.toml`、`uv.lock`、`specs/**`（handoff 除外）、`docs/CONTRACT.md`、`tests/golden/**`、
  `kernel/events.py`、`keys/**`、`widgets/**`（Markdown/Divider/Notice 的 revision 归 W4）、
  W2 的 driver/pane/dock 语义。
- 禁加：兼容 alias、旧名 re-export。
- 禁做：merge / push / tag / checkout main / 碰主检出或其它 worktree。
- 遇到阻塞：写清阻塞点后停止，不越界自救。

## 交接包

完成后写 `handoff/W3-values.md`（60–80 行）：

- A：`git diff --stat`、新增/变更公开签名、基线真实结果
- B：与 spec 的偏差、踩坑、下一波必须遵守的隐式约束、未决问题
- C：关键文件:行号、commit、稳定区

## 最终报告

工单状态表（T1–T8）/ commit 清单 / 自测真实输出 / 值语义变更清单 / 测试改动清单 /
偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
