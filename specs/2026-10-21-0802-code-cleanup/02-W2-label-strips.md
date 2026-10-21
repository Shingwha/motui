# W2 · Label strips (JIT ticket)

> 状态：占位。W1b 合并后由 lead 补全「前置上下文」再派工。
> 分支建议 `cleanup/w2-label-strips`。

## 目标

把 `Tabs` 与 `MenuBar` 中约 95% 相同的状态、光标动词、命中表与渲染骨架收敛到新的
私有模块 `src/motui/widgets/strip.py`；`NavList` 复用其中的钳制光标动词。
渲染字节、公开构造签名、`revision()` 快照必须零变化。

## 范围

- 新增 `src/motui/widgets/strip.py`：
  - `ClampedCursor`：`index` 只读属性、`select(index)`、`move(delta)`，
    钳制不循环、跳过 `_disabled_items`、`disabled` 拒绝全部手势。
  - `LabelStrip(ClampedCursor, Themed)`：`_entries` 抽象、`click`、`hover_at`、
    `_hit`、`_label_at`、`_spans_of`、`render`；`render` 调用子类 `_layout(width)`。
- `tabs.py` / `menubar.py` 继承 `LabelStrip`，只保留：
  - 各自独有的样式解析字段；
  - `_layout(width)`；
  - `MenuBar.activate` / `take_result` / 清 pending 的 `move` 覆盖；
  - 各自的 `revision()` 与 `__repr__`；
  - `Tabs` 的 underline indicator。
- `navlist.py`：继承 `ClampedCursor`，删除 `index` / `select` / `move` 的副本；
  `click` / `hover_at` / 分组行逻辑留在本类。

## 验收

- `pytest` 824 passed。
- `golden.py --check` 58 topics。
- `render-hash` 等于基线。
- `tests/widgets/test_navigation.py` 与 `tests/widgets/test_menubar.py` 全绿。
- 抽验 `Tabs.revision()` / `MenuBar.revision()` 的元组顺序未变。

## 依赖

- W1b 已合并（`navlist.py` 的 `_band` / `_rest` 已由 mixin 接管）。
- 契约见 `ref/interfaces.md` 的 W2 段。
