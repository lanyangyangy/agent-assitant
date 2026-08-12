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

## 2026-08-12 - SQLite memory FTS 维护、评分与中文检索复核问题
- 日期：2026-08-12
- 现象：代码质量复核指出 `memory_fts` 外部内容表只在 `add()` 中手动写入，直接更新或删除 `memories` 后可能出现 FTS 索引旧词残留；`score=max(0.0, -rank)` 分值过小，不利于后续上下文相关性排序；默认 FTS 对无空格中文内容检索不友好。
- 根因：`initialize()` 未创建 INSERT/UPDATE/DELETE triggers，也未 rebuild 已有外部内容索引；搜索结果未基于同一次查询内的最大原始分做归一化；FTS 索引文本未包含中文子串可命中的预处理词元。
- 修改文件：`docs/issue-resolution-log.md`、`tests/unit/core/test_memory.py`、`src/core/memory.py`
- 验证命令：`uv run pytest tests/unit/core/test_memory.py -v`、`uv run pytest tests/unit -v`
- 结果：PASS，memory 定向测试 11 项通过，unit 测试 16 项全部通过。

## 2026-08-12 - 天气工具注册名与规格不一致
- 日期：2026-08-12
- 现象：规格复核指出 `OpenMeteoWeatherTool.name` 当前为 `weather`，但总规格要求天气工具名必须是 `get_weather`，导致 registry/Qwen schema 暴露错误工具名，调用方执行 `invoke("get_weather", ...)` 会得到 `NOT_FOUND`。
- 根因：Task 6 实现时使用了简短工具名 `weather`，测试只覆盖了 HTTP 行为和默认参数，缺少对公开工具名和 registry 调用契约的断言。
- 修改文件：`docs/issue-resolution-log.md`、`tests/unit/tools/test_search_weather.py`、`src/tools/weather.py`
- 验证命令：`uv run pytest tests/unit/tools -v`、`uv run pytest tests/unit -v`
- 结果：新增工具名与 registry 调用回归测试，修正天气工具名后通过 `uv run pytest tests/unit/tools -v` 与 `uv run pytest tests/unit -v` 验证。

## 2026-08-12 - 工具执行边界与熔断恢复能力不足
- 日期：2026-08-12
- 现象：代码质量复核指出 calculator 可执行无界幂运算、超长/过深/过多节点表达式、大数字与非有限浮点；工具输入错误被 registry 记为 `EXECUTION_ERROR` 并计入熔断；熔断器打开后没有恢复/半开探测；`list_tools()` 只返回名称；`invoke()` 未校验 `arguments` 类型；`ToolResponse` 缺少稳定字典序列化；Tavily `max_results` 未拒绝 bool 和越界值，HTTP 错误消息不够稳定。
- 根因：首版工具系统只覆盖了最小可用路径，缺少资源消耗上限、用户输入错误类型、熔断状态机恢复窗口、API 层需要的对象列表与响应序列化契约。
- 修改文件：`docs/issue-resolution-log.md`、`src/tools/__init__.py`、`src/tools/calculator.py`、`src/tools/circuit_breaker.py`、`src/tools/errors.py`、`src/tools/registry.py`、`src/tools/response.py`、`src/tools/search.py`、`src/tools/weather.py`、`tests/unit/tools/test_calculator.py`、`tests/unit/tools/test_registry_and_circuit_breaker.py`、`tests/unit/tools/test_search_weather.py`
- 验证命令：`uv run pytest tests/unit/tools -v`、`uv run pytest tests/unit -v`
- 结果：新增资源边界、输入错误分类、半开熔断、工具列表对象返回、参数类型校验、响应序列化和 Tavily 边界测试；修复后 `uv run pytest tests/unit/tools -v` 与 `uv run pytest tests/unit -v` 均通过。

## 2026-08-12 - 半开探测释放与浮点幂溢出输入分类
- 日期：2026-08-12
- 现象：质量 re-review 指出半开探测期间遇到缺参或 `ToolInputError` 会让 `half_open_probe_in_progress` 长期保持占用，导致后续合法请求一直返回 `CIRCUIT_OPEN`；同时 calculator 的 float 幂运算可能在 `_ensure_safe_number()` 前抛出 `OverflowError`，被 registry 归为 `EXECUTION_ERROR` 并计入熔断。
- 根因：熔断器缺少“用户输入错误释放半开探测”的状态转换；calculator 只在幂运算前限制指数值和整数位数，未捕获算术溢出，也未预估 float 幂结果规模。
- 修改文件：`docs/issue-resolution-log.md`、`src/tools/calculator.py`、`src/tools/circuit_breaker.py`、`src/tools/registry.py`、`src/tools/weather.py`、`tests/unit/tools/test_calculator.py`、`tests/unit/tools/test_registry_and_circuit_breaker.py`、`tests/unit/tools/test_search_weather.py`
- 验证命令：`uv run pytest tests/unit/tools -v`、`uv run pytest tests/unit -v`
- 结果：新增半开输入错误释放、float 幂溢出输入分类和 Weather 网络错误包装回归测试；修复后 `uv run pytest tests/unit/tools -v` 与 `uv run pytest tests/unit -v` 均通过。

## 2026-08-12 - Qwen 与 Agent 调用链 async 合约偏差
- 日期：2026-08-12
- 现象：规格复核指出 `QwenClient` 使用同步 `httpx.Client`，`create_completion()` 与 `stream_completion()` 是同步方法；`ReactAgent.stream_chat()` 在 async generator 内同步调用 Qwen；`QwenCompressor.compress()` 也同步调用远程补全，后续压缩可能阻塞事件循环。
- 根因：Task 8/9 初版测试使用同步 `httpx.Client` 与同步 FakeQwenClient，未用 `await` 和 `async for` 验证 OpenAI-compatible Qwen 调用链的 async 合约，导致实现偏离后端 async 架构。
- 修改文件：`tests/unit/agents/test_qwen_client.py`、`tests/unit/context/test_context_builder.py`、`tests/unit/agents/test_react_agent.py`、`src/agents/qwen_client.py`、`src/context/compress.py`、`src/context/builder.py`、`src/agents/react_agent.py`
- 验证命令：`uv run pytest tests/unit/context tests/unit/agents tests/unit/core/test_streaming_trace.py -v`、`uv run pytest tests/unit -v`
- 结果：已补齐 async MockTransport/AsyncClient、`await` 与 `async for` 回归测试；修复后定向 async 合约测试通过，最终验证命令通过。

## 2026-08-12 - Agent 流式循环健壮性与工具调用多轮复核问题
- 日期：2026-08-12
- 现象：代码质量复核指出 `ReactAgent` 缺少 Qwen create/stream 与持久化阶段异常兜底；工具调用只处理首轮 `tool_calls`；tool message 多带 `name` 字段；空 assistant 回复和保存失败仍可能写入 memory；`ContextBuilder` recency/relevance 公式不符合规格；`QwenClient` 自建 `AsyncClient` 没有 ownership 与关闭能力。
- 根因：Task 9 初版只覆盖最小成功路径和单轮工具调用，未覆盖模型异常、流式中断、多轮工具调用、严格 tool message schema、客户端生命周期、持久化失败和真实时间衰减。
- 修改文件：`docs/issue-resolution-log.md`、`src/agents/qwen_client.py`、`src/agents/react_agent.py`、`src/context/builder.py`、`tests/unit/agents/test_qwen_client.py`、`tests/unit/agents/test_react_agent.py`、`tests/unit/context/test_context_builder.py`
- 验证命令：`uv run pytest tests/unit/context tests/unit/agents tests/unit/core/test_streaming_trace.py -v`、`uv run pytest tests/unit -v`
- 结果：新增异常兜底、多轮工具调用、严格 tool message schema、client ownership/close、空回复与持久化失败、真实时间衰减回归测试；修复后指定验证命令均通过。

## 2026-08-12 - sessions 列表响应契约偏差
- 日期：2026-08-12
- 现象：规格复核指出 `GET /sessions` 当前返回顶层数组，但公开 API 契约要求返回 `{ "sessions": [...] }`；同时缺少 `GET /sessions`、`DELETE /sessions/{id}`、`POST /chat/stream` 在缺失 `X-User-Id` 时返回 400 中文 detail 的覆盖。
- 根因：Task 10 首版 API 测试把列表响应断言成数组，导致实现与规格偏离；缺请求头测试只覆盖了 `POST /sessions`，未覆盖其他依赖同一鉴权头的入口。
- 修改文件：`docs/issue-resolution-log.md`、`tests/api/test_health_sessions_tools.py`、`src/api/schemas.py`、`src/api/routes.py`
- 验证命令：`uv run pytest tests/api -v`、`uv run pytest tests/unit tests/api -v`
- 结果：PASS，API 定向测试 6 项通过，unit+API 组合测试 92 项通过。

## 2026-08-12 - API 流式错误兜底、本地计算提取与校验错误契约偏差
- 日期：2026-08-12
- 现象：代码质量复核指出 `/chat/stream` 在 agent generator 直接抛异常时可能 500 或断流；trace 日志失败可能打断聊天；本地回显客户端无法正确提取中文紧贴的算术表达式；FastAPI/Pydantic 默认 422 响应不是稳定中文契约；工具调用响应缺少 response_model，shutdown 阶段工具关闭异常未隔离，未配置 Tavily 时 search 调用缺 API 覆盖。
- 根因：Task 10 首版只覆盖正常 SSE、缺 session 与基础工具调用，未覆盖流式迭代边界、日志副作用失败、中文无空格输入、请求体验证失败与关闭阶段异常隔离。
- 修改文件：`docs/issue-resolution-log.md`、`tests/api/test_chat_stream.py`、`tests/api/test_health_sessions_tools.py`、`src/api/schemas.py`、`src/api/routes.py`、`src/main.py`、`src/agents/react_agent.py`
- 验证命令：`uv run pytest tests/api -v`、`uv run pytest tests/unit tests/api -v`
- 结果：PASS，API 定向测试 17 项通过，unit+API 组合测试 104 项通过。

## 2026-08-12 - 前端首次 npm install 超时
- 日期：2026-08-12
- 现象：执行 `npm install` 时命令在 124 秒后超时，未返回明确成功状态。
- 根因：首次安装前端依赖耗时超过当前工具命令超时时间，属于依赖安装环境问题，不是预期的 TDD 红灯。
- 修改文件：`docs/issue-resolution-log.md`
- 验证命令：待重新执行 `npm install` 与 `npm test -- src/api/config.test.ts`
- 结果：重新执行 `npm install` 成功；随后 `npm test -- src/api/config.test.ts` 通过。

## 2026-08-12 - 前端 build 类型配置失败
- 日期：2026-08-12
- 现象：执行 `npm run build` 时失败，报错包括 `vite.config.ts` 中 `test` 不是 `UserConfigExport` 已知属性，以及 referenced project `tsconfig.node.json` 不能禁用 emit。
- 根因：Vite 配置未使用 Vitest 的类型增强入口；同时 `tsconfig.node.json` 作为 TypeScript project reference 配置了 `noEmit`，与 `tsc -b` 约束冲突。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/vite.config.ts`、`frontend/tsconfig.node.json`
- 验证命令：待重新执行 `npm test -- src/api/config.test.ts` 与 `npm run build`
- 结果：已修正 Vitest/Vite 类型入口与 TypeScript project reference 配置；`npm test -- src/api/config.test.ts` 与 `npm run build` 均通过。
