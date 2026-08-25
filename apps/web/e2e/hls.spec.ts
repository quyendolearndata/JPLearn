import { test, expect } from "@playwright/test";

test("phiên phát HLS khi item có hls_url T-NFR-P2", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));

  await page.goto("/login");
  const email = `h${Date.now()}${Math.floor(Math.random() * 1000)}@example.com`;
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");

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
