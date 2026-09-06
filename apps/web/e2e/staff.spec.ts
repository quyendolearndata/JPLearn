import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

function getTestMp4Path(): string {
  const candidates = [
    path.resolve(__dirname, "../../../media/stock/mp4/level-0-wash-hands.mp4"),
    path.resolve(process.cwd(), "../../media/stock/mp4/level-0-wash-hands.mp4"),
    path.resolve(process.cwd(), "media/stock/mp4/level-0-wash-hands.mp4"),
    "/Users/quyendo/Documents/Learn/JPLearn/media/stock/mp4/level-0-wash-hands.mp4",
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error("Could not find test MP4 file");
}

test.describe("Staff CMS E2E Lifecycle & RBAC (T-CMS-E2E-001)", () => {
  const uniqueId = Date.now();
  const learnerEmail = `learner-staff-${uniqueId}@example.com`;
  const draftTitle = `E2E CI Clip ${uniqueId}`;

  test("learner is forbidden, admin manages full draft -> qa -> publish -> unpublish lifecycle", async ({
    browser,
  }) => {
    test.setTimeout(180_000);
    const baseUrl = process.env.PLAYWRIGHT_TEST_BASE_URL ?? "http://localhost:3000";

    // -------------------------------------------------------------
    // 1. Learner registration & RBAC check
    // -------------------------------------------------------------
    const learnerCtx = await browser.newContext({ baseURL: baseUrl });
    const learnerPage = await learnerCtx.newPage();

    await learnerPage.goto("/login");
    await learnerPage.getByLabel("Email").fill(learnerEmail);
    await learnerPage.getByLabel("Mật khẩu").fill("password10");
    await learnerPage.getByRole("button", { name: "Đăng ký" }).click();
    await expect(learnerPage).toHaveURL("/");

    // Learner tries visiting /staff -> must see 403 / "Không có quyền truy cập"
    await learnerPage.goto("/staff");
    await expect(learnerPage.getByRole("heading", { name: "Không có quyền truy cập" })).toBeVisible();

    // -------------------------------------------------------------
    // 2. Admin logs in & accesses /staff
    // -------------------------------------------------------------
    const adminCtx = await browser.newContext({ baseURL: baseUrl });
    const adminPage = await adminCtx.newPage();

    await adminPage.goto("/login");
    await adminPage.getByLabel("Email").fill("admin@jplearn.local");
    await adminPage.getByLabel("Mật khẩu").fill("password10");
    await adminPage.getByRole("button", { name: "Đăng nhập" }).click();
    await expect(adminPage).toHaveURL("/");

    await adminPage.goto("/staff");
    await expect(adminPage.getByRole("heading", { name: "Quản trị nội dung CI" })).toBeVisible();

    // -------------------------------------------------------------
    // 3. Admin creates new draft catalog item
    // -------------------------------------------------------------
    await adminPage.getByRole("link", { name: "+ Tạo bài học mới" }).click();
    await expect(adminPage).toHaveURL("/staff/new");
    await expect(adminPage.getByRole("heading", { name: "Tạo bài học mới (Bản nháp)" })).toBeVisible();

    await adminPage.getByLabel(/Tiêu đề nội bộ/i).fill(draftTitle);
    await adminPage.getByLabel(/Thời lượng/i).fill("30");
    await adminPage.getByRole("button", { name: "Tạo bản nháp bài học" }).click();

    // Navigates to /staff/[id]
    await expect(adminPage).toHaveURL(/\/staff\/[0-9a-f-]+/);
    const itemId = adminPage.url().split("/staff/")[1].split("?")[0];
    await expect(adminPage.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();

    // -------------------------------------------------------------
    // 4. Learner verifies catalog does NOT show draft item
    // -------------------------------------------------------------
    await learnerPage.goto("/catalog");
    await expect(learnerPage.locator(`a[href*="${itemId}"]`)).toHaveCount(0);

    // -------------------------------------------------------------
    // 5. Admin uploads MP4 media
    // -------------------------------------------------------------
    const mp4Path = getTestMp4Path();
    await adminPage.locator("input#upload").setInputFiles(mp4Path);
    await adminPage.getByRole("button", { name: "Tải lên tệp MP4", exact: true }).click();
    await expect(adminPage.getByText("Tải tệp media lên thành công!")).toBeVisible();

    // -------------------------------------------------------------
    // 6. Admin submits for QA
    // -------------------------------------------------------------
    await adminPage.getByRole("button", { name: "Nộp kiểm định QA" }).click();
    await expect(adminPage.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();

    // Learner still cannot see item in catalog
    await learnerPage.goto("/catalog");
    await expect(learnerPage.locator(`a[href*="${itemId}"]`)).toHaveCount(0);

    // -------------------------------------------------------------
    // 7. Admin publishes the item
    // -------------------------------------------------------------
    await adminPage.getByRole("button", { name: "Xuất bản bài học" }).click();
    await expect(adminPage.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();

    // -------------------------------------------------------------
    // 8. Learner verifies catalog NOW shows the published item!
    // -------------------------------------------------------------
    await learnerPage.goto("/catalog");
    await expect(learnerPage.locator(`a[href*="${itemId}"]`)).toBeVisible();

    // -------------------------------------------------------------
    // 9. Admin unpublishes the item
    // -------------------------------------------------------------
    await adminPage.getByRole("button", { name: "Gỡ xuất bản (Về nháp)" }).click();
    await expect(adminPage.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();

    // -------------------------------------------------------------
    // 10. Learner verifies catalog no longer shows unpublished item
    // -------------------------------------------------------------
    await learnerPage.goto("/catalog");
    await expect(learnerPage.locator(`a[href*="${itemId}"]`)).toHaveCount(0);

    await learnerCtx.close();
    await adminCtx.close();
  });

  test("client-side validation rejects non-mp4 file in staff upload", async ({ browser }) => {
    const baseUrl = process.env.PLAYWRIGHT_TEST_BASE_URL ?? "http://localhost:3000";
    const ctx = await browser.newContext({ baseURL: baseUrl });
    const page = await ctx.newPage();

    // Login as admin
    await page.goto("/login");
    await page.getByLabel("Email").fill("admin@jplearn.local");
    await page.getByLabel("Mật khẩu").fill("password10");
    await page.getByRole("button", { name: "Đăng nhập" }).click();
    await expect(page).toHaveURL("/");

    // Visit /staff/new and attempt to select a non-mp4 file
    await page.goto("/staff/new");
    await expect(page.getByRole("heading", { name: "Tạo bài học mới (Bản nháp)" })).toBeVisible();
    await page.locator("input#mediaFile").setInputFiles({
      name: "invalid-file.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("plain text content"),
    });

    // Error alert must appear
    await expect(page.getByText("Chỉ chấp nhận tệp video định dạng MP4 (.mp4).")).toBeVisible();

    await ctx.close();
  });
});
