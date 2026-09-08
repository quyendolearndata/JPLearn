import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

function stockMp4(): string {
  const candidates = [
    path.resolve(__dirname, "../../../media/stock/mp4/level-0-wash-hands.mp4"),
    path.resolve(process.cwd(), "../../media/stock/mp4/level-0-wash-hands.mp4"),
  ];
  const hit = candidates.find((c) => fs.existsSync(c));
  if (!hit) throw new Error("stock mp4 missing");
  return hit;
}

async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page).toHaveURL("/");
}
async function register(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(`l${Date.now()}${Math.floor(Math.random() * 1e4)}@example.com`);
  await page.getByLabel("Mật khẩu").fill("password10");
  await page.getByRole("button", { name: "Đăng ký" }).click();
  await expect(page).toHaveURL("/");
}
async function createDraft(page: Page, title: string): Promise<string> {
  await page.goto("/staff/new");
  await page.getByLabel(/Tiêu đề nội bộ/i).fill(title);
  await page.getByLabel(/Thời lượng/i).fill("30");
  await page.getByRole("button", { name: "Tạo bản nháp bài học" }).click();
  await expect(page).toHaveURL(/\/staff\/[0-9a-f-]+/);
  return page.url().split("/staff/")[1].split("?")[0];
}

test.describe("Staff CMS T-CMS-E2E-001", () => {
  test("teacher drafts+uploads+submits (no publish button); admin publishes; learner sees; admin unpublishes — each step survives reload", async ({ browser }) => {
    test.setTimeout(180_000);
    const title = `E2E handoff ${Date.now()}`;

    const learnerCtx = await browser.newContext();
    const learner = await learnerCtx.newPage();
    await register(learner);
    await learner.goto("/staff");
    await expect(learner.getByRole("heading", { name: "Không có quyền truy cập" })).toBeVisible();

    const teacherCtx = await browser.newContext();
    const teacher = await teacherCtx.newPage();
    await login(teacher, "teacher@e2e.local");
    const itemId = await createDraft(teacher, title);
    await teacher.reload();
    await expect(teacher.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();
    await expect(teacher.getByLabel(/Tiêu đề nội bộ/i)).toHaveValue(title);

    await teacher.locator("input#upload").setInputFiles(stockMp4());
    await teacher.getByRole("button", { name: "Tải lên tệp MP4", exact: true }).click();
    await expect(teacher.getByText("Tải tệp media lên thành công!")).toBeVisible();
    await teacher.reload();
    await teacher.getByRole("button", { name: "Nộp kiểm định QA" }).click();
    await expect(teacher.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
    await teacher.reload();
    await expect(teacher.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
    await expect(teacher.getByRole("button", { name: "Xuất bản bài học" })).toHaveCount(0);
    await teacherCtx.close();

    await learner.goto("/catalog");
    await expect(learner.locator(`[data-item-id="${itemId}"]`)).toHaveCount(0);

    const adminCtx = await browser.newContext();
    const admin = await adminCtx.newPage();
    await login(admin, "admin@jplearn.local");
    await admin.goto("/staff");
    await expect(admin.getByRole("heading", { name: "Quản trị nội dung CI" })).toBeVisible();
    await admin.goto(`/staff/${itemId}`);
    await admin.getByRole("button", { name: "Duyệt QA", exact: true }).click();
    await expect(admin.getByText("Đã ghi nhận duyệt QA.", { exact: true })).toBeVisible();
    await admin.reload();
    await admin.getByRole("button", { name: "Xuất bản bài học" }).click();
    await expect(admin.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();
    await admin.reload();
    await expect(admin.getByText("Đã xuất bản (published)", { exact: true })).toBeVisible();

    await learner.goto("/catalog");
    await expect(learner.locator(`[data-item-id="${itemId}"]`)).toBeVisible();
    await expect(learner.getByText(title)).toHaveCount(0);

    await admin.getByRole("button", { name: "Gỡ xuất bản (Về nháp)" }).click();
    await expect(admin.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();
    await learner.goto("/catalog");
    await expect(learner.locator(`[data-item-id="${itemId}"]`)).toHaveCount(0);

    await adminCtx.close();
    await learnerCtx.close();
  });

  test("publish without media is refused and status stays level_qa", async ({ page }) => {
    await login(page, "admin@jplearn.local");
    await createDraft(page, `no-media ${Date.now()}`);
    await page.getByRole("button", { name: "Nộp kiểm định QA" }).click();
    await expect(page.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Xuất bản bài học" }).click();
    await expect(page.getByText(/Cannot publish without media/)).toBeVisible();
    await expect(page.getByText("Đã xuất bản (published)", { exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByText("Chờ kiểm duyệt QA (level_qa)", { exact: true })).toBeVisible();
  });

  test("upload failure keeps the draft and shows an error", async ({ page }) => {
    await login(page, "admin@jplearn.local");
    await createDraft(page, `upload-fail ${Date.now()}`);
    await page.route(/\/staff\/catalog\/[^/]+\/media$/, (route) =>
      route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "storage unavailable" }) }),
    );
    await page.locator("input#upload").setInputFiles(stockMp4());
    await page.getByRole("button", { name: "Tải lên tệp MP4", exact: true }).click();
    await expect(page.getByText("storage unavailable")).toBeVisible();
    await expect(page.getByText("Bản nháp (draft)", { exact: true })).toBeVisible();
  });

  test("stale revision → 409 → reload button loads the winner", async ({ browser }) => {
    const ctx = await browser.newContext();
    const p1 = await ctx.newPage();
    await login(p1, "admin@jplearn.local");
    const itemId = await createDraft(p1, `stale ${Date.now()}`);
    const p2 = await ctx.newPage();
    await p2.goto(`/staff/${itemId}`);
    await p2.getByLabel(/Tiêu đề nội bộ/i).fill("winner title");
    await p2.getByRole("button", { name: /Lưu thay đổi/ }).click();
    await expect(p2.getByText(/Đã lưu thay đổi thành công \(Phiên bản v2\)/)).toBeVisible();

    await p1.getByLabel(/Tiêu đề nội bộ/i).fill("loser title");
    await p1.getByRole("button", { name: /Lưu thay đổi/ }).click();
    await expect(p1.getByText(/Xung đột phiên bản/)).toBeVisible();
    await p1.getByRole("button", { name: "Tải lại dữ liệu" }).click();
    await expect(p1.getByLabel(/Tiêu đề nội bộ/i)).toHaveValue("winner title");
    await ctx.close();
  });

  test("client-side validation rejects non-mp4 in both staff forms", async ({ page }) => {
    await login(page, "admin@jplearn.local");
    await page.goto("/staff/new");
    await page.locator("input#mediaFile").setInputFiles({ name: "x.txt", mimeType: "text/plain", buffer: Buffer.from("t") });
    await expect(page.getByText("Chỉ chấp nhận tệp video định dạng MP4 (.mp4).")).toBeVisible();
    await expect(page.locator("input#mediaFile")).toHaveAttribute("accept", "video/mp4");
    await expect(page.locator('select option[value="audio"]')).toBeDisabled();
  });
});
