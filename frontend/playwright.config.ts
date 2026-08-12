import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run uvicorn src.main:app --host 127.0.0.1 --port 8002",
      url: "http://127.0.0.1:8002/health",
      cwd: "..",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --config vite.config.ts --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        VITE_BACKEND_TARGET: "http://127.0.0.1:8002",
      },
    },
  ],
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: "msedge" } },
    { name: "mobile", use: { ...devices["Pixel 5"], channel: "msedge" } },
  ],
});
