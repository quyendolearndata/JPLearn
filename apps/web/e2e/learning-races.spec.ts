import { expect, test, type Page } from "@playwright/test";

function barrier() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}

const historyItem = {
  playback_id: "old-playback", catalog_item_id: "clip-a", topic_id: "daily_home",
  item_type: "video", duration_seconds: 32, total_active_ms: 15000,
  created_at: "2026-09-08T00:00:00Z",
};

async function learner(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(`race${crypto.randomUUID()}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  const registration = page.waitForResponse("**/auth/register");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
  return new URL((await registration).url()).origin;
}

for (const operation of ["goal", "conflict-refresh", "delete"] as const) {
  test(`FR-ID-002: ${operation} response from A cannot overwrite mounted B after focus`, async ({ page }) => {
    const apiRoot = await learner(page);
    const accountResponse = await page.request.post(`${apiRoot}/auth/register`, {
      data: { email: `other${crypto.randomUUID()}@example.com`, password: "password10" },
    });
    expect(accountResponse.status()).toBe(201);
    const other = await accountResponse.json();
    const captured = barrier();
    const release = barrier();
    const delivered = barrier();
    let holdRefresh = false;
    await page.route("**/me/watch-history?limit=5", (route) => route.fulfill({
      json: { items: [historyItem], next_cursor: null },
    }));
    await page.route("**/me/learning-preferences", async (route) => {
      if (route.request().method() === "PUT") {
        if (operation === "conflict-refresh") {
          holdRefresh = true;
          await route.fulfill({ status: 409, json: {} });
          return;
        }
        const response = await route.fetch();
        captured.resolve();
        await release.promise;
        await route.fulfill({ response });
        delivered.resolve();
        return;
      }
      if (holdRefresh) {
        holdRefresh = false;
        const response = await route.fetch();
        const body = await response.json();
        body.current_policy.daily_goal_minutes = 60;
        captured.resolve();
        await release.promise;
        await route.fulfill({ json: body });
        delivered.resolve();
        return;
      }
      await route.continue();
    });
    await page.route("**/me/watch-history", async (route) => {
      captured.resolve();
      await release.promise;
      await route.fulfill({ status: 202, json: {
        deletion_id: "00000000-0000-4000-8000-000000000002",
        cutoff_time: "2026-09-08T01:00:00Z", status: "queued",
      } });
      delivered.resolve();
    });
    await page.goto("/progress");
    await expect(page.getByRole("button", { name: "Xóa lịch sử", exact: true })).toBeVisible();
    if (operation === "delete") {
      page.once("dialog", (dialog) => void dialog.accept());
      await page.getByRole("button", { name: "Xóa lịch sử", exact: true }).click();
    } else {
      await page.getByRole("button", { name: "30 phút / ngày", exact: true }).click();
    }
    await captured.promise;
    await page.evaluate((account) => {
      localStorage.setItem("jplearn.access_token", account.access_token);
      localStorage.setItem("jplearn.user", JSON.stringify(account.user));
      window.dispatchEvent(new Event("focus"));
    }, other);
    await expect(page.getByText("Đang tải tiến độ…")).toHaveCount(0);
    release.resolve();
    await delivered.promise;
    await page.evaluate(() => new Promise<void>((done) => {
      requestAnimationFrame(() => requestAnimationFrame(() => done()));
    }));
    await expect(page.getByText(/Mục tiêu hiện tại:/)).toContainText("15 phút / ngày");
    await expect(page.getByText(/Mục tiêu sắp có hiệu lực:/)).toHaveCount(0);
    await expect(page.getByText(/Đã yêu cầu xóa lịch sử xem/)).toHaveCount(0);
    await expect(page.locator('[data-playback-id="old-playback"]')).toBeVisible();
    await expect(page.getByRole("button", { name: "30 phút / ngày", exact: true })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Xóa lịch sử", exact: true })).toBeEnabled();
  });
}

test("FR-HIS-001: delayed history GET cannot restore rows after DELETE 202", async ({ page }) => {
  await learner(page);
  const captured = barrier();
  const release = barrier();
  const deleteCaptured = barrier();
  const releaseDelete = barrier();
  let holdNext = false;
  let deleted = false;
  await page.route("**/me/watch-history?limit=5", async (route) => {
    const items = deleted ? [] : [historyItem];
    if (holdNext) {
      holdNext = false;
      captured.resolve();
      await release.promise;
    }
    await route.fulfill({ json: { items, next_cursor: null } });
  });
  await page.route("**/me/watch-history", async (route) => {
    deleteCaptured.resolve();
    await releaseDelete.promise;
    deleted = true;
    await route.fulfill({ status: 202, json: {
      deletion_id: "00000000-0000-4000-8000-000000000001",
      cutoff_time: "2026-09-08T01:00:00Z", status: "queued",
    } });
  });
  await page.goto("/progress");
  await expect(page.locator('[data-playback-id="old-playback"]')).toBeVisible();
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Xóa lịch sử", exact: true }).click();
  await deleteCaptured.promise;
  holdNext = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await captured.promise;
  releaseDelete.resolve();
  await expect(page.getByText(/Đã yêu cầu xóa lịch sử xem/)).toBeVisible();
  await expect(page.getByText("Đang tải tiến độ…")).toHaveCount(0);
  const staleResponse = page.waitForResponse("**/me/watch-history?limit=5");
  release.resolve();
  await (await staleResponse).finished();
  await page.evaluate(() => new Promise<void>((done) => {
    requestAnimationFrame(() => requestAnimationFrame(() => done()));
  }));
  await expect(page.locator('[data-playback-id="old-playback"]')).toHaveCount(0);
  await expect(page.getByText("Chưa có lịch sử xem nào được ghi nhận.")).toBeVisible();
});

test("FR-ID-002: losing the token before a mutation never leaves controls busy", async ({ page }) => {
  await learner(page);
  await page.route("**/me/watch-history?limit=5", (route) => route.fulfill({
    json: { items: [historyItem], next_cursor: null },
  }));
  await page.goto("/progress");
  await expect(page.getByRole("button", { name: "Xóa lịch sử", exact: true })).toBeVisible();
  let mutationCount = 0;
  page.on("request", (request) => {
    if (["PUT", "DELETE"].includes(request.method())) mutationCount++;
  });
  await page.evaluate(() => localStorage.removeItem("jplearn.access_token"));
  const goal = page.getByRole("button", { name: "30 phút / ngày", exact: true });
  await goal.click();
  await expect(goal).toBeEnabled();
  page.once("dialog", (dialog) => void dialog.accept());
  const deletion = page.getByRole("button", { name: "Xóa lịch sử", exact: true });
  await deletion.click();
  await expect(deletion).toBeEnabled();
  expect(mutationCount).toBe(0);
});
