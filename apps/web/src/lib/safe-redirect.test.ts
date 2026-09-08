import { test } from "node:test";
import assert from "node:assert/strict";
import { getSafeRedirect } from "./safe-redirect";

test("T-AUTH-SEC-001: accepts only internal paths with exactly one leading slash", () => {
  assert.equal(getSafeRedirect("/progress"), "/progress");
  assert.equal(getSafeRedirect("/session?item_id=abc"), "/session?item_id=abc");
  assert.equal(getSafeRedirect("/staff/123"), "/staff/123");
});

test("T-AUTH-SEC-001: rejects protocol-relative, backslash, scheme and empty targets", () => {
  for (const bad of [null, undefined, "", "//evil.example", "/\\evil.example", "https://evil.example", "javascript:alert(1)", "progress", "/%2F%2Fevil"]) {
    assert.equal(getSafeRedirect(bad), "/", `expected "/" for ${String(bad)}`);
  }
});
