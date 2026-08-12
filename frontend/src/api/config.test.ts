import { beforeEach, describe, expect, it } from "vitest";

import { getApiBaseUrl, getDefaultUserId } from "./config";

describe("前端配置", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("默认通过 Vite 代理访问后端 API", () => {
    expect(getApiBaseUrl()).toBe("/api");
  });

  it("未配置默认用户时生成并复用浏览器本地用户 ID", () => {
    const firstUserId = getDefaultUserId();
    const secondUserId = getDefaultUserId();

    expect(firstUserId).toMatch(/^local-user-/);
    expect(secondUserId).toBe(firstUserId);
    expect(localStorage.getItem("agent-console-user-id")).toBe(firstUserId);
  });
});
