import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  use: { baseURL: "http://localhost:3000" },
});
