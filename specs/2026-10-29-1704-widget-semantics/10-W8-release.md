# W8 · 2.1.2 发版（目标占位，JIT 补全）

> 分支 `w2.1.2-w8-release`。依赖 W7。

## 目标

- `pyproject.toml`、`src/motui/__init__.py` fallback、`uv.lock` 相关引用升到
  2.1.2。
- `CHANGELOG.md` 新增 2.1.2（一致性重构定位 + breaking widget API 列表）；
  `docs/MIGRATION.md` 新增 “2.1.0 → 2.1.2”；`docs/releases/2.1.2.md`。
- README/WIDGETS 示例中所有构造顺序改新写法。
- `tools/api-2.1.txt` 由 lead 用 `tools/api.py --update` 重录。
- 终验：全量门禁 + `framebench` + `semantic` + 三入口抽验。

## 范围

`pyproject.toml`、`src/motui/__init__.py`、`CHANGELOG.md`、`docs/MIGRATION.md`、
`docs/releases/2.1.2.md`、`README.md`、`docs/WIDGETS.md`、`uv.lock`、
`tools/api-2.1.txt`。

## 验收

- 所有门禁全绿；`uv run python -m motui --version` 输出 2.1.2。
- 不 push、不打 tag（等用户指令）。

## 依赖

W7 合并。
