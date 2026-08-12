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

export interface ChatStreamRequest {
  session_id: string;
  message: string;
  metadata?: Record<string, unknown>;
}
