# W2a · Controls and forms

> 分支 `motui-2/w2a-controls`；起点 `main`（W1 已合并）；写入范围见下。

## 目标

把控件/表单组件从旧 Theme 字段迁移到 role groups。**零视觉变化**：使用 legacy
默认值下与旧字段等价的 group 字段；不改字形参数、不改渲染逻辑。

## 前置上下文

- 必读：`ref/interfaces.md` §3.1/§3.4/§5 → `handoff/W1-core.md`。
- 基线：`uv sync --locked`；`uv run pytest -q -p no:cacheprovider` 824 passed。

## 写入范围

源码：
`widgets/action.py`、`widgets/choice.py`、`widgets/textfield.py`、`widgets/form.py`、
`widgets/combobox.py`、`widgets/autocomplete.py`、`widgets/dialog.py`

测试（只做必要的构造/断言迁移）：
`tests/widgets/test_action.py`、`test_choice.py`、`test_editing.py`、`test_form.py`、
`test_combobox.py`、`test_autocomplete.py`、`test_dialog.py`

## 工单

1. 把 `_pick(explicit, "field")` 改为 `self.pick(explicit, self._theme.<group>.<field>)`。
2. 旧字段到 group 的映射：
   - `theme.accent` -> `theme.content.accent`（控件基准用 `theme.controls.base`）
   - `theme.hover` -> `theme.surfaces.hover`
   - `theme.focus` -> `theme.controls.focus`
   - `theme.dim` -> `theme.text.faint`
   - `theme.muted` -> `theme.text.muted`
   - `theme.error` -> `theme.status.danger`
   - `theme.selection` -> `theme.text.selection`
   - `theme.caret` -> `theme.text.caret`
   - `theme.border` -> `theme.borders.base`
3. 不改变组件构造签名、不引入 `glyphs=`（W3 做）。
4. `tests/` 只允许更新因 `replace(DEFAULT_THEME, ...)` 迁移而需要的构造；不得改断言预期。

## 验收

```bash
uv run pytest -q -p no:cacheprovider          # 824
uv run python tools/golden.py --check         # 58
uv run python tools/framebench.py             # hash 不变
```

## 禁触清单

其他 widget 文件、`kernel/`、`interaction/`、`app.py`、`tests/golden/`、`tools/`、`docs/`。
不 merge/push/tag；不 `golden --update`。

## 交接包

`handoff/W2a-controls.md`：迁移了哪些文件、旧字段到 group 的精确映射、测试是否改动、
门禁真实输出。
