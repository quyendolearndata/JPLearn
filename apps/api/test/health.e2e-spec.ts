import { INestApplication } from "@nestjs/common";
import { Test } from "@nestjs/testing";
import request from "supertest";
import { AppModule } from "../src/app.module";

describe("health (NFR-OBS-001)", () => {
  let app: INestApplication;
  beforeAll(async () => {
    const m = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = m.createNestApplication();
    await app.init();
  });
  afterAll(() => app.close());

  it("GET /health", async () => {
    const res = await request(app.getHttpServer()).get("/health").expect(200);
    expect(res.body).toEqual({ ok: true });
    expect(res.headers["x-request-id"]).toMatch(/./);
  });

  it("echoes x-request-id (T-NFR-O1)", async () => {
    const res = await request(app.getHttpServer())
      .get("/health")
      .set("x-request-id", "trace-obs-001")
      .expect(200);
    expect(res.headers["x-request-id"]).toBe("trace-obs-001");
  });
});
