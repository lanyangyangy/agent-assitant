import { expect, test } from "@playwright/test";

function uniqueUserId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

test("真实后端联调：创建会话、调用计算器并展示结果", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("用户 ID").fill(uniqueUserId("alice-e2e"));

  await expect(page.getByText("Agent 控制台")).toBeVisible();
  await expect(page.getByText("后端正常")).toBeVisible();
  await expect(page.getByText("calculator")).toBeVisible();

  await page.getByRole("button", { name: "新建会话" }).click();
  await expect(page.getByText(/当前会话/).first()).toBeVisible();

  await page.getByLabel("聊天输入").fill("请计算 19 * 23 并解释结果");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("调用工具：calculator")).toBeVisible();
  await expect(page.getByText(/"result": 437/)).toBeVisible();
  await expect(page.getByText(/19 × 23 = 437/)).toBeVisible();
});

test("真实后端联调：切换用户后隔离会话", async ({ page }) => {
  await page.goto("/");
  const aliceUserId = uniqueUserId("alice-e2e");
  const bobUserId = uniqueUserId("bob-e2e");
  await page.getByLabel("用户 ID").fill(aliceUserId);

  await page.getByRole("button", { name: "新建会话" }).click();
  await expect(page.getByText(/当前会话/).first()).toBeVisible();

  await page.getByLabel("用户 ID").fill(bobUserId);
  await expect(page.getByText("暂无会话")).toBeVisible();
  await expect(page.getByText(/当前会话/)).toHaveCount(0);
});

test("真实后端联调：切换会话恢复历史并支持删除", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("用户 ID").fill(uniqueUserId("history-e2e"));

  await page.getByRole("button", { name: "新建会话" }).click();
  const firstSessionId = await page.locator(".session-row.selected strong").innerText();
  await page.getByLabel("聊天输入").fill("请计算 2+2");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.locator(".chat-panel").getByText(/计算结果是 4|2 \+ 2 = 4/)).toBeVisible();

  await page.getByRole("button", { name: "新建会话" }).click();
  await expect
    .poll(async () => page.locator(".session-row.selected strong").innerText())
    .not.toBe(firstSessionId);
  const secondSessionId = await page.locator(".session-row.selected strong").innerText();
  await page.getByLabel("聊天输入").fill("请计算 3+4");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.locator(".chat-panel").getByText(/计算结果是 7|3 \+ 4 = 7/)).toBeVisible();

  await page.locator(".session-list").getByText(firstSessionId, { exact: true }).click();
  await expect(page.getByText("请计算 2+2")).toBeVisible();
  await expect(page.getByText("请计算 3+4")).toHaveCount(0);

  await page.getByRole("button", { name: `删除会话 ${firstSessionId}` }).click();
  await expect(page.locator(".session-list").getByText(firstSessionId, { exact: true })).toHaveCount(0);
  await expect(page.locator(".session-list").getByText(secondSessionId, { exact: true })).toBeVisible();
});

test("浏览器联调：切换会话后不串入仍在返回的流式内容", async ({ page }) => {
  await page.route("**/api/chat/stream", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream; charset=utf-8" },
      body: [
        'event: message_start\ndata: {"session_id":"alpha-session-1"}',
        'event: token\ndata: {"session_id":"alpha-session-1","content":"A 会话延迟回答"}',
        'event: message_end\ndata: {"session_id":"alpha-session-1"}',
        "",
      ].join("\n\n"),
    });
  });

  await page.goto("/");
  await page.getByLabel("用户 ID").fill(uniqueUserId("stream-isolate-e2e"));

  await page.getByRole("button", { name: "新建会话" }).click();
  const firstSessionId = await page.locator(".session-row.selected strong").innerText();
  await page.getByRole("button", { name: "新建会话" }).click();
  await expect
    .poll(async () => page.locator(".session-row.selected strong").innerText())
    .not.toBe(firstSessionId);
  const secondSessionId = await page.locator(".session-row.selected strong").innerText();

  await page.locator(".session-list").getByText(firstSessionId, { exact: true }).click();
  await page.getByLabel("聊天输入").fill("A 会话问题");
  await page.getByRole("button", { name: "发送" }).click();
  await page.locator(".session-list").getByText(secondSessionId, { exact: true }).click();

  await page.waitForTimeout(900);
  await expect(page.locator(".chat-panel").getByText("A 会话延迟回答")).toHaveCount(0);

  await page.locator(".session-list").getByText(firstSessionId, { exact: true }).click();
  await expect(page.locator(".chat-panel").getByText("A 会话延迟回答")).toBeVisible();
});
