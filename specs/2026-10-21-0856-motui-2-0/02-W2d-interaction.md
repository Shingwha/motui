# W2d · Interaction, app and chrome

> 分支 `motui-2/w2d-interaction`；起点 `main`（W1 已合并）；写入范围见下。

## 目标

把 interaction 层、`app.py` 与 `kernel/chrome.py` 迁移到 role groups。**零视觉变化**：
legacy 默认值下与旧字段等价；不改字形参数（W3 做）。

## 前置上下文

- 必读：`ref/interfaces.md` §3.1/§3.4/§5 → `handoff/W1-core.md`。
- 基线：`uv sync --locked`；896 passed。

## 写入范围

源码：
`interaction/find.py`、`interaction/modal.py`、`interaction/overlays.py`、
`interaction/palette.py`、`interaction/scrollbar.py`、`kernel/chrome.py`、`app.py`

测试：`tests/interaction/test_find.py`、`test_modal.py`、`test_overlays.py`、
`test_palette.py`、`test_scrollbar.py`、`tests/app/`（如需）。

## 工单

1. Find：`theme.selection` -> `text.selection`；`theme.hover` -> `surfaces.hover`；
   `theme.dim` -> `text.faint`；`theme.toast` -> `overlays.toast`。
2. Modal：`theme.dim` -> `overlays.scrim`。
3. Overlays：`theme.toast` -> `overlays.toast`；Tooltip/Stats 同步。
4. Scrollbar：`theme.scrollbar` -> `chrome.scrollbar`；
   `theme.scrollbar_thumb` -> `chrome.scrollbar_thumb`。
5. `kernel/chrome.py` Separator：`theme.accent` -> `content.accent`；
   `theme.border` -> `borders.base`。
6. `app.py`：`theme.selection` -> `text.selection`；其余 theme 读取同步。
7. 不改构造签名、不引入 `glyphs=`。

## 验收

```bash
uv run pytest -q -p no:cacheprovider          # 896 (824 baseline + 72 contracts)
uv run python tools/golden.py --check         # 58
uv run python tools/framebench.py             # hash 不变
```

## 禁触清单

`widgets/`、`kernel/`（`chrome.py` 除外）、`keys/`、`tests/golden/`、`tools/`、`docs/`。
不 merge/push/tag；不 `golden --update`。

## 交接包

`handoff/W2d-interaction.md`：overlay/scrim/scrollbar 映射、app/chrome 改动、门禁输出。
