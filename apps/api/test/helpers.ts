import { INestApplication } from "@nestjs/common";
import request from "supertest";

export function register(
  app: INestApplication,
  email: string,
  password = "password10",
) {
  return request(app.getHttpServer())
    .post("/auth/register")
    .send({ email, password });
}

export async function loginAdmin(app: INestApplication) {
  const response = await request(app.getHttpServer())
    .post("/auth/login")
    .send({ email: "admin@jplearn.local", password: "password10" })
    .expect(200);
  return response.body.access_token as string;
}
