import type { BackendClient } from "../api/backendClient";
import type {
  HealthResponse,
  MessageRecord,
  SessionRecord,
  SseEvent,
  ToolSchema,
} from "../api/types";

interface FakeApiOptions {
  health?: HealthResponse;
  sessions?: Record<string, SessionRecord[]>;
  messages?: Record<string, MessageRecord[]>;
  tools?: ToolSchema[];
  streamEvents?: SseEvent[];
}

interface FakeApiCalls {
  getHealth: number;
  listSessions: string[];
  listMessages: Array<{ userId: string; sessionId: string }>;
  createSession: string[];
  deleteSession: Array<{ userId: string; sessionId: string }>;
  listTools: number;
  streamChat: Array<{ userId: string; sessionId: string; message: string }>;
}

export type FakeBackendClient = BackendClient & {
  calls: FakeApiCalls;
};

const defaultHealth: HealthResponse = {
  status: "ok",
  message: "服务正常，SQLite 可用。",
  model_configured: true,
  sqlite_available: true,
  search_available: true,
};

const defaultTools: ToolSchema[] = [
  {
    name: "calculator",
    description: "安全计算算术表达式。",
    parameters: [
      {
        name: "expression",
        type: "string",
        description: "表达式",
        required: true,
        default: null,
      },
    ],
  },
];

const defaultStreamEvents: SseEvent[] = [
  { event: "message_start", data: { trace_id: "trace-1" } },
  {
    event: "tool_call",
    data: { name: "calculator", arguments: "{\"expression\":\"19 * 23\"}" },
  },
  {
    event: "tool_result",
    data: { name: "calculator", result: { success: true, data: { result: 437 } } },
  },
  { event: "token", data: { content: "19 × 23 = " } },
  { event: "token", data: { content: "437" } },
  { event: "message_end", data: { memory_saved: true } },
];

export function createFakeApi(options: FakeApiOptions = {}): FakeBackendClient {
  const sessionsByUser = new Map<string, SessionRecord[]>(
    Object.entries(options.sessions ?? {}).map(([userId, sessions]) => [userId, [...sessions]]),
  );
  const messagesBySession = new Map<string, MessageRecord[]>(
    Object.entries(options.messages ?? {}).map(([sessionId, messages]) => [sessionId, [...messages]]),
  );
  const calls: FakeApiCalls = {
    getHealth: 0,
    listSessions: [],
    listMessages: [],
    createSession: [],
    deleteSession: [],
    listTools: 0,
    streamChat: [],
  };

  return {
    calls,
    async getHealth() {
      calls.getHealth += 1;
      return options.health ?? defaultHealth;
    },
    async listSessions(userId) {
      calls.listSessions.push(userId);
      return { sessions: sessionsByUser.get(userId) ?? [] };
    },
    async listMessages(userId, sessionId) {
      calls.listMessages.push({ userId, sessionId });
      return { messages: messagesBySession.get(sessionId) ?? [] };
    },
    async createSession(userId) {
      calls.createSession.push(userId);
      const session = {
        session_id: `${userId}-session-${(sessionsByUser.get(userId) ?? []).length + 1}`,
        user_id: userId,
        created_at: new Date("2026-08-12T00:00:00Z").toISOString(),
      };
      sessionsByUser.set(userId, [...(sessionsByUser.get(userId) ?? []), session]);
      return session;
    },
    async deleteSession(userId, sessionId) {
      calls.deleteSession.push({ userId, sessionId });
      sessionsByUser.set(
        userId,
        (sessionsByUser.get(userId) ?? []).filter((session) => session.session_id !== sessionId),
      );
      messagesBySession.delete(sessionId);
    },
    async listTools() {
      calls.listTools += 1;
      return options.tools ?? defaultTools;
    },
    async *streamChat(userId, request): AsyncGenerator<SseEvent> {
      calls.streamChat.push({
        userId,
        sessionId: request.session_id,
        message: request.message,
      });
      let assistantContent = "";
      const nextMessages = [
        ...(messagesBySession.get(request.session_id) ?? []),
        createMessageRecord("user", request.message),
      ];
      for (const event of options.streamEvents ?? defaultStreamEvents) {
        if (event.event === "token") {
          assistantContent += String(event.data.content ?? event.data.text ?? "");
        }
        yield event;
      }
      if (assistantContent) {
        nextMessages.push(createMessageRecord("assistant", assistantContent));
      }
      messagesBySession.set(request.session_id, nextMessages);
    },
  };
}

function createMessageRecord(role: "user" | "assistant", content: string): MessageRecord {
  return {
    id: Math.floor(Math.random() * 1_000_000_000),
    role,
    content,
    created_at: new Date("2026-08-12T00:00:00Z").toISOString(),
  };
}
