import { describe, expect, it } from "@jest/globals";

import { ApiError } from "@/lib/api";
import {
  activeSuspension,
  isAccountSuspended,
  msUntilLifted,
  suspensionEnd,
  suspensionFromError,
} from "@/lib/suspension";
import type { Suspension } from "@/lib/types";

const NOW = new Date(2026, 9, 9, 10, 0).getTime();
const suspension = (until: string | null): Suspension => ({
  reason: "Reportes de manejo imprudente",
  suspended_at: "2026-10-08T12:00:00Z",
  until,
  by: null,
});

describe("activeSuspension", () => {
  it("keeps indefinite and future suspensions", () => {
    expect(activeSuspension(suspension(null), NOW)).not.toBeNull();
    const future = new Date(NOW + 60_000).toISOString();
    expect(activeSuspension(suspension(future), NOW)?.until).toBe(future);
  });

  it("drops expired suspensions and missing ones", () => {
    expect(
      activeSuspension(suspension(new Date(NOW - 1).toISOString()), NOW),
    ).toBeNull();
    expect(activeSuspension(null, NOW)).toBeNull();
    expect(activeSuspension(undefined, NOW)).toBeNull();
  });
});

describe("account_suspended errors", () => {
  it("builds a suspension from the error details", () => {
    const error = new ApiError(403, "account_suspended", "", {
      until: "2026-10-12T15:00:00Z",
      reason: "Acoso",
    });
    expect(isAccountSuspended(error)).toBe(true);
    expect(suspensionFromError(error)).toEqual({
      reason: "Acoso",
      suspended_at: "",
      until: "2026-10-12T15:00:00Z",
      by: null,
    });
  });

  it("treats missing details as an indefinite suspension", () => {
    const error = new ApiError(403, "account_suspended", "");
    expect(suspensionFromError(error)?.until).toBeNull();
  });

  it("ignores other errors", () => {
    expect(
      isAccountSuspended(new ApiError(403, "subscription_overdue", "")),
    ).toBe(false);
    expect(suspensionFromError(new Error("x"))).toBeNull();
    expect(suspensionFromError(null)).toBeNull();
  });
});

describe("suspensionEnd", () => {
  const now = new Date(NOW);

  it("is indefinite without until", () => {
    expect(suspensionEnd({ until: null }, now)).toEqual({ kind: "indefinite" });
  });

  it("flags a suspension that ends today", () => {
    const later = new Date(2026, 9, 9, 18, 30);
    expect(suspensionEnd({ until: later.toISOString() }, now)).toEqual({
      kind: "until",
      date: later,
      sameDay: true,
    });
  });

  it("gives the date of a later day", () => {
    const end = suspensionEnd(
      { until: new Date(2026, 9, 12, 9, 0).toISOString() },
      now,
    );
    expect(end.kind === "until" && end.sameDay).toBe(false);
  });
});

describe("msUntilLifted", () => {
  it("schedules a refresh for suspensions ending within a day", () => {
    expect(
      msUntilLifted({ until: new Date(NOW + 5_000).toISOString() }, NOW),
    ).toBe(5_000);
  });

  it("does not schedule indefinite, past or far away ends", () => {
    expect(msUntilLifted({ until: null }, NOW)).toBeNull();
    expect(
      msUntilLifted({ until: new Date(NOW - 5_000).toISOString() }, NOW),
    ).toBeNull();
    expect(
      msUntilLifted(
        { until: new Date(NOW + 2 * 86_400_000).toISOString() },
        NOW,
      ),
    ).toBeNull();
    expect(msUntilLifted(null, NOW)).toBeNull();
  });
});
