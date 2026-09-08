import { after, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { api } from "./api";

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.values.set(key, String(value));
  }

  removeItem(key: string) {
    this.values.delete(key);
  }

  clear() {
    this.values.clear();
  }
}

const originalFetch = globalThis.fetch;
const localStorage = new MemoryStorage();

beforeEach(() => {
  localStorage.clear();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    writable: true,
    value: localStorage,
  });
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    writable: true,
    value: {
      localStorage,
      location: { pathname: "/session", search: "", href: "/session" },
    },
  });
  globalThis.fetch = async () => new Response(
    JSON.stringify({ statusCode: 401, message: "Unauthorized" }),
    { status: 401, headers: { "Content-Type": "application/json" } },
  );
});

after(() => {
  globalThis.fetch = originalFetch;
});

test("T-SES-REC-001: stale-token 401 does not clear a newer user session", async () => {
  localStorage.setItem("jplearn.access_token", "new-token");
  localStorage.setItem("jplearn.user", JSON.stringify({
    id: "new-user",
    email: "new@example.com",
    roles: ["learner"],
  }));

  await api("/sessions/session-1", { token: "old-token" });

  assert.equal(localStorage.getItem("jplearn.access_token"), "new-token");
  assert.equal(JSON.parse(localStorage.getItem("jplearn.user") || "{}").id, "new-user");
  assert.equal(window.location.href, "/session");
});

test("T-SES-REC-001: current-token 401 still clears the current user session", async () => {
  localStorage.setItem("jplearn.access_token", "current-token");
  localStorage.setItem("jplearn.user", JSON.stringify({
    id: "current-user",
    email: "current@example.com",
    roles: ["learner"],
  }));

  await api("/sessions/session-1", { token: "current-token" });

  assert.equal(localStorage.getItem("jplearn.access_token"), null);
  assert.equal(localStorage.getItem("jplearn.user"), null);
  assert.equal(window.location.href, "/login?redirect=%2Fsession");
});
