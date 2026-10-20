# W7 · 文档、demo、版本与发布门禁（占位，JIT）
> 状态：待 W1–W6 合并后补全。依赖全部。

## 目标

重写/校准 `DESIGN.md`、`COMPONENTS.md`、`README.md`，让契约与代码一致；重录 golden；版本
`1.2.0`；CHANGELOG/release notes；最终全量门禁；清理死文档/旧名字/临时探针。

## 范围（草稿）

`docs/**`、`README.md`、`CHANGELOG.md`、`docs/releases/1.2.0.md`、`pyproject.toml`、`uv.lock`、
`tests/golden/**`（仅经工具）、`tests/test_readme_examples.py`。

## 验收（草稿）

- 全量 pytest / golden / framebench / demo 两入口
- `motui.__version__`、pyproject、installed metadata 三者一致
- README 示例全部可执行
- 文档层数/导出表/组件目录与代码一致
- 不 push/tag，等用户指令
