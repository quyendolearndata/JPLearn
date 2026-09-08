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
  await expect(page.locator(".progress-label")).toHaveText("Phút CI tích lũy");
  await expectNoBannedChrome(page);
});

test("catalog shows published seed item, hides draft T-CAT-002 T-FLG-002", async ({ page }) => {
  await register(page);
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "Catalog" })).toBeVisible();
  const seed = page.locator('[data-item-id="00000000-0000-4000-8000-0000000000c1"]');
  await expect(seed).toBeVisible();
  await expect(seed.getByRole("heading")).toHaveText("Đời sống hàng ngày");
  await expect(seed.getByText("30 giây")).toBeVisible();
  await expect(page.locator('[data-item-id="00000000-0000-4000-8000-0000000000d1"]')).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Tìm chủ đề" }).fill("chủ đề không tồn tại");
  await expect(seed).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Tìm chủ đề" }).fill("");
  await expect(seed).toBeVisible();
  await expectNoBannedChrome(page);
});

test("banned chrome stays absent even when server flags are on T-FLG-002 T-NEG-002", async ({ page, request }) => {
  const registerResponse = page.waitForResponse(
    (response) => response.request().method() === "POST" && /\/auth\/register$/.test(response.url()),
  );
  await register(page);
  const apiRoot = new URL((await registerResponse).url()).origin;

  const adminLogin = await request.post(`${apiRoot}/auth/login`, {
    data: { email: "admin@jplearn.local", password: "password10" },
  });
  expect(adminLogin.ok()).toBeTruthy();
  const adminToken = (await adminLogin.json()).access_token as string;
  const headers = { Authorization: `Bearer ${adminToken}` };

  try {
    const enabled = await request.patch(`${apiRoot}/staff/flags`, {
      headers,
      data: {
        grammar_enabled: true,
        flashcards_enabled: true,
        l1_subtitles_enabled: true,
        speaking_enabled: true,
      },
    });
    expect(enabled.ok()).toBeTruthy();

    const flagsResponse = page.waitForResponse(
      (response) => response.request().method() === "GET" && /\/flags$/.test(response.url()),
    );
    await page.reload();
    const flags = await flagsResponse;
    expect(flags.ok()).toBeTruthy();
    expect(await flags.json()).toMatchObject({
      grammar_enabled: true,
      flashcards_enabled: true,
      l1_subtitles_enabled: true,
      speaking_enabled: true,
    });
    await page.goto("/catalog");
    await expectNoBannedChrome(page);
    await expect(page.getByRole("link", { name: "Nói", exact: true })).toHaveCount(0);
  } finally {
    const restored = await request.patch(`${apiRoot}/staff/flags`, {
      headers,
      data: {
        grammar_enabled: false,
        flashcards_enabled: false,
        l1_subtitles_enabled: false,
        speaking_enabled: false,
      },
    });
    expect(restored.ok()).toBeTruthy();
  }
});
