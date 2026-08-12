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

## 2026-08-12 - 前端 Task 1 RED 证据未落库
- 日期：2026-08-12
- 现象：spec review 指出 Task 1 的 RED 证据没有落到仓库；最终 diff 里 `config.test.ts` 和 `config.ts` 同时新增，仓库里看不到 `config.ts` 实现前的失败证明。
- 根因：RED 失败只写在子代理汇报里，没有同步到可审计文档，导致后来只能从口头记录推断流程。
- 修改文件：`docs/issue-resolution-log.md`
- 验证命令：`cd frontend; npm test -- src/api/config.test.ts; npm run build`
- 结果：已补充 RED 失败摘要 `Failed to resolve import "./config"`；当前验证命令通过。

## 2026-08-12 - 前端 HTTP 请求内部参数泄漏到 fetch
- 日期：2026-08-12
- 现象：执行 `cd frontend; npm test -- src/api/http.test.ts src/api/config.test.ts` 时，`请求会话列表时注入 X-User-Id 请求头` 失败；`fetchMock` 收到的 options 里包含非标准 `userId: "alice"`，`headers` 是 `Headers {}`，断言无法看到 `X-User-Id`。
- 根因：`requestJson()` 用 `{ ...options, headers }` 直接传给 `fetch`，没有先剥离内部封装字段 `userId`；同时 Headers 对象不利于测试稳定检查具体请求头。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/api/http.ts`
- 验证命令：`cd frontend; npm test -- src/api/http.test.ts src/api/config.test.ts`
- 结果：已剥离内部 `userId` 字段，并稳定传入 `X-User-Id` 请求头；定向测试 2 个文件、4 项断言通过。

## 2026-08-12 - 前端组件测试 DOM 未隔离
- 日期：2026-08-12
- 现象：执行 `cd frontend; npm test -- src/components/AgentConsole.test.tsx` 时，4 个测试中 3 个失败，Testing Library 报告找到多个同名 `新建会话` 按钮。
- 根因：Vitest 测试环境只加载了 `@testing-library/jest-dom/vitest`，没有在每个测试后执行 React Testing Library 的 `cleanup()`，导致前一个测试渲染出的 DOM 残留到后续测试。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/vitest.setup.ts`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`
- 结果：已加入 `afterEach(cleanup)`；重新执行后 DOM 残留问题消失，继续暴露组件断言选择器不够精确的问题。

## 2026-08-12 - 前端组件测试文本断言过宽
- 日期：2026-08-12
- 现象：修复 DOM 清理后，`cd frontend; npm test -- src/components/AgentConsole.test.tsx` 仍有 2 项失败；`/当前会话/` 同时匹配会话行和聊天标题，`/437/` 同时匹配工具结果 JSON 与助手回答。
- 根因：测试使用宽泛文本正则断言跨区域 UI，未限定具体可见文本或语义区域；真实界面为了让侧边栏、聊天栏和事件栏都可扫描，会合理重复部分信息。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`
- 结果：已将断言收窄到 `当前会话 alice-se` 与工具结果 JSON 中的 `"result": 437`；定向组件测试 4 项通过。

## 2026-08-12 - 前端 build 缺少 jest-dom matcher 类型
- 日期：2026-08-12
- 现象：执行 `cd frontend; npm run build` 时，`AgentConsole.test.tsx` 中的 `toBeInTheDocument()`、`toBeDisabled()` 类型检查失败。
- 根因：`frontend/tsconfig.json` 显式配置了 `types: ["vite/client"]`，TypeScript 只加载 Vite 客户端全局类型，没有加载 Vitest 和 `@testing-library/jest-dom` 的 matcher 类型扩展。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/tsconfig.json`
- 验证命令：`cd frontend; npm run build`
- 结果：已补充 `vitest/globals` 与 `@testing-library/jest-dom` 类型入口；`npm run build` 通过。

## 2026-08-12 - 前端 Task 6 fake API 可控性不足
- 日期：2026-08-12
- 现象：Task 6 规格复核指出 `加载健康状态、工具和会话` 测试没有真正断言会话加载，`createFakeApi()` 也无法预置数据或检查调用记录。
- 根因：首版组件测试只覆盖了默认空会话下的健康状态和工具目录，fake API 只实现固定成功路径，没有暴露可控 seed 和调用记录。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/test/fakeApi.ts`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`
- 结果：已让测试预置 `alice-history-1` 会话并断言 `listSessions("alice")` 调用记录；`createFakeApi()` 支持预置 health/sessions/tools/stream events 和调用记录；定向组件测试 4 项通过。

## 2026-08-12 - 前端会话加载旧请求覆盖当前用户
- 日期：2026-08-12
- 现象：本地代码质量复核发现 `AgentConsole` 在用户 ID 连续变化时会并发请求会话列表；如果旧用户请求晚于新用户请求返回，旧用户会话可能覆盖当前用户界面。
- 根因：`loadSessions()` 没有给异步请求设置最新请求标记，也没有在用户切换、创建或删除会话时让旧的列表请求失效。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`
- 结果：已新增旧请求晚返回回归测试，并用递增请求号忽略过期会话列表响应；组件测试 5 项通过。

## 2026-08-12 - 前端 E2E 缺少 Playwright Chromium
- 日期：2026-08-12
- 现象：执行 `cd frontend; npm run e2e -- --project=desktop` 时，2 个测试都在浏览器启动前失败，提示 `chrome-headless-shell.exe` 不存在。
- 根因：本机 Playwright 依赖已安装，但对应版本的 Chromium 浏览器二进制尚未下载。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/playwright.config.ts`
- 验证命令：`cd frontend; npm run e2e -- --project=desktop`
- 结果：`npx playwright install chromium` 超过 244 秒仍未完成，已终止残留下载进程；改用本机已安装的 Microsoft Edge 通道执行 Playwright 验证，后续 desktop E2E 通过。

## 2026-08-12 - 前端 E2E Vite 代理未命中后端
- 日期：2026-08-12
- 现象：改用 Edge 后执行 `cd frontend; npm run e2e -- --project=desktop`，页面能打开但健康状态保持 `后端未知`，局部错误显示 HTML JSON 解析失败或 404。
- 根因：E2E 启动的 Vite dev server 没有把 `/api` 请求代理到 FastAPI，浏览器请求 `/api/health` 时拿到前端 HTML 或 Vite 404。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/playwright.config.ts`
- 验证命令：`cd frontend; npm run e2e -- --project=desktop`、`cd frontend; npm run e2e -- --project=mobile`
- 结果：已在 E2E 前端启动命令中显式指定 `--config vite.config.ts --strictPort`；重新执行后健康状态、会话创建和用户隔离路径可访问后端。

## 2026-08-12 - 前端 E2E 最终回答断言过窄
- 日期：2026-08-12
- 现象：`cd frontend; npm run e2e -- --project=desktop` 中计算器联调已显示 `tool_call`、`tool_result` 和 `437`，但断言 `/计算结果是 437/` 失败。
- 根因：真实后端在模型配置可用时返回更完整的解释文本，例如 `19 × 23 = 437。`，并不固定使用本地 fallback 文案 `计算结果是 437。`。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/e2e/agent-console.spec.ts`
- 验证命令：`cd frontend; npm run e2e -- --project=desktop`
- 结果：已改为断言核心事实 `19 × 23 = 437`；desktop E2E 2 项通过。

## 2026-08-12 - 前端 E2E 并行验证争用端口与固定用户残留
- 日期：2026-08-12
- 现象：同时执行 desktop 和 mobile E2E 时，desktop webServer 因 8002 端口已被占用失败；mobile 用户隔离测试使用固定 `bob-e2e`，发现该用户已有历史会话，导致 `暂无会话` 断言失败。
- 根因：Playwright webServer 不能被两条独立 `npm run e2e` 命令并行争用同一端口；同时真实后端使用持久 SQLite 数据，固定测试用户会跨运行残留状态。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/e2e/agent-console.spec.ts`
- 验证命令：按顺序执行 `cd frontend; npm run e2e -- --project=desktop` 与 `cd frontend; npm run e2e -- --project=mobile`
- 结果：已改为每次运行生成唯一 E2E 用户 ID；desktop 和 mobile E2E 各 2 项通过。

## 2026-08-12 - Vitest 误收集 Playwright E2E 文件
- 日期：2026-08-12
- 现象：执行 `cd frontend; npm test` 时，Vitest 收集了 `e2e/agent-console.spec.ts`，并报错 `Playwright Test did not expect test() to be called here`。
- 根因：Vitest 默认会匹配 `**/*.spec.ts`，新增 Playwright E2E 后没有在 Vitest 配置中排除 `e2e/**`。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/vite.config.ts`
- 验证命令：`cd frontend; npm test`
- 结果：已在 Vitest 配置中排除 `e2e/**`；`npm test` 5 个文件、15 项测试通过。

## 2026-08-12 - 前端会话删除与切换历史记录缺失
- 日期：2026-08-12
- 现象：界面打开后会看到本地 SQLite 中已有的多条历史会话；点击删除会话可能提示删除失败；切换会话后聊天区被清空，看不到该会话之前的聊天记录；代理异常时还可能显示 `Unexpected token '<'`。
- 根因：后端只暴露会话列表，没有暴露按会话读取消息的接口；前端切换会话时只能重置本地 reducer；`DELETE /sessions/{id}` 的 204 空响应被 HTTP 封装继续按 JSON 解析；成功响应若拿到前端 HTML 没有转换成中文诊断。
- 修改文件：`docs/issue-resolution-log.md`、`tests/api/test_health_sessions_tools.py`、`src/api/schemas.py`、`src/api/routes.py`、`frontend/src/api/http.test.ts`、`frontend/src/api/http.ts`、`frontend/src/api/types.ts`、`frontend/src/api/backendClient.ts`、`frontend/src/state/chatReducer.test.ts`、`frontend/src/state/types.ts`、`frontend/src/state/chatReducer.ts`、`frontend/src/test/fakeApi.ts`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`
- 验证命令：`uv run pytest tests/api/test_health_sessions_tools.py::test_session_messages_are_listed_per_user_after_chat -v`、`uv run pytest tests/api/test_health_sessions_tools.py -v`、`cd frontend; npm test -- src/api/config.test.ts src/api/http.test.ts src/state/chatReducer.test.ts src/components/AgentConsole.test.tsx`、`cd frontend; npm run build`
- 结果：PASS，消息读取接口、204 删除、切换会话历史恢复和中文代理错误处理的定向测试通过；前端构建通过。

## 2026-08-12 - 前端默认用户固定导致历史会话堆积
- 日期：2026-08-12
- 现象：前端首次打开即显示多个旧会话，容易误以为系统自动创建了会话。
- 根因：默认用户 ID 固定为 `alice`，手工调试、自动化联调和多次刷新都会复用同一个后端用户空间；真实 SQLite 会持久保存历史会话。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/api/config.test.ts`、`frontend/src/api/config.ts`
- 验证命令：`cd frontend; npm test -- src/api/config.test.ts src/api/http.test.ts src/state/chatReducer.test.ts src/components/AgentConsole.test.tsx`
- 结果：PASS，默认用户 ID 改为浏览器本地生成并复用，相关前端定向测试通过。

## 2026-08-12 - 前端 E2E 历史会话断言命中重复文本
- 日期：2026-08-12
- 现象：执行 `cd frontend; npm run e2e -- --project=desktop` 时，新增的“切换会话恢复历史并支持删除”用例失败；`3 + 4 = 7` 同时出现在聊天气泡和右侧事件 JSON，Playwright strict mode 报匹配到 2 个元素。
- 根因：E2E 使用全页面 `getByText()` 断言聊天内容，没有限定到聊天面板；会话短 ID 断言也没有限定到会话列表。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/e2e/agent-console.spec.ts`
- 验证命令：`cd frontend; npm run e2e -- --project=desktop`、`cd frontend; npm run e2e -- --project=mobile`
- 结果：PASS，desktop 与 mobile 的真实后端联调用例均通过。

## 2026-08-12 - 前端历史消息晚返回覆盖正在发送的消息
- 日期：2026-08-12
- 现象：代码复核发现切换或新建会话后，如果历史消息请求尚未返回，用户立即发送消息，晚返回的空历史可能覆盖当前聊天区。
- 根因：发送消息时没有让当前会话的历史加载请求失效；`load_messages` 仍可能在流式聊天开始后写入 reducer。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`
- 结果：PASS，晚返回历史不再覆盖正在发送的用户消息和助手流式回答。

## 2026-08-12 - 前端 E2E 新建会话后过早读取选中 ID
- 日期：2026-08-12
- 现象：重新执行 `cd frontend; npm run e2e -- --project=desktop` 时，“切换会话恢复历史并支持删除”偶发失败；错误上下文显示页面最终已切到第二个会话并展示 `3 + 4 = 7`，但测试记录的 `secondSessionId` 仍是旧会话短 ID。
- 根因：测试点击“新建会话”后立即读取 `.session-row.selected strong`，没有等待 React 完成选中状态更新，导致捕获到旧选中值。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/e2e/agent-console.spec.ts`
- 验证命令：`cd frontend; npm run e2e -- --project=desktop`、`cd frontend; npm run e2e -- --project=mobile`
- 结果：PASS，desktop 与 mobile 的真实后端联调用例均通过。

## 2026-08-12 - 前端删除未选中会话打断当前历史加载
- 日期：2026-08-12
- 现象：代码复核发现删除未选中的会话时，当前选中会话正在进行的历史消息请求会被无差别标记为过期，可能导致当前聊天区停留在空状态。
- 根因：`handleDeleteSession()` 在删除任意会话时都递增 `messageRequestIdRef`，而不是只在删除当前选中会话时让历史加载失效。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`
- 结果：PASS，删除未选中会话不再打断当前选中会话的历史加载。

## 2026-08-12 - 前端不同会话流式生成期间消息串流
- 日期：2026-08-12
- 现象：用户反馈在 A 会话流式生成时切到 B 会话，A 会话的 token 会临时显示到 B 会话；生成结束后切换回来又不互相影响。
- 根因：前端只有一份全局 `chatState`，`streamChat()` 返回的事件无论来自哪个会话都会写入当前聊天 reducer；同时切回原会话时可能重新拉取空历史并覆盖本地已完成的流式结果。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`、`frontend/e2e/agent-console.spec.ts`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`、`cd frontend; npm test`、`cd frontend; npm run build`、`uv run pytest -m "not integration" -v`、`cd frontend; npm run e2e -- --project=desktop`、`cd frontend; npm run e2e -- --project=mobile`
- 结果：PASS，聊天状态改为按 `session_id` 保存，流式事件写回发起请求的会话；已有本地状态的会话切回时不再用空历史覆盖；desktop 和 mobile E2E 均验证流式隔离。

## 2026-08-12 - 前端快速切换导致未完成历史请求被空状态占坑
- 日期：2026-08-12
- 现象：代码复核发现，如果 A 会话历史加载尚未返回就切到 B，会让 A 留下一个空聊天状态；A 的旧请求晚返回后会被判过期，之后再切回 A 时前端误以为已有缓存，不再重新拉取历史。
- 根因：历史加载请求发出时先 dispatch `reset_for_session`，导致 `chatStatesBySession[session_id]` 被创建为空状态；缓存判断只看该 key 是否存在，无法区分“加载完成”和“加载中占位”。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx`
- 结果：PASS，新增回归测试确认切离时不会创建空缓存占坑；历史加载只在真实返回消息后写入对应会话状态。

## 2026-08-12 - 前端历史请求全局失效导致跨会话竞态
- 日期：2026-08-12
- 现象：代码审阅发现历史消息请求仍共用一个全局版本号；当前 B 会话历史未返回时，A 会话的流式 token 写入或其他会话状态变化可能让 B 的请求过期；用户切换时旧会话也会短暂保留，删除会话 pending 期间切到被删会话后可能留下已删除选中状态。
- 根因：历史请求有效性没有按 `user_id + session_id` 隔离；用户 ID 输入变化时只等待异步会话列表刷新，没有同步清空本地旧会话；删除成功后判断选中会话使用了旧闭包状态。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "切换用户时立即清空旧会话并不读取旧会话消息"`、`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "切换离开后晚返回的历史消息会按原会话缓存"`、`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "其他会话流式更新不会重启当前会话的历史加载"`、`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "删除请求期间切到被删会话时删除完成后切回剩余会话"`
- 结果：PASS，历史请求版本改为按 `user_id + session_id` 管理；同一用户旧会话历史晚返回可写回对应缓存，换用户后旧请求不会落地；删除完成后使用最新会话列表和最新选中状态切换。

## 2026-08-12 - 后端消息 role 响应契约过宽
- 日期：2026-08-12
- 现象：代码审阅发现 `MessageResponse.role` 后端 schema 是裸 `str`，但前端类型假设只会收到 `user` 或 `assistant`。
- 根因：Pydantic 响应模型没有把消息角色声明为枚举值，OpenAPI 无法表达前后端契约。
- 修改文件：`docs/issue-resolution-log.md`、`tests/api/test_health_sessions_tools.py`、`src/api/schemas.py`
- 验证命令：`uv run pytest tests/api/test_health_sessions_tools.py::test_message_response_openapi_limits_role_values -v`
- 结果：PASS，`MessageResponse.role` 改为 `Literal["user", "assistant"]`，OpenAPI schema 已输出枚举约束。

## 2026-08-12 - 前端创建/删除会话 pending 期间切换用户可能污染界面
- 日期：2026-08-12
- 现象：代码复核发现创建会话请求尚未返回时切换用户，旧用户的新会话返回后仍可能追加到当前用户界面；创建/删除失败时，旧用户错误也可能显示到新用户界面。
- 根因：创建/删除会话的异步回调只依赖发起时闭包中的 `userId`，没有在返回后确认当前活跃用户仍是原用户；失败分支也缺少同样的隔离判断。
- 修改文件：`docs/issue-resolution-log.md`、`frontend/src/components/AgentConsole.test.tsx`、`frontend/src/components/AgentConsole.tsx`
- 验证命令：`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "创建会话未返回时切换用户会忽略旧用户新会话"`、`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "删除会话未返回时切换用户会忽略旧用户删除结果"`、`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "创建会话失败前切换用户不显示旧用户错误"`、`cd frontend; npm test -- src/components/AgentConsole.test.tsx -t "删除会话失败前切换用户不显示旧用户错误"`
- 结果：PASS，创建/删除会话成功或失败返回后先校验当前活跃用户，不匹配时丢弃旧用户异步结果和错误提示。

## 2026-08-12 - 后端 message_end 上下文字段语义不清
- 日期：2026-08-12
- 现象：用户看到 `selected_context: 0` 后容易误以为 Agent 没有读取最近对话历史，但实际回答已使用历史消息。
- 根因：`selected_context` 只统计被选中的记忆上下文包，不包含进入 `[State]` 的最近会话消息，字段名没有表达这个差异。
- 修改文件：`docs/issue-resolution-log.md`、`tests/unit/agents/test_react_agent.py`、`src/agents/react_agent.py`
- 验证命令：`uv run pytest tests/unit/agents/test_react_agent.py::test_react_agent_executes_calculator_tool_and_saves_streamed_answer -v`
- 结果：PASS，`message_end` 改为输出 `history_messages` 和 `selected_memory_context`，不再输出容易误导的 `selected_context`。

## 2026-08-12 - 中文长期记忆未召回用户原始事实
- 日期：2026-08-12
- 现象：用户此前说过“我中午吃了一碗蛋炒饭”，后续询问“你还记得我中午吃了什么吗”时，`memory_saved=true` 但 `selected_memory_context=0`，助手回答没有相关记录。
- 根因：记忆检索的 FTS 只索引助手回复 `content`，没有索引 `metadata_json.user_message`；中文长句查询按整句词元匹配，难以命中已有事实；同时后续“我不记得/无法知道”的错误回答也会进入记忆并可能排在事实记忆前面。
- 修改文件：`docs/issue-resolution-log.md`、`tests/unit/core/test_memory.py`、`tests/unit/agents/test_react_agent.py`、`src/core/memory.py`、`src/agents/react_agent.py`
- 验证命令：`uv run pytest tests/unit/core/test_memory.py::test_chinese_memory_search_matches_user_message_metadata -v`、`uv run pytest tests/unit/core/test_memory.py::test_chinese_recall_prefers_user_fact_over_later_uncertain_answers -v`、`uv run pytest tests/unit/core/test_memory.py -v`、`uv run pytest tests/unit/agents/test_react_agent.py -v`
- 结果：PASS，记忆 FTS 同时索引助手回复和用户原话；中文长句拆为 trigram 召回；回忆类问题优先返回用户事实陈述，并在 Agent 上下文中显式展示“用户消息/助手回复”。
## 2026-08-12 - 时间工具缺少 tzdata 兜底且天气工具混淆当前天气与日预报
- 日期：2026-08-12
- 现象：`get_time` 在本机未安装 `tzdata` 时无法解析 `Asia/Shanghai`；`get_weather` 在未传日期时也强制走日预报，导致旧接口回归失败；相对日期“后天”在北京时间场景下还会按 UTC 日期加天数，算错目标日。
- 根因：时区解析只依赖 `ZoneInfo`，没有固定偏移兜底；天气工具把“当前天气”和“指定日期预报”合并到单一路径，且相对日期基准使用了 UTC 而不是本地时区。
- 修改文件：`docs/issue-resolution-log.md`、`src/tools/time_tool.py`、`src/tools/weather.py`、`src/main.py`、`tests/unit/tools/test_search_weather.py`、`tests/api/test_chat_stream.py`、`tests/api/test_health_sessions_tools.py`
- 验证命令：`uv run pytest tests/unit/tools/test_search_weather.py -q`、`uv run pytest tests/api/test_chat_stream.py tests/api/test_health_sessions_tools.py -q`、`uv run pytest tests/unit/agents/test_react_agent.py tests/unit/agents/test_qwen_client.py -q`、`uv run pytest -m "not integration" -v`
- 结果：PASS，`get_time` 可在无 `tzdata` 环境下返回北京时间；`get_weather` 在无日期时仍返回 current，在 `target_date/days_ahead` 时返回 daily forecast；API 侧也验证了“后天合肥天气”会先调 `get_time` 再调 `get_weather`。
