import { test, expect, type Page, type TestInfo } from "@playwright/test";
import { injectAxe, checkA11y } from "axe-playwright";

const LEARNER_PAGES: { path: string; title: string; ready: (page: Page) => Promise<void> }[] = [
  {
    path: "/",
    title: "JPLearn — Catalog",
    ready: async (p) => p.getByRole("heading", { level: 1 }).waitFor(),
  },
  {
    path: "/login",
    title: "JPLearn — Đăng nhập",
    ready: async (p) => p.getByRole("button", { name: "Đăng ký" }).waitFor(),
  },
  {
    path: "/catalog",
    title: "JPLearn — Catalog",
    ready: async (p) => p.getByRole("heading", { name: "Catalog" }).waitFor(),
  },
  {
    path: "/session",
    title: "JPLearn — Phiên học",
    ready: async (p) => p.getByRole("heading", { name: "Phiên" }).waitFor(),
  },
  {
    path: "/progress",
    title: "JPLearn — Tiến độ",
    ready: async (p) => p.getByText(/phút/i).waitFor(),
  },
];

const STAFF_PAGES: { path: string; title: string; ready: (page: Page) => Promise<void> }[] = [
  {
    path: "/staff",
    title: "JPLearn — Staff CMS",
    ready: async (p) => p.getByRole("heading", { name: "Quản trị nội dung CI" }).waitFor(),
  },
  {
    path: "/staff/new",
    title: "JPLearn — Staff CMS",
    ready: async (p) => p.getByRole("heading", { name: "Tạo bài học mới (Bản nháp)" }).waitFor(),
  },
];

async function register(page: Page) {
  await page.goto("/login");
  const email = `a${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
}

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@jplearn.local");
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page).toHaveURL("/");
}

test("chrome learner đạt contrast AA + mọi route có document title T-NFR-A1", async ({ page }) => {
  await register(page);
  for (const { path, title, ready } of LEARNER_PAGES) {
    await page.goto(path);
    await ready(page);
    // NFR-A11Y-001 (#36): mọi route learner phải có document title có ý nghĩa.
    await expect(page).toHaveTitle(title);
    await page.evaluate(() => document.fonts.ready);
    await injectAxe(page);
    // Rule thuộc card #34 (contrast, WCAG AA) + #36 (document-title).
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: false },
    });
  }
});

test("chrome staff CMS đạt contrast AA + mọi route có document title T-NFR-A1", async ({ page }) => {
  await loginAdmin(page);
  for (const { path, title, ready } of STAFF_PAGES) {
    await page.goto(path);
    await ready(page);
    await expect(page).toHaveTitle(title);
    await page.evaluate(() => document.fonts.ready);
    await injectAxe(page);
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: { html: false },
    });
  }
});

test("axe: error state on login, active session state, staff detail route T-NFR-A1", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("bad");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.locator("p.status-error")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });

  await register(page);
  await page.goto("/session?item_id=00000000-0000-4000-8000-0000000000c1");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await expect(page.locator("video")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });
  await page.getByRole("button", { name: "Kết thúc phiên" }).click();
  await expect(page.getByText("Tổng kết phiên học")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });

  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await expect(page.getByRole("button", { name: "Đăng nhập" })).toBeVisible();
  await loginAdmin(page);
  await page.goto("/staff/00000000-0000-4000-8000-0000000000c1");
  await expect(page.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await injectAxe(page);
  await checkA11y(page, undefined, { detailedReport: true, detailedReportOptions: { html: false } });
});

async function waitForSessionVideo(page: Page) {
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await expect(video).toHaveAttribute("controls", "");
  await page.waitForFunction(() => {
    const element = document.querySelector("video");
    return Boolean(
      element
      && element.readyState >= 1
      && Number.isFinite(element.duration)
      && element.duration > 0,
    );
  }, undefined, { timeout: 20000 });
  return video;
}

async function focusedControlLabel(page: Page) {
  return page.evaluate(() => {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement)) return "";
    return (active.getAttribute("aria-label") || active.textContent || "").trim();
  });
}

async function describeFocus(page: Page) {
  return page.evaluate(() => {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement)) return "(none)";
    const label = (active.getAttribute("aria-label") || active.textContent || "").trim();
    return `${active.tagName.toLowerCase()}:${label.slice(0, 80)}`;
  });
}

async function focusControlByTab(
  page: Page,
  labels: string[],
  testInfo: TestInfo,
  maxTabs = 24,
) {
  const reached = async () => labels.includes(await focusedControlLabel(page));
  await page.getByRole("link", { name: "Catalog" }).focus();
  for (let i = 0; i < maxTabs; i += 1) {
    if (await reached()) return "tab-from-catalog";
    await page.keyboard.press("Tab");
  }

  // WebKit Playwright often traps Tab inside native media chrome (same class of
  // issue as the login password-manager widget). Walk backward from End.
  // Scripted getByRole(...).focus() on Phát/Tạm dừng is not a PASS path.
  await page.getByRole("button", { name: "Kết thúc phiên" }).focus();
  for (let i = 0; i < maxTabs; i += 1) {
    if (await reached()) return "shift-tab-from-end";
    await page.keyboard.press("Shift+Tab");
  }

  const lastFocus = await describeFocus(page);
  testInfo.annotations.push({
    type: "f04-play-focus-path",
    description: `${testInfo.project.name}: fail; lastFocus=${lastFocus}`,
  });
  throw new Error(
    `${testInfo.project.name}: Tab/Shift+Tab never reached ${labels.join(" / ")}; last focus ${lastFocus}`,
  );
}

test("keyboard: login form tab order and Enter-to-submit; player controls reachable T-NFR-A1", async ({ page }, testInfo) => {
  await page.goto("/login");
  const formOrder = await page.locator("main input, main button").evaluateAll((els) =>
    els.map((el) => {
      if (el instanceof HTMLInputElement) {
        const label = document.querySelector(`label[for="${el.id}"]`);
        return (label?.textContent || el.id).trim();
      }
      return (el.textContent || "").trim();
    }),
  );
  expect(formOrder).toEqual(["Email", "Mật khẩu", "Đăng nhập", "Đăng ký"]);

  await page.getByLabel("Email").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Mật khẩu")).toBeFocused();
  // Playwright WebKit does not deliver Tab past the password field the same way
  // Chromium does (password-manager widget). Chromium covers the full CTA walk.
  if (testInfo.project.name === "chromium") {
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Đăng nhập" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Đăng ký" })).toBeFocused();
  }
  await page.getByLabel("Email").fill(`k${Date.now()}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/");

  await page.goto("/session?item_id=00000000-0000-4000-8000-0000000000c1");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).focus();
  await page.keyboard.press("Enter");
  const video = await waitForSessionVideo(page);

  // F-04: do not treat video.focus() or scripted play() as the measured action.
  // Native media keys are not a PASS path — Playwright does not deliver them
  // reliably on Chromium/WebKit. Require a named keyboard affordance instead.
  const nativePausedBefore = await video.evaluate((element: HTMLVideoElement) => element.paused);
  await page.getByRole("link", { name: "Catalog" }).focus();
  let reachedNativeVideo = false;
  for (let i = 0; i < 24; i += 1) {
    reachedNativeVideo = await page.evaluate(() => document.activeElement?.tagName === "VIDEO");
    if (reachedNativeVideo) break;
    await page.keyboard.press("Tab");
  }
  if (reachedNativeVideo) {
    await page.keyboard.press("Space");
  }
  const nativePausedAfter = await video.evaluate((element: HTMLVideoElement) => element.paused);
  testInfo.annotations.push({
    type: "f04-native-media-keys",
    description: `${testInfo.project.name}: tab-to-video=${reachedNativeVideo}; spaceChangedPaused=${nativePausedBefore !== nativePausedAfter}`,
  });
  await video.evaluate((element: HTMLVideoElement) => {
    element.pause();
    element.currentTime = 0;
  });

  const playButton = page.getByRole("button", { name: "Phát" });
  await expect(playButton).toBeVisible();
  const playFocusPath = await focusControlByTab(page, ["Phát", "Tạm dừng"], testInfo);
  testInfo.annotations.push({
    type: "f04-play-focus-path",
    description: `${testInfo.project.name}: ${playFocusPath}`,
  });
  await expect(playButton).toBeFocused();

  const beforePlay = await video.evaluate((element: HTMLVideoElement) => ({
    paused: element.paused,
    currentTime: element.currentTime,
  }));
  expect(beforePlay.paused).toBe(true);
  await page.keyboard.press("Space");
  await expect.poll(
    async () => video.evaluate((element: HTMLVideoElement) => element.paused),
    { timeout: 15000 },
  ).toBe(false);
  await expect.poll(
    async () => video.evaluate((element: HTMLVideoElement) => element.currentTime),
    { timeout: 15000 },
  ).toBeGreaterThan(beforePlay.currentTime);

  const pauseButton = page.getByRole("button", { name: "Tạm dừng" });
  await expect(pauseButton).toBeVisible();
  const pauseFocusPath = (await focusedControlLabel(page)) === "Tạm dừng"
    ? "stayed-on-control"
    : await focusControlByTab(page, ["Tạm dừng", "Phát"], testInfo);
  testInfo.annotations.push({
    type: "f04-pause-focus-path",
    description: `${testInfo.project.name}: ${pauseFocusPath}`,
  });
  await expect(pauseButton).toBeFocused();
  await page.keyboard.press("Space");
  await expect.poll(
    async () => video.evaluate((element: HTMLVideoElement) => element.paused),
    { timeout: 15000 },
  ).toBe(true);

  console.log(`[F-04] ${testInfo.project.name} ${JSON.stringify(testInfo.annotations)}`);
});

test("F-04 recovery and summary errors expose role=alert T-NFR-A1", async ({ page }) => {
  await register(page);
  await page.goto("/session?item_id=00000000-0000-4000-8000-0000000000c1");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await expect(page.getByText(/Phiên đang chạy/)).toBeVisible();
  const sessionId = await page.evaluate(() => {
    const user = JSON.parse(localStorage.getItem("jplearn.user") || "{}") as { id?: string };
    const raw = user.id ? sessionStorage.getItem(`jplearn.session:${user.id}`) : null;
    return raw ? (JSON.parse(raw) as { sessionId?: string }).sessionId : null;
  });
  expect(sessionId).toBeTruthy();

  const statusPattern = new RegExp(`/sessions/${sessionId}$`);
  await page.route(statusPattern, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    return route.abort("failed");
  });
  await page.reload();
  await expect(page.getByRole("button", { name: "Thử khôi phục lại" })).toBeVisible();
  await page.unroute(statusPattern);

  await expect(page.getByRole("alert").filter({
    hasText: "Chưa xác nhận được trạng thái phiên với máy chủ.",
  })).toBeVisible();

  await page.getByRole("button", { name: "Thử khôi phục lại" }).click();
  await expect(page.getByRole("button", { name: "Kết thúc phiên" })).toBeEnabled();

  await page.route(/\/sessions\/[^/]+\/end$/, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    await route.fetch();
    await route.abort("failed");
  });
  await page.route(/\/progress$/, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ statusCode: 500, message: "Injected progress fault" }),
    });
  });
  await page.getByRole("button", { name: "Kết thúc phiên" }).click();
  await expect(page.getByRole("alert").filter({
    hasText: "Phiên đã kết thúc; chưa tải được tổng kết",
  })).toBeVisible();
});
