import { test, expect } from "@playwright/test";

async function register(page: import("@playwright/test").Page) {
  await page.goto("/login");
  const email = `h${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
}

async function forceHlsJs(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const original = HTMLMediaElement.prototype.canPlayType;
    HTMLMediaElement.prototype.canPlayType = function canPlayType(type: string) {
      if (type === "application/vnd.apple.mpegurl") return "";
      return original.call(this, type);
    };
  });
}

test("phiên phát HLS khi item có hls_url T-NFR-P2", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  await register(page);

  await page.goto("/session");
  const manifestReq = page.waitForRequest(
    (r) => r.url().includes("/hls/index.m3u8"),
    { timeout: 20000 },
  );
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  const video = page.locator("video");
  await expect(video).toBeVisible();

  // CiPlayer ưu tiên hls_url: đợi đúng request tới manifest — tránh race giữa
  // attach nguồn và đọc network (native src cũng có thể là MP4 fallback lúc chờ).
  await manifestReq;
  await page.waitForFunction(
    () => {
      const v = document.querySelector("video");
      return v !== null && v.readyState >= 1;
    },
    undefined,
    { timeout: 20000 },
  );

  const hlsRequests = requests.filter((u) => u.includes("/hls/"));
  expect(
    hlsRequests.some((u) => u.includes("index.m3u8")),
    `mong có request tới index.m3u8, thấy: ${hlsRequests.join(", ") || "(không có)"}`,
  ).toBe(true);
});

test("F-03 HLS lỗi vẫn fallback MP4 mà không refetch catalog T-LRN-001", async ({ page }) => {
  let catalogGets = 0;
  await register(page);
  await page.route(/\/fault\/f03-hls\.m3u8$/, (route) => route.abort("failed"));
  await page.route(/\/catalog$/, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    const response = await route.fetch();
    const body = await response.json() as { items: Array<Record<string, unknown>> };
    catalogGets += 1;
    const origin = new URL(route.request().url()).origin;
    body.items = body.items.map((catalogItem) => ({
      ...catalogItem,
      hls_url: `${origin}/fault/f03-hls.m3u8`,
    }));
    await route.fulfill({ response, json: body });
  });

  await page.goto("/session");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await page.waitForFunction(() => {
    const element = document.querySelector("video");
    return element !== null
      && element.readyState >= 1
      && element.currentSrc.includes("/media/")
      && !element.currentSrc.includes("/fault/");
  });
  expect(catalogGets).toBe(1);
  await expect(page.getByText("Không thể phát nội dung này.")).toHaveCount(0);
});

test("F-03 đổi URL HLS cùng item khôi phục vị trí pause T-LRN-001", async ({ page }) => {
  let catalogGets = 0;
  await forceHlsJs(page);
  await register(page);
  await page.route(/\/catalog$/, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    const response = await route.fetch();
    const body = await response.json() as { items: Array<Record<string, unknown>> };
    catalogGets += 1;
    if (catalogGets === 2) {
      await page.locator("video").evaluate((element: HTMLVideoElement) => {
        element.currentTime = 0;
      });
      await page.waitForFunction(() => {
        const element = document.querySelector("video");
        return element !== null && !element.seeking && element.currentTime < 0.1;
      });
    }
    body.items = body.items.map((catalogItem) => ({
      ...catalogItem,
      hls_url: `${catalogItem.hls_url as string}&recovery=${catalogGets === 1 ? "old" : "new"}`,
      playback_url: null,
    }));
    await route.fulfill({ response, json: body });
  });

  await page.goto("/session");
  const oldManifest = page.waitForRequest(
    (request) => request.url().includes("/hls/index.m3u8") && request.url().includes("recovery=old"),
  );
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  await oldManifest;
  const video = page.locator("video");
  await page.waitForFunction(() => {
    const element = document.querySelector("video");
    return element !== null && element.readyState >= 1;
  });
  await video.evaluate((element: HTMLVideoElement) => {
    element.pause();
    element.currentTime = 1;
  });
  await page.waitForFunction(() => {
    const element = document.querySelector("video");
    return element !== null && !element.seeking && element.currentTime >= 0.75;
  });

  const newManifest = page.waitForRequest(
    (request) => request.url().includes("/hls/index.m3u8") && request.url().includes("recovery=new"),
  );
  await video.evaluate((element: HTMLVideoElement) => {
    element.dispatchEvent(new Event("error"));
  });
  await newManifest;
  await expect.poll(() => catalogGets).toBe(2);
  await page.waitForFunction(() => {
    const element = document.querySelector("video");
    return element !== null && element.readyState >= 1 && element.currentTime >= 0.75;
  });
  expect(await video.evaluate((element: HTMLVideoElement) => element.paused)).toBe(true);
});

test("F-03 HLS fallback lấy trạng thái play tại lúc fallback T-LRN-001", async ({ page }) => {
  let catalogGets = 0;
  await forceHlsJs(page);
  await register(page);
  await page.route(/\/catalog$/, async (route) => {
    if (route.request().method() === "OPTIONS") return route.continue();
    catalogGets += 1;
    await route.continue();
  });

  await page.goto("/session");
  await page.getByRole("button", { name: "Bắt đầu phiên" }).click();
  const video = page.locator("video");
  await page.waitForFunction(() => {
    const element = document.querySelector("video");
    return element !== null && element.readyState >= 1;
  });
  await video.evaluate(async (element: HTMLVideoElement) => {
    element.muted = true;
    await element.play();
  });
  await expect.poll(
    () => video.evaluate((element: HTMLVideoElement) => element.paused),
  ).toBe(false);

  await video.evaluate((element: HTMLVideoElement) => {
    element.dispatchEvent(new Event("error"));
  });
  await page.waitForFunction(() => {
    const element = document.querySelector("video");
    return element !== null
      && element.readyState >= 1
      && element.currentSrc.includes("/media/")
      && !element.currentSrc.startsWith("blob:");
  });
  await expect.poll(
    () => video.evaluate((element: HTMLVideoElement) => element.paused),
  ).toBe(false);
  expect(catalogGets).toBe(1);
});
