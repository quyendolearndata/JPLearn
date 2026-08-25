import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { register } from "./helpers";

jest.setTimeout(120_000);

// UC-L06 / T-ID-002 / T-PRG-004: cùng một user đăng nhập trên 3 "client"
// (3 phiên token độc lập mô phỏng web, phone, ipad) phải thấy cùng catalog
// published và cùng minutes_comprehensible; tiến độ gắn user, không gắn thiết bị.
describe("UC-L06 sync devices (T-ID-002, T-PRG-004)", () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const module = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = module.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  it("same identity, same published catalog, same progress across web/phone/ipad", async () => {
    const email = `sync-${Date.now()}@example.com`;
    const password = "password10";
    const web = (await register(app, email, password)).body;
    const login = () =>
      request(app.getHttpServer())
        .post("/auth/login")
        .send({ email, password })
        .expect(200)
        .then((res) => res.body);
    const phone = await login();
    const ipad = await login();
    const tokens = { web: web.access_token, phone: phone.access_token, ipad: ipad.access_token };

    const seed = Date.now();
    const topicId = `sync-topic-${seed}`;
    await prisma.topic.create({ data: { id: topicId, labelInternal: topicId } });
    const published = await prisma.catalogItem.create({
      data: {
        topicId, ciLevel: 0, durationSeconds: 45, mediaType: "video",
        visualSupport: "high", titleInternal: `sync-published-${seed}`,
        status: "published", createdById: web.user.id,
      },
    });
    const draft = await prisma.catalogItem.create({
      data: {
        topicId, ciLevel: 0, durationSeconds: 30, mediaType: "audio",
        visualSupport: "medium", titleInternal: `sync-draft-${seed}`,
        status: "draft", createdById: web.user.id,
      },
    });

    // FR-ID-002: 3 session token độc lập cùng resolve về một identity
    for (const token of Object.values(tokens)) {
      const me = await request(app.getHttpServer())
        .get("/me")
        .set("Authorization", `Bearer ${token}`)
        .expect(200);
      expect(me.body.id).toBe(web.user.id);
      expect(me.body.email).toBe(email);
    }

    // UC-L06 main: cùng catalog published trên cả 3 client
    const catalogs = await Promise.all(
      Object.values(tokens).map((token) =>
        request(app.getHttpServer())
          .get("/catalog")
          .set("Authorization", `Bearer ${token}`)
          .expect(200)
          .then((res) => res.body),
      ),
    );
    expect(catalogs[1]).toEqual(catalogs[0]);
    expect(catalogs[2]).toEqual(catalogs[0]);
    const ids = catalogs[0].items.map((item: { id: string }) => item.id);
    expect(ids).toContain(published.id);
    expect(ids).not.toContain(draft.id);

    const progressOf = (token: string) =>
      request(app.getHttpServer())
        .get("/progress")
        .set("Authorization", `Bearer ${token}`)
        .expect(200)
        .then((res) => res.body);

    // Ban đầu cả 3 client đọc cùng tiến độ
    expect(await progressOf(tokens.web)).toEqual({ minutes_comprehensible: 0, current_ci_level: 0 });
    expect(await progressOf(tokens.phone)).toEqual({ minutes_comprehensible: 0, current_ci_level: 0 });
    expect(await progressOf(tokens.ipad)).toEqual({ minutes_comprehensible: 0, current_ci_level: 0 });

    // Client "phone" học 3 phút rồi kết thúc phiên
    const phoneSession = await request(app.getHttpServer())
      .post("/sessions")
      .set("Authorization", `Bearer ${tokens.phone}`)
      .send({ device_class: "phone" })
      .expect(201);
    expect(phoneSession.body.device_class).toBe("phone");
    await prisma.learningSession.update({
      where: { id: phoneSession.body.id },
      data: { startedAt: new Date(Date.now() - 180_000) },
    });
    const phoneEnd = await request(app.getHttpServer())
      .post(`/sessions/${phoneSession.body.id}/end`)
      .set("Authorization", `Bearer ${tokens.phone}`)
      .expect(200);
    expect(phoneEnd.body.minutes_comprehensible).toBe(3);

    // FR-PRG-004: web và ipad đọc lại thấy cùng giá trị (đồng bộ server-side)
    expect(await progressOf(tokens.web)).toEqual({ minutes_comprehensible: 3, current_ci_level: 0 });
    expect(await progressOf(tokens.ipad)).toEqual({ minutes_comprehensible: 3, current_ci_level: 0 });

    // Chiều ngược lại: client "ipad" học thêm 1 phút, web thấy tổng mới
    const ipadSession = await request(app.getHttpServer())
      .post("/sessions")
      .set("Authorization", `Bearer ${tokens.ipad}`)
      .send({ device_class: "ipad" })
      .expect(201);
    expect(ipadSession.body.device_class).toBe("ipad");
    await prisma.learningSession.update({
      where: { id: ipadSession.body.id },
      data: { startedAt: new Date(Date.now() - 60_000) },
    });
    await request(app.getHttpServer())
      .post(`/sessions/${ipadSession.body.id}/end`)
      .set("Authorization", `Bearer ${tokens.ipad}`)
      .expect(200);
    expect(await progressOf(tokens.web)).toEqual({ minutes_comprehensible: 4, current_ci_level: 0 });
    expect(await progressOf(tokens.phone)).toEqual({ minutes_comprehensible: 4, current_ci_level: 0 });

    // device_class: web client cũng mở phiên → đủ 3 thiết bị
    await request(app.getHttpServer())
      .post("/sessions")
      .set("Authorization", `Bearer ${tokens.web}`)
      .send({ device_class: "web" })
      .expect(201);
    const devices = await prisma.device.findMany({ where: { userId: web.user.id } });
    expect(devices.map((device) => device.deviceClass).sort()).toEqual(["ipad", "phone", "web"]);

    // Tiến độ gắn với user, không gắn thiết bị: đúng 1 dòng learner_progress
    await expect(
      prisma.learnerProgress.count({ where: { userId: web.user.id } }),
    ).resolves.toBe(1);
  });
});
