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
