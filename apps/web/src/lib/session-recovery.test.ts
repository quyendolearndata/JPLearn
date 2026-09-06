import { test } from "node:test";
import assert from "node:assert/strict";
import {
  classifyReplayFailure,
  classifySessionRecoveryBootstrap,
  classifySessionStatusFailure,
  classifySessionStatusResponse,
  createSessionOperationGuard,
  isLearningSessionResponse,
  isSessionOperationCurrent,
} from "./session-recovery";

const validRequiredFields = {
  id: "123e4567-e89b-42d3-a456-426614174000",
  device_class: "web",
  started_at: "2026-09-06T08:00:00Z",
};

test("T-SES-REC-001: session recovery cannot become ready before authenticated identity", () => {
  assert.deepEqual(classifySessionRecoveryBootstrap(null, null), { kind: "awaiting_identity" });
  assert.deepEqual(classifySessionRecoveryBootstrap("token", null), { kind: "awaiting_identity" });
  assert.deepEqual(classifySessionRecoveryBootstrap(null, "u1"), { kind: "awaiting_identity" });
  assert.deepEqual(
    classifySessionRecoveryBootstrap("token", "u1"),
    { kind: "inspect", token: "token", userId: "u1" },
  );
});

test("T-SES-REC-001: end fallback GET 403 and 404 are terminal while 500 is unverified", () => {
  assert.equal(classifySessionStatusFailure(403), "terminal");
  assert.equal(classifySessionStatusFailure(404), "terminal");
  assert.equal(classifySessionStatusFailure(500), "unverified");
  assert.equal(classifySessionStatusFailure(401), "auth");
});

test("T-SES-REC-001: invalid or mismatched ended GET is not terminal", () => {
  assert.equal(classifySessionStatusResponse(
    { ...validRequiredFields, ended_at: "2026-09-06T08:01:00Z" },
    validRequiredFields.id,
  ).kind, "ended");
  assert.equal(classifySessionStatusResponse(
    { ...validRequiredFields, ended_at: "not-a-date" },
    validRequiredFields.id,
  ).kind, "invalid");
  assert.equal(classifySessionStatusResponse(
    { ...validRequiredFields, id: "123e4567-e89b-42d3-a456-426614174001", ended_at: "2026-09-06T08:01:00Z" },
    validRequiredFields.id,
  ).kind, "invalid");
});

test("T-SES-REC-001: recovery and end share one in-flight operation", () => {
  const guard = createSessionOperationGuard();
  const recovery = guard.begin("recovery");
  assert.ok(recovery);
  assert.equal(guard.begin("end"), null);
  assert.equal(guard.finish(recovery), true);

  const end = guard.begin("end");
  assert.ok(end);
  assert.equal(guard.begin("recovery"), null);
  assert.equal(guard.finish(end), true);
});

test("T-SES-REC-001: stale start and end tickets are ignored after user change or cancel", () => {
  const guard = createSessionOperationGuard();
  const start = guard.begin("start");
  assert.ok(start);
  assert.equal(isSessionOperationCurrent(guard, start, "u1", "u2"), false);
  assert.equal(isSessionOperationCurrent(guard, start, "u1", "u1"), true);
  guard.finish(start);

  const end = guard.begin("end");
  assert.ok(end);
  guard.cancel();
  assert.equal(isSessionOperationCurrent(guard, end, "u1", "u1"), false);
});

test("T-SES-REC-001: LearningSession accepts omitted optional fields", () => {
  assert.equal(isLearningSessionResponse(validRequiredFields), true);
});

test("T-SES-REC-001: LearningSession rejects invalid UUID, date-time and fractional duration", () => {
  assert.equal(isLearningSessionResponse({ ...validRequiredFields, id: "not-a-uuid" }), false);
  assert.equal(isLearningSessionResponse({ ...validRequiredFields, started_at: "not-a-date" }), false);
  assert.equal(isLearningSessionResponse({ ...validRequiredFields, ended_at: "yesterday" }), false);
  assert.equal(isLearningSessionResponse({ ...validRequiredFields, duration_seconds: 1.5 }), false);
});

test("T-SES-REC-001: replay 409 is terminal while 500 stays unverified", () => {
  assert.equal(classifyReplayFailure(409), "terminal");
  assert.equal(classifyReplayFailure(500), "unverified");
  assert.equal(classifyReplayFailure(401), "auth");
});
