/**
 * Pure logic for reports (phase 1E, docs/api/phase-1e.md): which categories apply, description limits, the
 * status timeline and the notification payloads. No React and no network, so it can be unit tested. The API
 * validates everything again.
 */
import { ApiError } from "./api";
import type {
  Report,
  ReportAlreadyOpenDetails,
  ReportCategory,
  ReportStatus,
} from "./types";

/** Every category, in the order the picker shows them (urgent ones first). */
export const REPORT_CATEGORIES: readonly ReportCategory[] = [
  "safety",
  "harassment",
  "driving",
  "fare",
  "vehicle_mismatch",
  "no_show",
  "lost_item",
  "app_issue",
  "other",
];

/** Categories allowed without a ride (anything else answers 422). */
export const GENERAL_REPORT_CATEGORIES: readonly ReportCategory[] = [
  "app_issue",
  "lost_item",
  "other",
];

/** Categories the picker offers: all of them about a ride, only the general ones otherwise. */
export function reportCategoriesFor(hasRide: boolean): ReportCategory[] {
  return hasRide ? [...REPORT_CATEGORIES] : [...GENERAL_REPORT_CATEGORIES];
}

/** Safety and harassment are urgent for the team, and the app points to 911. */
export const isUrgentCategory = (category: ReportCategory | null | undefined) =>
  category === "safety" || category === "harassment";

export function isReportCategory(value: unknown): value is ReportCategory {
  return (
    typeof value === "string" &&
    (REPORT_CATEGORIES as readonly string[]).includes(value)
  );
}

// ── Description ──

export const DESCRIPTION_MIN = 10;
export const DESCRIPTION_MAX = 2000;

/** Characters the API will count: surrounding spaces do not count. */
export const descriptionLength = (text: string) => text.trim().length;

export type DescriptionProblem = "too_short" | "too_long" | null;

export function descriptionProblem(text: string): DescriptionProblem {
  const length = descriptionLength(text);
  if (length < DESCRIPTION_MIN) return "too_short";
  if (length > DESCRIPTION_MAX) return "too_long";
  return null;
}

// ── Status ──

export const OPEN_STATUSES: readonly ReportStatus[] = ["open", "in_review"];

/** Still being handled (counts towards the limit of 5 open reports). */
export const isOpenReport = (status: ReportStatus | null | undefined) =>
  !!status && OPEN_STATUSES.includes(status);

export type TimelineStepKey =
  | "created"
  | "in_review"
  | "resolved"
  | "dismissed";
export type TimelineStepState = "done" | "current" | "upcoming";

export interface TimelineStep {
  key: TimelineStepKey;
  state: TimelineStepState;
  /** When it happened, when the API says so. */
  at: string | null;
}

/**
 * Created → in review → resolved | dismissed. The last step reads "Resuelto" until the report is closed;
 * a report closed straight from `open` still shows "En revisión" as done (the team did review it).
 */
export function reportTimeline(
  report: Pick<Report, "status" | "created_at" | "resolved_at">,
): TimelineStep[] {
  const { status } = report;
  const closed = status === "resolved" || status === "dismissed";
  return [
    { key: "created", state: "done", at: report.created_at },
    {
      key: "in_review",
      state: closed ? "done" : status === "in_review" ? "current" : "upcoming",
      at: null,
    },
    {
      key: status === "dismissed" ? "dismissed" : "resolved",
      state: closed ? "done" : "upcoming",
      at: closed ? report.resolved_at : null,
    },
  ];
}

// ── Errors ──

/** The open report a 409 report_already_open points to, if any. */
export function existingReportId(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.code !== "report_already_open")
    return null;
  const details = error.details as Partial<ReportAlreadyOpenDetails> | null;
  return typeof details?.report_id === "string" && details.report_id
    ? details.report_id
    : null;
}

// ── Notifications ──

type NotificationPayload = {
  type?: unknown;
  kind?: unknown;
  report_id?: unknown;
  data?: { type?: unknown; kind?: unknown; report_id?: unknown } | null;
} | null;

const tagOf = (payload: unknown) => {
  const record = payload as NotificationPayload;
  const value =
    record?.kind ?? record?.type ?? record?.data?.kind ?? record?.data?.type;
  return typeof value === "string" ? value : null;
};

/**
 * Report pushes (resolved or dismissed) carry {kind | type: "report", report_id}. Realtime notifications wrap
 * that in `data`, so both shapes count.
 */
export function isReportNotification(payload: unknown): boolean {
  const tag = tagOf(payload);
  return (tag !== null && tag.startsWith("report")) || !!reportIdOf(payload);
}

/** The report a notification is about. */
export function reportIdOf(payload: unknown): string | null {
  const record = payload as NotificationPayload;
  const value = record?.report_id ?? record?.data?.report_id;
  return typeof value === "string" && value ? value : null;
}

/** Account pushes (suspended, suspension lifted) carry {kind | type: "account"}. */
export function isAccountNotification(payload: unknown): boolean {
  const tag = tagOf(payload);
  return tag !== null && tag.startsWith("account");
}
