import { test, expect, devices } from "@playwright/test";

// UC-L06 / T-ID-002 / T-PRG-004 trên web shell THẬT (API + web dev server đang chạy).
// Hai browser context riêng biệt = hai "client": Desktop Chrome (web) và
// iPhone 13 emulation (đứng ra cho phone web; KHÔNG phải thiết bị iOS thật).
// Session kéo dài thật ~65s để minutesFromDuration cộng đúng 1 phút.

const MINUTE_MS = 65_000;

test("UC-L06 cùng user hai client: cùng catalog published, cùng minutes_comprehensible", async ({
  browser,
}) => {
  test.setTimeout(300_000);
  const email = `uicl6-${Date.now()}@example.com`;

  const fillAuth = async (page: import("@playwright/test").Page) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Mật khẩu").fill("password10");
  };

  // Client A: desktop web — đăng ký tài khoản mới qua UI
  const ctxA = await browser.newContext({ baseURL: "http://localhost:3000" });
  const pageA = await ctxA.newPage();
  await fillAuth(pageA);
  await pageA.getByRole("button", { name: "Đăng ký" }).click();
  await expect(pageA).toHaveURL("/");
  await expect(pageA.locator("ul li").first()).toBeVisible();
  const itemsA = (await pageA.locator("ul li").allInnerTexts()).sort();
  expect(itemsA.length).toBeGreaterThan(0);

  await pageA.goto("/progress");
  await expect(pageA.getByText("0 phút · cấp 0")).toBeVisible();

  // Client B: phone web (iPhone emulation) — đăng nhập cùng tài khoản
  const ctxB = await browser.newContext({
    ...devices["iPhone 13"],
    baseURL: "http://localhost:3000",
  });
  const pageB = await ctxB.newPage();
  await fillAuth(pageB);
  await pageB.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(pageB).toHaveURL("/");
  await expect(pageB.locator("ul li").first()).toBeVisible();
  const itemsB = (await pageB.locator("ul li").allInnerTexts()).sort();
  expect(itemsB).toEqual(itemsA);

  await pageB.goto("/progress");
  await expect(pageB.getByText("0 phút · cấp 0")).toBeVisible();

  // Client B chạy một phiên THẬT ~65s rồi kết thúc → +1 phút trên server
  await pageB.goto("/session");
  await pageB.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await expect(pageB.getByText("Phiên đang chạy.")).toBeVisible();
  await pageB.waitForTimeout(MINUTE_MS);
  await pageB.getByRole("button", { name: "Kết thúc phiên" }).click();
  await expect(pageB.getByText("Đã kết thúc phiên.")).toBeVisible();

  // FR-PRG-004: client A (web) đọc lại thấy cùng tiến độ
  await pageB.goto("/progress");
  await expect(pageB.getByText("1 phút · cấp 0")).toBeVisible();
  await pageA.goto("/progress");
  await expect(pageA.getByText("1 phút · cấp 0")).toBeVisible();

  // Chiều ngược lại: client A chạy phiên ~65s → client B thấy tổng 2 phút
  await pageA.goto("/session");
  await pageA.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await expect(pageA.getByText("Phiên đang chạy.")).toBeVisible();
  await pageA.waitForTimeout(MINUTE_MS);
  await pageA.getByRole("button", { name: "Kết thúc phiên" }).click();
  await expect(pageA.getByText("Đã kết thúc phiên.")).toBeVisible();

  await pageA.goto("/progress");
  await expect(pageA.getByText("2 phút · cấp 0")).toBeVisible();
  await pageB.goto("/progress");
  await expect(pageB.getByText("2 phút · cấp 0")).toBeVisible();

  await ctxA.close();
  await ctxB.close();
});
