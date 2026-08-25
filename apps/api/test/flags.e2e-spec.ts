import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { PrismaService } from "../src/prisma/prisma.service";
import { register } from "./helpers";

jest.setTimeout(120_000);

describe("feature flags", () => {
  let app: INestApplication;
  let prisma: PrismaService;

  beforeAll(async () => {
    const module = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = module.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  it("GET /flags returns all flags disabled by default FR-FLG-001", async () => {
    const token = (await register(app, `f${Date.now()}@example.com`))
      .body.access_token;

    const response = await request(app.getHttpServer())
      .get("/flags")
      .set("Authorization", `Bearer ${token}`)
      .expect(200);

    expect(response.body).toEqual({
      speaking_enabled: false,
      l1_subtitles_enabled: false,
      grammar_enabled: false,
      flashcards_enabled: false,
    });
  });

  it("learner PATCH /staff/flags is forbidden NFR-SEC-002", async () => {
    const token = (await register(app, `p${Date.now()}@example.com`))
      .body.access_token;

    await request(app.getHttpServer())
      .patch("/staff/flags")
      .set("Authorization", `Bearer ${token}`)
      .send({
        speaking_enabled: true,
        l1_subtitles_enabled: false,
        grammar_enabled: false,
        flashcards_enabled: false,
      })
      .expect(403);
  });

  it("admin PATCH /staff/flags updates all flags", async () => {
    const email = `a${Date.now()}@example.com`;
    const registration = await register(app, email);
    const user = await prisma.user.findUniqueOrThrow({
      where: { email: email.toLowerCase() },
    });
    await prisma.userRole.create({
      data: { userId: user.id, role: "admin" },
    });

    await request(app.getHttpServer())
      .patch("/staff/flags")
      .set("Authorization", `Bearer ${registration.body.access_token}`)
      .send({
        speaking_enabled: true,
        l1_subtitles_enabled: true,
        grammar_enabled: false,
        flashcards_enabled: true,
      })
      .expect(200);

    await request(app.getHttpServer())
      .get("/flags")
      .set("Authorization", `Bearer ${registration.body.access_token}`)
      .expect(200)
      .expect({
        speaking_enabled: true,
        l1_subtitles_enabled: true,
        grammar_enabled: false,
        flashcards_enabled: true,
      });
  });
});
