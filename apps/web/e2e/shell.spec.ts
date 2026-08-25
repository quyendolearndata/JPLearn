import { test, expect } from "@playwright/test";

test("login and progress have no grammar chrome FR-FLG-002 FR-NEG-002", async ({ page }) => {
  await page.goto("/login");
  const email = `w${Date.now()}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByText("Ngữ pháp")).toHaveCount(0);
  await expect(page.getByText("Flashcard")).toHaveCount(0);
  await page.goto("/progress");
  await expect(page.getByText(/phút/i)).toBeVisible();
});
