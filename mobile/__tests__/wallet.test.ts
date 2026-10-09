import { describe, expect, it } from "@jest/globals";

import {
  isSubscriptionNotification,
  isWalletNotification,
} from "@/hooks/useWallet";
import type { Charge, FeeTier, SubscriptionSummary } from "@/lib/types";
import {
  chargeDate,
  feeFor,
  feeTierFor,
  formatTierBound,
  isValidBinancePayId,
  maxTransfer,
  monthDate,
  nextDueAt,
  normalizeBinancePayId,
  normalizeOrderReference,
  parseAmountInput,
  parseMonth,
  parseRecipientQuery,
  pendingTotal,
  sanitizeAmountInput,
  shortfall,
  subscriptionState,
  tierBounds,
  topUpAmountError,
  transferAmountError,
} from "@/lib/wallet";

/** The initial schedule from docs/product/business-model.md. */
const TIERS: FeeTier[] = [
  { above: "0.00", fee: "0.00" },
  { above: "100.00", fee: "5.00" },
  { above: "200.00", fee: "10.00" },
  { above: "300.00", fee: "15.00" },
  { above: "400.00", fee: "20.00" },
  { above: "500.00", fee: "25.00" },
  { above: "600.00", fee: "30.00" },
];

const charge = (overrides: Partial<Charge> = {}): Charge => ({
  id: "c1",
  month: "2026-10",
  earnings: "142.50",
  fee: "5.00",
  status: "pending",
  free_period: false,
  due_at: "2026-11-08T04:00:00Z",
  paid_at: null,
  waived_reason: null,
  ...overrides,
});

const summary = (
  overrides: Partial<SubscriptionSummary> = {},
): SubscriptionSummary => ({
  month: "2026-10",
  earnings: "142.50",
  estimated_fee: "5.00",
  free_until: "2026-07-14T04:00:00Z",
  in_free_period: false,
  tiers: TIERS,
  next_charge_at: "2026-11-01T04:00:00Z",
  pending: [],
  overdue: false,
  blocked: false,
  ...overrides,
});

describe("fee tiers", () => {
  it("picks the tier with the highest `above` the earnings exceed", () => {
    expect(feeTierFor(TIERS, "142.50")).toEqual({ from: 100, to: 200, fee: 5 });
    expect(feeTierFor(TIERS, "50")).toEqual({ from: 0, to: 100, fee: 0 });
    expect(feeTierFor(TIERS, "650.10")).toEqual({
      from: 600,
      to: null,
      fee: 30,
    });
  });

  it("uses strict 'above' at the bounds", () => {
    expect(feeFor(TIERS, "100.00")).toBe(0);
    expect(feeFor(TIERS, "100.01")).toBe(5);
    expect(feeFor(TIERS, "200.00")).toBe(5);
    expect(feeFor(TIERS, "600.00")).toBe(25);
    expect(feeFor(TIERS, "600.01")).toBe(30);
  });

  it("charges nothing without earnings or schedule", () => {
    expect(feeTierFor(TIERS, "0")).toBeNull();
    expect(feeTierFor(TIERS, null)).toBeNull();
    expect(feeTierFor([], "150")).toBeNull();
    expect(feeFor(undefined, "150")).toBe(0);
  });

  it("sorts unsorted schedules and skips malformed rows", () => {
    const shuffled = [TIERS[2], TIERS[0], { above: "x", fee: "1" }, TIERS[1]];
    expect(feeTierFor(shuffled, "150")).toEqual({ from: 100, to: 200, fee: 5 });
    expect(feeTierFor(shuffled, "250")).toEqual({
      from: 200,
      to: null,
      fee: 10,
    });
  });

  it("formats tier bounds for sentences", () => {
    expect(formatTierBound(100)).toBe("$100");
    expect(formatTierBound(99.5)).toBe("$99.50");
    expect(tierBounds({ from: 100, to: 200, fee: 5 })).toEqual({
      from: "$100",
      to: "$200",
    });
    expect(tierBounds({ from: 600, to: null, fee: 30 })).toEqual({
      from: "$600",
      to: null,
    });
  });
});

describe("what is owed", () => {
  it("adds up only pending charges", () => {
    expect(
      pendingTotal([
        charge(),
        charge({ id: "c2", fee: "10.00" }),
        charge({ id: "c3", status: "paid" }),
      ]),
    ).toBe(15);
    expect(pendingTotal([])).toBe(0);
    expect(pendingTotal(undefined)).toBe(0);
  });

  it("computes the shortfall in cents", () => {
    expect(shortfall("2.50", "5.00")).toBe(2.5);
    expect(shortfall("0.10", 0.3)).toBe(0.2);
    expect(shortfall("5.00", "5.00")).toBe(0);
    expect(shortfall("8", "5")).toBe(0);
    expect(shortfall(undefined, "5")).toBe(5);
    expect(shortfall("-1", "5")).toBe(5);
  });

  it("finds the earliest due date of pending charges", () => {
    expect(
      nextDueAt([
        charge({ due_at: "2026-12-08T04:00:00Z" }),
        charge({ due_at: "2026-11-08T04:00:00Z" }),
        charge({ due_at: "2026-10-08T04:00:00Z", status: "paid" }),
        charge({ due_at: null }),
      ]),
    ).toBe("2026-11-08T04:00:00Z");
    expect(nextDueAt([])).toBeNull();
  });
});

describe("subscriptionState", () => {
  it("prioritizes blocked, then pending", () => {
    expect(subscriptionState(summary({ blocked: true }))).toBe("blocked");
    expect(subscriptionState(summary({ overdue: true }))).toBe("blocked");
    expect(
      subscriptionState(summary({ pending: [charge()], in_free_period: true })),
    ).toBe("pending");
  });

  it("knows the free period and drivers without trips", () => {
    expect(subscriptionState(summary({ in_free_period: true }))).toBe("free");
    expect(
      subscriptionState(
        summary({ free_until: null, earnings: "0.00", estimated_fee: "0.00" }),
      ),
    ).toBe("not_started");
    expect(subscriptionState(summary())).toBe("active");
    expect(subscriptionState(undefined)).toBeNull();
  });
});

describe("months", () => {
  it("parses API months", () => {
    expect(parseMonth("2026-10")).toEqual({ year: 2026, month: 10 });
    expect(parseMonth("2026-13")).toBeNull();
    expect(parseMonth("oct")).toBeNull();
    expect(parseMonth(null)).toBeNull();
  });

  it("builds local dates for formatting", () => {
    const october = monthDate("2026-10");
    expect(october?.getFullYear()).toBe(2026);
    expect(october?.getMonth()).toBe(9);
    const charged = chargeDate("2026-10");
    expect([
      charged?.getFullYear(),
      charged?.getMonth(),
      charged?.getDate(),
    ]).toEqual([2026, 10, 1]);
    const december = chargeDate("2026-12");
    expect([december?.getFullYear(), december?.getMonth()]).toEqual([2027, 0]);
  });
});

describe("amount inputs", () => {
  it("sanitizes what the driver types", () => {
    expect(sanitizeAmountInput("5,5")).toBe("5.5");
    expect(sanitizeAmountInput("5,509")).toBe("5.50");
    expect(sanitizeAmountInput("$12")).toBe("12");
    expect(sanitizeAmountInput("1.2.3")).toBe("1.23");
    expect(sanitizeAmountInput(".5")).toBe("0.5");
    expect(sanitizeAmountInput("007")).toBe("7");
    expect(sanitizeAmountInput("abc")).toBe("");
  });

  it("parses amounts with at most two decimals", () => {
    expect(parseAmountInput("5")).toBe(5);
    expect(parseAmountInput("5,50")).toBe(5.5);
    expect(parseAmountInput(" 3.25 ")).toBe(3.25);
    expect(parseAmountInput("3.255")).toBeNull();
    expect(parseAmountInput("0")).toBeNull();
    expect(parseAmountInput("")).toBeNull();
    expect(parseAmountInput("-2")).toBeNull();
  });

  it("checks the top-up minimum", () => {
    expect(topUpAmountError("5", "5.00")).toBeNull();
    expect(topUpAmountError("4.99", "5.00")).toBe("below_minimum");
    expect(topUpAmountError("x", "5.00")).toBe("invalid");
  });
});

describe("transfers", () => {
  it("validates against the balance and the monthly allowance", () => {
    const limits = { balance: "10.00", available: "4.00" };
    expect(transferAmountError("3", limits)).toBeNull();
    expect(transferAmountError("4.00", limits)).toBeNull();
    expect(transferAmountError("4.01", limits)).toBe("transfer_limit_exceeded");
    expect(transferAmountError("12", limits)).toBe("insufficient_balance");
    expect(transferAmountError("0", limits)).toBe("invalid");
    expect(transferAmountError("0.3", { balance: "0.30" })).toBeNull();
  });

  it("knows the most that can be sent", () => {
    expect(maxTransfer({ balance: "10.00", available: "4.00" })).toBe(4);
    expect(maxTransfer({ balance: "2.50", available: "47.00" })).toBe(2.5);
    expect(maxTransfer({ balance: "2.50" })).toBe(2.5);
    expect(maxTransfer({ balance: "2.50", available: "-1" })).toBe(0);
  });
});

describe("parseRecipientQuery", () => {
  it("normalizes emails", () => {
    expect(parseRecipientQuery("  Luis@Correo.com ")).toEqual({
      type: "email",
      value: "luis@correo.com",
    });
    expect(parseRecipientQuery("luis@")).toBeNull();
  });

  it("normalizes Venezuelan mobiles to E.164", () => {
    expect(parseRecipientQuery("0412 123 4567")).toEqual({
      type: "phone",
      value: "+584121234567",
    });
    expect(parseRecipientQuery("+58 414-765.43.21")).toEqual({
      type: "phone",
      value: "+584147654321",
    });
    expect(parseRecipientQuery("4241234567")).toEqual({
      type: "phone",
      value: "+584241234567",
    });
  });

  it("rejects anything else", () => {
    expect(parseRecipientQuery("")).toBeNull();
    expect(parseRecipientQuery("luis")).toBeNull();
    expect(parseRecipientQuery("0212 123 4567")).toBeNull();
  });
});

describe("Binance inputs", () => {
  it("accepts 6–20 digits", () => {
    expect(normalizeBinancePayId(" 123 456-789 ")).toBe("123456789");
    expect(isValidBinancePayId("123456789")).toBe(true);
    expect(isValidBinancePayId("12345")).toBe(false);
    expect(isValidBinancePayId("1".repeat(21))).toBe(false);
    expect(isValidBinancePayId("12345a")).toBe(false);
  });

  it("cleans order references", () => {
    expect(normalizeOrderReference(" 2849-3105 7382 ")).toBe("284931057382");
  });
});

describe("push payloads", () => {
  it("recognizes wallet and subscription pushes", () => {
    expect(isWalletNotification({ type: "wallet" })).toBe(true);
    expect(isWalletNotification({ type: "wallet_top_up" })).toBe(true);
    expect(isWalletNotification({ data: { type: "subscription" } })).toBe(true);
    expect(isWalletNotification({ kind: "promo_credit" })).toBe(true);
    expect(isWalletNotification({ type: "ride.updated" })).toBe(false);
    expect(isSubscriptionNotification({ type: "subscription" })).toBe(true);
    expect(isSubscriptionNotification({ type: "subscription_blocked" })).toBe(
      true,
    );
    expect(isSubscriptionNotification({ type: "wallet" })).toBe(false);
    expect(isSubscriptionNotification(null)).toBe(false);
  });
});
