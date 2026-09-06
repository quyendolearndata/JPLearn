import { test, expect } from "@playwright/test";

test("T-AUTH-SEC-001: open-redirect targets fall back to /, internal path is honoured", async ({ page }) => {
  await page.goto("/login?redirect=//evil.example/phish");
  await page.getByLabel("Email").fill(`r${Date.now()}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");

  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await expect(page.getByRole("button", { name: "Đăng nhập" })).toBeVisible();
  await page.goto("/login?redirect=%2Fprogress");
  await page.getByLabel("Email").fill(`r${Date.now()}b@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/progress");
});

test("T-AUTH-ERR-001: a 400 validation error from the API is shown verbatim in the alert", async ({ page }) => {
  await page.route(/\/auth\/login$/, (route) =>
    route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "email must be lowercase" }) }),
  );
  await page.goto("/login");
  await page.getByLabel("Email").fill("Mixed@Example.com");
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.locator("p.status-error")).toHaveText("email must be lowercase");
});
