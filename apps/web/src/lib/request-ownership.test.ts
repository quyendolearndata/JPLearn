import assert from "node:assert/strict";
import { test } from "node:test";
import { AuthIdentity, RequestOwnershipGate } from "./request-ownership";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

const accountA: AuthIdentity = { token: "token-a", userId: "user-a" };
const accountB: AuthIdentity = { token: "token-b", userId: "user-b" };

test("a response cannot update another auth epoch, including A to B to A", async () => {
  const gate = new RequestOwnershipGate();
  const response = deferred<string>();
  const ticket = gate.next("goal", accountA);
  let rendered = "initial";
  const settle = response.promise.then((value) => {
    if (gate.isCurrent(ticket, accountA)) rendered = value;
  });

  gate.changeAuthEpoch();
  gate.next("goal", accountB);
  gate.changeAuthEpoch();
  gate.next("goal", accountA);
  response.resolve("stale account A response");
  await settle;

  assert.equal(rendered, "initial");
});

test("a stale read cannot restore history after an accepted deletion", async () => {
  const gate = new RequestOwnershipGate();
  const response = deferred<string[]>();
  const ticket = gate.next("progress-read", accountA);
  let history: string[] = [];
  const settle = response.promise.then((items) => {
    if (gate.isCurrent(ticket, accountA)) history = items;
  });

  gate.invalidateScope("progress-read");
  response.resolve(["deleted-playback"]);
  await settle;

  assert.deepEqual(history, []);
});

test("a slow 409 refresh is still owned by the mutation that triggered it", async () => {
  const gate = new RequestOwnershipGate();
  const refresh = deferred<string>();
  const ticket = gate.next("goal", accountA);
  let policy = "account-a-current";
  const settle = refresh.promise.then((value) => {
    if (gate.isCurrent(ticket, accountA)) policy = value;
  });

  gate.changeAuthEpoch();
  gate.next("goal", accountB);
  refresh.resolve("stale-refresh");
  await settle;

  assert.equal(policy, "account-a-current");
});

test("reversed filter responses only expose the latest filter", async () => {
  const gate = new RequestOwnershipGate();
  const slow = deferred<string>();
  const fast = deferred<string>();
  const first = gate.next("catalog", accountA);
  const firstSettle = slow.promise.then((value) => gate.isCurrent(first, accountA) ? value : null);
  const second = gate.next("catalog", accountA);
  const secondSettle = fast.promise.then((value) => gate.isCurrent(second, accountA) ? value : null);

  fast.resolve("CI4");
  slow.resolve("CI0");

  assert.equal(await secondSettle, "CI4");
  assert.equal(await firstSettle, null);
});

test("an old finally cannot clear the busy flag of a newer operation", () => {
  const gate = new RequestOwnershipGate();
  const oldOperation = gate.next("goal", accountA);
  const currentOperation = gate.next("goal", accountA);
  let busy = true;

  if (gate.isCurrent(oldOperation, accountA)) busy = false;
  assert.equal(busy, true);
  if (gate.isCurrent(currentOperation, accountA)) busy = false;
  assert.equal(busy, false);
});

test("dispose invalidates slow JSON parsing and capability work", () => {
  const gate = new RequestOwnershipGate();
  const capability = gate.next("capabilities", accountA);
  const recommendations = gate.next("recommendations", accountA);
  gate.dispose();
  assert.equal(gate.isCurrent(capability, accountA), false);
  assert.equal(gate.isCurrent(recommendations, accountA), false);
});

test("Strict Mode reactivation accepts new work but never revives disposed tickets", () => {
  const gate = new RequestOwnershipGate();
  const old = gate.next("capabilities", accountA);
  gate.dispose();
  gate.activate();
  const fresh = gate.next("capabilities", accountA);
  assert.equal(gate.isCurrent(old, accountA), false);
  assert.equal(gate.isCurrent(fresh, accountA), true);
});

for (const scope of ["capabilities", "recommendations", "history-delete"]) {
  test(`${scope}: delayed body completion after logout cannot publish state`, async () => {
    const gate = new RequestOwnershipGate();
    const body = deferred<string>();
    const ticket = gate.next(scope, accountA);
    let state = "empty";
    const parsing = (async () => {
      const parsed = await body.promise;
      if (gate.isCurrent(ticket, accountA)) state = parsed;
    })();
    gate.changeAuthEpoch();
    gate.next(scope, accountB);
    gate.changeAuthEpoch();
    gate.next(scope, accountA);
    body.resolve("old-account-body");
    await parsing;
    assert.equal(state, "empty");
  });
}
