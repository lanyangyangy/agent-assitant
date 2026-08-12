import type { SseEvent } from "./types";

export function parseSseText(text: string): SseEvent[] {
  return text
    .split(/\n\n+/)
    .filter((block) => block.trim().length > 0)
    .map(parseBlock);
}

export async function* streamSseEvents(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
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
