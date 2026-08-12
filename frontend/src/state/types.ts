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
