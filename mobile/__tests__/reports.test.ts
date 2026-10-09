import { describe, expect, it } from "@jest/globals";

import { ApiError } from "@/lib/api";
import {
  DESCRIPTION_MAX,
  descriptionLength,
  descriptionProblem,
  existingReportId,
  GENERAL_REPORT_CATEGORIES,
  isAccountNotification,
  isOpenReport,
  isReportCategory,
  isReportNotification,
  isUrgentCategory,
  REPORT_CATEGORIES,
  reportCategoriesFor,
  reportIdOf,
  reportTimeline,
} from "@/lib/reports";

describe("reportCategoriesFor", () => {
  it("offers every category about a ride", () => {
    expect(reportCategoriesFor(true)).toEqual([...REPORT_CATEGORIES]);
    expect(reportCategoriesFor(true)).toHaveLength(9);
  });

  it("offers only app_issue, lost_item and other without a ride", () => {
    expect(reportCategoriesFor(false).sort()).toEqual(
      ["app_issue", "lost_item", "other"].sort(),
    );
    expect(
      GENERAL_REPORT_CATEGORIES.every((c) => REPORT_CATEGORIES.includes(c)),
    ).toBe(true);
  });

  it("returns a copy the caller can change", () => {
    const list = reportCategoriesFor(false);
    list.pop();
    expect(reportCategoriesFor(false)).toHaveLength(3);
  });
});

describe("categories", () => {
  it("treats only safety and harassment as urgent", () => {
    expect(REPORT_CATEGORIES.filter(isUrgentCategory)).toEqual([
      "safety",
      "harassment",
    ]);
    expect(isUrgentCategory(null)).toBe(false);
  });

  it("recognizes category strings", () => {
    expect(isReportCategory("fare")).toBe(true);
    expect(isReportCategory("nope")).toBe(false);
    expect(isReportCategory(undefined)).toBe(false);
  });
});

describe("description", () => {
  it("counts trimmed characters", () => {
    expect(descriptionLength("  hola  ")).toBe(4);
  });

  it("needs 10 to 2000 characters", () => {
    expect(descriptionProblem("corto")).toBe("too_short");
    expect(descriptionProblem("          123456789 ")).toBe("too_short");
    expect(descriptionProblem("0123456789")).toBeNull();
    expect(descriptionProblem("x".repeat(DESCRIPTION_MAX))).toBeNull();
    expect(descriptionProblem("x".repeat(DESCRIPTION_MAX + 1))).toBe(
      "too_long",
    );
  });
});

describe("reportTimeline", () => {
  const base = {
    created_at: "2026-10-09T12:00:00Z",
    resolved_at: null,
  };

  it("an open report has only the first step done", () => {
    expect(reportTimeline({ ...base, status: "open" })).toEqual([
      { key: "created", state: "done", at: base.created_at },
      { key: "in_review", state: "upcoming", at: null },
      { key: "resolved", state: "upcoming", at: null },
    ]);
  });

  it("marks the review as current while in review", () => {
    const steps = reportTimeline({ ...base, status: "in_review" });
    expect(steps.map((s) => s.state)).toEqual(["done", "current", "upcoming"]);
  });

  it("ends in resolved or dismissed with the closing date", () => {
    const at = "2026-10-10T09:00:00Z";
    const resolved = reportTimeline({
      ...base,
      status: "resolved",
      resolved_at: at,
    });
    expect(resolved[2]).toEqual({ key: "resolved", state: "done", at });
    expect(resolved[1]!.state).toBe("done");
    const dismissed = reportTimeline({
      ...base,
      status: "dismissed",
      resolved_at: at,
    });
    expect(dismissed[2]).toEqual({ key: "dismissed", state: "done", at });
  });

  it("knows which statuses are still open", () => {
    expect(isOpenReport("open")).toBe(true);
    expect(isOpenReport("in_review")).toBe(true);
    expect(isOpenReport("resolved")).toBe(false);
    expect(isOpenReport("dismissed")).toBe(false);
  });
});

describe("existingReportId", () => {
  it("reads details.report_id of a report_already_open", () => {
    const error = new ApiError(409, "report_already_open", "", {
      report_id: "r1",
    });
    expect(existingReportId(error)).toBe("r1");
  });

  it("is null for other errors or missing details", () => {
    expect(
      existingReportId(new ApiError(409, "report_already_open", "")),
    ).toBeNull();
    expect(
      existingReportId(
        new ApiError(409, "too_many_open_reports", "", { report_id: "r1" }),
      ),
    ).toBeNull();
    expect(existingReportId(new Error("x"))).toBeNull();
  });
});

describe("notifications", () => {
  it("recognizes report pushes and their report id", () => {
    const push = { type: "report", event: "resolved", report_id: "r9" };
    expect(isReportNotification(push)).toBe(true);
    expect(reportIdOf(push)).toBe("r9");
  });

  it("recognizes realtime notifications that wrap the payload in data", () => {
    const inbox = {
      id: "n1",
      title: "",
      data: { kind: "report", report_id: "r2" },
    };
    expect(isReportNotification(inbox)).toBe(true);
    expect(reportIdOf(inbox)).toBe("r2");
  });

  it("recognizes account pushes", () => {
    expect(isAccountNotification({ type: "account", event: "suspended" })).toBe(
      true,
    );
    expect(isAccountNotification({ data: { kind: "account" } })).toBe(true);
    expect(isAccountNotification({ type: "wallet" })).toBe(false);
    expect(isReportNotification({ type: "wallet" })).toBe(false);
    expect(isReportNotification(null)).toBe(false);
  });
});
