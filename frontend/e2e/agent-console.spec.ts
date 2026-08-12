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
