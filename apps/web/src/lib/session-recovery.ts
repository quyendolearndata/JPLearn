export interface LearningSessionResponse {
  id: string;
  device_class: "web" | "phone" | "ipad";
  started_at: string;
  ended_at?: string | null;
  duration_seconds?: number | null;
}

export type ReplayFailureDisposition = "auth" | "terminal" | "unverified";
export type SessionOperation = "recovery" | "start" | "end";

export interface SessionOperationTicket {
  id: number;
  operation: SessionOperation;
}

export interface SessionOperationGuard {
  begin(operation: SessionOperation): SessionOperationTicket | null;
  isCurrent(ticket: SessionOperationTicket): boolean;
  finish(ticket: SessionOperationTicket): boolean;
  cancel(): void;
}

export type SessionStatusClassification =
  | { kind: "invalid" }
  | { kind: "active"; session: LearningSessionResponse }
  | { kind: "ended"; session: LearningSessionResponse };

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/i;

function isDateTime(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = DATE_TIME_PATTERN.exec(value);
  if (!match) return false;
  const [, yearText, monthText, dayText, hourText, minuteText, secondText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  if (year === 0 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) {
    return false;
  }
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return day >= 1 && day <= daysInMonth && Number.isFinite(Date.parse(value));
}

export function isLearningSessionResponse(
  value: unknown,
  expectedId?: string,
): value is LearningSessionResponse {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const session = value as Record<string, unknown>;
  if (typeof session.id !== "string" || !UUID_PATTERN.test(session.id)) return false;
  if (expectedId && session.id !== expectedId) return false;
  if (!["web", "phone", "ipad"].includes(session.device_class as string)) return false;
  if (!isDateTime(session.started_at)) return false;
  if (session.ended_at !== undefined && session.ended_at !== null && !isDateTime(session.ended_at)) {
    return false;
  }
  if (
    session.duration_seconds !== undefined
    && session.duration_seconds !== null
    && !Number.isInteger(session.duration_seconds)
  ) {
    return false;
  }
  return true;
}

export function classifySessionStatusResponse(
  value: unknown,
  expectedId: string,
): SessionStatusClassification {
  if (!isLearningSessionResponse(value, expectedId)) return { kind: "invalid" };
  return value.ended_at
    ? { kind: "ended", session: value }
    : { kind: "active", session: value };
}

export function createSessionOperationGuard(): SessionOperationGuard {
  let sequence = 0;
  let current: SessionOperationTicket | null = null;
  const isCurrent = (ticket: SessionOperationTicket) =>
    current?.id === ticket.id && current.operation === ticket.operation;
  return {
    begin(operation) {
      if (current) return null;
      current = { id: ++sequence, operation };
      return current;
    },
    isCurrent,
    finish(ticket) {
      if (!isCurrent(ticket)) return false;
      current = null;
      return true;
    },
    cancel() {
      current = null;
    },
  };
}

export function isSessionOperationCurrent(
  guard: SessionOperationGuard,
  ticket: SessionOperationTicket,
  requestUserId: string,
  currentUserId: string | null,
): boolean {
  return guard.isCurrent(ticket) && requestUserId === currentUserId;
}

export function classifyReplayFailure(status: number): ReplayFailureDisposition {
  if (status === 401) return "auth";
  if (status === 409) return "terminal";
  return "unverified";
}
