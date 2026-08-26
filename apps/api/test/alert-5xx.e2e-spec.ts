import {
  BadRequestException,
  Controller,
  Get,
  INestApplication,
} from "@nestjs/common";
import { APP_INTERCEPTOR } from "@nestjs/core";
import { Test } from "@nestjs/testing";
import { createServer, Server } from "node:http";
import { AddressInfo } from "node:net";
import request from "supertest";
import { RequestIdInterceptor } from "../src/request-id.interceptor";

@Controller()
class BoomController {
  @Get("/__test/boom")
  boom(): never {
    throw new Error("boom");
  }

  @Get("/__test/bad")
  bad(): never {
    throw new BadRequestException("bad_input");
  }
}

describe("5xx alert webhook (NFR-OBS-001, T-NFR-O2)", () => {
  let app: INestApplication;
  let hook: Server;
  let hookUrl: string;
  let received: Record<string, unknown>[];
  let waiter: ((payload: Record<string, unknown>) => void) | null;

  beforeAll(async () => {
    const m = await Test.createTestingModule({
      controllers: [BoomController],
      providers: [{ provide: APP_INTERCEPTOR, useClass: RequestIdInterceptor }],
    }).compile();
    app = m.createNestApplication();
    await app.init();

    hook = createServer((req, res) => {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", () => {
        const payload = JSON.parse(body) as Record<string, unknown>;
        received.push(payload);
        waiter?.(payload);
        res.writeHead(200).end();
      });
    });
    await new Promise<void>((resolve) => hook.listen(0, "127.0.0.1", resolve));
    const { port } = hook.address() as AddressInfo;
    hookUrl = `http://127.0.0.1:${port}/hook`;
  });

  afterAll(async () => {
    await app.close();
    await new Promise((resolve) => hook.close(resolve));
  });

  beforeEach(() => {
    received = [];
    waiter = null;
  });

  afterEach(() => {
    delete process.env.ALERT_WEBHOOK_URL;
    jest.restoreAllMocks();
  });

  it("env TẮT (không ALERT_WEBHOOK_URL) → không gọi fetch khi 5xx", async () => {
    delete process.env.ALERT_WEBHOOK_URL;
    const spy = jest.spyOn(global, "fetch");
    await request(app.getHttpServer()).get("/__test/boom").expect(500);
    expect(spy).not.toHaveBeenCalled();
  });

  it("env BẬT → webhook nhận đúng payload khi 5xx", async () => {
    process.env.ALERT_WEBHOOK_URL = hookUrl;
    const got = new Promise<Record<string, unknown>>((resolve) => {
      waiter = resolve;
    });
    await request(app.getHttpServer())
      .get("/__test/boom")
      .set("x-request-id", "req-alert-001")
      .expect(500);
    const payload = await got;
    expect(payload.method).toBe("GET");
    expect(payload.path).toBe("/__test/boom");
    expect(payload.status).toBe(500);
    expect(payload.requestId).toBe("req-alert-001");
    expect(payload.message).toBe("boom");
    expect(payload.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(payload.text).toContain("500");
    expect(payload.text).toContain("/__test/boom");
    expect(payload.text).toContain("req-alert-001");
  });

  it("4xx KHÔNG alert", async () => {
    process.env.ALERT_WEBHOOK_URL = hookUrl;
    const spy = jest.spyOn(global, "fetch");
    await request(app.getHttpServer()).get("/__test/bad").expect(400);
    expect(spy).not.toHaveBeenCalled();
    expect(received).toHaveLength(0);
  });
});
