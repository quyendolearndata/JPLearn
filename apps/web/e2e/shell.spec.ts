import { test, expect, type Page } from "@playwright/test";

const BANNED_CHROME = ["Ngữ pháp", "Flashcard", "Bản dịch"];

async function register(page: Page) {
  await page.goto("/login");
  const email = `w${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
}

async function expectNoBannedChrome(page: Page) {
  for (const text of BANNED_CHROME) {
    await expect(page.getByText(text, { exact: true })).toHaveCount(0);
  }
}

test("login and progress have no grammar chrome T-FLG-002 T-NEG-002", async ({ page }) => {
  await register(page);
  await expectNoBannedChrome(page);
  await page.goto("/session");
  await expect(page.getByRole("heading", { name: "Phiên" })).toBeVisible();
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
  await expectNoBannedChrome(page);
  await page.goto("/progress");
  await expect(page.locator(".progress-label")).toHaveText("Phút CI tích lũy");
  await expectNoBannedChrome(page);
});

test("catalog shows published seed item, hides draft T-CAT-002 T-FLG-002", async ({ page }) => {
  await register(page);
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "Catalog" })).toBeVisible();
  const seed = page.locator('[data-item-id="00000000-0000-4000-8000-0000000000c1"]');
  await expect(seed).toBeVisible();
  await expect(seed.getByRole("heading")).toHaveText("Đời sống hàng ngày");
  await expect(seed.getByText("30 giây")).toBeVisible();
  await expect(page.locator('[data-item-id="00000000-0000-4000-8000-0000000000d1"]')).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Tìm chủ đề" }).fill("chủ đề không tồn tại");
  await expect(seed).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Tìm chủ đề" }).fill("");
  await expect(seed).toBeVisible();
  await expectNoBannedChrome(page);
});
