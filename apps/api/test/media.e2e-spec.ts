import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { loginAdmin, register } from "./helpers";
import argon2 from "argon2";

jest.setTimeout(120_000);

describe("media upload and playback URL", () => {
  let app: INestApplication;

  beforeAll(async () => {
    process.env.API_PUBLIC_URL = "http://localhost:3001";
    const module = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = module.createNestApplication();
    await app.init();
    const prisma = app.get(PrismaService);
    await prisma.topic.create({ data: { id: "media_topic", labelInternal: "media_topic" } });
    const passwordHash = await argon2.hash("password10");
    await prisma.user.upsert({
      where: { email: "admin@jplearn.local" },
      create: {
        email: "admin@jplearn.local",
        passwordHash,
        roles: { create: [{ role: "admin" }, { role: "teacher" }] },
      },
      update: { passwordHash },
    });
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  it("allows staff to upload media and exposes its playback URL after publish", async () => {
    const adminToken = await loginAdmin(app);
    const learnerToken = (await register(app, `media-${Date.now()}@example.com`)).body.access_token;
    const created = await request(app.getHttpServer())
      .post("/staff/catalog")
      .set("Authorization", `Bearer ${adminToken}`)
      .send({
        topic_id: "media_topic", ci_level: 0, duration_seconds: 4,
        media_type: "video", visual_support: "high", title_internal: "media",
      })
      .expect(201);

    const uploaded = await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/media`)
      .set("Authorization", `Bearer ${adminToken}`)
      .attach("file", Buffer.from("tiny media"), "tiny.mp4")
      .expect(201);
    expect(uploaded.body.playback_url).toMatch(/^http:\/\//);

    await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/submit-qa`)
      .set("Authorization", `Bearer ${adminToken}`)
      .expect(200);
    await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/publish`)
      .set("Authorization", `Bearer ${adminToken}`)
      .expect(200);

    const listed = await request(app.getHttpServer())
      .get("/catalog")
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(200);
    const item = listed.body.items.find((candidate: { id: string }) => candidate.id === created.body.id);
    expect(item.playback_url).toMatch(/^http:\/\//);
    expect(new URL(item.playback_url).searchParams.get("sig")).toMatch(/^[a-f0-9]{64}$/);

    const playback = await request(app.getHttpServer())
      .get(new URL(uploaded.body.playback_url).pathname)
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(200);
    expect(playback.headers["x-content-type-options"]).toBe("nosniff");
    expect(playback.body.toString()).toBe("tiny media");

    const signedPath = new URL(item.playback_url).pathname + new URL(item.playback_url).search;
    const viaSig = await request(app.getHttpServer()).get(signedPath).expect(200);
    expect(viaSig.body.toString()).toBe("tiny media");

    await request(app.getHttpServer())
      .get(new URL(item.playback_url).pathname + "?exp=1&sig=" + "ab".repeat(32))
      .expect(401);
  });

  it("forbids learner media uploads and rejects empty files", async () => {
    const adminToken = await loginAdmin(app);
    const learnerToken = (await register(app, `empty-${Date.now()}@example.com`)).body.access_token;
    const created = await request(app.getHttpServer())
      .post("/staff/catalog")
      .set("Authorization", `Bearer ${adminToken}`)
      .send({
        topic_id: "media_topic", ci_level: 0, duration_seconds: 4,
        media_type: "audio", visual_support: "low", title_internal: "empty",
      })
      .expect(201);

    await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/media`)
      .set("Authorization", `Bearer ${learnerToken}`)
      .attach("file", Buffer.from("learner"), "learner.mp3")
      .expect(403);
    await request(app.getHttpServer())
      .post(`/staff/catalog/${created.body.id}/media`)
      .set("Authorization", `Bearer ${adminToken}`)
      .attach("file", Buffer.alloc(0), "empty.mp3")
      .expect(400);
  });
});
