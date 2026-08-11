# 后端 MVP Agent

这是一个基于 FastAPI、Qwen Plus 和 SSE 的后端最小可用 Agent。第一版目标是先把多会话隔离、工具调用、上下文构建、SQLite 记忆和接口测试跑通。

## 安装

```bash
uv sync
```

## 运行

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## 测试

```bash
uv run pytest -m "not integration" -v
uv run pytest -m integration -v
```

## 请求头

会话和聊天接口都需要 `X-User-Id` 请求头，用于隔离不同用户的数据。
