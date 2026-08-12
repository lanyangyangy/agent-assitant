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
