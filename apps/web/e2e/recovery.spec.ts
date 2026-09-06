import { test, expect, type APIRequestContext, type Page, type BrowserContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const SEED_PUBLISHED_ITEM = "00000000-0000-4000-8000-0000000000c1";

function stockMp4(): Buffer {
  const candidates = [
    path.resolve(__dirname, "../../../media/stock/mp4/level-0-wash-hands.mp4"),
    path.resolve(process.cwd(), "../../media/stock/mp4/level-0-wash-hands.mp4"),
  ];
  const hit = candidates.find((candidate) => fs.existsSync(candidate));
  if (!hit) throw new Error("stock mp4 missing");
  return fs.readFileSync(hit);
}

async function createPublishedCompanion(
  request: APIRequestContext,
  apiRoot: string,
  token: string,
): Promise<string> {
  const headers = { Authorization: `Bearer ${token}` };
  const created = await request.post(`${apiRoot}/staff/catalog`, {
    headers,
    data: {
      topic_id: "food",
      ci_level: 0,
      duration_seconds: 30,
      media_type: "video",
      visual_support: "high",
      title_internal: `F-03 companion ${Date.now()}`,
    },
  });
  expect(created.ok()).toBeTruthy();
  const itemId = (await created.json()).id as string;

  const uploaded = await request.post(`${apiRoot}/staff/catalog/${itemId}/media`, {
    headers,
    multipart: {
      file: {
        name: "f03-companion.mp4",
        mimeType: "video/mp4",
        buffer: stockMp4(),
      },
    },
  });
  expect(uploaded.ok()).toBeTruthy();
  expect((await request.post(`${apiRoot}/staff/catalog/${itemId}/submit-qa`, { headers })).ok()).toBeTruthy();
  expect((await request.post(`${apiRoot}/staff/catalog/${itemId}/publish`, { headers })).ok()).toBeTruthy();
  return itemId;
}

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

async function mockEndedDuration(page: Page, sessionId: string, durationSeconds: number) {
  const pattern = new RegExp(`/sessions/${sessionId}$`);
  await page.route(pattern, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    const response = await route.fetch();
    const body = await response.json() as Record<string, unknown>;
    await route.fulfill({
      response,
      json: { ...body, duration_seconds: durationSeconds },
    });
  });
  return pattern;
}

async function mockProgress(page: Page, progress: { minutes: number; level: number }) {
  const pattern = /\/progress$/;
  await page.route(pattern, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        minutes_comprehensible: progress.minutes,
        current_ci_level: progress.level,
      }),
    });
  });
  return pattern;
}

async function expectSummary(
  page: Page,
  expected: { duration: string; minutes: number; level: number },
) {
  await expect(page.getByRole("heading", { name: "Tổng kết phiên học" })).toBeVisible();
  await expect(page.getByText(`Thời lượng: ${expected.duration}`, { exact: true })).toBeVisible();
  await expect(page.getByText(`Tổng tích luỹ: ${expected.minutes} phút`, { exact: true })).toBeVisible();
  await expect(page.getByText(`Cấp độ CI: Cấp ${expected.level}`, { exact: true })).toBeVisible();
}

test.describe("Session recovery T-SES-REC-001", () => {
  test("F-01 pending active GET disables Start and cannot POST a new session T-SES-REC-001", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const stored = await readRecord(page, userId);
    const sessionId = stored?.sessionId as string;

    let markStatusRequested!: () => void;
    const statusRequested = new Promise<void>((resolve) => { markStatusRequested = resolve; });
    let releaseStatus!: () => void;
    const statusGate = new Promise<void>((resolve) => { releaseStatus = resolve; });
    let newSessionPosts = 0;
    const countPosts = (request: { method(): string; url(): string }) => {
      if (request.method() === "POST" && /\/sessions$/.test(request.url())) newSessionPosts += 1;
    };
    page.on("request", countPosts);
    const statusPattern = new RegExp(`/sessions/${sessionId}$`);
    await page.route(statusPattern, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      markStatusRequested();
      await statusGate;
      await route.continue();
    });

    await page.reload();
    await statusRequested;
    try {
      const start = page.getByRole("button", { name: "Bắt đầu phiên" });
      await expect(start).toBeDisabled();
      await start.evaluate((button: HTMLButtonElement) => button.click());
      expect(newSessionPosts).toBe(0);
    } finally {
      const statusResponse = page.waitForResponse(statusPattern);
      releaseStatus();
      await statusResponse;
      await page.unroute(statusPattern);
      page.off("request", countPosts);
    }
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
  });

  for (const fault of ["network", "HTTP 500"] as const) {
    const recoveryState = fault === "network" ? "active" : "outcome_unknown";
    test(`F-01 ${fault} during ${recoveryState} recovery keeps the record and retries the same GET T-SES-REC-001`, async ({ page }) => {
      const { userId } = await register(page);
      await page.goto("/session");
      await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
      await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
      const before = await readRecord(page, userId);
      const sessionId = before?.sessionId as string;
      if (fault === "HTTP 500") {
        await page.evaluate(({ key }) => {
          const stored = JSON.parse(sessionStorage.getItem(key) || "{}");
          sessionStorage.setItem(key, JSON.stringify({ ...stored, state: "outcome_unknown" }));
        }, { key: `jplearn.session:${userId}` });
      }
      const expected = await readRecord(page, userId);

      let newSessionPosts = 0;
      const countPosts = (request: { method(): string; url(): string }) => {
        if (request.method() === "POST" && /\/sessions$/.test(request.url())) newSessionPosts += 1;
      };
      page.on("request", countPosts);
      const statusPattern = new RegExp(`/sessions/${sessionId}$`);
      await page.route(statusPattern, async (route) => {
        if (route.request().method() === "OPTIONS") return route.continue();
        if (fault === "network") return route.abort("failed");
        return route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ statusCode: 500, message: "Injected recovery fault" }),
        });
      });

      await page.reload();
      await expect(page.getByRole("button", { name: "Thử khôi phục lại" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Bắt đầu phiên" })).toBeDisabled();
      expect(await readRecord(page, userId)).toEqual(expected);
      expect(newSessionPosts).toBe(0);

      await page.unroute(statusPattern);
      await page.getByRole("button", { name: "Thử khôi phục lại" }).click();
      await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
      expect((await readRecord(page, userId))?.sessionId).toBe(sessionId);
      expect(newSessionPosts).toBe(0);
      page.off("request", countPosts);
    });
  }

  test("F-01 starting replay keeps one key through HTTP 500 and malformed success T-SES-REC-001", async ({ page }) => {
    const { userId } = await register(page);
    const replayKeys: string[] = [];
    let committedId = "";
    await page.route(/\/sessions$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      if (route.request().method() !== "POST") return route.continue();
      replayKeys.push(route.request().headers()["idempotency-key"]);
      const response = await route.fetch();
      committedId = (await response.json()).id as string;
      await route.abort("failed");
    });
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText("Lỗi kết nối máy chủ khi bắt đầu phiên.")).toBeVisible();
    const starting = await readRecord(page, userId);
    await page.unroute(/\/sessions$/);

    let faultAttempt = 0;
    await page.route(/\/sessions$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      if (route.request().method() !== "POST") return route.continue();
      replayKeys.push(route.request().headers()["idempotency-key"]);
      faultAttempt += 1;
      if (faultAttempt === 1) {
        return route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ statusCode: 500, message: "Injected replay fault" }),
        });
      }
      return route.fulfill({ status: 201, contentType: "application/json", body: "{}" });
    });

    await page.reload();
    await expect(page.getByRole("button", { name: "Thử khôi phục lại" })).toBeVisible();
    expect(await readRecord(page, userId)).toEqual(starting);
    await page.getByRole("button", { name: "Thử khôi phục lại" }).click();
    await expect(page.getByRole("button", { name: "Thử khôi phục lại" })).toBeVisible();
    expect(await readRecord(page, userId)).toEqual(starting);

    await page.unroute(/\/sessions$/);
    await page.getByRole("button", { name: "Thử khôi phục lại" }).click();
    await expect(page.getByText("Phiên đang chạy (đã khôi phục).")).toBeVisible();
    const active = await readRecord(page, userId);
    expect(active?.sessionId).toBe(committedId);
    expect(new Set(replayKeys)).toEqual(new Set([starting?.idempotencyKey as string]));
  });

  test("F-01 starting replay 409 is terminal and allows a new start T-SES-REC-001", async ({ page }) => {
    const { userId } = await register(page);
    const starting = {
      v: 1,
      state: "starting",
      idempotencyKey: "conflicting-key",
      startedAt: "2026-09-06T00:00:00.000Z",
      itemId: SEED_PUBLISHED_ITEM,
      deviceClass: "web",
    };
    await page.evaluate(({ key, record }) => sessionStorage.setItem(key, JSON.stringify(record)), {
      key: `jplearn.session:${userId}`,
      record: starting,
    });
    await page.route(/\/sessions$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      return route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ statusCode: 409, message: "Idempotency key conflict" }),
      });
    });

    await page.goto("/session");
    await expect(page.getByText("Không thể khôi phục phiên do khóa chống trùng bị xung đột.")).toBeVisible();
    expect(await readRecord(page, userId)).toBeNull();
    await expect(page.getByRole("button", { name: "Thử khôi phục lại" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Bắt đầu phiên" })).toBeEnabled();
  });

  test("F-01 starting replay returned ended does not restore End or send it twice T-SES-REC-001", async ({ page, request }) => {
    const { userId, token } = await register(page);
    const startResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" && /\/sessions$/.test(response.url()),
    );
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    const startUrl = (await startResponse).url();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const active = await readRecord(page, userId);
    const sessionId = active?.sessionId as string;
    const ended = await request.post(`${startUrl}/${sessionId}/end`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(ended.ok()).toBeTruthy();
    await page.evaluate((key) => {
      const activeRecord = JSON.parse(sessionStorage.getItem(key) || "{}");
      const { sessionId: _sessionId, ...startingRecord } = activeRecord;
      sessionStorage.setItem(key, JSON.stringify({ ...startingRecord, state: "starting" }));
    }, `jplearn.session:${userId}`);

    let browserEndPosts = 0;
    page.on("request", (req) => {
      if (req.method() === "POST" && /\/sessions\/[^/]+\/end$/.test(req.url())) browserEndPosts += 1;
    });
    await page.reload();
    await expect(page.getByText("Đã kết thúc phiên.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toHaveCount(0);
    expect(await readRecord(page, userId)).toBeNull();
    expect(browserEndPosts).toBe(0);
  });

  test("F-01 replay 401 redirects to login without deleting the user recovery record T-SES-REC-001", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto("/session");
    const starting = {
      v: 1,
      state: "starting",
      idempotencyKey: "persisted-on-401",
      startedAt: "2026-09-06T00:00:00.000Z",
      itemId: SEED_PUBLISHED_ITEM,
      deviceClass: "web",
    };
    await page.evaluate(({ key, record }) => sessionStorage.setItem(key, JSON.stringify(record)), {
      key: `jplearn.session:${userId}`,
      record: starting,
    });
    await page.route(/\/sessions$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ statusCode: 401, message: "Unauthorized" }),
      });
    });

    await page.reload();
    await expect(page).toHaveURL(/\/login\?redirect=%2Fsession/);
    expect(await readRecord(page, userId)).toEqual(starting);
  });

  for (const terminalStatus of [403, 404] as const) {
    test(`F-01 GET ${terminalStatus} clears only the unusable record with an explicit terminal status T-SES-REC-001`, async ({ page }) => {
      const { userId } = await register(page);
      await page.goto("/session");
      await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
      await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
      const active = await readRecord(page, userId);
      await page.route(new RegExp(`/sessions/${active?.sessionId}$`), async (route) => {
        if (route.request().method() === "OPTIONS") return route.continue();
        return route.fulfill({
          status: terminalStatus,
          contentType: "application/json",
          body: JSON.stringify({
            statusCode: terminalStatus,
            message: terminalStatus === 403 ? "Forbidden" : "Session not found",
          }),
        });
      });

      await page.reload();
      await expect(page.getByText(
        terminalStatus === 403
          ? "Bạn không có quyền khôi phục phiên này."
          : "Phiên cần khôi phục không còn tồn tại.",
      )).toBeVisible();
      expect(await readRecord(page, userId)).toBeNull();
      await expect(page.getByRole("button", { name: "Bắt đầu phiên" })).toBeEnabled();
      await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toHaveCount(0);
    });
  }

  test("F-01 late recovery response cannot overwrite state after the user changes T-SES-REC-001", async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const userOne = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const active = await readRecord(page, userOne.userId);
    await page.evaluate((key) => {
      const stored = JSON.parse(sessionStorage.getItem(key) || "{}");
      sessionStorage.setItem(key, JSON.stringify({ ...stored, state: "outcome_unknown" }));
    }, `jplearn.session:${userOne.userId}`);

    let markStatusRequested!: () => void;
    const statusRequested = new Promise<void>((resolve) => { markStatusRequested = resolve; });
    let releaseStatus!: () => void;
    const statusGate = new Promise<void>((resolve) => { releaseStatus = resolve; });
    const statusPattern = new RegExp(`/sessions/${active?.sessionId}$`);
    await page.route(statusPattern, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      markStatusRequested();
      await statusGate;
      await route.continue();
    });
    await page.reload();
    await statusRequested;

    const otherPage = await context.newPage();
    const userTwo = await register(otherPage);
    await page.evaluate(({ token, user }) => {
      localStorage.setItem("jplearn.access_token", token);
      localStorage.setItem("jplearn.user", JSON.stringify(user));
    }, {
      token: userTwo.token,
      user: { id: userTwo.userId, email: userTwo.email, roles: ["learner"] },
    });
    const responseReceived = page.waitForResponse(statusPattern);
    releaseStatus();
    await responseReceived;
    await page.evaluate(() => new Promise<void>((resolve) => setTimeout(resolve, 0)));

    expect((await readRecord(page, userOne.userId))?.state).toBe("outcome_unknown");
    await context.close();
  });

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

  test("F-02 end response lost after commit → GET confirms ended → real summary shown, no second end T-SES-REC-001", async ({ page, request }) => {
    const { userId, token } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const rec = await readRecord(page, userId);
    const sessionId = rec?.sessionId as string;
    await mockEndedDuration(page, sessionId, 125);
    await mockProgress(page, { minutes: 12, level: 2 });

    let endUrl = "";
    await page.route(/\/sessions\/[^/]+\/end$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      endUrl = route.request().url();
      await route.fetch();
      await route.abort("failed");
    });
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Đã kết thúc phiên.")).toBeVisible();
    await expectSummary(page, { duration: "02:05", minutes: 12, level: 2 });
    expect(await readRecord(page, userId)).toBeNull();

    const again = await request.post(endUrl, { headers: { Authorization: `Bearer ${token}` } });
    expect(again.status()).toBe(400);
    const got = await request.get(endUrl.replace(/\/end$/, ""), { headers: { Authorization: `Bearer ${token}` } });
    expect((await got.json()).id).toBe(sessionId);
    expect((await got.json()).ended_at).not.toBeNull();
  });

  test("F-02 progress HTTP 500 after ended confirmation keeps recovery and retry loads summary without second end T-SES-REC-001", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const rec = await readRecord(page, userId);
    const sessionId = rec?.sessionId as string;
    await mockEndedDuration(page, sessionId, 125);

    let endPosts = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && /\/sessions\/[^/]+\/end$/.test(request.url())) endPosts += 1;
    });
    await page.route(/\/sessions\/[^/]+\/end$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      await route.fetch();
      await route.abort("failed");
    });
    const progressPattern = /\/progress$/;
    await page.route(progressPattern, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ statusCode: 500, message: "Injected progress fault" }),
      });
    });

    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByText("Phiên đã kết thúc; chưa tải được tổng kết", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tổng kết phiên học" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Thử tải lại tổng kết" })).toBeEnabled();
    expect(await readRecord(page, userId)).toMatchObject({ state: "outcome_unknown", sessionId });
    expect(endPosts).toBe(1);

    await page.unroute(progressPattern);
    await mockProgress(page, { minutes: 12, level: 2 });
    await page.getByRole("button", { name: "Thử tải lại tổng kết" }).click();
    await expectSummary(page, { duration: "02:05", minutes: 12, level: 2 });
    expect(await readRecord(page, userId)).toBeNull();
    expect(endPosts).toBe(1);
  });

  test("F-02 reload with progress offline keeps ended reference and next reload loads summary without POST end T-SES-REC-001", async ({ page, request }) => {
    const { userId, token } = await register(page);
    const startResponsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && /\/sessions$/.test(response.url()),
    );
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    const startResponse = await startResponsePromise;
    await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
    const rec = await readRecord(page, userId);
    const sessionId = rec?.sessionId as string;
    const ended = await request.post(`${startResponse.url()}/${sessionId}/end`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(ended.ok()).toBeTruthy();
    await page.evaluate((key) => {
      const stored = JSON.parse(sessionStorage.getItem(key) || "{}");
      sessionStorage.setItem(key, JSON.stringify({ ...stored, state: "outcome_unknown" }));
    }, `jplearn.session:${userId}`);
    await mockEndedDuration(page, sessionId, 125);

    let browserEndPosts = 0;
    page.on("request", (browserRequest) => {
      if (
        browserRequest.method() === "POST"
        && /\/sessions\/[^/]+\/end$/.test(browserRequest.url())
      ) browserEndPosts += 1;
    });
    const progressPattern = /\/progress$/;
    await page.route(progressPattern, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      await route.abort("failed");
    });

    await page.reload();
    await expect(page.getByText("Phiên đã kết thúc; chưa tải được tổng kết", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tổng kết phiên học" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Thử tải lại tổng kết" })).toBeEnabled();
    expect(await readRecord(page, userId)).toMatchObject({ state: "outcome_unknown", sessionId });
    expect(browserEndPosts).toBe(0);

    await page.unroute(progressPattern);
    await mockProgress(page, { minutes: 12, level: 2 });
    await page.reload();
    await expectSummary(page, { duration: "02:05", minutes: 12, level: 2 });
    expect(await readRecord(page, userId)).toBeNull();
    expect(browserEndPosts).toBe(0);
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

  test("F-03 recovery persists the chosen default item but never media URLs T-SES-REC-001 T-LRN-001", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.locator("video")).toBeVisible();
    expect((await readRecord(page, userId))?.itemId).toBe(SEED_PUBLISHED_ITEM);
    const raw = await page.evaluate((k) => sessionStorage.getItem(k), `jplearn.session:${userId}`);
    expect(raw).not.toContain("hls_url");
    expect(raw).not.toContain("playback_url");
    expect(raw).not.toContain("sig=");

    const catalogRefetch = page.waitForRequest((r) => r.url().endsWith("/catalog") && r.method() === "GET");
    await page.reload();
    await catalogRefetch;
    await expect(page.locator("video")).toBeVisible();
  });

  test("F-03 legacy session without item persists the first default once T-SES-REC-001 T-LRN-001", async ({ page }) => {
    const { userId } = await register(page);
    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.locator("video")).toBeVisible();

    await page.evaluate((key) => {
      const stored = JSON.parse(sessionStorage.getItem(key) || "{}");
      delete stored.itemId;
      sessionStorage.setItem(key, JSON.stringify(stored));
    }, `jplearn.session:${userId}`);

    await page.reload();
    await expect(page.locator("video")).toBeVisible();
    expect((await readRecord(page, userId))?.itemId).toBe(SEED_PUBLISHED_ITEM);
  });

  test("F-03 MP4 failure refetches a changed real URL and restores paused position T-LRN-001", async ({ page }) => {
    const { userId } = await register(page);
    let catalogGets = 0;
    await page.route(/\/catalog$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      const response = await route.fetch();
      const body = await response.json() as { items: Array<Record<string, unknown>> };
      catalogGets += 1;
      body.items = body.items.map((catalogItem) => (
        catalogItem.id === SEED_PUBLISHED_ITEM
          ? {
            ...catalogItem,
            hls_url: null,
            playback_url: `${catalogItem.playback_url as string}&recovery=${catalogGets === 1 ? "old" : "new"}`,
          }
          : catalogItem
      ));
      await route.fulfill({ response, json: body });
    });

    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    const video = page.locator("video");
    await expect(video).toBeVisible();
    await page.waitForFunction(() => {
      const element = document.querySelector("video");
      return element !== null && element.readyState >= 1;
    });
    const before = await readRecord(page, userId);
    await video.evaluate((element: HTMLVideoElement) => {
      element.pause();
      element.currentTime = 1;
      element.dispatchEvent(new Event("error"));
    });

    await expect.poll(() => catalogGets).toBe(2);
    await page.waitForFunction(() => {
      const element = document.querySelector("video");
      return element !== null
        && element.currentSrc.includes("recovery=new")
        && element.readyState >= 1;
    });
    const playback = await video.evaluate((element: HTMLVideoElement) => ({
      currentTime: element.currentTime,
      paused: element.paused,
      currentSrc: element.currentSrc,
    }));
    expect(playback.currentSrc).toContain("recovery=new");
    expect(playback.currentTime).toBeGreaterThanOrEqual(0.75);
    expect(playback.paused).toBe(true);
    expect((await readRecord(page, userId))?.sessionId).toBe(before?.sessionId);
    expect((await readRecord(page, userId))?.itemId).toBe(SEED_PUBLISHED_ITEM);
  });

  test("F-03 manual retry can choose the default after initial catalog failure T-LRN-001", async ({ page }) => {
    const { userId } = await register(page);
    let catalogGets = 0;
    await page.route(/\/catalog$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      catalogGets += 1;
      if (catalogGets === 1) return route.abort("failed");
      await route.continue();
    });

    await page.goto("/session");
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText("Phiên đang chạy. Chưa tải được nguồn video.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Thử tải lại video" })).toBeEnabled();

    await page.getByRole("button", { name: "Thử tải lại video" }).click();
    await expect.poll(() => catalogGets).toBe(2);
    await expect(page.locator("video")).toBeVisible();
    expect((await readRecord(page, userId))?.itemId).toBe(SEED_PUBLISHED_ITEM);
  });

  test("F-03 dual-source faults use one auto refetch and manual retry starts a new cycle T-LRN-001", async ({ page }) => {
    const { userId } = await register(page);
    let catalogGets = 0;
    let sessionPosts = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && /\/sessions$/.test(request.url())) sessionPosts += 1;
    });
    await page.route(/\/fault\/f03-/, (route) => route.abort("failed"));
    await page.route(/\/catalog$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      const response = await route.fetch();
      const body = await response.json() as { items: Array<Record<string, unknown>> };
      catalogGets += 1;
      if (catalogGets <= 2) {
        const origin = new URL(route.request().url()).origin;
        body.items = body.items.map((catalogItem) => (
          catalogItem.id === SEED_PUBLISHED_ITEM
            ? {
              ...catalogItem,
              hls_url: `${origin}/fault/f03-${catalogGets}.m3u8`,
              playback_url: `${origin}/fault/f03-${catalogGets}.mp4`,
            }
            : catalogItem
        ));
      }
      await route.fulfill({ response, json: body });
    });

    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText("Không thể phát nội dung này.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Thử tải lại video" })).toBeEnabled();
    expect(catalogGets).toBe(2);
    expect(sessionPosts).toBe(1);
    expect((await readRecord(page, userId))?.itemId).toBe(SEED_PUBLISHED_ITEM);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();

    await page.getByRole("button", { name: "Thử tải lại video" }).click();
    await expect.poll(() => catalogGets).toBe(3);
    await page.waitForFunction(() => {
      const element = document.querySelector("video");
      return element !== null && element.readyState >= 1;
    });
    expect(sessionPosts).toBe(1);
  });

  test("F-03 real unpublish keeps target unavailable instead of playing another item T-SES-REC-001 T-LRN-001", async ({ page, request }) => {
    test.setTimeout(120_000);
    const { userId, token: learnerToken } = await register(page);
    const initialCatalog = page.waitForResponse(
      (response) => response.request().method() === "GET" && /\/catalog$/.test(response.url()),
    );
    await page.route(/\/catalog$/, async (route) => {
      if (route.request().method() === "OPTIONS") return route.continue();
      const response = await route.fetch();
      const body = await response.json() as { items: Array<Record<string, unknown>> };
      body.items = body.items.map((catalogItem) => (
        catalogItem.id === SEED_PUBLISHED_ITEM
          ? { ...catalogItem, hls_url: null }
          : catalogItem
      ));
      await route.fulfill({ response, json: body });
    });

    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    const catalogResponse = await initialCatalog;
    await expect(page.locator("video")).toBeVisible();
    const apiRoot = new URL(catalogResponse.url()).origin;

    const adminLogin = await request.post(`${apiRoot}/auth/login`, {
      data: { email: "admin@jplearn.local", password: "password10" },
    });
    expect(adminLogin.ok()).toBeTruthy();
    const adminToken = (await adminLogin.json()).access_token as string;
    const companionId = await createPublishedCompanion(request, apiRoot, adminToken);
    const learnerCatalog = await request.get(`${apiRoot}/catalog`, {
      headers: { Authorization: `Bearer ${learnerToken}` },
    });
    const publishedIds = ((await learnerCatalog.json()).items as Array<{ id: string }>).map((catalogItem) => catalogItem.id);
    expect(publishedIds).toContain(SEED_PUBLISHED_ITEM);
    expect(publishedIds).toContain(companionId);

    const unpublished = await request.post(`${apiRoot}/staff/catalog/${SEED_PUBLISHED_ITEM}/unpublish`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(unpublished.ok()).toBeTruthy();
    await page.locator("video").evaluate((element: HTMLVideoElement) => {
      element.dispatchEvent(new Event("error"));
    });

    await expect(page.getByText("Nội dung này không còn khả dụng.")).toBeVisible();
    await expect(page.locator("video")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
    expect((await readRecord(page, userId))?.itemId).toBe(SEED_PUBLISHED_ITEM);

    await page.reload();
    await expect(page.getByText("Nội dung này không còn khả dụng.")).toBeVisible();
    await expect(page.locator("video")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
    await page.getByRole("button", { name: "Kết thúc phiên" }).click();
    await expect(page.getByRole("heading", { name: "Tổng kết phiên học" })).toBeVisible();

    await page.goto(`/session?item_id=${SEED_PUBLISHED_ITEM}`);
    await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
    await expect(page.getByText("Nội dung này không còn khả dụng.")).toBeVisible();
    await expect(page.locator("video")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();
    expect((await readRecord(page, userId))?.itemId).toBe(SEED_PUBLISHED_ITEM);
  });
});
