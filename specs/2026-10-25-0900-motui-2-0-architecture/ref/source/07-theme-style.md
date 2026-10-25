# 07 · 主题与样式：一个解析器

> 上级：`01-architecture.md`　相关：`10-waves/W2` `W3`
> 状态：ready

## 1. 目标

把 1.x 的两套主题机制收成一套：

- `Theme`：10 组语义 token 的冻结值；
- `Styles`：按组覆盖（可选）；
- `Widget.style(group)`：渲染时解析“覆盖 → 主题”；
- 删除 `Themed`（构造期解析的旧基类）；
- `Border` / `Glyphs` 只作为结构内容，不进主题。

## 2. 为什么

- 1.x 同时存在 `Themed`（构造时解析，13 处使用）与 `Widget.group`（渲染时解析）；`Widget` 的 docstring 明确“deliberately not Themed”，说明旧基类已是遗留。
- `Styles` 是一个 10 字段 dataclass，每个 widget 又各自接受 `theme/styles`；解析逻辑分散。
- 主题切换（`App.theme = ...`）依赖属性名遍历（`_CHILD_ATTRS`），新容器改名就静默失效。

## 3. 值模型

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    text: TextStyles = field(default_factory=TextStyles)
    surfaces: SurfaceStyles = ...
    borders: BorderStyles = ...
    controls: ControlStyles = ...
    rows: RowStyles = ...
    status: StatusStyles = ...
    content: ContentStyles = ...
    chrome: ChromeStyles = ...
    overlays: OverlayStyles = ...
    syntax: SyntaxStyles = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class Styles:
    text: TextStyles | None = None
    ...  # 与 Theme 同名，None = 继承
```

- `Theme.dark()` / `light()` / `flat()` / `auto()` / `from_palette()`；
- `Color` 仍是“truecolor + ANSI 锚点”的值；
- `Glyphs`/`Border` 是内容（结构字符），不是颜色，不进 `Theme`；
- `Border.paint(surface, rect, style)`：Panel 与 frame 分隔条共用一套画框。

## 4. 解析规则

```python
class Widget:
    theme: Theme | None          # None = 继承 App
    styles: Styles | None        # 按组覆盖

    def style(self, group: str) -> object:
        override = getattr(self.styles, group, None) if self.styles else None
        return override if override is not None else getattr(self._theme, group)
```

- 渲染时解析，不缓存解析结果；
- `revision`/`touch` 必须包含 `theme` 与 `styles`（改变即失效）；
- 主题传播：`Workspace` 沿 `children` 前序赋值，不再属性名遍历；
- `App.theme` 赋值后，mounted widget 下一帧重绘，不需要重建。

## 5. 删除 `Themed`

- 所有 `Themed` 子类改为 `Widget`；
- `pick(explicit, fallback)` 删除；显式覆盖由 `styles` 组承担；
- 迁移测试：同一主题下像素输出与 1.x 一致（W2 字节级基线）。

## 6. Glyphs / Border

- `Glyphs` 保持一个 frozen bundle（`check_on`/`check_off`/`bar_*`/`cursor`/...）；
- `Border` 保持 14 个字符的 frozen 值（square/rounded/heavy/double/ascii/none）；
- `seat` / `seat_width` / `pair_seat` 是字符串度量 helper，放进 `text`/`glyphs` 命名空间，不做成 `Line` 方法；
- `MarkSet.prefix(index, glyphs=)` 取代自由函数 `mark_prefix`。

## 7. 测试

| 项 | 测试 |
|---|---|
| Theme | 10 组默认 = Dark；`replace` 不改变其他组 |
| Styles | 覆盖优先；`None` 继承；只覆盖一组 |
| 传播 | 新挂载子节点继承 App 主题；改主题即时生效 |
| 画框 | `Border.paint` 与 Panel/分隔条像素一致 |
| 删除 | 仓库无 `Themed` / `_CHILD_ATTRS` |

## 8. 重构方式

1. 删除 `core/theme.py:Themed`，保留 `Theme`/`Styles`；新位置 `kernel/theme.py`。
2. 所有 widget 的 `super().__init__(theme, styles)` 统一；`group()` → `style()`。
3. `_CHILD_ATTRS`/`_walk` 删除；主题传播走 `Widget.walk()`。
4. `Border.paint` 抽出；Panel/Divider 迁移。
5. 全量 golden 重录（W2 之后允许视觉变化，附差异分类）。

## 9. 不做的

- ❌ per-component theme recipe（`theme.button` 这种）。
- ❌ CSS / 主题文件格式。
- ❌ 运行时颜色查询协商（能力来自环境/显式配置）。
- ❌ 把 `Glyphs` 放进 `Theme`（结构不是颜色）。
