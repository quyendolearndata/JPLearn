import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { loginAdmin, register } from "./helpers";
import argon2 from "argon2";

jest.setTimeout(120_000);

const storageRoot = join(process.cwd(), "storage");

const MANIFEST = [
  "#EXTM3U",
  "#EXT-X-VERSION:3",
  "#EXT-X-TARGETDURATION:4",
  "#EXTINF:4.000,",
  "segment-000.ts",
  "#EXT-X-ENDLIST",
  "",
].join("\n");

describe("HLS playback (NFR-PERF-002)", () => {
  let app: INestApplication;
  let adminToken: string;
  let learnerToken: string;
  let itemId: string;
  let assetId: string;

  beforeAll(async () => {
    process.env.API_PUBLIC_URL = "http://localhost:3001";
    const module = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = module.createNestApplication();
    await app.init();
    const prisma = app.get(PrismaService);
    await prisma.topic.createMany({
      data: [{ id: "hls_topic", labelInternal: "hls_topic" }],
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
      update: { passwordHash },
    });

    adminToken = await loginAdmin(app);
    learnerToken = (await register(app, `hls-${Date.now()}@example.com`)).body.access_token;

    const created = await request(app.getHttpServer())
      .post("/staff/catalog")
      .set("Authorization", `Bearer ${adminToken}`)
      .send({
        topic_id: "hls_topic", ci_level: 0, duration_seconds: 4,
        media_type: "video", visual_support: "high", title_internal: "hls",
      })
      .expect(201);
    itemId = created.body.id;

    const uploaded = await request(app.getHttpServer())
      .post(`/staff/catalog/${itemId}/media`)
      .set("Authorization", `Bearer ${adminToken}`)
      .attach("file", Buffer.from("fake mp4 bytes"), "clip.mp4")
      .expect(201);
    assetId = uploaded.body.id;
    expect(uploaded.body.hls_url).toBeNull();
  });

  afterAll(async () => {
    if (assetId) await rm(join(storageRoot, "hls", assetId), { recursive: true, force: true });
    if (app) await app.close();
  });

  it("rejects registration before the manifest exists on disk", async () => {
    await request(app.getHttpServer())
      .post(`/staff/media/${assetId}/hls`)
      .set("Authorization", `Bearer ${adminToken}`)
      .expect(400);
  });

  it("forbids learners from registering HLS", async () => {
    await request(app.getHttpServer())
      .post(`/staff/media/${assetId}/hls`)
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(403);
  });

  it("registers, exposes hls_url on the catalog, and serves manifest and segments", async () => {
    const dir = join(storageRoot, "hls", assetId);
    await mkdir(dir, { recursive: true });
    await writeFile(join(dir, "index.m3u8"), MANIFEST);
    await writeFile(join(dir, "segment-000.ts"), Buffer.from("fake ts segment"));

    const registered = await request(app.getHttpServer())
      .post(`/staff/media/${assetId}/hls`)
      .set("Authorization", `Bearer ${adminToken}`)
      .expect(201);
    expect(new URL(registered.body.hls_url).pathname).toBe(
      `/media/${assetId}/hls/index.m3u8`,
    );
    expect(new URL(registered.body.hls_url).searchParams.get("sig")).toMatch(/^[a-f0-9]{64}$/);

    await request(app.getHttpServer())
      .post(`/staff/catalog/${itemId}/submit-qa`)
      .set("Authorization", `Bearer ${adminToken}`)
      .expect(200);
    await request(app.getHttpServer())
      .post(`/staff/catalog/${itemId}/publish`)
      .set("Authorization", `Bearer ${adminToken}`)
      .expect(200);

    const listed = await request(app.getHttpServer())
      .get("/catalog")
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(200);
    const item = listed.body.items.find((candidate: { id: string }) => candidate.id === itemId);
    expect(new URL(item.hls_url).pathname).toBe(`/media/${assetId}/hls/index.m3u8`);
    expect(item.playback_url).toMatch(/^http:\/\//);

    const manifest = await request(app.getHttpServer())
      .get(`/media/${assetId}/hls/index.m3u8`)
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(200);
    expect(manifest.headers["content-type"]).toMatch(/application\/vnd\.apple\.mpegurl/);
    expect(manifest.headers["x-content-type-options"]).toBe("nosniff");
    expect(manifest.text).toContain("#EXTM3U");

    const segment = await request(app.getHttpServer())
      .get(`/media/${assetId}/hls/segment-000.ts`)
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(200);
    expect(segment.headers["content-type"]).toMatch(/video\/mp2t/);
    expect(segment.headers["x-content-type-options"]).toBe("nosniff");
    expect(segment.body.toString()).toBe("fake ts segment");
  });

  it("signs segment URIs inside the manifest when served via a signed URL", async () => {
    const listed = await request(app.getHttpServer())
      .get("/catalog")
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(200);
    const item = listed.body.items.find((candidate: { id: string }) => candidate.id === itemId);
    const signedManifest = new URL(item.hls_url);

    const manifest = await request(app.getHttpServer())
      .get(signedManifest.pathname + signedManifest.search)
      .expect(200);
    expect(manifest.headers["x-content-type-options"]).toBe("nosniff");
    const segmentLine = manifest.text
      .split("\n")
      .find((line: string) => line.trim() && !line.trim().startsWith("#"));
    expect(segmentLine).toMatch(/^segment-000\.ts\?exp=\d+&sig=[a-f0-9]{64}$/);

    // Segment được ký sẵn trong manifest phải tải được không cần Bearer (hls.js không gửi header).
    await request(app.getHttpServer())
      .get(`/media/${assetId}/hls/${segmentLine}`)
      .expect(200);
  });

  it("rejects traversal and unsupported HLS file types", async () => {
    await request(app.getHttpServer())
      .get(`/media/${assetId}/hls/evil.exe`)
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(400);
    await request(app.getHttpServer())
      .get(`/media/${assetId}/hls/..%2Fsecret.m3u8`)
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(400);
  });

  it("requires auth and returns 404 for missing bundles", async () => {
    await request(app.getHttpServer())
      .get(`/media/${assetId}/hls/index.m3u8`)
      .expect(401);
    await request(app.getHttpServer())
      .get(`/media/${assetId}/hls/segment-999.ts`)
      .set("Authorization", `Bearer ${learnerToken}`)
      .expect(404);
  });
});
