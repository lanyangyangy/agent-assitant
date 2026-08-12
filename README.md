# 最小可用 Agent

基于 FastAPI、Qwen Plus、SQLite、SSE 和 React 的最小可用 Agent 项目。项目包含后端 Agent 服务和前端控制台，重点验证多会话隔离、工具识别与调用、流式回答、上下文构建、长期记忆召回和 trace 记录。

未配置真实模型密钥时，后端会自动使用本地回显客户端，方便先跑通完整链路。

## 功能特性

- 多用户、多会话隔离：通过 `X-User-Id` 和 `session_id` 隔离会话、消息、记忆和 trace。
- 流式聊天：`POST /chat/stream` 使用 SSE 输出 `message_start`、`tool_call`、`tool_result`、`token`、`message_end` 等事件。
- ReAct 工具调用：Agent 可识别模型 tool_calls，调用工具后把结果整合进最终流式回答。
- 内置工具：计算器、Tavily 搜索、Open-Meteo 天气。
- 上下文流水线：最近历史、长期记忆、相关性选择、超预算压缩。
- SQLite 持久化：保存 sessions、messages、memories。
- 中文长期记忆召回：支持从用户原始消息 metadata 中召回事实，并优先返回用户事实陈述。
- Trace 日志：每轮对话写入 JSONL 和 HTML，便于调试。
- 前端控制台：会话列表、聊天区、工具目录、事件流面板、删除会话和历史恢复。
- 自动化测试：后端单元/API/集成测试，前端 Vitest 和 Playwright E2E。

## 技术栈

后端：

- Python 3.12+
- FastAPI
- Uvicorn
- aiosqlite
- httpx
- pydantic / pydantic-settings
- uv

前端：

- React 18
- TypeScript
- Vite
- Vitest
- Playwright
- lucide-react

## 项目结构

```text
.
├── src
│   ├── agents          # Qwen 客户端与 ReAct Agent
│   ├── api             # FastAPI 路由、依赖、schema
│   ├── context         # 历史、记忆、选择、压缩、token 估算
│   ├── core            # 配置、SQLite 会话/记忆、SSE、trace
│   ├── tools           # 工具基类、注册表、计算/搜索/天气工具
│   └── main.py         # FastAPI 应用入口
├── frontend
│   ├── src
│   │   ├── api         # HTTP/SSE 客户端
│   │   ├── components  # Agent 控制台组件
│   │   ├── state       # 聊天 reducer
│   │   └── test        # 前端测试辅助
│   └── e2e             # Playwright E2E
├── tests
│   ├── api
│   ├── integration
│   └── unit
├── docs                # 设计、计划和问题解决记录
├── pyproject.toml
├── uv.lock
└── README.md
```

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd <your-repo-name>
```

### 2. 安装后端依赖

```bash
uv sync
```

### 3. 配置环境变量

可以创建 `.env` 文件。最小本地运行不需要任何密钥。

```env
APP_DATA_DIR=data
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=qwen-plus
TAVILY_API_KEY=
TOOL_TIMEOUT_SECONDS=180
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
```

变量说明：

- `DASHSCOPE_API_KEY`：配置后使用真实 Qwen Plus；为空时使用本地回显客户端。
- `DASHSCOPE_BASE_URL`：DashScope OpenAI compatible endpoint。
- `LLM_MODEL_ID`：默认 `qwen-plus`。
- `TAVILY_API_KEY`：配置后启用搜索工具；为空时搜索工具会返回中文不可用提示。
- `APP_DATA_DIR`：SQLite 数据库和 trace 目录，默认 `data`。
- `TOOL_TIMEOUT_SECONDS`：工具调用超时时间，默认 180 秒。
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD`：工具连续失败熔断阈值，默认 3 次。

### 4. 启动后端

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8002
```

访问健康检查：

```text
http://127.0.0.1:8002/health
```

### 5. 启动前端

```bash
cd frontend
npm install
```

PowerShell：

```powershell
$env:VITE_BACKEND_TARGET="http://127.0.0.1:8002"
npm run dev -- --port 5173
```

Bash：

```bash
VITE_BACKEND_TARGET=http://127.0.0.1:8002 npm run dev -- --port 5173
```

打开：

```text
http://127.0.0.1:5173
```

前端默认会在浏览器 `localStorage` 中生成 `local-user-xxxx`，避免不同调试会话都堆到固定用户下。如需固定用户：

```powershell
$env:VITE_DEFAULT_USER_ID="alice"
```

## API 概览

所有用户级接口都需要请求头：

```http
X-User-Id: alice
```

接口列表：

- `GET /health`：服务状态、模型配置状态、SQLite 可用状态、搜索可用状态。
- `POST /sessions`：创建当前用户会话。
- `GET /sessions`：列出当前用户会话。
- `DELETE /sessions/{session_id}`：删除当前用户会话；不存在或无权访问返回 404。
- `GET /sessions/{session_id}/messages`：读取当前用户某会话的最近消息。
- `GET /tools`：列出工具 schema。
- `POST /tools/{tool_name}/invoke`：直接调用工具。
- `POST /chat/stream`：SSE 流式聊天。

创建会话：

```bash
curl -s -X POST http://127.0.0.1:8002/sessions \
  -H "X-User-Id: alice"
```

发起流式聊天：

```bash
curl -N -X POST http://127.0.0.1:8002/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-User-Id: alice" \
  -d "{\"session_id\":\"替换为返回的 session_id\",\"message\":\"请计算 19 * 23 并解释结果\"}"
```

典型 SSE 事件：

```text
event: message_start
data: {"compressed_context":false,...}

event: tool_call
data: {"name":"calculator",...}

event: tool_result
data: {"result":{"success":true,...},...}

event: token
data: {"content":"计算结果是",...}

event: message_end
data: {"history_messages":10,"selected_memory_context":1,"memory_saved":true,...}
```

## 记忆与上下文

Agent 每轮会读取：

- 最近 `10` 条会话消息，约等于最近 5 轮问答。
- 当前 `user_id + session_id` 下最多 `5` 条相关长期记忆。

长期记忆保存在 SQLite `memories` 表中。检索会同时索引助手回复 `content` 和 `metadata_json.user_message`，因此用户事实类表达也能被召回。

召回时机：

- 每次 `POST /chat/stream` 进入一次新对话轮次时都会先做记忆召回。
- 先保存当前用户消息，再用这条用户消息作为检索查询。
- 只有当前 `user_id + session_id` 范围内的记忆会参与召回。
- 如果没有命中记忆，Agent 仍会继续只依赖最近历史消息。

放置方式：

- 召回到的记忆会被转换成 `ContextPacket`。
- 这些记忆包会作为 `memory_packets` 传入 `ContextBuilder.build()`。
- 记忆内容最终放在上下文里的 `[Context]` 区段，不会替代 `[State]` 中的最近会话历史。
- `[State]` 只放最近历史消息，`[Context]` 负责放长期记忆和可选自定义上下文。
- `message_end` 会返回 `selected_memory_context`，用于查看这轮实际选中了多少条长期记忆。

`message_end` 中的关键字段：

- `history_messages`：本轮进入上下文的最近历史消息条数。
- `selected_memory_context`：本轮选中的长期记忆上下文条数。
- `memory_saved`：本轮助手回复是否成功写入记忆库。

查看本地记忆：

```powershell
uv run python -c "import sqlite3; db=sqlite3.connect('data/agent.sqlite3'); [print(row) for row in db.execute('SELECT id,user_id,session_id,created_at,content,metadata_json FROM memories ORDER BY id DESC LIMIT 20')]"
```

## Trace 日志

默认写入：

```text
data/traces/
```

每轮对话会生成：

- JSONL：机器可读，适合排查事件序列。
- HTML：人类可读，适合快速查看一次对话过程。

## 测试

后端非集成测试：

```bash
uv run pytest -m "not integration" -v
```

后端集成测试：

```bash
uv run pytest -m integration -v
```

说明：

- Open-Meteo 天气冒烟测试不需要密钥。
- Tavily 和 Qwen 外部测试在缺少 `TAVILY_API_KEY` 或 `DASHSCOPE_API_KEY` 时会自动跳过。

前端测试：

```bash
cd frontend
npm test
npm run build
npm run e2e -- --project=desktop
npm run e2e -- --project=mobile
```

Playwright 当前配置优先使用本机 Microsoft Edge 通道。如果机器没有 Edge，可以安装 Chromium：

```bash
npx playwright install chromium
```

然后根据本机浏览器环境调整 `frontend/playwright.config.ts`。
