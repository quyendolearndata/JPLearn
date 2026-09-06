import { test, expect, type Page, type BrowserContext } from "@playwright/test";

const SEED_PUBLISHED_ITEM = "00000000-0000-4000-8000-0000000000c1";

async function register(page: Page): Promise<{ email: string; userId: string; token: string }> {
  await page.goto("/login");
  const email = `rec${Date.now()}${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
  const { userId, token } = await page.evaluate(() => ({
    userId: JSON.parse(localStorage.getItem("jplearn.user") || "{}").id as string,
    token: localStorage.getItem("jplearn.access_token") as string,
  }));
  return { email, userId, token };
}

async function readRecord(page: Page, userId: string) {
  return page.evaluate((k) => {
    const raw = sessionStorage.getItem(k);
    return raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
  }, `jplearn.session:${userId}`);
}

test.describe("Session recovery T-SES-REC-001", () => {
  test("start response lost after commit → reload replays same key → one session", async ({ page }) => {
    const { userId } = await register(page);
    const committed: string[] = [];
    await page.route(/\/sessions$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      if (route.request().method() !== "POST") return route.continue();
      const resp = await route.fetch();
      committed.push((await resp.json()).id);
      await route.abort("failed");
    });
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText("Lỗi kết nối máy chủ khi bắt đầu phiên.")).toBeVisible();
    const starting = await readRecord(page, userId);
    expect(starting?.state).toBe("starting");
    expect(committed).toHaveLength(1);

    await page.unroute(/\/sessions$/);
    await page.reload();
    await expect(page.getByText("Phiên đang chạy (đã khôi phục).")).toBeVisible();
    const active = await readRecord(page, userId);
    expect(active?.state).toBe("active");
    expect(active?.sessionId).toBe(committed[0]);
    expect(active?.idempotencyKey).toBe(starting?.idempotencyKey);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
  });

  test("started → reload → route away and back → session still active, end works once", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const before = await readRecord(page, userId);

    await page.reload();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    await page.goto("/progress");
    await page.goto("/session");
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
    const after = await readRecord(page, userId);
    expect(after?.sessionId).toBe(before?.sessionId);

    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Tổng kết phiên học")).toBeVisible();
    expect(await readRecord(page, userId)).toBeNull();
  });

  test("end response lost after commit → GET confirms ended → summary shown, no second end", async ({ page, request }) => {
    const { userId, token } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const rec = await readRecord(page, userId);
    const sessionId = rec?.sessionId as string;

    let endUrl = "";
    await page.route(/\/sessions\/[^/]+\/end$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      endUrl = route.request().url();
      await route.fetch();
      await route.abort("failed");
    });
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Đã kết thúc phiên.")).toBeVisible();
    expect(await readRecord(page, userId)).toBeNull();

    const again = await request.post(endUrl, { headers: { Authorization: `Bearer ${token}` } });
    expect(again.status()).toBe(400);
    const got = await request.get(endUrl.replace(/\/end$/, ""), { headers: { Authorization: `Bearer ${token}` } });
    expect((await got.json()).id).toBe(sessionId);
    expect((await got.json()).ended_at).not.toBeNull();
  });

  test("end and status check both offline → not reported ended, record kept for retry", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();

    await page.route(/\/sessions\/[^/]+(\/end)?$/, (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      return route.abort("failed");
    });
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Lỗi kết nối khi kết thúc phiên.")).toBeVisible();
    await expect(page.getByText("Tổng kết phiên học")).toHaveCount(0);
    const rec = await readRecord(page, userId);
    expect(rec?.state).toBe("outcome_unknown");
    expect(rec?.sessionId).toBeTruthy();

    await page.unroute(/\/sessions\/[^/]+(\/end)?$/);
    await page.reload();
    await expect(page.getByText(/đang chạy/)).toBeVisible();
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Tổng kết phiên học")).toBeVisible();
  });

  test("two tabs same user keep independent records; switching user hides previous record", async ({ browser }) => {
    const ctx: BrowserContext = await browser.newContext();
    const tabA = await ctx.newPage();
    const { userId: u1 } = await register(tabA);
    await tabA.goto("/session");
    await tabA.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(tabA.getByText(/Phiên đang chạy/)).toBeVisible();
    const recA = await readRecord(tabA, u1);

    const tabB = await ctx.newPage();
    await tabB.goto("/session");
    expect(await readRecord(tabB, u1)).toBeNull();
    await expect(tabB.getByRole("button", { name: "Bắt đầu phiên" })).toBeEnabled();
    await tabB.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(tabB.getByText(/Phiên đang chạy/)).toBeVisible();
    const recB = await readRecord(tabB, u1);
    expect(recB?.sessionId).not.toBe(recA?.sessionId);
    expect((await readRecord(tabA, u1))?.sessionId).toBe(recA?.sessionId);

    await tabA.goto("/login");
    await tabA.getByRole("button", { name: "Đăng xuất" }).click();
    await expect(tabA.getByRole("button", { name: "Đăng nhập" })).toBeVisible();
    expect(await readRecord(tabA, u1)).toBeNull();
    const { userId: u2 } = await register(tabA);
    await tabA.goto("/session");
    expect(await readRecord(tabA, u2)).toBeNull();
    await expect(tabA.getByRole("button", { name: "Bắt đầu phiên" })).toBeEnabled();
    await expect(tabA.getByText(/đã khôi phục/)).toHaveCount(0);
    await ctx.close();
  });

  test("recovery refetches catalog; record never contains media URLs", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.locator("video")).toBeVisible();
    const raw = await page.evaluate((k) => sessionStorage.getItem(k), `jplearn.session:${userId}`);
    expect(raw).not.toContain("hls_url");
    expect(raw).not.toContain("playback_url");
    expect(raw).not.toContain("sig=");

    const catalogRefetch = page.waitForRequest((r) => r.url().endsWith("/catalog") && r.method() === "GET");
    await page.reload();
    await catalogRefetch;
    await expect(page.locator("video")).toBeVisible();
  });
});
