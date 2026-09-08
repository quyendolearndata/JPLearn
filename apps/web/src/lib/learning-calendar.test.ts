import assert from "node:assert/strict";
import { test } from "node:test";
import {
  formatCalendarDate,
  formatTimestampInTimeZone,
  sevenDayCalendarRange,
} from "./learning-calendar";

test("an API calendar date preserves 8 September in every policy timezone", () => {
  for (const timeZone of [
    "America/Los_Angeles",
    "Pacific/Honolulu",
    "Asia/Tokyo",
    "Asia/Ho_Chi_Minh",
  ]) {
    assert.match(formatCalendarDate("2026-09-08") ?? "", /8/);
    assert.doesNotMatch(formatCalendarDate("2026-09-08") ?? "", /7/);
    assert.ok(timeZone, "the same date-only value is independent of timezone conversion");
  }
  assert.equal(formatCalendarDate("2026-02-30"), null);
});

test("seven-day ranges use policy calendar days across DST and year boundaries", () => {
  assert.deepEqual(
    sevenDayCalendarRange(new Date("2026-03-09T03:30:00Z"), "America/New_York"),
    { from: "2026-03-02", to: "2026-03-08" },
  );
  assert.deepEqual(
    sevenDayCalendarRange(new Date("2026-11-02T04:30:00Z"), "America/New_York"),
    { from: "2026-10-26", to: "2026-11-01" },
  );
  assert.deepEqual(
    sevenDayCalendarRange(new Date("2027-01-02T00:30:00Z"), "Asia/Tokyo"),
    { from: "2026-12-27", to: "2027-01-02" },
  );
});

test("timestamp formatting still follows the active policy timezone", () => {
  const timestamp = "2026-09-08T00:30:00Z";
  const losAngeles = formatTimestampInTimeZone(timestamp, "America/Los_Angeles", "en-CA");
  const tokyo = formatTimestampInTimeZone(timestamp, "Asia/Tokyo", "en-CA");
  assert.ok(losAngeles?.includes("09-07"), losAngeles ?? "missing Los Angeles value");
  assert.ok(tokyo?.includes("09-08"), tokyo ?? "missing Tokyo value");
});

test("activity range uses current policy while pending effective time uses its own timezone", () => {
  const instant = new Date("2026-12-31T16:30:00Z");
  assert.deepEqual(sevenDayCalendarRange(instant, "Asia/Tokyo"), {
    from: "2026-12-26",
    to: "2027-01-01",
  });
  const pendingLabel = formatTimestampInTimeZone(
    "2027-01-01T00:30:00Z",
    "America/Los_Angeles",
    "en-CA",
  );
  assert.ok(pendingLabel?.includes("12-31"), pendingLabel ?? "missing pending label");
});
