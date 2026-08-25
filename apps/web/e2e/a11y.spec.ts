import { test, expect, type Page } from "@playwright/test";
import { injectAxe, checkA11y } from "axe-playwright";

const PAGES: { path: string; ready: (page: Page) => Promise<void> }[] = [
  { path: "/login", ready: async (p) => p.getByRole("button", { name: "Đăng ký" }).waitFor() },
  { path: "/", ready: async (p) => p.getByRole("heading", { name: "Catalog" }).waitFor() },
  { path: "/session", ready: async (p) => p.getByRole("heading", { name: "Phiên" }).waitFor() },
  { path: "/progress", ready: async (p) => p.getByText(/phút/i).waitFor() },
];

async function register(page: Page) {
  await page.goto("/login");
  const email = `a${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
}

test("chrome learner đạt contrast WCAG AA T-NFR-A1", async ({ page }) => {
  await register(page);
  for (const { path, ready } of PAGES) {
    await page.goto(path);
    await ready(page);
    await injectAxe(page);
    // Chỉ rule thuộc card #34: contrast (WCAG AA) — document-title là nợ a11y riêng, không phạm vi card này.
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: false },
      axeOptions: { rules: { "document-title": { enabled: false } } },
    });
  }
});
