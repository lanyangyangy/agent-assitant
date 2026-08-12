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

function applyStreamEvent(
  state: ChatState,
  eventName: string,
  data: Record<string, unknown>,
): ChatState {
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
    summary: eventSummary(data),
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

function eventSummary(data: Record<string, unknown>): string {
  return JSON.stringify(data, null, 2);
}
