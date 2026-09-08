import { afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { PlaybackTracker } from "./playback-tracker";

class Video extends EventTarget {
  currentTime = 1;
  duration = 120;
  playbackRate = 1;
  paused = true;
  seeking = false;
  pause() { this.paused = true; this.dispatchEvent(new Event("pause")); }
}
const originalFetch = globalThis.fetch;
const trackers: PlaybackTracker[] = [];
afterEach(() => {
  trackers.splice(0).forEach((tracker) => tracker.destroy());
  globalThis.fetch = originalFetch;
});
function fixture(interval = 60_000) {
  const video = new Video();
  const tracker = new PlaybackTracker({
    video: video as unknown as HTMLVideoElement,
    catalogItemId: "clip-1", contentVersionId: "version-2", heartbeatIntervalMs: interval,
  });
  trackers.push(tracker);
  return { video, tracker };
}
function startResponse() {
  return Response.json({ playback_id: "playback-1", epoch: 3, initial_position_ms: 0, resume_checkpoint: null });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

test("start retains the exact version, body and idempotency key after an uncertain response", async () => {
  const calls: RequestInit[] = [];
  globalThis.fetch = async (_url, init) => {
    calls.push(init!);
    if (calls.length === 1) throw new Error("ACK lost after commit");
    return startResponse();
  };
  const { tracker } = fixture();
  assert.equal(await tracker.start(), null);
  assert.equal((await tracker.start())?.playbackId, "playback-1");
  assert.equal(calls[0].body, calls[1].body);
  assert.equal(JSON.parse(String(calls[0].body)).content_version_id, "version-2");
  const key = new Headers(calls[0].headers).get("Idempotency-Key");
  assert.ok(key);
  assert.equal(new Headers(calls[1].headers).get("Idempotency-Key"), key);
  await tracker.start();
  assert.equal(calls.length, 2, "starting an active tracker must not reset its seq");
});

test("retry checkpoint keeps its payload despite video movement, then advances exactly once", async () => {
  const calls: { url: string; body: string }[] = [];
  globalThis.fetch = async (url, init) => {
    if (String(url).endsWith("/playbacks")) return startResponse();
    calls.push({ url: String(url), body: String(init?.body) });
    if (calls.length === 1) throw new Error("receipt lost");
    return Response.json({ seq: calls.length === 2 ? 1 : 2 });
  };
  const { video, tracker } = fixture();
  await tracker.start();
  assert.equal(await tracker.sendCheckpoint(), false);
  video.currentTime = 45;
  video.playbackRate = 2;
  assert.equal(await tracker.sendCheckpoint(), true);
  assert.deepEqual(calls[1], calls[0]);
  assert.equal(await tracker.sendCheckpoint(), true);
  assert.ok(calls[2].url.endsWith("/checkpoints/2"));
  assert.equal(JSON.parse(calls[2].body).position_ms, 45_000);
});

test("end waits for in-flight checkpoint and freezes a final payload across retries", async () => {
  const checkpoint = deferred<Response>();
  const endBodies: string[] = [];
  let checkpointCalls = 0;
  globalThis.fetch = async (url, init) => {
    if (String(url).endsWith("/playbacks")) return startResponse();
    if (String(url).includes("/checkpoints/")) { checkpointCalls++; return checkpoint.promise; }
    endBodies.push(String(init?.body));
    if (endBodies.length === 1) return new Response("unavailable", { status: 503 });
    return Response.json({ status: "ended" });
  };
  const { video, tracker } = fixture();
  await tracker.start();
  const sending = tracker.sendCheckpoint();
  const ending = tracker.end();
  await Promise.resolve();
  assert.equal(endBodies.length, 0);
  video.currentTime = 90;
  checkpoint.resolve(Response.json({ seq: 1 }));
  await Promise.all([sending, ending]);
  assert.equal(checkpointCalls, 1);
  assert.equal(JSON.parse(endBodies[0]).final_seq, 2);
  assert.equal(JSON.parse(endBodies[0]).final_position_ms, 1000);
  video.currentTime = 100;
  await tracker.end();
  assert.equal(endBodies[1], endBodies[0]);
  await tracker.end();
  assert.equal(endBodies.length, 2, "ACK closes tracker; no extra end request");
});

test("end reconciles a lost checkpoint ACK before posting the next sequence", async () => {
  const bodies: string[] = [];
  let ended = false;
  globalThis.fetch = async (url, init) => {
    if (String(url).endsWith("/playbacks")) return startResponse();
    if (String(url).includes("/checkpoints/")) {
      bodies.push(String(init?.body));
      if (bodies.length === 1) throw new Error("lost ACK");
      return Response.json({ seq: 1 });
    }
    assert.equal(bodies.length, 2);
    assert.equal(JSON.parse(String(init?.body)).final_seq, 2);
    ended = true;
    return Response.json({ status: "ended" });
  };
  const { video, tracker } = fixture();
  await tracker.start();
  await tracker.sendCheckpoint();
  video.currentTime = 10;
  await tracker.end();
  assert.equal(bodies[0], bodies[1]);
  assert.equal(ended, true);
});

test("failed end is retried automatically while mounted with an unchanged payload", async () => {
  const retried = deferred<void>();
  const bodies: string[] = [];
  globalThis.fetch = async (url, init) => {
    if (String(url).endsWith("/playbacks")) return startResponse();
    assert.ok(String(url).endsWith("/end"));
    bodies.push(String(init?.body));
    if (bodies.length === 1) throw new Error("lost end ACK");
    retried.resolve();
    return Response.json({ status: "ended" });
  };
  const { tracker } = fixture(10);
  await tracker.start();
  await tracker.end();
  await retried.promise;
  assert.equal(bodies.length, 2);
  assert.equal(bodies[0], bodies[1]);
});
