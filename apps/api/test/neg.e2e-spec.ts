import { Test } from "@nestjs/testing";
import { INestApplication } from "@nestjs/common";
import request from "supertest";
import { AppModule } from "../src/app.module";
import { register } from "./helpers";

jest.setTimeout(120_000);

describe("negative API surface (textbook absent)", () => {
  let app: INestApplication;

  beforeAll(async () => {
    const module = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = module.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  const paths = [
    "/flashcards",
    "/grammar",
    "/grammar/lessons",
    "/vocabulary",
    "/translations",
  ];

  it.each(paths)("FR-NEG no %s", async (path) => {
    const token = (
      await register(app, `neg-${path.replaceAll("/", "-")}-${Date.now()}@example.com`)
    ).body.access_token;
    const response = await request(app.getHttpServer())
      .get(path)
      .set("Authorization", `Bearer ${token}`);
    expect(response.status).toBe(404);
  });

  it("progress JSON keys only FR-PRG-003", async () => {
    const token = (
      await register(app, `keys-${Date.now()}@example.com`)
    ).body.access_token;
    const response = await request(app.getHttpServer())
      .get("/progress")
      .set("Authorization", `Bearer ${token}`)
      .expect(200);
    expect(Object.keys(response.body).sort()).toEqual([
      "current_ci_level",
      "minutes_comprehensible",
    ]);
  });
});
