# 后端 MVP Agent

这是一个基于 FastAPI、Qwen Plus、SQLite 和 SSE 的最小可用 Agent 后端。服务支持多用户会话隔离、工具调用、流式聊天和本地 trace 日志。

## 安装

```bash
uv sync
```

## 启动

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

如果 `8000` 端口已被占用，可以改用其他本地端口，例如：

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8001
```

可选环境变量：

- `DASHSCOPE_API_KEY`：配置后使用真实 Qwen；未配置时使用本地回显客户端。
- `TAVILY_API_KEY`：配置后启用搜索工具；未配置时 `/tools` 仍保留 `search`，调用会返回中文不可用信息。
- `APP_DATA_DIR`：SQLite 和 trace 日志目录，默认 `data`。

trace 日志写入 `APP_DATA_DIR/traces`。

## 接口

- `GET /health`：返回服务状态、模型配置状态和 SQLite 可用状态。
- `POST /sessions`：创建当前用户会话，需要 `X-User-Id` 请求头。
- `GET /sessions`：列出当前用户会话，需要 `X-User-Id` 请求头。
- `DELETE /sessions/{session_id}`：删除当前用户会话；不存在或无权访问统一返回 404。
- `GET /tools`：列出 `calculator`、`search`、`get_weather` 的名称、描述和参数。
- `POST /tools/{tool_name}/invoke`：直接调用工具，请求体必须是 JSON object。
- `POST /chat/stream`：流式聊天，需要 `X-User-Id`，请求体包含 `session_id`、`message` 和可选 `metadata`，响应为 `text/event-stream`。

## 测试

```bash
uv run pytest tests/api -v
uv run pytest tests/unit tests/api -v
```

完整验收命令：

```bash
uv run pytest -m "not integration" -v
uv run pytest -m integration -v
```

### Integration 测试

真实外部冒烟测试位于 `tests/integration`，会通过 `.env` 读取本地密钥：

```bash
uv run pytest tests/integration/test_external_smoke.py::test_real_open_meteo_weather_smoke -v -m integration
uv run pytest tests/integration -v -m integration
```

`Open-Meteo` 测试无需密钥；`Tavily` 和 `Qwen` 测试在缺少 `TAVILY_API_KEY` 或
`DASHSCOPE_API_KEY` 时会自动跳过。本地 API SSE 冒烟测试不使用外部密钥。

## 手工联调

创建会话：

```bash
curl -s -X POST http://127.0.0.1:8000/sessions -H "X-User-Id: alice"
```

使用返回的 `session_id` 发起流式聊天：

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-User-Id: alice" \
  -d "{\"session_id\":\"替换为返回的 session_id\",\"message\":\"请计算 19 * 23 并解释结果\"}"
```

响应应包含 `message_start`、`tool_call`、`tool_result`、`token` 和 `message_end`
事件。用其他 `X-User-Id` 调用 `GET /sessions` 时，不应看到 Alice 的会话。

## 前端控制台

前端位于 `frontend/`，用于验证 Agent 能识别工具、调用工具，并把工具结果整合进流式回答。

安装依赖：

```bash
cd frontend
npm install
```

启动后端到前端默认代理端口：

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8002
```

启动前端：

```bash
cd frontend
$env:VITE_BACKEND_TARGET="http://127.0.0.1:8002"
npm run dev -- --port 5173
```

访问：

```text
http://127.0.0.1:5173
```

前端测试：

```bash
cd frontend
npm test
npm run build
npm run e2e -- --project=desktop
npm run e2e -- --project=mobile
```

E2E 会自动启动或复用 `127.0.0.1:8002` 后端和 `127.0.0.1:5173` 前端。当前配置优先使用本机 Microsoft Edge 通道运行 Playwright；如果机器没有 Edge，请先执行 `npx playwright install chromium`，再把 `frontend/playwright.config.ts` 的 `channel` 设置调整为 Chromium 默认配置。
