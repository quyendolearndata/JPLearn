import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { register } from "./helpers";

jest.setTimeout(120_000);

describe("auth FR-ID-001..004", () => {
  let app: INestApplication;
  let prisma: PrismaService;
  beforeAll(async () => {
    const m = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = m.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);
  });
  afterAll(async () => {
    if (app) await app.close();
  });

  it("registers, logins, me has learner role; password not plaintext", async () => {
    const email = `u${Date.now()}@example.com`;
    const res = await register(app, email).expect(201);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.user.email).toBe(email.toLowerCase());
    expect(res.body.user.roles).toEqual(["learner"]);
    const row = await prisma.user.findUnique({ where: { email: email.toLowerCase() } });
    expect(row?.passwordHash).not.toBe("password10");
    expect(row?.passwordHash).not.toContain("password10");

    await request(app.getHttpServer())
      .post("/auth/login")
      .send({ email, password: "wrong-wrong" })
      .expect(401);

    const me = await request(app.getHttpServer())
      .get("/me")
      .set("Authorization", `Bearer ${res.body.access_token}`)
      .expect(200);
    expect(me.body.roles).toEqual(["learner"]);
    expect(me.body).not.toHaveProperty("passwordHash");
  });

  it("logs in with registered credentials and uses the token for /me FR-ID-001", async () => {
    const email = `login${Date.now()}@example.com`;
    const password = "password10";
    await register(app, email, password).expect(201);

    const login = await request(app.getHttpServer())
      .post("/auth/login")
      .send({ email, password })
      .expect(200);
    expect(login.body.access_token).toBeTruthy();

    const me = await request(app.getHttpServer())
      .get("/me")
      .set("Authorization", `Bearer ${login.body.access_token}`)
      .expect(200);
    expect(me.body.email).toBe(email.toLowerCase());
    expect(me.body.roles).toEqual(["learner"]);
  });

  it("logout then me is 401 FR-ID-003", async () => {
    const email = `l${Date.now()}@example.com`;
    const res = await register(app, email).expect(201);
    await request(app.getHttpServer())
      .post("/auth/logout")
      .set("Authorization", `Bearer ${res.body.access_token}`)
      .expect(204);
    await request(app.getHttpServer())
      .get("/me")
      .set("Authorization", `Bearer ${res.body.access_token}`)
      .expect(401);
  });
});
