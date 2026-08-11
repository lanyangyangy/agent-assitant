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
