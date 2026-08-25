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
  await expect(page.getByText(/phút/i)).toBeVisible();
  await expectNoBannedChrome(page);
});

test("catalog shows published seed item, hides draft T-CAT-002 T-FLG-002", async ({ page }) => {
  await register(page);
  await expect(page.getByRole("heading", { name: "Catalog" })).toBeVisible();
  await expect(page.getByText(/daily_home · video · 30s/)).toBeVisible();
  await expect(page.getByText(/food · video · 25s/)).toHaveCount(0);
  await expectNoBannedChrome(page);
});
