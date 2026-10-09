/**
 * Account suspensions (phase 1E, docs/api/phase-1e.md). A suspended person can sign in, see their history and
 * wallet and create reports, but cannot request rides nor go online. Pure helpers, unit tested.
 */
import { ApiError } from "./api";
import type { AccountSuspendedDetails, Suspension } from "./types";

const toTime = (value: string | null | undefined) => {
  if (!value) return null;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : null;
};

/**
 * The suspension still in force at `now`, or null. The API only sends suspensions in force, but the cached
 * user can outlive `until` (an expired suspension stops applying by itself).
 */
export function activeSuspension(
  suspension: Suspension | null | undefined,
  now: number = Date.now(),
): Suspension | null {
  if (!suspension) return null;
  const until = toTime(suspension.until);
  if (until !== null && until <= now) return null;
  return suspension;
}

/** 403 account_suspended from quote, ride request or going online. */
export const isAccountSuspended = (error: unknown): error is ApiError =>
  error instanceof ApiError && error.code === "account_suspended";

/**
 * A suspension built from a 403 account_suspended, used until GET /users/me confirms it (or when an older
 * profile does not send `suspension`).
 */
export function suspensionFromError(error: unknown): Suspension | null {
  if (!isAccountSuspended(error)) return null;
  const details = (error.details ?? {}) as Partial<AccountSuspendedDetails>;
  return {
    reason: typeof details.reason === "string" ? details.reason : "",
    suspended_at: "",
    until: typeof details.until === "string" ? details.until : null,
    by: null,
  };
}

export type SuspensionEnd =
  | { kind: "indefinite" }
  | { kind: "until"; date: Date; sameDay: boolean };

/** When the suspension ends: indefinite, or a date (`sameDay` when it ends today, to show only the time). */
export function suspensionEnd(
  suspension: Pick<Suspension, "until">,
  now: Date = new Date(),
): SuspensionEnd {
  const until = toTime(suspension.until);
  if (until === null) return { kind: "indefinite" };
  const date = new Date(until);
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  return { kind: "until", date, sameDay };
}

/**
 * Milliseconds until the suspension ends, to refresh the screen right then; null when indefinite, already
 * over or too far away for a timer (more than a day).
 */
export function msUntilLifted(
  suspension: Pick<Suspension, "until"> | null | undefined,
  now: number = Date.now(),
): number | null {
  const until = toTime(suspension?.until);
  if (until === null || until <= now) return null;
  const ms = until - now;
  return ms > 24 * 60 * 60_000 ? null : ms;
}
