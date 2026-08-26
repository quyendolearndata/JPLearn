import { test, expect, type Page } from "@playwright/test";
import { injectAxe, checkA11y } from "axe-playwright";

const PAGES: { path: string; title: string; ready: (page: Page) => Promise<void> }[] = [
  {
    path: "/login",
    title: "JPLearn — Đăng nhập",
    ready: async (p) => p.getByRole("button", { name: "Đăng ký" }).waitFor(),
  },
  {
    path: "/",
    title: "JPLearn — Catalog",
    ready: async (p) => p.getByRole("heading", { name: "Catalog" }).waitFor(),
  },
  {
    path: "/session",
    title: "JPLearn — Phiên học",
    ready: async (p) => p.getByRole("heading", { name: "Phiên" }).waitFor(),
  },
  {
    path: "/progress",
    title: "JPLearn — Tiến độ",
    ready: async (p) => p.getByText(/phút/i).waitFor(),
  },
];

async function register(page: Page) {
  await page.goto("/login");
  const email = `a${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
}

test("chrome learner đạt contrast AA + mọi route có document title T-NFR-A1", async ({ page }) => {
  await register(page);
  for (const { path, title, ready } of PAGES) {
    await page.goto(path);
    await ready(page);
    // NFR-A11Y-001 (#36): mọi route learner phải có document title có ý nghĩa.
    await expect(page).toHaveTitle(title);
    await injectAxe(page);
    // Rule thuộc card #34 (contrast, WCAG AA) + #36 (document-title, đã mở lại).
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: false },
    });
  }
});
