import { test } from "node:test";
import assert from "node:assert/strict";
import type { CatalogItemPublic } from "@jplearn/domain";
import {
  completeAutomaticCatalogRefetch,
  createMediaRecoveryCycle,
  reconcileMediaRecoveryTarget,
  requestAutomaticCatalogRefetch,
  restartMediaRecoveryManually,
  selectSessionCatalogItem,
} from "./media-recovery";

const item = (id: string, playbackUrl = `https://media.test/${id}.mp4`): CatalogItemPublic => ({
  id,
  ci_level: 0,
  duration_seconds: 30,
  media_type: "video",
  topic_id: "daily_home",
  visual_support: "high",
  playback_url: playbackUrl,
});

test("T-LRN-001 F-03: one error cycle permits only one automatic catalog refetch", () => {
  const initial = createMediaRecoveryCycle("item-a");
  const first = requestAutomaticCatalogRefetch(initial);
  assert.equal(first.action, "refetch");

  const completed = completeAutomaticCatalogRefetch(first.cycle);
  const sameItemWithNewUrls = reconcileMediaRecoveryTarget(completed, "item-a");
  const second = requestAutomaticCatalogRefetch(sameItemWithNewUrls);

  assert.equal(second.action, "exhausted");
  assert.equal(second.cycle.automaticRefetches, 1);
});

test("T-LRN-001 F-03: concurrent source errors coalesce into the in-flight refetch", () => {
  const first = requestAutomaticCatalogRefetch(createMediaRecoveryCycle("item-a"));
  const duplicate = requestAutomaticCatalogRefetch(first.cycle);

  assert.equal(first.action, "refetch");
  assert.equal(duplicate.action, "coalesced");
  assert.equal(duplicate.cycle.automaticRefetches, 1);
});

test("T-LRN-001 F-03: manual retry starts a fresh error cycle", () => {
  const used = completeAutomaticCatalogRefetch(
    requestAutomaticCatalogRefetch(createMediaRecoveryCycle("item-a")).cycle,
  );
  const restarted = restartMediaRecoveryManually(used);

  assert.equal(requestAutomaticCatalogRefetch(restarted).action, "refetch");
});

test("T-LRN-001 F-03: a missing target is unavailable and never falls back to another item", () => {
  const selected = selectSessionCatalogItem([item("item-b")], "item-a");

  assert.deepEqual(selected, { kind: "unavailable", targetItemId: "item-a" });
});

test("T-LRN-001 F-03: a session without an item chooses one default exactly once", () => {
  const selected = selectSessionCatalogItem([item("item-a"), item("item-b")], null);

  assert.deepEqual(selected, { kind: "selected", item: item("item-a"), choseDefault: true });
  assert.deepEqual(
    selectSessionCatalogItem([item("item-b")], "item-a"),
    { kind: "unavailable", targetItemId: "item-a" },
  );
});
