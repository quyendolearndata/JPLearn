import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { loginAdmin, register } from "./helpers";
import argon2 from "argon2";

jest.setTimeout(120_000);

describe("catalog CMS and public list", () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const module = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = module.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);
    await prisma.topic.createMany({
      data: [
        "daily_home", "food", "body", "go_somewhere", "nature", "people",
      ].map((id) => ({ id, labelInternal: id })),
      skipDuplicates: true,
    });
    const passwordHash = await argon2.hash("password10");
    await prisma.user.upsert({
      where: { email: "admin@jplearn.local" },
      create: {
        email: "admin@jplearn.local",
        passwordHash,
        roles: { create: [{ role: "admin" }, { role: "teacher" }] },
      },
      update: {
        passwordHash,
      },
    });
    const admin = await prisma.user.findUniqueOrThrow({ where: { email: "admin@jplearn.local" } });
    await prisma.userRole.upsert({
      where: { userId_role: { userId: admin.id, role: "admin" } },
      create: { userId: admin.id, role: "admin" },
      update: {},
    });
    await prisma.userRole.upsert({
      where: { userId_role: { userId: admin.id, role: "teacher" } },
      create: { userId: admin.id, role: "teacher" },
      update: {},
    });
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  it("hides drafts and publishes QA items without internal or L1 fields", async () => {
    const learnerTok = (await register(app, `c${Date.now()}@example.com`)).body.access_token;
    const adminTok = await loginAdmin(app);
    const created = await request(app.getHttpServer())
      .post("/staff/catalog")
      .set("Authorization", `Bearer ${adminTok}`)
      .send({
        topic_id: "daily_home", ci_level: 0, duration_seconds: 30,
        media_type: "video", visual_support: "high", title_internal: "pour water",
      })
      .expect(201);
    expect(created.body.has_l1_translation).toBe(false);
    expect(created.body.status).toBe("draft");

    await request(app.getHttpServer()).get("/catalog")
      .set("Authorization", `Bearer ${learnerTok}`).expect(200)
      .then((res) => expect(res.body.items.some((item: { id: string }) => item.id === created.body.id)).toBe(false));

    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/media`)
      .set("Authorization", `Bearer ${adminTok}`)
      .attach("file", Buffer.from("tiny media"), "tiny.mp4").expect(201);

    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/submit-qa`)
      .set("Authorization", `Bearer ${adminTok}`).expect(200);
    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/publish`)
      .set("Authorization", `Bearer ${adminTok}`).expect(200);

    const shown = await request(app.getHttpServer()).get("/catalog?ci_level=0")
      .set("Authorization", `Bearer ${learnerTok}`).expect(200);
    const item = shown.body.items.find((candidate: { id: string }) => candidate.id === created.body.id);
    expect(item).toBeTruthy();
    expect(item).not.toHaveProperty("title_internal");
    expect(item).not.toHaveProperty("has_l1_translation");
    expect(item).not.toHaveProperty("translation_vi");
  });

  it("forbids learner catalog creation", async () => {
    const tok = (await register(app, `n${Date.now()}@example.com`)).body.access_token;
    await request(app.getHttpServer()).post("/staff/catalog")
      .set("Authorization", `Bearer ${tok}`)
      .send({
        topic_id: "food", ci_level: 0, duration_seconds: 10,
        media_type: "video", visual_support: "high", title_internal: "x",
      }).expect(403);
  });

  it("rejects publishing directly from draft", async () => {
    const adminTok = await loginAdmin(app);
    const created = await request(app.getHttpServer()).post("/staff/catalog")
      .set("Authorization", `Bearer ${adminTok}`)
      .send({
        topic_id: "food", ci_level: 1, duration_seconds: 10,
        media_type: "audio", visual_support: "high", title_internal: "skip",
      }).expect(201);
    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/publish`)
      .set("Authorization", `Bearer ${adminTok}`).expect(400);
  });

  it("FR-CAT-002 blocks publish without media, allows after upload", async () => {
    const adminTok = await loginAdmin(app);
    const created = await request(app.getHttpServer()).post("/staff/catalog")
      .set("Authorization", `Bearer ${adminTok}`)
      .send({
        topic_id: "body", ci_level: 0, duration_seconds: 12,
        media_type: "video", visual_support: "high", title_internal: "no-media",
      }).expect(201);

    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/submit-qa`)
      .set("Authorization", `Bearer ${adminTok}`).expect(200);

    const blocked = await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/publish`)
      .set("Authorization", `Bearer ${adminTok}`).expect(400);
    expect(blocked.body.message).toMatch(/without media/);

    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/media`)
      .set("Authorization", `Bearer ${adminTok}`)
      .attach("file", Buffer.from("tiny media"), "tiny.mp4").expect(201);
    const published = await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/publish`)
      .set("Authorization", `Bearer ${adminTok}`).expect(200);
    expect(published.body.status).toBe("published");
  });

  it("unpublishes published items to draft and rejects non-published", async () => {
    const adminTok = await loginAdmin(app);
    const learnerTok = (await register(app, `u${Date.now()}@example.com`)).body.access_token;
    const created = await request(app.getHttpServer()).post("/staff/catalog")
      .set("Authorization", `Bearer ${adminTok}`)
      .send({
        topic_id: "nature", ci_level: 0, duration_seconds: 15,
        media_type: "video", visual_support: "medium", title_internal: "unpublish-me",
      }).expect(201);

    // draft cannot be unpublished
    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/unpublish`)
      .set("Authorization", `Bearer ${adminTok}`).expect(400);
    // learner cannot unpublish
    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/unpublish`)
      .set("Authorization", `Bearer ${learnerTok}`).expect(403);

    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/media`)
      .set("Authorization", `Bearer ${adminTok}`)
      .attach("file", Buffer.from("tiny media"), "tiny.mp4").expect(201);
    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/submit-qa`)
      .set("Authorization", `Bearer ${adminTok}`).expect(200);
    await request(app.getHttpServer()).post(`/staff/catalog/${created.body.id}/publish`)
      .set("Authorization", `Bearer ${adminTok}`).expect(200);

    const visible = await request(app.getHttpServer()).get("/catalog")
      .set("Authorization", `Bearer ${learnerTok}`).expect(200);
    expect(visible.body.items.some((item: { id: string }) => item.id === created.body.id)).toBe(true);

    const unpublished = await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/unpublish`)
      .set("Authorization", `Bearer ${adminTok}`).expect(200);
    expect(unpublished.body.status).toBe("draft");

    const hidden = await request(app.getHttpServer()).get("/catalog")
      .set("Authorization", `Bearer ${learnerTok}`).expect(200);
    expect(hidden.body.items.some((item: { id: string }) => item.id === created.body.id)).toBe(false);
  });
});
