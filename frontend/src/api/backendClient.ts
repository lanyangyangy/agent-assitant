import { requestJson } from "./http";
import { streamSseEvents } from "./sse";
import type {
  ChatStreamRequest,
  HealthResponse,
  MessageListResponse,
  SessionListResponse,
  SessionRecord,
  SseEvent,
  ToolSchema,
} from "./types";

type FetchLike = typeof fetch;

export interface BackendClientOptions {
  baseUrl: string;
  fetchImpl?: FetchLike;
}

export interface BackendClient {
  getHealth(): Promise<HealthResponse>;
  listSessions(userId: string): Promise<SessionListResponse>;
  listMessages(userId: string, sessionId: string): Promise<MessageListResponse>;
  createSession(userId: string): Promise<SessionRecord>;
  deleteSession(userId: string, sessionId: string): Promise<void>;
  listTools(): Promise<ToolSchema[]>;
  streamChat(userId: string, request: ChatStreamRequest): AsyncGenerator<SseEvent>;
}

export function createBackendClient(options: BackendClientOptions): BackendClient {
  const fetchImpl = options.fetchImpl ?? fetch;

  return {
    getHealth: () => requestJson<HealthResponse>(options.baseUrl, "/health", {}, fetchImpl),
    listSessions: (userId) =>
      requestJson<SessionListResponse>(options.baseUrl, "/sessions", { userId }, fetchImpl),
    listMessages: (userId, sessionId) =>
      requestJson<MessageListResponse>(
        options.baseUrl,
        `/sessions/${sessionId}/messages`,
        { userId },
        fetchImpl,
      ),
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
    },
  };
}
