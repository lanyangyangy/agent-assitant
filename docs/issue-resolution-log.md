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
