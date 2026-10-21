# W2 · 包与运行时合并（core / widgets / app）

> 占位；W1 合并后由 lead 补全「前置上下文」再派工。
> 分支建议 `refactor/1.2-runtime`。

## 目标

把当前 8 个命名空间收敛成 3 层：`motui.core`（kernel + keys）、`motui.widgets`、`motui.app`（interaction + app + commands）。删除 `Host` seam 和两个 widget 工厂，让 `app` 直接 import `widgets`。所有旧 import 路径必须消失。

## 范围

- `git mv src/motui/kernel src/motui/core`；`keys/*` 并入 `core/`（decoder/keymap/sources/console）。
- `src/motui/app.py` → `src/motui/app/driver.py`；`interaction/*` → `src/motui/app/*`；`commands.py` → `src/motui/app/commands.py`。
- 删除 `kernel/host.py`、`Host`、`QueryInput`、`FilterList`、`OptionLike`、`make_input`、`make_autocomplete`。
- 更新 `src/**`、`tests/**`、`tools/**`、`docs/**` 的 import 路径；更新各层 `__init__.py`。
- 本波不改 `read_event` 行为、不改控件构造器、不改视觉。

## 依赖

W1 已合并。

## 验收

- 全量 pytest、golden、framebench、两个 demo 入口全绿。
- `rg "motui\.(kernel|keys|interaction|commands)" src tests tools docs` 为空。
- `rg "Host|make_input|make_autocomplete|QueryInput|FilterList|OptionLike" src` 为空（specs 除外）。
- golden 逐字节不变。
