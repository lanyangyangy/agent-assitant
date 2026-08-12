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
