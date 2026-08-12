import { describe, expect, it } from "vitest";

import { chatReducer, createInitialChatState } from "./chatReducer";

describe("聊天状态 reducer", () => {
  it("收到 token 时增量拼接助手消息", () => {
    let state = createInitialChatState();
    state = chatReducer(state, { type: "user_message", content: "请计算 19 * 23" });
    state = chatReducer(state, {
      type: "stream_event",
      event: { event: "token", data: { content: "19 ×" } },
    });
    state = chatReducer(state, {
      type: "stream_event",
      event: { event: "token", data: { content: " 23 = 437" } },
    });

    expect(state.messages.at(-1)).toMatchObject({
      role: "assistant",
      content: "19 × 23 = 437",
    });
  });

  it("记录工具调用和工具结果事件", () => {
    let state = createInitialChatState();
    state = chatReducer(state, {
      type: "stream_event",
      event: {
        event: "tool_call",
        data: { name: "calculator", arguments: "{\"expression\":\"19 * 23\"}" },
      },
    });
    state = chatReducer(state, {
      type: "stream_event",
      event: {
        event: "tool_result",
        data: { name: "calculator", result: { success: true, data: { result: 437 } } },
      },
    });

    expect(state.events.map((event) => event.kind)).toEqual(["tool_call", "tool_result"]);
    expect(state.events[1].summary).toContain("437");
  });

  it("加载后端历史消息时替换当前聊天记录并清空事件", () => {
    let state = createInitialChatState();
    state = chatReducer(state, { type: "user_message", content: "临时消息" });
    state = chatReducer(state, {
      type: "stream_event",
      event: { event: "tool_call", data: { name: "calculator" } },
    });

    state = chatReducer(state, {
      type: "load_messages",
      messages: [
        {
          id: 10,
          role: "user",
          content: "历史问题",
          created_at: "2026-08-12T00:00:00.000Z",
        },
        {
          id: 11,
          role: "assistant",
          content: "历史回答",
          created_at: "2026-08-12T00:00:01.000Z",
        },
      ],
    });

    expect(state.messages).toEqual([
      { id: "history-10", role: "user", content: "历史问题" },
      { id: "history-11", role: "assistant", content: "历史回答" },
    ]);
    expect(state.events).toEqual([]);
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
