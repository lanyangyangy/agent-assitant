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
