import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { PrismaClient } from "@prisma/client";

jest.setTimeout(120_000);

const C1 = "00000000-0000-4000-8000-0000000000c1";
const D1 = "00000000-0000-4000-8000-0000000000d1";
const apiRoot = join(__dirname, "..");
const tsxBin = join(apiRoot, "node_modules", ".bin", "tsx");

// Chạy seed qua đúng entrypoint vận hành (`prisma db seed` → tsx prisma/seed.ts),
// thừa kế DATABASE_URL của embedded postgres mà test-env.cjs đã set.
function runSeed() {
  execFileSync(tsxBin, ["prisma/seed.ts"], {
    cwd: apiRoot,
    env: process.env,
    stdio: "pipe",
  });
}

describe("seed idempotency (FR-CAT-002)", () => {
  const prisma = new PrismaClient();

  beforeAll(async () => {
    // Embedded postgres persistent qua các lần chạy: dọn 2 item seed để mọi
    // lần chạy test đều bắt đầu từ trạng thái chưa seed.
    await prisma.catalogItem.deleteMany({ where: { id: { in: [C1, D1] } } });
  });

  afterAll(async () => {
    await prisma.catalogItem.updateMany({
      where: { id: { in: [C1, D1] } },
      data: { status: "draft" },
    });
    await prisma.$disconnect();
  });

  it("two consecutive runs are idempotent and leave no published seed item without media", async () => {
    runSeed();
    runSeed();

    const c1 = await prisma.catalogItem.findUniqueOrThrow({
      where: { id: C1 },
      include: { media: true },
    });
    expect(c1.status).toBe("draft");
    expect(c1.media).toHaveLength(0);

    const seededPublished = await prisma.catalogItem.findMany({
      where: { status: "published", titleInternal: { startsWith: "seed-" } },
      include: { media: true },
    });
    for (const item of seededPublished) {
      expect(item.media.length).toBeGreaterThan(0);
    }
  });

  it("never overrides item status on reseed (regression guard for update.status)", async () => {
    runSeed();
    // Mô phỏng quyết định vận hành sau seed (#35 unpublish, QA archive...):
    // reseed không được đè ngược các trạng thái này.
    await prisma.catalogItem.update({ where: { id: C1 }, data: { status: "archived" } });
    await prisma.catalogItem.update({ where: { id: D1 }, data: { status: "level_qa" } });

    runSeed();

    await expect(
      prisma.catalogItem.findUniqueOrThrow({ where: { id: C1 } }),
    ).resolves.toMatchObject({ status: "archived" });
    await expect(
      prisma.catalogItem.findUniqueOrThrow({ where: { id: D1 } }),
    ).resolves.toMatchObject({ status: "level_qa" });
  });
});
