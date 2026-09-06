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
    await page.evaluate(() => document.fonts.ready);
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
    await page.evaluate(() => document.fonts.ready);
    await injectAxe(page);
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: false },
    });
  }
});

test("axe: error state on login, active session state, staff detail route T-NFR-A1", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("bad");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.locator("p.status-error")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });

  await register(page);
  await page.goto("/session?item_id=00000000-0000-4000-8000-0000000000c1");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await expect(page.locator("video")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });
  await page.getByRole("button", { name: "Kết thúc phiên" }).click();
  await expect(page.getByText("Tổng kết phiên học")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });

  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await expect(page.getByRole("button", { name: "Đăng nhập" })).toBeVisible();
  await loginAdmin(page);
  await page.goto("/staff/00000000-0000-4000-8000-0000000000c1");
  await expect(page.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });
});

test("keyboard: login form tab order and Enter-to-submit; player controls reachable T-NFR-A1", async ({ page }, testInfo) => {
  await page.goto("/login");
  const formOrder = await page.locator("main input, main button").evaluateAll((els) =>
    els.map((el) => {
      if (el instanceof HTMLInputElement) {
        const label = document.querySelector(`label[for="${el.id}"]`);
        return (label?.textContent || el.id).trim();
      }
      return (el.textContent || "").trim();
    }),
  );
  expect(formOrder).toEqual(["Email", "Mật khẩu", "Đăng nhập", "Đăng ký"]);

  await page.getByLabel("Email").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Mật khẩu")).toBeFocused();
  // Playwright WebKit does not deliver Tab past the password field the same way
  // Chromium does (password-manager widget). Chromium covers the full CTA walk.
  if (testInfo.project.name === "chromium") {
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Đăng nhập" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Đăng ký" })).toBeFocused();
  }
  await page.getByLabel("Email").fill(`k${Date.now()}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/");

  await page.goto("/session?item_id=00000000-0000-4000-8000-0000000000c1");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).focus();
  await page.keyboard.press("Enter");
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await expect(video).toHaveAttribute("controls", "");
  await video.focus();
  await expect(video).toBeFocused();
});
