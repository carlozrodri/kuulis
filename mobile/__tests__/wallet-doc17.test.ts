import { describe, expect, it } from "@jest/globals";

import { ApiError } from "@/lib/api";
import type { Receipt } from "@/lib/types";
import {
  canDisputeTopUp,
  disputeError,
  isValidTransactionId,
  normalizeTransactionId,
  receiptShareText,
  reducedFrom,
} from "@/lib/wallet";

describe("reducedFrom", () => {
  it("returns the original fee only when Kuulis lowered it", () => {
    expect(reducedFrom({ fee: "3.00", original_fee: "5.00" })).toBe(5);
    expect(reducedFrom({ fee: "0.00", original_fee: "2.50" })).toBe(2.5);
    expect(reducedFrom({ fee: "5.00", original_fee: null })).toBeNull();
    expect(reducedFrom({ fee: "5.00" })).toBeNull();
    expect(reducedFrom({ fee: "5.00", original_fee: "5.00" })).toBeNull();
    expect(reducedFrom(null)).toBeNull();
  });
});

describe("canDisputeTopUp", () => {
  it("allows pending and rejected top-ups without an open claim", () => {
    expect(canDisputeTopUp({ status: "pending", dispute_report_id: null })).toBe(true);
    expect(canDisputeTopUp({ status: "rejected" })).toBe(true);
    expect(canDisputeTopUp({ status: "pending", dispute_report_id: "r1" })).toBe(false);
    expect(canDisputeTopUp({ status: "completed" })).toBe(false);
    expect(canDisputeTopUp({ status: "unmatched" })).toBe(false);
    expect(canDisputeTopUp(null)).toBe(false);
  });
});

describe("transaction id", () => {
  it("drops spaces like the API and needs at least 4 characters", () => {
    expect(normalizeTransactionId(" 2849 3105 ")).toBe("28493105");
    expect(normalizeTransactionId("x".repeat(80))).toHaveLength(64);
    expect(isValidTransactionId("12 3")).toBe(false);
    expect(isValidTransactionId("1234")).toBe(true);
  });
});

describe("disputeError", () => {
  it("maps the claim error codes", () => {
    expect(
      disputeError(new ApiError(409, "top_up_dispute_open", "", { report_id: "r1" })),
    ).toEqual({ kind: "open", reportId: "r1" });
    expect(disputeError(new ApiError(409, "top_up_dispute_open", "", null))).toEqual({
      kind: "open",
      reportId: null,
    });
    expect(disputeError(new ApiError(409, "top_up_dispute_not_allowed", ""))).toEqual({
      kind: "not_allowed",
    });
    expect(disputeError(new ApiError(404, "top_up_not_found", ""))).toEqual({ kind: "not_found" });
    expect(disputeError(new ApiError(400, "attachment_invalid", ""))).toEqual({ kind: "attachment" });
    expect(disputeError(new ApiError(429, "rate_limited", ""))).toEqual({ kind: "other" });
    expect(disputeError(new Error("network"))).toEqual({ kind: "other" });
  });
});

describe("receiptShareText", () => {
  const receipt: Receipt = {
    id: "rc1",
    number: "000123",
    kind: "top_up",
    concept: "Recarga Binance Pay",
    amount: "10",
    balance_after: "12.5",
    reference: "2849310573821",
    issued_at: "2026-10-14T15:00:00Z",
    entry_id: "e1",
    driver: { id: "u1", name: "Luis Gómez", email: "luis@example.com" },
    issuer: "Kuulis",
    fiscal: false,
  };
  const t = (key: string, values?: Record<string, unknown>) =>
    values ? `${key} ${JSON.stringify(values)}` : key;
  const date = () => "14 oct";

  it("lists every field and says it is not fiscal", () => {
    expect(receiptShareText(receipt, t, date).split("\n")).toEqual([
      'wallet.receipt.shareTitle {"issuer":"Kuulis","number":"000123"}',
      "wallet.receipt.nonFiscal",
      "",
      "wallet.receipt.concept: Recarga Binance Pay",
      "wallet.receipt.amount: 10.00 USDT",
      "wallet.receipt.balanceAfter: 12.50 USDT",
      "wallet.receipt.date: 14 oct",
      "wallet.receipt.reference: 2849310573821",
      "wallet.receipt.driver: Luis Gómez",
    ]);
  });

  it("skips the reference when there is none", () => {
    const text = receiptShareText({ ...receipt, reference: null }, t, date);
    expect(text).not.toContain("wallet.receipt.reference");
  });
});
