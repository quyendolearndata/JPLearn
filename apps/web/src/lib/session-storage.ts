/**
 * Per-user, per-tab learning-session record (R-03 / T-SES-REC-001).
 * Stored in sessionStorage so tabs never overwrite each other. Never stores catalog objects
 * or signed playback/HLS URLs — recovery always refetches the catalog.
 */
export type SessionLifecycleState = "starting" | "active" | "ending" | "outcome_unknown";

export interface StoredSession {
  v: 1;
  state: SessionLifecycleState;
  idempotencyKey: string;
  deviceClass: "web";
  startedAt: string;
  itemId?: string;
  sessionId?: string;
}

export type SessionRecoveryRequest =
  | {
      kind: "replay_start";
      idempotencyKey: string;
      deviceClass: "web";
      itemId?: string;
    }
  | {
      kind: "verify_session";
      sessionId: string;
      itemId?: string;
    };

export type SessionRecordInspection =
  | { kind: "unavailable" }
  | { kind: "empty" }
  | { kind: "record"; record: StoredSession };

export type StartSessionPreparation =
  | { kind: "unavailable" }
  | { kind: "existing"; record: StoredSession }
  | { kind: "starting"; record: StoredSession };

const PREFIX = "jplearn.session:";
const ACCESS_PROBE_KEY = `${PREFIX}__access_probe__`;
const STATES: readonly SessionLifecycleState[] = ["starting", "active", "ending", "outcome_unknown"];
const ALLOWED_KEYS = new Set(["v", "state", "idempotencyKey", "deviceClass", "startedAt", "itemId", "sessionId"]);

export function sessionStorageKey(userId: string): string {
  return `${PREFIX}${userId}`;
}

function store(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function accessibleStore(): Storage | null {
  const s = store();
  if (!s) return null;
  let previous: string | null = null;
  let readPrevious = false;
  try {
    previous = s.getItem(ACCESS_PROBE_KEY);
    readPrevious = true;
    s.setItem(ACCESS_PROBE_KEY, "ok");
    if (s.getItem(ACCESS_PROBE_KEY) !== "ok") throw new Error("sessionStorage write verification failed");
    if (previous === null) s.removeItem(ACCESS_PROBE_KEY);
    else s.setItem(ACCESS_PROBE_KEY, previous);
    return s;
  } catch {
    if (readPrevious) {
      try {
        if (previous === null) s.removeItem(ACCESS_PROBE_KEY);
        else s.setItem(ACCESS_PROBE_KEY, previous);
      } catch {
        // Storage remains unavailable.
      }
    }
    return null;
  }
}

function isValid(x: unknown): x is StoredSession {
  if (!x || typeof x !== "object") return false;
  const r = x as Record<string, unknown>;
  if (r.v !== 1) return false;
  if (!STATES.includes(r.state as SessionLifecycleState)) return false;
  if (typeof r.idempotencyKey !== "string" || typeof r.startedAt !== "string") return false;
  if (r.deviceClass !== "web") return false;
  for (const k of Object.keys(r)) if (!ALLOWED_KEYS.has(k)) return false;
  return true;
}

export function inspectSessionRecord(userId: string): SessionRecordInspection {
  const s = accessibleStore();
  if (!s) return { kind: "unavailable" };
  const key = sessionStorageKey(userId);
  let raw: string | null;
  try {
    raw = s.getItem(key);
  } catch {
    return { kind: "unavailable" };
  }
  if (raw === null) return { kind: "empty" };
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isValid(parsed)) return { kind: "record", record: parsed };
  } catch {
    try {
      s.removeItem(key);
    } catch {
      return { kind: "unavailable" };
    }
    return { kind: "empty" };
  }
  try {
    s.removeItem(key);
  } catch {
    return { kind: "unavailable" };
  }
  return { kind: "empty" };
}

export function readSessionRecord(userId: string): StoredSession | null {
  const inspected = inspectSessionRecord(userId);
  return inspected.kind === "record" ? inspected.record : null;
}

export function writeSessionRecord(userId: string, rec: StoredSession): boolean {
  if (!isValid(rec)) throw new Error("StoredSession must not carry catalog/media payload");
  const s = accessibleStore();
  if (!s) return false;
  const serialized = JSON.stringify(rec);
  try {
    s.setItem(sessionStorageKey(userId), serialized);
    return s.getItem(sessionStorageKey(userId)) === serialized;
  } catch {
    return false;
  }
}

export function clearSessionRecord(userId: string): void {
  try {
    store()?.removeItem(sessionStorageKey(userId));
  } catch {
    // Best effort for unavailable storage.
  }
}

export function prepareStartingSession(
  inspection: SessionRecordInspection,
  input: { startedAt: string; itemId?: string },
  createKey: () => string = newIdempotencyKey,
): StartSessionPreparation {
  if (inspection.kind === "unavailable") return { kind: "unavailable" };
  if (inspection.kind === "record") {
    return { kind: "existing", record: inspection.record };
  }
  return {
    kind: "starting",
    record: {
      v: 1,
      state: "starting",
      idempotencyKey: createKey(),
      startedAt: input.startedAt,
      itemId: input.itemId,
      deviceClass: "web",
    },
  };
}

export function recoveryRequestFor(stored: StoredSession): SessionRecoveryRequest | null {
  if (stored.state === "starting") {
    return {
      kind: "replay_start",
      idempotencyKey: stored.idempotencyKey,
      deviceClass: stored.deviceClass,
      itemId: stored.itemId,
    };
  }
  if (!stored.sessionId) return null;
  return {
    kind: "verify_session",
    sessionId: stored.sessionId,
    itemId: stored.itemId,
  };
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
