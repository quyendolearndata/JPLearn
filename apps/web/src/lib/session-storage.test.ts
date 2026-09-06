import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
// Static import is safe: session-storage.ts only touches window/sessionStorage lazily inside store().
import {
  sessionStorageKey,
  readSessionRecord,
  writeSessionRecord,
  clearSessionRecord,
  newIdempotencyKey,
  recoveryRequestFor,
  type StoredSession,
} from "./session-storage";

// Minimal Storage shim for node --test (sessionStorage is per-tab in browsers).
class MemoryStorage {
  private m = new Map<string, string>();
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { this.m.set(k, String(v)); }
  removeItem(k: string) { this.m.delete(k); }
  clear() { this.m.clear(); }
}
(globalThis as unknown as { window: unknown }).window = globalThis;
(globalThis as unknown as { sessionStorage: MemoryStorage }).sessionStorage = new MemoryStorage();

beforeEach(() => (globalThis as unknown as { sessionStorage: MemoryStorage }).sessionStorage.clear());

const rec = (over: Partial<StoredSession> = {}): StoredSession => ({
  v: 1, state: "starting", idempotencyKey: "k1", deviceClass: "web", startedAt: "2026-09-06T00:00:00.000Z", ...over,
});

test("T-SES-REC-001: key is scoped per user", () => {
  assert.equal(sessionStorageKey("u1"), "jplearn.session:u1");
  writeSessionRecord("u1", rec());
  assert.equal(readSessionRecord("u2"), null);
  assert.deepEqual(readSessionRecord("u1"), rec());
});

test("T-SES-REC-001: clear only touches the given user", () => {
  writeSessionRecord("u1", rec({ idempotencyKey: "a" }));
  writeSessionRecord("u2", rec({ idempotencyKey: "b" }));
  clearSessionRecord("u1");
  assert.equal(readSessionRecord("u1"), null);
  assert.equal(readSessionRecord("u2")?.idempotencyKey, "b");
});

test("T-SES-REC-001: corrupt or foreign-shaped records are dropped, never returned", () => {
  sessionStorage.setItem("jplearn.session:u1", "{not json");
  assert.equal(readSessionRecord("u1"), null);
  assert.equal(sessionStorage.getItem("jplearn.session:u1"), null);
  sessionStorage.setItem("jplearn.session:u1", JSON.stringify({ state: "active", clip: { hls_url: "x" } }));
  assert.equal(readSessionRecord("u1"), null, "records without v:1 or with clip payload are rejected");
});

test("T-SES-REC-001: writer refuses payloads carrying catalog/media URLs", () => {
  assert.throws(() => writeSessionRecord("u1", { ...rec(), clip: { hls_url: "signed" } } as unknown as StoredSession));
});

test("newIdempotencyKey returns distinct, header-safe values ≤128 chars", () => {
  const a = newIdempotencyKey(); const b = newIdempotencyKey();
  assert.notEqual(a, b);
  assert.match(a, /^[A-Za-z0-9-]{8,128}$/);
});

test("T-SES-REC-001: starting retries preserve the stored key, device and item", () => {
  const stored = rec({ idempotencyKey: "persisted-key", deviceClass: "web", itemId: "item-1" });

  const first = recoveryRequestFor(stored);
  const retry = recoveryRequestFor(stored);

  assert.deepEqual(first, {
    kind: "replay_start",
    idempotencyKey: "persisted-key",
    deviceClass: "web",
    itemId: "item-1",
  });
  assert.deepEqual(retry, first);
});

test("T-SES-REC-001: non-starting recovery only verifies the stored session id", () => {
  for (const state of ["active", "ending", "outcome_unknown"] as const) {
    assert.deepEqual(
      recoveryRequestFor(rec({ state, sessionId: "session-1", itemId: "item-1" })),
      { kind: "verify_session", sessionId: "session-1", itemId: "item-1" },
    );
  }
});
