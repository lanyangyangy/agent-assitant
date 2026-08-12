import { describe, expect, it } from "vitest";

import { getApiBaseUrl, getDefaultUserId } from "./config";

describe("前端配置", () => {
  it("默认通过 Vite 代理访问后端 API", () => {
    expect(getApiBaseUrl()).toBe("/api");
  });

  it("默认用户 ID 是 alice", () => {
    expect(getDefaultUserId()).toBe("alice");
  });
});
