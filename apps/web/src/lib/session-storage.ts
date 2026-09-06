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

const PREFIX = "jplearn.session:";
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

export function readSessionRecord(userId: string): StoredSession | null {
  const s = store();
  if (!s) return null;
  const key = sessionStorageKey(userId);
  const raw = s.getItem(key);
  if (raw === null) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isValid(parsed)) return parsed;
  } catch {
    /* fallthrough */
  }
  s.removeItem(key);
  return null;
}

export function writeSessionRecord(userId: string, rec: StoredSession): void {
  if (!isValid(rec)) throw new Error("StoredSession must not carry catalog/media payload");
  store()?.setItem(sessionStorageKey(userId), JSON.stringify(rec));
}

export function clearSessionRecord(userId: string): void {
  store()?.removeItem(sessionStorageKey(userId));
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
