# W4b · Choice / Navigation 迁移（目标占位，JIT 补全）

> 分支 `w2.1.2-w4b-choice-nav`。依赖 W4a。

## 目标

把 `choice.py`、`autocomplete.py`、`combobox.py`、`menubar.py`、`list.py`、
`table.py`、`tree.py`、`tabs.py`、`navlist.py` 迁到 `CursorWidget`/
`ResultWidget`；统一 `index`/`selected`/`marked`、`activate`/`toggle`/
`select`/`move`、`take` 返回值、`open` 属性、`CURSOR_KEYMAP` 与
`TREE_KEYMAP`；删除死键位和方言动作名。

## 范围

上述源文件 + `tests/widgets/test_choice.py`、`test_autocomplete.py`、
`test_combobox.py`、`test_menubar.py`、`test_navigation.py`、`test_data.py`
+ 新文件 `tests/widgets/test_contract_choice_nav.py`。
不写 `test_contracts.py`（W4a 独占）。

## 验收

- 全量门禁 + semantic 全绿（字符零变化）。
- Choice/Nav 的构造签名符合 `ref/interfaces.md` §2；`take` 返回符合 §5；
  `on_action` 九动词符合 §4。
- `api.py --check` 差异报告给 lead。

## 依赖

W4a 合并、`ref/interfaces.md` 更新。
