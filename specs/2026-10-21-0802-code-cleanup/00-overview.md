# Code cleanup after the 1.1.x refactors

> 启动：2026-10-21 08:02（UTC+8）

## 目标

在**不改公开 API、不改渲染字节、不改测试断言**的前提下，删除 1.1.x 重构留下的重复实现，
收紧驱动与交互层之间的类型契约，让每一条规则只有一个实现。

完成后应满足：

- `pytest` 824 passed 不变；
- `tools/golden.py --check` 58 个 topic 零 diff；
- `tools/framebench.py` 的 `render-hash` 保持
  `f872187ac70286da20e4dc1e6b5b4d64006f17c891001b5dd3a3ec50ad44d6e1`；
- 根 facade 的 34 个名字与各层 `__all__` 不变；
- 净删除约 450–550 行重复代码。

## 非目标

- 不重写渲染器、不改 golden 帧、不调整布局算法。
- 不搬模块、不改公开名字、不新增兼容 shim。
- 不重写历史决策文档（D1–D8 等）；只把重复方法上的 docstring 收敛到共享实现。
- 不优化性能（`framebench` 只作为“没动渲染”的证据，不作为提速目标）。

## 基线（开工时实测）

| 门禁 | 基线 |
|---|---|
| `.venv/Scripts/python -m pytest -q -p no:cacheprovider` | `824 passed in 3.58s` |
| `python tools/golden.py --check` | `golden: 58 topics match` |
| `python tools/framebench.py` | `render-hash: f872187a…d6e1`，`replay ~301 ms` |

## 波次表

| 波 | 分支 | 写入范围 | 依赖 | 执行者 |
|---|---|---|---|---|
| W1a 驱动与 seam | `cleanup/w1a-driver-seams` | `app.py`、`kernel/host.py`、`interaction/{find,palette,overlays}.py`、`docs/{DESIGN,CONTRACT}.md` | 无 | worker a |
| W1b 行带与选择组 | `cleanup/w1b-widget-rows` | `widgets/{bands,choice,list,tree,navlist,table}.py` | 无 | worker b |
| W2 标签条 | `cleanup/w2-label-strips` | `widgets/strip.py`（新增）、`widgets/{tabs,menubar,navlist}.py` | W1b 合并 | worker（JIT 派工） |
| W3 收尾 | lead 直接在 main | 未使用 import 所在文件、必要的 docs 同步 | W1a/W1b/W2 合并 | lead |

W1a 与 W1b 文件级不相交，可并行。`navlist.py` 先归 W1b，W2 在 W1b 合并后接手。

## 全局不变量

1. **行为零变化**：测试、golden、render-hash 三处同时不变才算通过。
2. **公开面零变化**：根 `__all__`（34 名）与五个 layer facade 的 `__all__` 不动。
3. **依赖方向不变**：`kernel` 不向上 import；`interaction` 只依赖 `kernel` 与 `Host`。
4. **一条规则一个实现**：共享实现只能放在已有归属点或新的私有模块，不新增转发层。
5. **测试只读**：worker 不得修改 `tests/`；测试红了就是实现错了。
6. **不碰 golden**：不得运行 `tools/golden.py --update`。
7. **注释与 commit 风格**：英文 docstring/注释；commit 用 `area: imperative summary`。

## 回归红线

- `pytest` 任何失败 → 整分支打回。
- `golden.py --check` 任何 diff → 整分支打回（不允许重录）。
- `render-hash` 变化 → 整分支打回（说明渲染路径被改了）。
- 公开 facade 名字增删 → 整分支打回。
- `tests/`、`tests/golden/`、`pyproject.toml`、`uv.lock` 出现 diff → 越界，打回。

## 共享文件所有者

| 文件 | 所有者 |
|---|---|
| `ref/interfaces.md` | lead（每波合并后回写） |
| `docs/DESIGN.md`、`docs/CONTRACT.md` 的 Host 协议段 | W1a |
| `widgets/navlist.py` | 先 W1b，合并后 W2 |
| 其余文件 | 各波独占 |

## 接口索引

- `ref/interfaces.md`：本操作涉及的 Host 工厂协议、内部共享基类与错误语义。
- `ref/repo-map.md`：仓库地图、命令、环境陷阱。

## 决策记录

- 力度：标准（W1–W4），不做 docstring 大改与模块搬迁。
- 公开 API：保持稳定。
- 执行：W1a/W1b 并行，W2 串行，W3 lead 收尾。
- 文档：保留现有详度，只移动/合并重复的 docstring。
