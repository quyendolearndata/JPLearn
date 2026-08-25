import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { register } from "./helpers";

jest.setTimeout(120_000);

describe("sessions, progress, and events", () => {
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

  it("starts without media, records events, and increments progress", async () => {
    const registration = await register(app, `session-${Date.now()}@example.com`);
    const token = registration.body.access_token;
    await request(app.getHttpServer()).get("/progress").expect(401);

    const started = await request(app.getHttpServer())
      .post("/sessions")
      .set("Authorization", `Bearer ${token}`)
      .send({ device_class: "web" })
      .expect(201);
    expect(started.body).toEqual(expect.objectContaining({
      id: expect.any(String),
      device_class: "web",
      started_at: expect.any(String),
      ended_at: null,
      duration_seconds: null,
    }));

    await request(app.getHttpServer())
      .post("/sessions")
      .set("Authorization", `Bearer ${token}`)
      .send({ device_class: "web" })
      .expect(201);
    await expect(prisma.device.count({
      where: { userId: registration.body.user.id, deviceClass: "web" },
    })).resolves.toBe(1);

    const startEvents = await prisma.learningEvent.findMany({
      where: { sessionId: started.body.id },
      orderBy: { createdAt: "asc" },
    });
    expect(startEvents.map((event) => event.type)).toEqual([
      "session_started",
      "level_exposed",
    ]);
    expect(startEvents[1].payload).toEqual({ ci_level: 0 });

    await prisma.learningSession.update({
      where: { id: started.body.id },
      data: { startedAt: new Date(Date.now() - 120_000) },
    });
    const ended = await request(app.getHttpServer())
      .post(`/sessions/${started.body.id}/end`)
      .set("Authorization", `Bearer ${token}`)
      .send({})
      .expect(200);
    expect(Object.keys(ended.body).sort()).toEqual([
      "current_ci_level",
      "minutes_comprehensible",
    ]);
    expect(ended.body).toEqual({ minutes_comprehensible: 2, current_ci_level: 0 });

    const progress = await request(app.getHttpServer())
      .get("/progress")
      .set("Authorization", `Bearer ${token}`)
      .expect(200);
    expect(progress.body).toEqual({ minutes_comprehensible: 2, current_ci_level: 0 });
    const events = await prisma.learningEvent.findMany({ where: { sessionId: started.body.id } });
    expect(events.map((event) => event.type).sort()).toEqual([
      "level_exposed",
      "minutes_comprehensible",
      "session_ended",
      "session_started",
    ]);
    expect(events.find((event) => event.type === "minutes_comprehensible")?.payload)
      .toEqual({ minutes: 2 });
  });

  it("rejects double-ending and ending another user's session", async () => {
    const first = (await register(app, `first-${Date.now()}@example.com`)).body.access_token;
    const second = (await register(app, `second-${Date.now()}@example.com`)).body.access_token;
    const session = await request(app.getHttpServer())
      .post("/sessions")
      .set("Authorization", `Bearer ${first}`)
      .send({ device_class: "phone" })
      .expect(201);
    await request(app.getHttpServer())
      .post(`/sessions/${session.body.id}/end`)
      .set("Authorization", `Bearer ${second}`)
      .expect(403);
    await request(app.getHttpServer())
      .post(`/sessions/${session.body.id}/end`)
      .set("Authorization", `Bearer ${first}`)
      .expect(200);
    await request(app.getHttpServer())
      .post(`/sessions/${session.body.id}/end`)
      .set("Authorization", `Bearer ${first}`)
      .expect(400);
  });

  it("does not count zombie sessions", async () => {
    const token = (await register(app, `zombie-${Date.now()}@example.com`)).body.access_token;
    const session = await request(app.getHttpServer())
      .post("/sessions")
      .set("Authorization", `Bearer ${token}`)
      .send({ device_class: "ipad" })
      .expect(201);
    await prisma.learningSession.update({
      where: { id: session.body.id },
      data: { startedAt: new Date(Date.now() - (4 * 60 * 60 + 10) * 1000) },
    });
    const ended = await request(app.getHttpServer())
      .post(`/sessions/${session.body.id}/end`)
      .set("Authorization", `Bearer ${token}`)
      .expect(200);
    expect(ended.body.minutes_comprehensible).toBe(0);
  });
});
