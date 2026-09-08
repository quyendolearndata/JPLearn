import { apiBaseUrl } from "../api";

describe("apiBaseUrl", () => {
  const original = process.env.EXPO_PUBLIC_API_URL;
  afterEach(() => {
    if (original === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = original;
  });

  test("defaults to the FastAPI dev port 3002 (matches root dev:api)", () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(apiBaseUrl()).toBe("http://localhost:3002");
  });

  test("honours EXPO_PUBLIC_API_URL", () => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.test";
    expect(apiBaseUrl()).toBe("https://api.example.test");
  });
});
