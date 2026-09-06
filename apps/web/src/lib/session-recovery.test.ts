import { test } from "node:test";
import assert from "node:assert/strict";
import {
  classifyReplayFailure,
  isLearningSessionResponse,
} from "./session-recovery";

const validRequiredFields = {
  id: "123e4567-e89b-42d3-a456-426614174000",
  device_class: "web",
  started_at: "2026-09-06T08:00:00Z",
};

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
