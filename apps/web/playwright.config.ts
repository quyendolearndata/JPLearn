import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  use: { baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL ?? "http://localhost:3000" },
});
