# Backend MVP Agent Design

## Goal

Build a backend-only MVP for a Qwen Plus streaming conversation Agent. The service must support multiple isolated sessions per user, Qwen tool calling, three working tools, context construction, SQLite-backed memory, trace logging, module-level tests, integration smoke tests, and final end-to-end debugging.

## Scope

This phase delivers only the backend MVP. The Vue frontend is intentionally out of scope until the backend interfaces are stable and verified.

The first version must prove that the Agent can:

- accept a streaming chat request through FastAPI;
- isolate sessions by `X-User-Id` and `session_id`;
- let Qwen recognize when a tool is needed;
- call `calculator`, `search`, and `get_weather`;
- pass tool results back to Qwen;
- stream the final integrated answer through SSE;
- persist sessions, messages, and memories in SQLite;
- record traces and issue-resolution notes during development.

## Architecture

Use one FastAPI service with clear internal modules:

- `src/api`: HTTP and SSE routes.
- `src/agents`: Qwen Plus tool-calling Agent orchestration.
- `src/tools`: tool protocol, registry, calculator, Tavily search, Open-Meteo weather, timeout, and circuit breaker.
- `src/context`: Gather-Select-Structure-Compress context pipeline.
- `src/core`: configuration, exceptions, session store, streaming helpers, trace logger, and memory.
- `tests`: unit tests, API tests, integration smoke tests, and end-to-end checks.

Implementation work can be divided across agent workers by module, but runtime delivery remains a single backend service. This keeps the MVP deployable and debuggable without introducing service orchestration too early.

## API Contract

### `GET /health`

Returns service health, whether required model configuration is present, and whether SQLite is available.

### `POST /sessions`

Creates a session for the caller identified by `X-User-Id`.

Response includes:

- `session_id`
- `user_id`
- `created_at`

### `GET /sessions`

Lists only the sessions owned by the caller identified by `X-User-Id`.

### `DELETE /sessions/{session_id}`

Deletes only a session owned by the caller. If the session does not exist or belongs to another user, return `404` to avoid leaking session existence.

### `POST /chat/stream`

Accepts:

- request header: `X-User-Id`
- JSON body: `session_id`, `message`, optional `metadata`

Returns `text/event-stream`.

SSE event types:

- `message_start`
- `token`
- `tool_call`
- `tool_result`
- `message_end`
- `error`

Flow:

1. Validate `X-User-Id`, `session_id`, and message.
2. Save the user message.
3. Build context from system policy, memory, recent history, and custom packets.
4. Call Qwen Plus with tool schemas.
5. If Qwen requests tools, execute them through the registry.
6. Send tool results back to Qwen.
7. Stream the final integrated assistant answer.
8. Save the assistant message and relevant memory.
9. Write JSONL and HTML trace artifacts.

### `GET /tools`

Returns registered tool names, descriptions, and JSON-schema-like parameter definitions.

### `POST /tools/{tool_name}/invoke`

Invokes one registered tool directly. This endpoint exists for interface testing, smoke tests, and debugging. Calls still use the same parameter validation, timeout, error response, and circuit breaker path as Agent-driven calls.

## User And Session Isolation

`X-User-Id` is the required user boundary for the MVP.

Each user may own multiple sessions. A session belongs to exactly one user. Message history, context retrieval, memory search, and trace output must always be scoped by both `user_id` and `session_id` unless a route intentionally lists all sessions for one user.

Cross-user access must fail with `404` for session-specific routes.

## Qwen Integration

Configuration is loaded with `pydantic-settings` from `.env`:

- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `LLM_MODEL_ID`
- `TAVILY_API_KEY`

The Agent uses Qwen Plus through DashScope-compatible chat completions. Missing API keys should not prevent the app from starting, but integration smoke tests must skip or fail with a clear message depending on the test mode.

The Agent must support tool calling in the chat stream path. It is not enough for tools to exist as standalone endpoints. A successful MVP requires a chat request where Qwen recognizes a calculator, search, or weather need, invokes the tool, receives the result, and streams an answer that incorporates that result.

## Tool System

Every tool exposes:

- `name`
- `description`
- parameter schema
- async execution function

The registry converts registered tools into Qwen-compatible tool schemas and provides direct invocation by name.

Required tools:

- `calculator`: evaluates arithmetic with a restricted AST parser. It must not execute arbitrary Python code.
- `search`: calls Tavily using `TAVILY_API_KEY`.
- `get_weather`: calls Open-Meteo geocoding and current forecast APIs, avoiding a required weather API key for the MVP.

All tool results use one response protocol with:

- success flag
- data payload for successful calls
- error code and message for failed calls
- elapsed time

The circuit breaker opens after 3 consecutive failures for a tool. Single tool calls time out after 180 seconds.

## Context Pipeline

The context builder implements the reusable pipeline described in the source document:

1. Gather
2. Select
3. Structure
4. Compress

Configuration fields:

- `max_tokens`
- `reserve_ratio`
- `min_relevance`
- `enable_compression`
- `recency_weight`
- `relevance_weight`

`ContextPacket` contains:

- `content`
- `timestamp`
- `relevance_score`
- `metadata`

Gathering includes:

- system policy with highest priority;
- memory search results converted to packets;
- last 5 rounds of session history;
- optional custom packets.

Selection computes Jaccard relevance and recency:

```text
age_hours = (now - timestamp).total_seconds() / 3600
recency_score = exp(-0.1 * age_hours / 24)
recency_score = clamp(recency_score, 0.1, 1.0)
combined_score = relevance_weight * relevance_score + recency_weight * recency_score
```

Structured output uses:

- `[Role & Policies]`
- `[Task]`
- `[State]`
- `[Context]`
- `[Output]`

If estimated tokens exceed `max_tokens` and compression is enabled, compress only the `[Context]` section through Qwen summarization.

## Persistence

SQLite stores:

- sessions
- messages
- memories

Memory search uses SQLite FTS5 with BM25 ranking. Memory records include content, metadata, timestamps, user id, and session id.

The MVP uses a simple local database file configured by environment variable or a sensible default under project data storage.

## Trace And Issue Records

Trace logging writes two formats:

- JSONL for machine-readable append-only events;
- HTML for human-readable inspection.

Development bug fixes must be recorded in `docs/issue-resolution-log.md`. Each entry should include date, symptom, root cause, changed files, verification command, and result.

## Testing Strategy

Tests are required at each module boundary before combined debugging.

Unit tests cover:

- calculator safety and arithmetic correctness;
- tool registry schema and invocation;
- circuit breaker open and reset behavior;
- context scoring, sorting, structuring, and compression trigger;
- SQLite session and memory isolation;
- SSE event formatting.

API tests cover:

- health;
- session create/list/delete;
- cross-user session isolation;
- tool listing and direct tool invocation;
- chat stream success and error events with mocked Qwen/tool calls.

Integration smoke tests cover real external calls:

- Qwen streaming/tool-calling smoke test;
- Tavily search smoke test;
- Open-Meteo weather smoke test;
- end-to-end chat stream where the Agent calls a tool and integrates the result.

Integration tests should be explicitly marked so normal `pytest` can remain fast and deterministic.

## Git And Development Process

Use frequent commits:

- initial design/spec commit;
- module commits after tests pass;
- integration/debug commits after combined verification.

Do not commit `.env`.

When an error requires a code change, append an issue-resolution entry before the related fix commit.

## Acceptance Criteria

The backend MVP is complete when:

- the FastAPI app starts locally with uv;
- all ordinary tests pass;
- integration smoke tests can make real calls when required keys are available;
- `POST /chat/stream` emits valid SSE;
- at least one chat test proves Qwen can call a tool and stream a final answer using the tool result;
- one user cannot access another user's sessions or history;
- calculator, search, and weather work through both standalone tool endpoints and Agent-driven chat;
- trace logs and issue-resolution records are present;
- git history contains meaningful commits for the delivered work.
