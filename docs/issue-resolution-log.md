# 问题解决记录

每次因为失败测试、运行时异常或集成错误而修改代码时，都需要先在这里追加记录，再提交修复。

## 记录格式

- 日期：
- 现象：
- 根因：
- 修改文件：
- 验证命令：
- 结果：

## 2026-08-11 - pytest 无法导入 src 包

- 日期：2026-08-11
- 现象：执行 `uv run pytest tests/unit/core/test_config.py -v` 时，测试收集阶段报 `ModuleNotFoundError: No module named 'src'`。
- 根因：pytest 没有稳定地把项目根目录加入导入路径，导致源码包在测试收集阶段不可见。
- 修改文件：`pyproject.toml`
- 验证命令：`uv run pytest tests/unit/core/test_config.py -v`
- 结果：PASS，配置测试可以正常收集并通过。

## 2026-08-11 - aiosqlite 连接未激活时设置 row_factory 失败
- 日期：2026-08-11
- 现象：执行 `uv run pytest tests/unit/core/test_session_store.py -v` 时，两个 session_store 测试都在 `initialize()` 阶段失败，报错 `ValueError: no active connection`。
- 根因：`aiosqlite.connect()` 返回的连接对象在进入 `async with` 前尚未激活，此时设置 `row_factory` 会访问未初始化的底层 SQLite 连接。
- 修改文件：`src/core/session_store.py`
- 验证命令：`uv run pytest tests/unit/core/test_session_store.py -v`
- 结果：PASS，2 个 session_store 单测全部通过。

## 2026-08-12 - session message 写入竞态与删除级联覆盖不足
- 日期：2026-08-12
- 现象：代码质量复核指出 `add_message()` 使用先查询会话再插入消息的两步写法，若会话在两步之间被其他连接删除，可能因外键异常上冒导致后续 API 500；同时 `delete_session()` 缺少跨用户删除与消息级联清理测试。
- 根因：消息写入没有用单条条件插入表达“仅当当前用户拥有会话时才插入”，测试也未覆盖删除边界。
- 修改文件：`tests/unit/core/test_session_store.py`、`src/core/session_store.py`
- 验证命令：`uv run pytest tests/unit/core/test_session_store.py -v`、`uv run pytest tests/unit -v`
- 结果：PASS，session_store 定向测试与 unit 测试全部通过。
