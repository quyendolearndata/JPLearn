export type CalendarRange = Readonly<{ from: string; to: string }>;

const CALENDAR_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

function calendarParts(value: string): { year: number; month: number; day: number } | null {
  const match = CALENDAR_DATE.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const probe = new Date(Date.UTC(year, month - 1, day, 12));
  if (
    probe.getUTCFullYear() !== year
    || probe.getUTCMonth() !== month - 1
    || probe.getUTCDate() !== day
  ) return null;
  return { year, month, day };
}

function dateFromParts(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function calendarDateInTimeZone(instant: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(instant);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return dateFromParts(Number(value.year), Number(value.month), Number(value.day));
}

export function addCalendarDays(value: string, amount: number): string | null {
  const parts = calendarParts(value);
  if (!parts) return null;
  const date = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + amount, 12));
  return dateFromParts(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
}

export function sevenDayCalendarRange(instant: Date, timeZone: string): CalendarRange {
  const to = calendarDateInTimeZone(instant, timeZone);
  const from = addCalendarDays(to, -6);
  if (!from) throw new Error(`Could not derive a calendar range from ${to}`);
  return { from, to };
}

export function formatCalendarDate(value: string, locale = "vi-VN"): string | null {
  const parts = calendarParts(value);
  if (!parts) return null;
  const date = new Date(Date.UTC(parts.year, parts.month - 1, parts.day, 12));
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatTimestampInTimeZone(
  value: string,
  timeZone: string,
  locale = "vi-VN",
): string | null {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(date);
}
