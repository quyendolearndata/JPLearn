import { test, expect, type Page } from "@playwright/test";
import { sevenDayCalendarRange } from "../src/lib/learning-calendar";

const BANNED_CHROME = ["Ngữ pháp", "Flashcard", "Bản dịch"];
const SEED_ITEM_ID = "00000000-0000-4000-8000-0000000000c1";

interface RegisteredUser {
  token: string;
  apiRoot: string;
}

interface LearningPreferences {
  revision: number;
  current_policy: { daily_goal_minutes: number; timezone: string; effective_at: string };
  pending_policy: { daily_goal_minutes: number; timezone: string; effective_at: string } | null;
}

interface ActivitySummary {
  total_active_watch_seconds: number;
}

interface WatchHistory {
  items: Array<{
    playback_id: string;
    catalog_item_id: string;
    total_active_ms: number;
  }>;
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}

async function register(page: Page): Promise<RegisteredUser> {
  await page.goto("/login");
  const email = `lrn${Date.now()}${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  const registerResponsePromise = page.waitForResponse(
    (res) => res.url().includes("/auth/register") && res.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Đăng ký" }).click();
  const registerRes = await registerResponsePromise;
  const apiRoot = new URL(registerRes.url()).origin;
  await expect(page).toHaveURL("/");

  const token = await page.evaluate(() => localStorage.getItem("jplearn.access_token"));
  expect(token).toBeTruthy();
  return { token: token!, apiRoot };
}

async function getJson<T>(page: Page, user: RegisteredUser, path: string): Promise<T> {
  const response = await page.request.get(`${user.apiRoot}${path}`, {
    headers: { Authorization: `Bearer ${user.token}` },
  });
  expect(response.ok(), `${path} returned ${response.status()}`).toBe(true);
  return await response.json() as T;
}

async function expectNoBannedChrome(page: Page) {
  for (const text of BANNED_CHROME) {
    await expect(page.getByText(text, { exact: true })).toHaveCount(0);
  }
}

test.describe("Learning Loop Integration (PR7, Waves A-C)", () => {
  test("real playback credits active time while history deletion preserves numeric progress and activity", async ({ page }) => {
    test.setTimeout(150_000);

    const user = await register(page);
    await expectNoBannedChrome(page);

    await page.goto("/catalog");
    await expect(page.getByRole("heading", { name: "Catalog" })).toBeVisible();
    const seedCard = page.locator(`[data-item-id="${SEED_ITEM_ID}"]`);
    await expect(seedCard).toBeVisible();
    await seedCard.getByRole("link", { name: "Vào học bài này" }).click();

    await expect(page).toHaveURL(new RegExp(`/session\\?item_id=${SEED_ITEM_ID}`));
    const sessionStartPromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/sessions" && response.request().method() === "POST";
    });
    const playbackStartPromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/playbacks" && response.request().method() === "POST";
    });
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();

    const sessionStartResponse = await sessionStartPromise;
    expect(sessionStartResponse.status()).toBe(201);
    const startedSession = await sessionStartResponse.json() as { started_at: string };
    const playbackStartResponse = await playbackStartPromise;
    expect(playbackStartResponse.status()).toBe(201);
    const startedPlayback = await playbackStartResponse.json() as { playback_id: string };

    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const video = page.locator("video");
    await expect(video).toBeVisible();
    await expect.poll(
      () => video.evaluate((element: HTMLVideoElement) => element.readyState),
      { timeout: 20_000 },
    ).toBeGreaterThanOrEqual(2);

    const checkpointPromise = page.waitForResponse(
      (response) => (
        response.url().includes(`/playbacks/${startedPlayback.playback_id}/checkpoints/`)
        && response.request().method() === "PUT"
      ),
      { timeout: 30_000 },
    );
    const playbackEndPromise = page.waitForResponse(
      (response) => (
        new URL(response.url()).pathname === `/playbacks/${startedPlayback.playback_id}/end`
        && response.request().method() === "POST"
      ),
      { timeout: 45_000 },
    );
    const initialPosition = await video.evaluate((element: HTMLVideoElement) => element.currentTime);
    await page.getByRole("button", { name: "Phát", exact: true }).click();
    await expect.poll(
      () => video.evaluate((element: HTMLVideoElement) => element.paused),
      { timeout: 10_000 },
    ).toBe(false);
    await expect.poll(
      () => video.evaluate((element: HTMLVideoElement) => element.currentTime),
      { timeout: 10_000 },
    ).toBeGreaterThan(initialPosition + 0.5);

    const checkpointResponse = await checkpointPromise;
    expect(checkpointResponse.status()).toBe(200);
    const checkpoint = await checkpointResponse.json() as {
      accepted_delta_ms: number;
      server_acknowledged_active_ms: number;
    };
    expect(checkpoint.accepted_delta_ms).toBeGreaterThan(0);
    expect(checkpoint.server_acknowledged_active_ms).toBeGreaterThan(0);

    const playbackEndResponse = await playbackEndPromise;
    expect(playbackEndResponse.status()).toBe(200);
    await expect.poll(
      () => video.evaluate((element: HTMLVideoElement) => element.ended),
      { timeout: 5_000 },
    ).toBe(true);

    const sessionStartedAt = Date.parse(startedSession.started_at);
    expect(sessionStartedAt).not.toBeNaN();
    await expect.poll(
      () => Math.floor((Date.now() - sessionStartedAt) / 1000),
      { timeout: 75_000, intervals: [1_000] },
    ).toBeGreaterThanOrEqual(61);

    const sessionEndPromise = page.waitForResponse((response) => (
      /\/sessions\/[0-9a-f-]+\/end$/.test(new URL(response.url()).pathname)
      && response.request().method() === "POST"
    ));
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    const sessionEndResponse = await sessionEndPromise;
    expect(sessionEndResponse.status()).toBe(200);
    const endedProgress = await sessionEndResponse.json() as { minutes_comprehensible: number };
    expect(endedProgress.minutes_comprehensible).toBeGreaterThan(0);
    await expect(page.getByRole("heading", { name: "Tổng kết phiên học" })).toBeVisible();

    const preferencesBefore = await getJson<LearningPreferences>(page, user, "/me/learning-preferences");
    const range = sevenDayCalendarRange(new Date(), preferencesBefore.current_policy.timezone);
    const progressBefore = await getJson<{ minutes_comprehensible: number }>(page, user, "/progress");
    const activityBefore = await getJson<ActivitySummary>(
      page,
      user,
      `/me/activity?from=${range.from}&to=${range.to}`,
    );
    const historyBefore = await getJson<WatchHistory>(page, user, "/me/watch-history?limit=5");
    expect(progressBefore.minutes_comprehensible).toBeGreaterThan(0);
    expect(activityBefore.total_active_watch_seconds).toBeGreaterThan(0);
    const playbackHistory = historyBefore.items.find(
      (item) => item.playback_id === startedPlayback.playback_id,
    );
    expect(playbackHistory?.catalog_item_id).toBe(SEED_ITEM_ID);
    expect(playbackHistory?.total_active_ms).toBeGreaterThan(0);

    await page.goto("/progress");
    await expect(page.getByRole("heading", { name: "Tiến độ" })).toBeVisible();
    await expect(page.getByTestId("legacy-progress-minutes")).toHaveAttribute(
      "data-progress-minutes",
      String(progressBefore.minutes_comprehensible),
    );
    await expect(page.getByTestId("active-watch-total")).toHaveAttribute(
      "data-active-watch-seconds",
      String(activityBefore.total_active_watch_seconds),
    );
    await expect(page.locator(`[data-playback-id="${startedPlayback.playback_id}"]`)).toHaveAttribute(
      "data-active-ms",
      String(playbackHistory!.total_active_ms),
    );

    const goalResponsePromise = page.waitForResponse((response) => (
      new URL(response.url()).pathname === "/me/learning-preferences"
      && response.request().method() === "PUT"
    ));
    await page.getByRole("button", { name: "30 phút / ngày" }).click();
    const goalResponse = await goalResponsePromise;
    expect(goalResponse.status()).toBe(200);
    expect(goalResponse.request().postDataJSON()).toEqual({
      expected_revision: preferencesBefore.revision,
      daily_goal_minutes: 30,
    });
    const preferencesAfter = await goalResponse.json() as LearningPreferences;
    expect(preferencesAfter.current_policy.daily_goal_minutes).toBe(
      preferencesBefore.current_policy.daily_goal_minutes,
    );
    expect(preferencesAfter.pending_policy?.daily_goal_minutes).toBe(30);
    await expect(page.getByText(/Mục tiêu sắp có hiệu lực:\s*30 phút \/ ngày/)).toBeVisible();
    await page.reload();
    await expect(page.getByText(/Mục tiêu sắp có hiệu lực:\s*30 phút \/ ngày/)).toBeVisible();

    page.once("dialog", (dialog) => void dialog.accept());
    const deletionResponsePromise = page.waitForResponse((response) => (
      new URL(response.url()).pathname === "/me/watch-history"
      && response.request().method() === "DELETE"
    ));
    await page.getByRole("button", { name: "Xóa lịch sử" }).click();
    const deletionResponse = await deletionResponsePromise;
    expect(deletionResponse.status()).toBe(202);
    const deletionReceipt = await deletionResponse.json() as {
      deletion_id: string;
      cutoff_time: string;
      status: string;
    };
    expect(deletionReceipt.deletion_id).toMatch(/^[0-9a-f-]{36}$/);
    expect(Date.parse(deletionReceipt.cutoff_time)).not.toBeNaN();
    expect(deletionReceipt.status).toBe("queued");
    await expect(page.getByText(/Đã yêu cầu xóa lịch sử xem/)).toBeVisible();
    await expect(page.getByText("Chưa có lịch sử xem nào được ghi nhận.")).toBeVisible();

    const progressAfterDelete = await getJson<{ minutes_comprehensible: number }>(page, user, "/progress");
    const activityAfterDelete = await getJson<ActivitySummary>(
      page,
      user,
      `/me/activity?from=${range.from}&to=${range.to}`,
    );
    const historyAfterDelete = await getJson<WatchHistory>(page, user, "/me/watch-history?limit=5");
    expect(progressAfterDelete.minutes_comprehensible).toBe(progressBefore.minutes_comprehensible);
    expect(activityAfterDelete.total_active_watch_seconds).toBe(activityBefore.total_active_watch_seconds);
    expect(historyAfterDelete.items).toEqual([]);

    await page.reload();
    await expect(page.getByText("Chưa có lịch sử xem nào được ghi nhận.")).toBeVisible();
    await expect(page.getByTestId("legacy-progress-minutes")).toHaveAttribute(
      "data-progress-minutes",
      String(progressBefore.minutes_comprehensible),
    );
    await expect(page.getByTestId("active-watch-total")).toHaveAttribute(
      "data-active-watch-seconds",
      String(activityBefore.total_active_watch_seconds),
    );
    await expectNoBannedChrome(page);
  });

  test("catalog keeps the final CI filter when controlled responses arrive in reverse order", async ({ page }) => {
    await register(page);
    await page.goto("/catalog");
    await expect(page.locator(`[data-item-id="${SEED_ITEM_ID}"]`)).toBeVisible();

    const firstArrived = deferred();
    const releaseFirst = deferred();
    await page.route("**/catalog?ci_level=0", async (route) => {
      const response = await route.fetch();
      firstArrived.resolve();
      await releaseFirst.promise;
      await route.fulfill({ response });
    });

    const levelZeroResponse = page.waitForResponse((response) => (
      new URL(response.url()).searchParams.get("ci_level") === "0"
    ));
    await page.getByRole("button", { name: "Cấp 0" }).click();
    await firstArrived.promise;

    const levelFourResponse = page.waitForResponse((response) => (
      new URL(response.url()).searchParams.get("ci_level") === "4"
    ));
    await page.getByRole("button", { name: "Cấp 4" }).click();
    expect((await levelFourResponse).status()).toBe(200);
    releaseFirst.resolve();
    const staleResponse = await levelZeroResponse;
    await staleResponse.finished();
    await page.evaluate(() => new Promise<void>((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    }));

    await expect(page.getByRole("button", { name: "Cấp 4" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(`[data-item-id="${SEED_ITEM_ID}"]`)).toHaveCount(0);
    await expect(page.getByText("Hiện chưa có bài học nào ở Cấp 4. Vui lòng chọn cấp độ khác.")).toBeVisible();
  });

  test("disabled playback and smart stream capabilities preserve the legacy learning path", async ({ page }) => {
    await page.route("**/capabilities", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          video_scene_breakdown_enabled: false,
          smart_stream_enabled: false,
          interactive_dual_subs_enabled: false,
          immersion_lookup_enabled: false,
          personal_collections_enabled: false,
          content_reports_enabled: false,
          playback_tracking_enabled: false,
          scene_search_enabled: false,
          staff_ai_enabled: false,
        }),
      });
    });
    await page.route("**/me/recommendations?limit=4", (route) => route.fulfill({ status: 403 }));
    await page.route("**/playbacks", (route) => {
      if (route.request().method() === "POST") return route.fulfill({ status: 403 });
      return route.continue();
    });

    await register(page);
    await page.goto("/catalog");
    await expect(page.locator(`[data-item-id="${SEED_ITEM_ID}"]`)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Gợi ý cho bạn" })).toHaveCount(0);
    await page.locator(`[data-item-id="${SEED_ITEM_ID}"]`).getByRole("link").click();

    const playbackRejection = page.waitForResponse((response) => (
      new URL(response.url()).pathname === "/playbacks"
      && response.request().method() === "POST"
    ));
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    expect((await playbackRejection).status()).toBe(403);
    const video = page.locator("video");
    await expect.poll(
      () => video.evaluate((element: HTMLVideoElement) => element.readyState),
      { timeout: 20_000 },
    ).toBeGreaterThanOrEqual(2);
    await page.getByRole("button", { name: "Phát", exact: true }).click();
    await expect.poll(
      () => video.evaluate((element: HTMLVideoElement) => element.currentTime),
      { timeout: 10_000 },
    ).toBeGreaterThan(0.5);
    await page.getByRole("button", { name: "Tạm dừng", exact: true }).click();
    const endResponse = page.waitForResponse((response) => (
      /\/sessions\/[0-9a-f-]+\/end$/.test(new URL(response.url()).pathname)
    ));
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    expect((await endResponse).status()).toBe(200);
  });

  test("409, HTTP 500 and offline failures render actionable feedback", async ({ page }) => {
    await register(page);
    await page.route("**/me/learning-preferences", async (route) => {
      if (route.request().method() === "PUT") {
        await route.fulfill({ status: 409, contentType: "application/json", body: "{}" });
        return;
      }
      await route.continue();
    });
    await page.goto("/progress");
    await page.getByRole("button", { name: "30 phút / ngày" }).click();
    await expect(page.locator(".status-error[role=alert]")).toContainText("xung đột phiên bản");

    await page.route("**/catalog?ci_level=4", (route) => route.fulfill({ status: 500 }));
    await page.goto("/catalog");
    await page.getByRole("button", { name: "Cấp 4" }).click();
    await expect(page.locator(".status-error[role=alert]")).toContainText("Không thể tải danh mục bài học");

    await page.route("**/catalog?ci_level=3", (route) => route.abort("failed"));
    await page.getByRole("button", { name: "Cấp 3" }).click();
    await expect(page.locator(".status-error[role=alert]")).toContainText("Lỗi kết nối máy chủ khi tải danh mục");
  });
});
