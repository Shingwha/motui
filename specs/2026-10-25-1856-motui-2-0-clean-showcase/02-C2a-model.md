# C2a · Revisioned → touch/generation、Themed 删除、RowRange → RowSpan

> 分支 `2.0-clean/c2a-model`；前置：C1 已合并（`2e55970`）；写入范围：`src/motui/kernel/{document,layout,hit,theme}.py`、`src/motui/widgets/**`、`src/motui/app/{find,overlays}.py`、`src/motui/demo/{shell,stage}.py`、`tests/**`、`tools/api-2.0.txt`
> 权威：`../2026-10-25-0900-motui-2-0-architecture/ref/source/{02-core-contracts,03-interaction,11-decisions}.md`（ADR-004/016/017）

## 目标

完成 2.0 的失效与主题模型，删除 1.x 遗留：

1. **删除 `Revisioned`/`revision()`/`_revision()`**；`Section` 缓存键改为 `(width, max_height, widget.generation)`；所有就地变更补 `touch()`；
2. **删除 `Themed`/`pick()`**；`Theme.group(name, styles=None)` 成为唯一解析；Widget/控制器/高亮器共用；
3. **`RowRange` → `RowSpan`**（移到 `kernel/layout.py`），全仓改名；
4. 新增缓存失效测试（Text/List/Input/Canvas/ScrollPanel/Table/Form）；
5. 1592 用例、57 byte/semantic、hash 不变。

**本波结束：`grep Revisioned|def revision|Themed|pick(|RowRange` 在 src 为 0；缓存测试覆盖就地修改；全量绿；字节不变。**

## 前置上下文

- 必读：`../2026-10-25-0900-motui-2-0-architecture/handoff/W5-final.md` → C1 handoff → 本工单。
- 基线：`uv sync --locked`；`pytest`（1592 passed）；`golden --check`（57）；`semantic --check`（57）；hash `e7ca544b…`。
- 现状：
  - `kernel/document.py`：`Revisioned` Protocol；`Section._cacheable = isinstance(widget, Revisioned)`；缓存键 `(width, max_height, revision())`；`Section.revision()`。
  - `kernel/layout.py`：`_BodyIndex` 用 `block.revision()`（行 430/488）。
  - 约 40 个组件实现 `revision()`/`_revision()`（action/choice/list/tree/table/tabs/menubar/navlist/rows/decor/layout/scroll/text/textfield/diff/markdown/indicators/collapsible/combobox/dialog/form/canvas/autocomplete）。
  - `Widget.touch()`/generation 已存在；`__setattr__` 对公开属性自动 touch；`_` 开头不 touch。
  - `TextBuffer` 有 `_version`（行 595 递增）；所有编辑变更都经过它。
  - `Themed` 用于 `app/find.py:Find`、`app/overlays.py:_MountedOverlay`、`widgets/syntax.py:RegexHighlighter`；`Themed.pick(explicit, fallback)`。
  - `RowRange(first,last)` 在 `kernel/hit.py`；`Runtime/Workspace.visible_range` 返回它；tests 5 处。
- 设计：
  - `Section`：
    ```python
    self._cacheable = hasattr(widget, "generation")
    @property
    def generation(self) -> int | None: return getattr(widget, "generation", None)
    # _refresh: gen is None -> fresh render; else key (width,max_height,gen)
    ```
  - `_BodyIndex`：`entry.generation` 替代 `revision`；`block.generation`；`None` 时每次重算该 entry。
  - `Widget`：删除 `revision()` 默认；基类 `touch()`/generation 保留。
  - `Theme.group(name, styles=None)`：
    ```python
    def group(self, name, styles=None):
        override = getattr(styles, name, None) if styles is not None else None
        return override if override is not None else getattr(self, name)
    ```
    `Widget.group(name)` → `self._theme.group(name, self.styles)`。
  - `Themed` 删除；`Find`/`_MountedOverlay`/`RegexHighlighter` 保存 `theme/styles`，用 `self._theme.group(name, self.styles)`；删除 `pick`。
  - `RowSpan` 在 `kernel/layout.py`：`@dataclass(frozen=True, slots=True) class RowSpan: first:int; last:int`；`kernel/hit.py` 不再定义；`kernel/__init__` 从 layout 导入；`visible_range` 返回 `RowSpan`。
- 就地变更清单（必须补 `touch()`；用测试兜底）：
  - `Text.hover_at`（span 变化时）；`Markdown.hover_at`；`Text.click` 不改行，不需要。
  - `TextBuffer` 加 `on_change: Callable[[], None]|None`，在 `_version += 1` 处调用；`_TextField.__init__` 设 `self._buf.on_change = self.touch`；`_TextField.on_key/on_paste/on_click` 若消费则 `touch()`（覆盖光标移动/选择）。
  - `List`/`Select`/`MultiSelect`/`CheckboxGroup`/`RadioGroup`/`Tree`/`NavList`/`Tabs`/`MenuBar`/`Table`/`Collapsible`：所有修改 `_index`/cursor/选中/展开/标记的方法末尾 `touch()`。
  - `ScrollPanel.scroll_y/scroll_x/scroll_to_*`：修改 offset 后 `touch()`。
  - `Canvas.put/text/hline/vline/box/blit/plot/clear`：修改后 `touch()`；`Sparkline.set_values/plot` 后 `touch()`。
  - `Slider.value` 已是公开属性 auto；`Spinner.advance` 修改内部 frame → `touch()`；`ProgressBar.value` 公开 auto。
  - `Markdown.text/max_width/code_wrap` 公开 auto；`hover_at` → touch。
  - `Dialog`/`Form`/`Panel`/`Row`/`Column`/`Padding`：子组件 touch 会沿 parent 冒泡；自己的字段（title/active 等）公开 auto；`Dialog` 按钮按下改 `_pending`/按钮状态时 touch。
  - `Table.rows` 是公开 list，就地 `append` 不会 auto；文档写明需 `touch()`，测试覆盖；`List.options` 同理。
- 已知坑：
  - 删除 `revision()` 后，任何漏 touch 的就地变更会让 Section 缓存陈旧；测试必须覆盖每个有内部状态的组件；宁可在 mutator 末尾多 `touch()`（一次 generation++ 很便宜）。
  - `Section._cacheable` 不能用 `isinstance(widget, Widget)`（kernel 不能 import widgets）；用 `hasattr(widget, "generation")`。
  - `_BodyIndex` 的 entry key 从 revision 改 generation；`None` 表示不可缓存，必须每次重算。
  - `TextBuffer.on_change` 在 `__init__` 里回调 `self.touch` 可能循环？`touch` 只改 generation，不写 buffer，安全。
  - `Find`/`_MountedOverlay` 不是 Widget，不能继承 Widget；用 `theme.group()`。
  - `RegexHighlighter` 的 `_plain`/`styles` 在构造时从 theme 解析；`theme` 改变时重建？现有行为按构造；保留。
  - `RowSpan` 移到 layout 后，`kernel/hit.py` 的 `__all__` 和 `kernel/__init__` 要同步；`tests/test_kernel_imports` 的期望名单更新。
  - 57 golden/hash 不能变；缓存语义变化不应改变输出，只改变“是否重渲染”。
- 不改 `Frame.revision`（结构 revision，与行缓存无关）；不改渲染算法。

## 工单（按序，每步一个 commit）

### T1 Section 缓存 → generation

- `kernel/document.py`：
  - 删除 `Revisioned` Protocol 与 `__all__` 条目。
  - `Section._cacheable = hasattr(widget, "generation")`；`Section.generation` property；删除 `Section.revision()`。
  - `_refresh` 用 `gen = self.generation`；`gen is None` → 每次 fresh；否则缓存键 `(width,max_height,gen)`。
- `kernel/layout.py`：
  - `_BodyEntry` 的 `revision` 字段改 `generation`；`_BodyIndex` 用 `block.generation`；`None` 时重算。
- 测试 `tests/kernel/test_document.py`/`test_layout.py`：
  - 用一个自定义 Widget（可变 `count` + `touch()`）验证：touch 后 rows 变化；未 touch 时命中缓存；
  - 非 Widget 纯 Component 每次 fresh；
  - `_BodyIndex` 在 generation 变化后重算高度。
- 验证：`uv run pytest -q tests/kernel/test_document.py tests/kernel/test_layout.py`。

### T2 删除 revision 方法 + 补 touch

- 全仓删除 `def revision`/`def _revision`（widgets/demo/app；保留 `Frame.revision`）。
- 按“就地变更清单”给 mutator 补 `touch()`：
  - Text/Markdown hover；TextBuffer `on_change` + `_TextField` hooks；List/Select/Tree/Nav/Tabs/Menu/Table/Collapsible；ScrollPanel；Canvas/Sparkline；Spinner；Dialog/Form 必要处。
- 测试：新增 `tests/widgets/test_invalidation.py`：
  - `Text` 改 text / hover span → Section rows 变；
  - `List.move` → rows 变；
  - `Input` 输入字符 → rows 变；
  - `Canvas.put` → rows 变；
  - `ScrollPanel.scroll_down` → rows 变；
  - `Table` `move` 与 `rows.append()+touch()` → rows 变；
  - `Form` 子字段输入 → Form 行变。
- 验证：`uv run pytest -q -p no:cacheprovider`；golden/semantic/hash 不变。

### T3 Themed → Theme.group

- `kernel/theme.py`：删除 `Themed`/`pick` 与 `__all__`；新增 `Theme.group(name, styles=None)`。
- `widgets/base.py:Widget.group` 调 `self._theme.group(name, self.styles)`。
- `app/find.py:Find`、`app/overlays.py:_MountedOverlay`、`widgets/syntax.py:RegexHighlighter`：
  - 删除 `Themed` 继承；保存 `theme`/`styles`；所有 `self.pick(explicit, fallback)` → `fallback`（或显式覆盖优先，按原语义）；`self._theme` 解析不变；需要覆盖组时用 `theme.group`。
- 更新 import/`__all__`/测试（`test_theme` 的 `Themed` 用例删除）。
- 验证：`uv run pytest -q tests/kernel/test_theme.py tests/widgets/test_syntax.py tests/app/test_find.py tests/app/test_overlays.py`。

### T4 RowSpan

- `kernel/layout.py`：新增 `RowSpan(first,last)`（frozen/slots），`__all__` 增加。
- `kernel/hit.py`：删除 `RowRange`；`__all__` 只 `Hit`。
- `kernel/__init__.py`：从 layout 导出 `RowSpan`，删 `RowRange`。
- `app/runtime.py`/`workspace.py`：`visible_range -> RowSpan`；构造 `RowSpan(...)`。
- 测试：`tests/app/test_hit.py`/`test_driver.py`/`test_kernel_imports.py` 更新。
- 验证：`uv run pytest -q tests/app tests/kernel/test_kernel_imports.py`。

### T5 收口

- `grep -rn "Revisioned\|def revision\|def _revision\|Themed\|\.pick(\|RowRange" src/motui` → 只允许 `Frame.revision`（结构修订）；报告剩余。
- `tools/api.py --update`；全量验收；`growth.py` full。
- 报告 Section 缓存命中率/性能（framebench 不劣化 >10%）。

## 验收

1. `uv run pytest -q -p no:cacheprovider` 全绿（贴数字）。
2. 57 byte golden、57 semantic、hash `e7ca544b…` 不变。
3. `python -m motui < /dev/null` / `--pages` exit 0（70/4059 行）。
4. 缓存失效测试全部通过；`Revisioned`/`Themed`/`RowRange` 在 src 为 0（`Frame.revision` 除外）。
5. `ruff` / `pyright` / `lint-imports` / `api --check` / `growth.py` full 全绿。
6. framebench 无 >10% 劣化。

## 禁触清单

`terminal/**`、`kernel/{cell,frame,hit 的 Hit,overlay,selection,style,glyphs,text,events,keymap,geom}.py`、`tests/golden/**`、`tools/{golden,framebench,semantic,growth}.py`、`README.md`、`docs/**`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`；不改 demo 结构/文案（C4）。

## 交接包

最后 commit 写 `handoff/C2a-model.md`：A 节给缓存键/generation/touch 清单/Theme.group/RowSpan/门禁；B 节给就地变更清单、漏网风险、RowSpan 位置、C2b（ScrollState）清单、坑；C 节给路径与 commit。

## 最终报告

工单状态表 / commit 清单 / 自测真实结论 / 偏差与取舍 / 交接校验 / 探索审计 / 未决问题。
