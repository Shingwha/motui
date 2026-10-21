# W4 · Remove the bridge and ship 2.0 (JIT)

> 依赖 W3 合并。详细工单在 W3 合并后补全。

## 目标

删除临时兼容层与全部旧 API，更新文档与版本，终验 2.0。

## 范围

- `kernel/theme.py`：删除 §3.4 兼容属性、`Themed._pick`（若已无消费者）。
- `kernel/style.py`：删除旧语义常量。
- `kernel/glyphs.py`：删除旧字形常量。
- `widgets/bands.py`：删除 `RowBands`/`BandedRows`（若已无消费者）。
- 各组件：删除遗留的逐字形参数与旧 `*_style` 映射（保留显式 `style=` 覆盖）。
- `docs/COMPONENTS.md`、`docs/DESIGN.md`、`docs/CONTRACT.md`、`README.md`、
  `CONTRIBUTING.md`、`CHANGELOG.md`、`pyproject.toml` 版本 2.0.0。
- 全仓 `grep` 旧字段/常量，确保零消费者。

## 验收

```bash
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages > /tmp/pages.txt
```

`tests/test_api.py` 通过；`Theme` 不再有旧字段；公开 facade 只新增
`Palette`/`Glyphs`/`Border`。
