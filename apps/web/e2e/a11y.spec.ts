import { test, expect, type Page } from "@playwright/test";
import { injectAxe, checkA11y } from "axe-playwright";

const LEARNER_PAGES: { path: string; title: string; ready: (page: Page) => Promise<void> }[] = [
  {
    path: "/",
    title: "JPLearn — Catalog",
    ready: async (p) => p.getByRole("heading", { level: 1 }).waitFor(),
  },
  {
    path: "/login",
    title: "JPLearn — Đăng nhập",
    ready: async (p) => p.getByRole("button", { name: "Đăng ký" }).waitFor(),
  },
  {
    path: "/catalog",
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

const STAFF_PAGES: { path: string; title: string; ready: (page: Page) => Promise<void> }[] = [
  {
    path: "/staff",
    title: "JPLearn — Staff CMS",
    ready: async (p) => p.getByRole("heading", { name: "Quản trị nội dung CI" }).waitFor(),
  },
  {
    path: "/staff/new",
    title: "JPLearn — Staff CMS",
    ready: async (p) => p.getByRole("heading", { name: "Tạo bài học mới (Bản nháp)" }).waitFor(),
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

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@jplearn.local");
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page).toHaveURL("/");
}

test("chrome learner đạt contrast AA + mọi route có document title T-NFR-A1", async ({ page }) => {
  await register(page);
  for (const { path, title, ready } of LEARNER_PAGES) {
    await page.goto(path);
    await ready(page);
    // NFR-A11Y-001 (#36): mọi route learner phải có document title có ý nghĩa.
    await expect(page).toHaveTitle(title);
    await injectAxe(page);
    // Rule thuộc card #34 (contrast, WCAG AA) + #36 (document-title).
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: false },
    });
  }
});

test("chrome staff CMS đạt contrast AA + mọi route có document title T-NFR-A1", async ({ page }) => {
  await loginAdmin(page);
  for (const { path, title, ready } of STAFF_PAGES) {
    await page.goto(path);
    await ready(page);
    await expect(page).toHaveTitle(title);
    await injectAxe(page);
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: false },
    });
  }
});
