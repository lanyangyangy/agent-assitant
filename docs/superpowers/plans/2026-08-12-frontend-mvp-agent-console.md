# Frontend MVP Agent Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 `frontend/` React + Vite 前端 MVP，真实连接 FastAPI 后端，完成三栏 Agent 控制台、SSE 流式聊天、工具事件展示和会话隔离验证。

**Architecture:** 前端作为独立 Vite 应用运行，开发期通过 `/api` 代理连接本地后端，避免浏览器 CORS 阻塞。业务分为 API/SSE 解析、状态 reducer、容器组件、展示组件和端到端验收测试，保证后续从 A 三栏工作台切换到 B 聊天优先布局时不重写数据层。

**Tech Stack:** React 18、Vite、TypeScript、Vitest、React Testing Library、Playwright、CSS、FastAPI 后端现有接口。

---

## File Structure

- Create: `frontend/package.json`，前端依赖、脚本和测试命令。
- Create: `frontend/index.html`，Vite HTML 入口。
- Create: `frontend/tsconfig.json`，前端 TypeScript 配置。
- Create: `frontend/tsconfig.node.json`，Vite/Playwright Node 端配置。
- Create: `frontend/vite.config.ts`，React 插件、Vitest、`/api` 后端代理。
- Create: `frontend/vitest.setup.ts`，测试环境扩展。
- Create: `frontend/playwright.config.ts`，真实后端和前端联调配置。
- Create: `frontend/src/main.tsx`，React 挂载入口。
- Create: `frontend/src/App.tsx`，应用根组件。
- Create: `frontend/src/styles.css`，冷静工程台视觉样式和响应式布局。
- Create: `frontend/src/api/types.ts`，后端响应和前端事件类型。
- Create: `frontend/src/api/config.ts`，API base URL 和默认用户配置。
- Create: `frontend/src/api/http.ts`，统一 HTTP 请求封装。
- Create: `frontend/src/api/backendClient.ts`，health、sessions、tools、chat stream 客户端。
- Create: `frontend/src/api/sse.ts`，SSE 分块解析器。
- Create: `frontend/src/state/chatReducer.ts`，消息和事件状态转换。
- Create: `frontend/src/state/types.ts`，前端状态类型。
- Create: `frontend/src/components/AgentConsole.tsx`，容器组件和数据编排。
- Create: `frontend/src/components/StatusBar.tsx`，顶部状态栏。
- Create: `frontend/src/components/SessionSidebar.tsx`，左侧会话栏。
- Create: `frontend/src/components/ChatPanel.tsx`，中间聊天区。
- Create: `frontend/src/components/EventPanel.tsx`，右侧工具事件栏。
- Create: `frontend/src/components/ToolCatalog.tsx`，工具目录。
- Create: `frontend/src/components/ErrorBanner.tsx`，局部错误提示。
- Create: `frontend/src/test/fakeApi.ts`，组件测试用可控 API。
- Create: `frontend/src/api/config.test.ts`，配置测试。
- Create: `frontend/src/api/http.test.ts`，请求封装测试。
- Create: `frontend/src/api/sse.test.ts`，SSE parser 测试。
- Create: `frontend/src/state/chatReducer.test.ts`，状态 reducer 测试。
- Create: `frontend/src/components/AgentConsole.test.tsx`，组件集成测试。
- Create: `frontend/e2e/agent-console.spec.ts`，真实后端端到端测试。
- Modify: `README.md`，补充前端启动、测试和联调命令。

---

### Task 1: Frontend Scaffold And Config Test

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/src/api/config.test.ts`
- Create: `frontend/src/api/config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`

- [ ] **Step 1: Create the minimal package and test harness**

Create `frontend/package.json`:

```json
{
  "name": "agent-console-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.7",
    "typescript": "^5.7.2",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.49.1",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "jsdom": "^25.0.1",
    "vitest": "^2.1.8"
  }
}
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Agent 控制台</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts", "playwright.config.ts"]
}
```

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_BACKEND_TARGET || "http://127.0.0.1:8002";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./vitest.setup.ts",
      css: true,
    },
  };
});
```

Create `frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: Write the failing config test**

Create `frontend/src/api/config.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { getApiBaseUrl, getDefaultUserId } from "./config";

describe("前端配置", () => {
  it("默认通过 Vite 代理访问后端 API", () => {
    expect(getApiBaseUrl()).toBe("/api");
  });

  it("默认用户 ID 是 alice", () => {
    expect(getDefaultUserId()).toBe("alice");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
cd frontend
npm install
npm test -- src/api/config.test.ts
```

Expected: FAIL with `Cannot find module './config'`.

- [ ] **Step 4: Implement the minimal config and app entry**

Create `frontend/src/api/config.ts`:

```ts
export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || "/api";
}

export function getDefaultUserId(): string {
  return import.meta.env.VITE_DEFAULT_USER_ID || "alice";
}
```

Create `frontend/src/App.tsx`:

```tsx
export function App() {
  return <main className="app-shell">Agent 控制台</main>;
}
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Create `frontend/src/styles.css`:

```css
:root {
  font-family: Inter, "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
  color: #172033;
  background: #f7f8fb;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button,
input,
textarea {
  font: inherit;
}

.app-shell {
  min-height: 100vh;
  padding: 24px;
}
```

- [ ] **Step 5: Run config test and build**

Run:

```bash
cd frontend
npm test -- src/api/config.test.ts
npm run build
```

Expected: PASS for config tests and successful production build.

- [ ] **Step 6: Commit scaffold**

```bash
git add frontend/package.json frontend/package-lock.json frontend/index.html frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/vitest.setup.ts frontend/src
git commit -m "chore: scaffold frontend agent console"
```

---

### Task 2: API Types, HTTP Client, And Backend Client

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/http.test.ts`
- Create: `frontend/src/api/http.ts`
- Create: `frontend/src/api/backendClient.ts`

- [ ] **Step 1: Write failing HTTP client tests**

Create `frontend/src/api/http.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";

import { createBackendClient } from "./backendClient";

describe("后端 API 客户端", () => {
  it("请求会话列表时注入 X-User-Id 请求头", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ sessions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const client = createBackendClient({ baseUrl: "/api", fetchImpl: fetchMock });
    await client.listSessions("alice");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/sessions",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-User-Id": "alice" }),
      }),
    );
  });

  it("后端不可达时返回中文错误", async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });

    const client = createBackendClient({ baseUrl: "/api", fetchImpl: fetchMock });

    await expect(client.getHealth()).rejects.toThrow("无法连接后端，请确认服务已启动。");
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend
npm test -- src/api/http.test.ts
```

Expected: FAIL with `Cannot find module './backendClient'`.

- [ ] **Step 3: Implement API types and client**

Create `frontend/src/api/types.ts`:

```ts
export interface HealthResponse {
  status: string;
  message: string;
  model_configured: boolean;
  sqlite_available: boolean;
  search_available: boolean;
}

export interface SessionRecord {
  session_id: string;
  user_id: string;
  created_at: string;
}

export interface SessionListResponse {
  sessions: SessionRecord[];
}

export interface ToolParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default: unknown;
}

export interface ToolSchema {
  name: string;
  description: string;
  parameters: ToolParameter[];
}

export interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}
```

Create `frontend/src/api/http.ts`:

```ts
type FetchLike = typeof fetch;

export interface RequestOptions extends RequestInit {
  userId?: string;
}

export async function requestJson<T>(
  baseUrl: string,
  path: string,
  options: RequestOptions = {},
  fetchImpl: FetchLike = fetch,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.userId) {
    headers.set("X-User-Id", options.userId);
  }
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}${path}`, { ...options, headers });
  } catch (error) {
    throw new Error("无法连接后端，请确认服务已启动。");
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail || `请求失败，状态码 ${response.status}。`);
  }

  return response.json() as Promise<T>;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return typeof payload.detail === "string" ? payload.detail : "";
  } catch {
    return "";
  }
}
```

Create `frontend/src/api/backendClient.ts`:

```ts
import { requestJson } from "./http";
import type { HealthResponse, SessionListResponse, SessionRecord, ToolSchema } from "./types";

type FetchLike = typeof fetch;

export interface BackendClientOptions {
  baseUrl: string;
  fetchImpl?: FetchLike;
}

export interface BackendClient {
  getHealth(): Promise<HealthResponse>;
  listSessions(userId: string): Promise<SessionListResponse>;
  createSession(userId: string): Promise<SessionRecord>;
  deleteSession(userId: string, sessionId: string): Promise<void>;
  listTools(): Promise<ToolSchema[]>;
}

export function createBackendClient(options: BackendClientOptions): BackendClient {
  const fetchImpl = options.fetchImpl ?? fetch;

  return {
    getHealth: () => requestJson<HealthResponse>(options.baseUrl, "/health", {}, fetchImpl),
    listSessions: (userId) =>
      requestJson<SessionListResponse>(options.baseUrl, "/sessions", { userId }, fetchImpl),
    createSession: (userId) =>
      requestJson<SessionRecord>(
        options.baseUrl,
        "/sessions",
        { method: "POST", userId },
        fetchImpl,
      ),
    async deleteSession(userId, sessionId) {
      await requestJson<unknown>(
        options.baseUrl,
        `/sessions/${sessionId}`,
        { method: "DELETE", userId },
        fetchImpl,
      );
    },
    listTools: () => requestJson<ToolSchema[]>(options.baseUrl, "/tools", {}, fetchImpl),
  };
}
```

- [ ] **Step 4: Run API tests**

Run:

```bash
cd frontend
npm test -- src/api/http.test.ts src/api/config.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit API client**

```bash
git add frontend/src/api
git commit -m "feat: add frontend api client"
```

---

### Task 3: SSE Parser And Streaming Chat Client

**Files:**
- Create: `frontend/src/api/sse.test.ts`
- Create: `frontend/src/api/sse.ts`
- Modify: `frontend/src/api/backendClient.ts`
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Write failing SSE parser tests**

Create `frontend/src/api/sse.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { parseSseText, streamSseEvents } from "./sse";

describe("SSE 解析器", () => {
  it("解析 event 和 JSON data", () => {
    const events = parseSseText('event: token\ndata: {"content":"你好"}\n\n');

    expect(events).toEqual([{ event: "token", data: { content: "你好" } }]);
  });

  it("支持 data 多行拼接", () => {
    const events = parseSseText('event: token\ndata: {"content":\ndata: "你好"}\n\n');

    expect(events).toEqual([{ event: "token", data: { content: "你好" } }]);
  });

  it("支持 ReadableStream 分块输入", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: tool_call\ndata: {"name":"cal'));
        controller.enqueue(encoder.encode('culator"}\n\n'));
        controller.close();
      },
    });

    const events = [];
    for await (const event of streamSseEvents(stream)) {
      events.push(event);
    }

    expect(events).toEqual([{ event: "tool_call", data: { name: "calculator" } }]);
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend
npm test -- src/api/sse.test.ts
```

Expected: FAIL with `Cannot find module './sse'`.

- [ ] **Step 3: Implement SSE parser and chat stream client**

Create `frontend/src/api/sse.ts`:

```ts
import type { SseEvent } from "./types";

export function parseSseText(text: string): SseEvent[] {
  return text
    .split(/\n\n+/)
    .filter((block) => block.trim().length > 0)
    .map(parseBlock);
}

export async function* streamSseEvents(stream: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\n\n+/);
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      if (part.trim()) {
        yield parseBlock(part);
      }
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    yield parseBlock(buffer);
  }
}

function parseBlock(block: string): SseEvent {
  const lines = block.split(/\r?\n/);
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  const dataText = dataLines.join("");
  try {
    return { event, data: JSON.parse(dataText) as Record<string, unknown> };
  } catch {
    return {
      event: "error",
      data: { message: "收到无法解析的流式事件。", raw: dataText },
    };
  }
}
```

Modify `frontend/src/api/types.ts`:

```ts
export interface ChatStreamRequest {
  session_id: string;
  message: string;
  metadata?: Record<string, unknown>;
}
```

Modify `frontend/src/api/backendClient.ts` to include streaming:

```ts
import { streamSseEvents } from "./sse";
import type { ChatStreamRequest, SseEvent } from "./types";

// Add to BackendClient:
streamChat(userId: string, request: ChatStreamRequest): AsyncGenerator<SseEvent>;

// Add to createBackendClient return object:
async *streamChat(userId, request) {
  const response = await fetchImpl(`${options.baseUrl}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": userId,
    },
    body: JSON.stringify(request),
  });

  if (!response.ok || !response.body) {
    throw new Error("聊天流中断，请重试。");
  }

  yield* streamSseEvents(response.body);
}
```

- [ ] **Step 4: Run SSE and API tests**

Run:

```bash
cd frontend
npm test -- src/api/sse.test.ts src/api/http.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit SSE client**

```bash
git add frontend/src/api
git commit -m "feat: parse frontend sse chat stream"
```

---

### Task 4: Chat State Reducer

**Files:**
- Create: `frontend/src/state/types.ts`
- Create: `frontend/src/state/chatReducer.test.ts`
- Create: `frontend/src/state/chatReducer.ts`

- [ ] **Step 1: Write failing reducer tests**

Create `frontend/src/state/chatReducer.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { chatReducer, createInitialChatState } from "./chatReducer";

describe("聊天状态 reducer", () => {
  it("收到 token 时增量拼接助手消息", () => {
    let state = createInitialChatState();
    state = chatReducer(state, { type: "user_message", content: "请计算 19 * 23" });
    state = chatReducer(state, { type: "stream_event", event: { event: "token", data: { content: "19 ×" } } });
    state = chatReducer(state, { type: "stream_event", event: { event: "token", data: { content: " 23 = 437" } } });

    expect(state.messages.at(-1)).toMatchObject({
      role: "assistant",
      content: "19 × 23 = 437",
    });
  });

  it("记录工具调用和工具结果事件", () => {
    let state = createInitialChatState();
    state = chatReducer(state, {
      type: "stream_event",
      event: { event: "tool_call", data: { name: "calculator", arguments: "{\"expression\":\"19 * 23\"}" } },
    });
    state = chatReducer(state, {
      type: "stream_event",
      event: { event: "tool_result", data: { name: "calculator", result: { success: true, data: { result: 437 } } } },
    });

    expect(state.events.map((event) => event.kind)).toEqual(["tool_call", "tool_result"]);
    expect(state.events[1].summary).toContain("437");
  });

  it("收到 error 时结束生成状态并显示中文错误", () => {
    let state = createInitialChatState();
    state = chatReducer(state, { type: "start_stream" });
    state = chatReducer(state, {
      type: "stream_event",
      event: { event: "error", data: { message: "会话不存在或无权访问。" } },
    });

    expect(state.isStreaming).toBe(false);
    expect(state.error).toBe("会话不存在或无权访问。");
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend
npm test -- src/state/chatReducer.test.ts
```

Expected: FAIL with `Cannot find module './chatReducer'`.

- [ ] **Step 3: Implement state types and reducer**

Create `frontend/src/state/types.ts`:

```ts
import type { SseEvent } from "../api/types";

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
}

export interface TimelineEvent {
  id: string;
  kind: string;
  title: string;
  summary: string;
  data: Record<string, unknown>;
}

export interface ChatState {
  messages: ChatMessage[];
  events: TimelineEvent[];
  isStreaming: boolean;
  error: string | null;
}

export type ChatAction =
  | { type: "reset_for_session" }
  | { type: "user_message"; content: string }
  | { type: "start_stream" }
  | { type: "stream_event"; event: SseEvent };
```

Create `frontend/src/state/chatReducer.ts`:

```ts
import type { ChatAction, ChatMessage, ChatState, TimelineEvent } from "./types";

let nextId = 0;

export function createInitialChatState(): ChatState {
  return {
    messages: [],
    events: [],
    isStreaming: false,
    error: null,
  };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "reset_for_session":
      return createInitialChatState();
    case "user_message":
      return {
        ...state,
        messages: [...state.messages, createMessage("user", action.content)],
        error: null,
      };
    case "start_stream":
      return { ...state, events: [], isStreaming: true, error: null };
    case "stream_event":
      return applyStreamEvent(state, action.event.event, action.event.data);
  }
}

function applyStreamEvent(state: ChatState, eventName: string, data: Record<string, unknown>): ChatState {
  if (eventName === "token") {
    return appendAssistantToken(state, String(data.content ?? data.text ?? ""));
  }

  const timelineEvent = createTimelineEvent(eventName, data);
  const nextState = { ...state, events: [...state.events, timelineEvent] };

  if (eventName === "error") {
    return {
      ...nextState,
      isStreaming: false,
      error: String(data.message ?? "聊天流中断，请重试。"),
    };
  }

  if (eventName === "message_end") {
    return { ...nextState, isStreaming: false };
  }

  return nextState;
}

function appendAssistantToken(state: ChatState, token: string): ChatState {
  const messages = [...state.messages];
  const last = messages.at(-1);
  if (last?.role === "assistant") {
    messages[messages.length - 1] = { ...last, content: `${last.content}${token}` };
  } else {
    messages.push(createMessage("assistant", token));
  }
  return { ...state, messages };
}

function createMessage(role: "user" | "assistant", content: string): ChatMessage {
  return { id: `msg-${++nextId}`, role, content };
}

function createTimelineEvent(kind: string, data: Record<string, unknown>): TimelineEvent {
  return {
    id: `evt-${++nextId}`,
    kind,
    title: eventTitle(kind, data),
    summary: eventSummary(kind, data),
    data,
  };
}

function eventTitle(kind: string, data: Record<string, unknown>): string {
  if (kind === "tool_call") return `调用工具：${String(data.name ?? "未知工具")}`;
  if (kind === "tool_result") return `工具结果：${String(data.name ?? "未知工具")}`;
  if (kind === "message_start") return "开始生成";
  if (kind === "message_end") return "生成完成";
  if (kind === "error") return "发生错误";
  return kind;
}

function eventSummary(kind: string, data: Record<string, unknown>): string {
  return JSON.stringify(data, null, 2);
}
```

- [ ] **Step 4: Run reducer tests**

Run:

```bash
cd frontend
npm test -- src/state/chatReducer.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit reducer**

```bash
git add frontend/src/state
git commit -m "feat: add frontend chat reducer"
```

---

### Task 5: Presentational Components

**Files:**
- Create: `frontend/src/components/StatusBar.tsx`
- Create: `frontend/src/components/SessionSidebar.tsx`
- Create: `frontend/src/components/ChatPanel.tsx`
- Create: `frontend/src/components/EventPanel.tsx`
- Create: `frontend/src/components/ToolCatalog.tsx`
- Create: `frontend/src/components/ErrorBanner.tsx`

- [ ] **Step 1: Create focused presentational components**

Create these components with typed props only and no direct network calls.

`StatusBar.tsx` must render product title, backend URL, health labels, user input, and refresh button.

`SessionSidebar.tsx` must render new session button, session rows, selected row, delete buttons, and empty state.

`ChatPanel.tsx` must render messages, current session short ID, input, send button, and disabled states.

`EventPanel.tsx` must render timeline events with status class names based on event kind.

`ToolCatalog.tsx` must render tool names, descriptions, and parameter rows.

`ErrorBanner.tsx` must render only when a message exists.

The visible text must be Chinese. Use lucide icons for refresh, plus, trash, send, activity, and tools.

- [ ] **Step 2: Run TypeScript build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS after all component props are type-consistent.

- [ ] **Step 3: Commit components**

```bash
git add frontend/src/components
git commit -m "feat: add frontend console components"
```

---

### Task 6: AgentConsole Container And Component Tests

**Files:**
- Create: `frontend/src/test/fakeApi.ts`
- Create: `frontend/src/components/AgentConsole.test.tsx`
- Create: `frontend/src/components/AgentConsole.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing AgentConsole tests**

Create `frontend/src/components/AgentConsole.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AgentConsole } from "./AgentConsole";
import { createFakeApi } from "../test/fakeApi";

describe("Agent 控制台", () => {
  it("加载健康状态、工具和会话", async () => {
    const api = createFakeApi();

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);

    expect(await screen.findByText("Agent 控制台")).toBeInTheDocument();
    expect(await screen.findByText("后端正常")).toBeInTheDocument();
    expect(await screen.findByText("calculator")).toBeInTheDocument();
  });

  it("创建会话后自动选中新会话", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);
    await user.click(await screen.findByRole("button", { name: "新建会话" }));

    expect(await screen.findByText(/当前会话/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  });

  it("发送消息后展示工具调用、工具结果和流式回答", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);
    await user.click(await screen.findByRole("button", { name: "新建会话" }));
    await user.type(screen.getByLabelText("聊天输入"), "请计算 19 * 23 并解释结果");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("调用工具：calculator")).toBeInTheDocument();
    expect(await screen.findByText(/437/)).toBeInTheDocument();
    expect(await screen.findByText(/19 × 23 = 437/)).toBeInTheDocument();
  });

  it("切换用户后不展示原用户会话", async () => {
    const user = userEvent.setup();
    const api = createFakeApi();

    render(<AgentConsole api={api} apiBaseUrl="/api" defaultUserId="alice" />);
    await user.click(await screen.findByRole("button", { name: "新建会话" }));
    await user.clear(screen.getByLabelText("用户 ID"));
    await user.type(screen.getByLabelText("用户 ID"), "bob");

    await waitFor(() => {
      expect(screen.getByText("暂无会话")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd frontend
npm test -- src/components/AgentConsole.test.tsx
```

Expected: FAIL with `Cannot find module './AgentConsole'`.

- [ ] **Step 3: Implement fake API**

Create `frontend/src/test/fakeApi.ts`:

```ts
import type { BackendClient } from "../api/backendClient";
import type { SseEvent } from "../api/types";

export function createFakeApi(): BackendClient {
  const sessionsByUser = new Map<string, Array<{ session_id: string; user_id: string; created_at: string }>>();

  return {
    async getHealth() {
      return {
        status: "ok",
        message: "服务正常，SQLite 可用。",
        model_configured: true,
        sqlite_available: true,
        search_available: true,
      };
    },
    async listSessions(userId) {
      return { sessions: sessionsByUser.get(userId) ?? [] };
    },
    async createSession(userId) {
      const session = {
        session_id: `${userId}-session-1`,
        user_id: userId,
        created_at: new Date("2026-08-12T00:00:00Z").toISOString(),
      };
      sessionsByUser.set(userId, [...(sessionsByUser.get(userId) ?? []), session]);
      return session;
    },
    async deleteSession(userId, sessionId) {
      sessionsByUser.set(
        userId,
        (sessionsByUser.get(userId) ?? []).filter((session) => session.session_id !== sessionId),
      );
    },
    async listTools() {
      return [
        {
          name: "calculator",
          description: "安全计算算术表达式。",
          parameters: [{ name: "expression", type: "string", description: "表达式", required: true, default: null }],
        },
      ];
    },
    async *streamChat(): AsyncGenerator<SseEvent> {
      yield { event: "message_start", data: { trace_id: "trace-1" } };
      yield { event: "tool_call", data: { name: "calculator", arguments: "{\"expression\":\"19 * 23\"}" } };
      yield {
        event: "tool_result",
        data: { name: "calculator", result: { success: true, data: { result: 437 } } },
      };
      yield { event: "token", data: { content: "19 × 23 = " } };
      yield { event: "token", data: { content: "437" } };
      yield { event: "message_end", data: { memory_saved: true } };
    },
  };
}
```

- [ ] **Step 4: Implement AgentConsole and wire App**

Create `frontend/src/components/AgentConsole.tsx` as the container that:

- keeps `userId`, sessions, selected session, tools, health, local error, and `chatReducer` state;
- loads health/tools/sessions on mount;
- reloads sessions when `userId` changes;
- creates and deletes sessions via API;
- sends stream requests with `api.streamChat`;
- dispatches every SSE event into `chatReducer`;
- passes typed props to presentational components.

Modify `frontend/src/App.tsx`:

```tsx
import { createBackendClient } from "./api/backendClient";
import { getApiBaseUrl, getDefaultUserId } from "./api/config";
import { AgentConsole } from "./components/AgentConsole";

const apiBaseUrl = getApiBaseUrl();
const api = createBackendClient({ baseUrl: apiBaseUrl });

export function App() {
  return <AgentConsole api={api} apiBaseUrl={apiBaseUrl} defaultUserId={getDefaultUserId()} />;
}
```

- [ ] **Step 5: Run component tests**

Run:

```bash
cd frontend
npm test -- src/components/AgentConsole.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit container**

```bash
git add frontend/src/components frontend/src/test frontend/src/App.tsx
git commit -m "feat: wire frontend agent console"
```

---

### Task 7: Three-Column Styling And Responsive Layout

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/components/*.tsx` as needed for class names and accessibility labels.

- [ ] **Step 1: Implement the A layout visual system**

Update CSS with these layout rules:

- `.console-root` min-height `100vh`, background `#f7f8fb`。
- `.status-bar` height-dense top band with health chips。
- `.console-layout` desktop grid: `260px minmax(0, 1fr) 340px`。
- `.session-sidebar`、`.chat-panel`、`.event-panel` use white surfaces, 1px border, radius <= 8px。
- Chat and event lists each scroll independently。
- Buttons use icon + Chinese label where commands need clarity。
- Event kinds use color classes: blue/yellow/green/red/gray。
- At `max-width: 900px`, layout collapses to one column and right event panel becomes lower section。
- At `max-width: 480px`, buttons and inputs wrap without text overflow。

- [ ] **Step 2: Run component tests and build**

Run:

```bash
cd frontend
npm test -- src/components/AgentConsole.test.tsx
npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit styling**

```bash
git add frontend/src
git commit -m "feat: style frontend console layout"
```

---

### Task 8: Playwright Real Backend E2E

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/agent-console.spec.ts`

- [ ] **Step 1: Write e2e test**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run uvicorn src.main:app --host 127.0.0.1 --port 8002",
      url: "http://127.0.0.1:8002/health",
      cwd: "..",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        VITE_BACKEND_TARGET: "http://127.0.0.1:8002",
      },
    },
  ],
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
});
```

Create `frontend/e2e/agent-console.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("真实后端联调：创建会话、调用计算器并展示结果", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText("Agent 控制台")).toBeVisible();
  await expect(page.getByText("后端正常")).toBeVisible();

  await page.getByRole("button", { name: "新建会话" }).click();
  await expect(page.getByText(/当前会话/)).toBeVisible();

  await page.getByLabel("聊天输入").fill("请计算 19 * 23 并解释结果");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("调用工具：calculator")).toBeVisible();
  await expect(page.getByText(/437/)).toBeVisible();
  await expect(page.getByText(/19/)).toBeVisible();
});

test("真实后端联调：切换用户后隔离会话", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "新建会话" }).click();
  await expect(page.getByText(/当前会话/)).toBeVisible();

  await page.getByLabel("用户 ID").fill("bob");
  await expect(page.getByText("暂无会话")).toBeVisible();
});
```

- [ ] **Step 2: Run e2e to verify current gaps**

Run:

```bash
cd frontend
npx playwright install chromium
npm run e2e -- --project=desktop
```

Expected: FAIL if selectors, server startup, or layout wiring is incomplete. The failure must be fixed before commit. If the failure is from app code, append an entry to `docs/issue-resolution-log.md` before changing code.

- [ ] **Step 3: Fix e2e gaps with tests preserved**

Apply focused fixes until:

```bash
cd frontend
npm run e2e -- --project=desktop
```

Expected: PASS.

- [ ] **Step 4: Run mobile e2e**

Run:

```bash
cd frontend
npm run e2e -- --project=mobile
```

Expected: PASS without text overflow or inaccessible controls.

- [ ] **Step 5: Commit e2e tests**

```bash
git add frontend/playwright.config.ts frontend/e2e frontend/src docs/issue-resolution-log.md
git commit -m "test: add frontend e2e smoke tests"
```

---

### Task 9: README And Final Verification

**Files:**
- Modify: `README.md`
- Modify as required by failures: `docs/issue-resolution-log.md`

- [ ] **Step 1: Update README frontend runbook**

Add Chinese frontend instructions:

```markdown
## 前端控制台

安装：

```bash
cd frontend
npm install
```

启动前端，并代理到 8002 后端：

```bash
cd frontend
$env:VITE_BACKEND_TARGET="http://127.0.0.1:8002"
npm run dev -- --port 5173
```

访问：

```text
http://127.0.0.1:5173
```

测试：

```bash
cd frontend
npm test
npm run build
npm run e2e -- --project=desktop
npm run e2e -- --project=mobile
```
```

- [ ] **Step 2: Run full frontend verification**

Run:

```bash
cd frontend
npm test
npm run build
npm run e2e
```

Expected: PASS.

- [ ] **Step 3: Run backend verification**

Run:

```bash
uv run pytest -m "not integration" -v
```

Expected: PASS.

- [ ] **Step 4: Browser visual verification**

Run frontend dev server:

```bash
cd frontend
$env:VITE_BACKEND_TARGET="http://127.0.0.1:8002"
npm run dev -- --port 5173
```

Open `http://127.0.0.1:5173` and verify:

- desktop view uses three columns;
- mobile view collapses without horizontal overflow;
- all visible text is Chinese;
- health, sessions, chat, events, tools are visible;
- event panel shows `tool_call` and `tool_result`;
- result `437` appears after asking `请计算 19 * 23 并解释结果`。

- [ ] **Step 5: Final git hygiene**

Run:

```bash
git status --short --branch
```

Expected: only the original source design document may remain untracked unless the user asks to commit it.

- [ ] **Step 6: Commit runbook**

```bash
git add README.md docs/issue-resolution-log.md
git commit -m "docs: add frontend runbook"
```

## Plan Self-Review

- Spec coverage: Tasks 1-9 cover React/Vite scaffold, API client, SSE parsing, reducer, A layout components, real backend e2e, responsive verification, README, and git hygiene.
- Scope check: The plan only implements frontend A three-column console. B chat-first layout is preserved as a later evolution, not implemented here.
- Type consistency: `BackendClient`、`SseEvent`、`ChatState`、`TimelineEvent`、`AgentConsole` prop names are used consistently across tests and implementation steps.
- Ambiguity scan: The development backend target is explicit: Vite proxies `/api` to `http://127.0.0.1:8002` by default and can be overridden with `VITE_BACKEND_TARGET`。
