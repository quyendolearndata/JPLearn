import { test, expect, type Page } from "@playwright/test";

const BANNED_CHROME = ["Ngữ pháp", "Flashcard", "Bản dịch"];
const SEED_ITEM_ID = "00000000-0000-4000-8000-0000000000c1";

interface RegisteredUser {
  email: string;
  token: string;
  userId: string;
  apiRoot: string;
}

async function register(page: Page): Promise<RegisteredUser> {
  await page.goto("/login");
  const email = `lrn${Date.now()}${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  const registerResponsePromise = page.waitForResponse(
    (res) => res.url().includes("/auth/register") && res.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Đăng ký" }).click();
  const registerRes = await registerResponsePromise;
  const apiRoot = new URL(registerRes.url()).origin;
  await expect(page).toHaveURL("/");

  const userData = await page.evaluate(() => ({
    token: localStorage.getItem("jplearn.access_token")!,
    userId: JSON.parse(localStorage.getItem("jplearn.user")!).id,
  }));

  return { email, token: userData.token, userId: userData.userId, apiRoot };
}

async function expectNoBannedChrome(page: Page) {
  for (const text of BANNED_CHROME) {
    await expect(page.getByText(text, { exact: true })).toHaveCount(0);
  }
}

async function seedPlayback(page: Page, apiRoot: string, token: string, itemId: string) {
  const idempotencyKey = `seed-play-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const response = await page.request.post(`${apiRoot}/playbacks`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    data: {
      catalog_item_id: itemId,
      device_id: "e2e-device",
      take_over: true,
    },
  });
  expect(response.status()).toBe(201);
  return await response.json();
}

test.describe("Learning Loop Integration (PR7, Waves A-C)", () => {
  test("deterministic learning loop: catalog navigation, playback start, goal update, watch history deletion and persistence", async ({ page }) => {
    test.setTimeout(120_000);

    // 1. Register learner and verify clean slate
    const user = await register(page);
    await expectNoBannedChrome(page);

    // 2. Open /catalog: seed item must be visible
    await page.goto("/catalog");
    await expect(page.getByRole("heading", { name: "Catalog" })).toBeVisible();
    await expectNoBannedChrome(page);

    const seedCard = page.locator(`[data-item-id="${SEED_ITEM_ID}"]`);
    await expect(seedCard).toBeVisible();
    await seedCard.getByRole("link", { name: "Vào học bài này" }).click();

    // 3. In /session: verify session page and start session
    await expect(page).toHaveURL(new RegExp(`/session\\?item_id=${SEED_ITEM_ID}`));
    await expect(page.getByRole("heading", { name: "Phiên" })).toBeVisible();
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();

    const video = page.locator("video");
    await expect(video).toBeVisible();
    const playPauseBtn = page.getByRole("button", { name: /Phát|Tạm dừng/ });
    await expect(playPauseBtn).toBeVisible();
    await expectNoBannedChrome(page);

    // 4. Seed a playback record to ensure watch history is populated
    await seedPlayback(page, user.apiRoot, user.token, SEED_ITEM_ID);

    // 5. Open /progress: verify metrics and daily goals
    await page.goto("/progress");
    await expect(page.getByRole("heading", { name: "Tiến độ" })).toBeVisible();
    await expect(page.locator(".progress-label")).toHaveText("Phút CI tích lũy");

    // Check Daily Goal section and update to 30 minutes
    await expect(page.getByText("Mục tiêu học tập hàng ngày")).toBeVisible();
    const goalBtn = page.getByRole("button", { name: "30 phút / ngày" });
    await expect(goalBtn).toBeVisible();
    await goalBtn.click();
    await expect(page.getByText(/Mục tiêu sắp có hiệu lực:\s*30 phút \/ ngày/)).toBeVisible();

    // Reload page to verify pending goal persistence
    await page.reload();
    await expect(page.getByText(/Mục tiêu sắp có hiệu lực:\s*30 phút \/ ngày/)).toBeVisible();

    // Check 7-day activity section
    await expect(page.getByText("Hoạt động 7 ngày gần đây")).toBeVisible();

    // Check Watch History section - must contain watch items
    await expect(page.getByText("Lịch sử xem gần đây")).toBeVisible();
    const deleteBtn = page.getByRole("button", { name: "Xóa lịch sử" });
    await expect(deleteBtn).toBeVisible();

    // 6. Non-destructive watch history deletion
    page.on("dialog", (dialog) => dialog.accept());
    await deleteBtn.click();

    // Deletion notice with receipt appears
    await expect(page.getByText(/Đã yêu cầu xóa lịch sử xem/)).toBeVisible();
    await expect(page.getByText("Chưa có lịch sử xem nào được ghi nhận.")).toBeVisible();

    // Verify progress number is retained
    await expect(page.locator(".progress-label")).toHaveText("Phút CI tích lũy");

    // Reload progress page and verify watch history remains hidden
    await page.reload();
    await expect(page.getByText("Chưa có lịch sử xem nào được ghi nhận.")).toBeVisible();
    await expect(page.locator(".progress-label")).toHaveText("Phút CI tích lũy");

    // Verify no banned chrome
    await expectNoBannedChrome(page);
  });

  test("catalog filter rapid switching does not cause race-condition corruption", async ({ page }) => {
    await register(page);
    await page.goto("/catalog");
    await expect(page.getByRole("heading", { name: "Catalog" })).toBeVisible();

    // Rapidly switch between CI filters
    const filterPills = page.locator(".filter-pills button");
    const count = await filterPills.count();
    for (let i = 0; i < count; i++) {
      await filterPills.nth(i).click();
    }
    // Switch back to "Tất cả cấp độ"
    await filterPills.first().click();

    const seedCard = page.locator(`[data-item-id="${SEED_ITEM_ID}"]`);
    await expect(seedCard).toBeVisible();
    await expectNoBannedChrome(page);
  });
});
